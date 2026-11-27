"""11-27 mixed text+image PDF read boundary (synthetic 가상인 PDFs, fake OCR words).

PdfText reads only the first page's text layer. Before this fix a 주민등록초본 whose page 1 is a text layer
(with a labeled 발급일) reached PASS without the image pages, hidden text layers or same-page table images ever
being read, and a text 초본 missing page 2 or 3 passed too. Every case here was a wrong PASS/FAIL on main
e7336d3/bb5e807 with real PP-OCRv5 ONNX (verification-mixedpdf-20261127). Real-ONNX evidence lives there;
these tests pin the reader decisions with fake OCR words.
"""
import dataclasses
import io
from datetime import date

import pymupdf
import pytest
from PIL import Image

from demo.backend.ocr import localocr, read_document
from demo.backend.rules.doc_types import DocType
from demo.backend.rules.identity import Identity
from demo.backend.rules.programs import DOUBLE_SAVINGS, JOB_PACKAGE, PROGRAMS
from demo.backend.rules.required_docs import ApplicantDocInput, WorkCategory, build_checklist, find_slot
from demo.backend.upload_assessment import assess_upload
from engine_v2.pipeline import ocr as v2ocr
from engine_v2.tests import p2_resident_samples as sample
from engine_v2.tests import test_resident_abstract as T

RECT = pymupdf.Rect(0, 0, 595, 842)
LABEL = "발급일자 : 2026년 03월 03일"  # PdfText reads only labeled issue dates: the label makes PASS reachable


def _pages(drop_page=None):
    pages = sample.resident()
    pages[0][1].words.append(T.wd(7.0, 76.0, LABEL, 1.0, 40))
    return [page for index, page in enumerate(pages) if index != drop_page]


def _png():
    buffer = io.BytesIO()
    Image.new("RGB", (1240, 1754), "white").save(buffer, "PNG")  # A4 150dpi: above the resolution floor
    return buffer.getvalue()


def _text(page, words, size, render_mode=0, below=None):
    width, height = size
    for word in words:
        x0, y0, x1, y1 = word.bbox_px
        if below is not None and y0 < below * height:
            continue
        page.insert_text((x0 / width * 595, y1 / height * 842 - 1), word.text, fontname="korea",
                         fontsize=max(5.0, (y1 - y0) / height * 842 * .8), render_mode=render_mode)


def _pdf(path, kinds, pages):
    """kinds per page: text | image | hidden (image + invisible text) | table_image (text head + image body)."""
    with pymupdf.open() as document:
        for kind, (page_image, result) in zip(kinds, pages):
            page = document.new_page(width=595, height=842)
            if kind == "text":
                _text(page, result.words, page_image.pixel_size)
            elif kind == "image":
                page.insert_image(RECT, stream=_png())
            elif kind == "hidden":
                page.insert_image(RECT, stream=_png())
                _text(page, result.words, page_image.pixel_size, render_mode=3)
            elif kind == "table_image":
                head = [w for w in result.words if w.bbox_px[1] < .2 * page_image.pixel_size[1] or w.text == LABEL]
                _text(page, head, page_image.pixel_size)
                page.insert_image(pymupdf.Rect(0, .2 * 842, 595, .86 * 842), stream=_png())
        document.save(path)
    return path


@pytest.fixture
def ocr_words(monkeypatch):
    """Fake own OCR: the n-th recognized image returns the n-th sample page, scaled to the image size."""
    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    calls = []

    def use(pages):
        queue = list(pages)

        def recognize(png, size):
            calls.append(size)
            page, result = queue.pop(0)
            sx, sy = size[0] / page.pixel_size[0], size[1] / page.pixel_size[1]
            return [dataclasses.replace(w, bbox_px=(w.bbox_px[0] * sx, w.bbox_px[1] * sy,
                                                    w.bbox_px[2] * sx, w.bbox_px[3] * sy)) for w in result.words]
        monkeypatch.setitem(v2ocr.ENGINES, "own", recognize)
        return calls
    return use


def _verdict(path, program):
    checklist = build_checklist(PROGRAMS[program], ApplicantDocInput(work_category=WorkCategory.EMPLOYEE))
    slot = find_slot(checklist, "resident_abstract")
    ocr = read_document(str(path), DocType.RESIDENT_ABSTRACT)
    _, check = assess_upload(path, slot, identity=Identity(sample.NAME, date.fromisoformat(sample.BIRTH)),
                             checklist=checklist, reader=lambda _p, _e: ocr)
    return ocr, check


PROGRAM_CODES = [DOUBLE_SAVINGS, JOB_PACKAGE]


@pytest.mark.parametrize("program", PROGRAM_CODES)
@pytest.mark.parametrize("kinds", [
    ("text", "image", "image"),               # scanned pages 2-3 behind a text page 1
    ("text", "image", "text"),                # one scanned page in the middle
    ("hidden", "hidden", "hidden"),           # scanner OCR layer (render mode 3) over page images
    ("table_image", "table_image", "table_image"),  # history table drawn as a picture on text pages
])
def test_raster_content_abstract_is_read_as_a_scan_and_guarded(tmp_path, ocr_words, kinds, program):
    calls = ocr_words(_pages())
    path = _pdf(tmp_path / "FAKE-mixed.pdf", kinds, _pages())
    ocr, check = _verdict(path, program)
    assert len(calls) == 3                     # every page is rendered and recognized, not only page 1's text
    assert ocr.tier == "localocr" and ocr.engine == "own"
    assert ocr.fallback_reason == "RENDER_RETRY:TEXT_RASTER_CONTENT"
    assert "SCAN_UNVERIFIED" in ocr.fields["주소이력불확실사유"]
    assert ocr.fields["전입일"] == "불확실"
    assert check.status == "NEEDS_REVIEW"     # complete content: never PASS (guard), never a wrong FAIL
    assert "ADDRESS_HISTORY_INCOMPLETE" in [f.code for f in check.findings]


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_unreadable_raster_content_never_falls_back_to_the_first_page_text(tmp_path, monkeypatch, program):
    monkeypatch.setenv("ENGINE_V2_OCR", "own")

    def broken(png, size):
        raise RuntimeError("model crashed")
    monkeypatch.setitem(v2ocr.ENGINES, "own", broken)
    path = _pdf(tmp_path / "FAKE-mixed.pdf", ("text", "image", "image"), _pages())
    ocr, check = _verdict(path, program)
    assert ocr.tier == "localocr" and ocr.fallback_reason.startswith("RENDER_RETRY_FAILED:TEXT_RASTER_CONTENT")
    assert ocr.detected_doc_type == DocType.RESIDENT_ABSTRACT and ocr.confidence == 0
    assert check.status == "NEEDS_REVIEW"


@pytest.mark.parametrize("program", PROGRAM_CODES)
@pytest.mark.parametrize("drop_page", [1, 2])
def test_text_abstract_with_a_missing_page_is_not_passed(tmp_path, ocr_words, drop_page, program):
    calls = ocr_words([])
    path = _pdf(tmp_path / "FAKE-text.pdf", ("text", "text"), _pages(drop_page))
    ocr, check = _verdict(path, program)
    assert calls == [] and ocr.tier == "pdftext" and ocr.engine == "pdftext"
    assert check.status == "FAIL" and [f.code for f in check.findings] == ["PAGES_INCOMPLETE"]


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_complete_text_abstract_still_passes_without_ocr(tmp_path, ocr_words, program):
    calls = ocr_words([])
    path = _pdf(tmp_path / "FAKE-text.pdf", ("text", "text", "text"), _pages())
    ocr, check = _verdict(path, program)
    assert calls == [] and ocr.tier == "pdftext" and ocr.engine == "pdftext"
    assert ocr.fields["발급일"] == "2026-03-03" and ocr.fields["초본신청인성명"] == sample.NAME
    assert check.status == "PASS", check.findings


def test_raster_content_pages_signal_has_no_area_threshold(tmp_path):
    pages = _pages()
    _pdf(tmp_path / "text.pdf", ("text",), pages)
    assert localocr.raster_content_pages(tmp_path / "text.pdf") == []
    with pymupdf.open(tmp_path / "text.pdf") as document:
        document[0].insert_image(pymupdf.Rect(500, 20, 530, 50), stream=_png())  # 0.2% of the page
        document.new_page(width=595, height=842)                               # blank page
        document.save(tmp_path / "small.pdf")
    assert localocr.raster_content_pages(tmp_path / "small.pdf") == [0, 1]
    _pdf(tmp_path / "hidden.pdf", ("hidden",), pages)
    assert localocr.raster_content_pages(tmp_path / "hidden.pdf") == [0]
    assert localocr.page_has_hidden_text(tmp_path / "hidden.pdf")
    assert not localocr.page_has_hidden_text(tmp_path / "small.pdf")


def test_hidden_text_scan_is_recovered_when_the_picture_is_smaller_than_the_page(tmp_path, ocr_words):
    """The 90% cover-image gate alone skipped this retry (11-27 regression): invisible text is the signal."""
    ocr_words(_pages())
    with pymupdf.open() as document:
        for _ in range(3):
            page = document.new_page(width=595, height=842)
            page.insert_image(pymupdf.Rect(70, 100, 525, 744), stream=_png())  # 60% of the page
            for line, text in enumerate(("스캔 문서 자동 인식 결과 일부", "판독 품질 낮음 다시 확인 필요",
                                         "가상 기관 문서 처리 시스템 출력본", "합성 시험용 숨은 글자층 이 줄에는 서식 단서가 없습니다")):
                page.insert_text((60, 100 + 20 * line), text, fontname="korea", fontsize=9, render_mode=3)
        document.save(tmp_path / "FAKE-hidden.pdf")
    assert not localocr.page_has_cover_image(tmp_path / "FAKE-hidden.pdf")
    ocr = read_document(str(tmp_path / "FAKE-hidden.pdf"), None)
    assert ocr.detected_doc_type == DocType.RESIDENT_ABSTRACT
    assert ocr.fallback_reason == "RENDER_RETRY:TEXT_RECLASS_NONE"
    assert "SCAN_UNVERIFIED" in ocr.fields["주소이력불확실사유"]


def test_guard_follows_the_final_type_when_the_extractor_title_check_misses():
    """Body classification says 초본 while the extractor's header title check did not: the guard still applies."""
    from engine_v2.extractors import resident_abstract
    from engine_v2.schemas.models import DocType as V2Type
    pages = sample.resident()
    ex = dataclasses.replace(resident_abstract.extract(pages), detected_type=V2Type.UNKNOWN, type_confidence=.4)
    unguarded = localocr._from_resident(ex, pages, resident_abstract, V2Type)
    assert "주소이력불확실사유" not in unguarded.fields             # the pre-11-27 behaviour this fixes
    guarded = localocr._from_resident(ex, pages, resident_abstract, V2Type, DocType.RESIDENT_ABSTRACT)
    assert "SCAN_UNVERIFIED" in guarded.fields["주소이력불확실사유"]
    assert guarded.fields["전입일"] == "불확실" and guarded.fields["현주소시도"] == "불확실"


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_text_abstract_without_any_page_marker_keeps_the_tier2_result(tmp_path, ocr_words, program):
    """No marker read at all (the extractor reports [None]): no completeness evidence either way, Tier2 as before."""
    from demo.backend.tests.test_resident_slot_type_gate import TEXT_ABSTRACT, text_pdf
    calls = ocr_words([])
    ocr, check = _verdict(text_pdf(tmp_path / "FAKE-text-nomarker.pdf", TEXT_ABSTRACT), program)
    assert calls == [] and ocr.tier == "pdftext" and "쪽표기자료" not in ocr.fields
    assert check.status == "PASS", check.findings
