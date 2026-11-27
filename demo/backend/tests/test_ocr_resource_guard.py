"""11-27 OCR CPU/memory guard (synthetic 가상인 PDFs, fake OCR words; model-free).

Before this change (main 08bc4f4 / ec00da1, real PP-OCRv5 ONNX, verification-resguard-20261127):
  - a rendered re-read made every page's Pixmap/PNG before reading the first one (20 pages: +425 MB),
  - nothing bounded the pages or pixels a document could make the server decode (a 20 KB PDF holding a
    144 MP 1-bit image, a large-format page, hundreds of scanned pages),
  - the upload handler read the whole upload into memory.
The guard must never turn into a partial read: a document over a limit is not read at all and goes to the
officer (NEEDS_REVIEW) - never PASS, never a FAIL from unread content, never the first-page-text tier.
"""
import asyncio
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
from engine_v2.pipeline import limits, preprocess as v2preprocess
from engine_v2.pipeline import ocr as v2ocr
from engine_v2.tests import p2_resident_samples as sample
from engine_v2.tests import test_resident_abstract as T

RECT = pymupdf.Rect(0, 0, 595, 842)
LABEL = "발급일자 : 2026년 03월 03일"  # PdfText reads only labeled issue dates: the label makes PASS reachable
PROGRAM_CODES = [DOUBLE_SAVINGS, JOB_PACKAGE]


def _pages():
    pages = sample.resident()
    pages[0][1].words.append(T.wd(7.0, 76.0, LABEL, 1.0, 40))
    return pages


def _png(size=(1240, 1754), mode="RGB"):
    buffer = io.BytesIO()
    Image.new(mode, size, "white" if mode == "RGB" else 255).save(buffer, "PNG")
    return buffer.getvalue()


def _text(page, words, size):
    width, height = size
    for word in words:
        x0, y0, x1, y1 = word.bbox_px
        page.insert_text((x0 / width * 595, y1 / height * 842 - 1), word.text, fontname="korea",
                         fontsize=max(5.0, (y1 - y0) / height * 842 * .8))


def _pdf(path, kinds, image=None, page_size=(595, 842)):
    """kinds per page: text (the sample 초본 page 1..3 text layer, cycling) | image (A4-sized picture) | tiny."""
    pages = _pages()
    with pymupdf.open() as document:
        for index, kind in enumerate(kinds):
            page = document.new_page(width=page_size[0], height=page_size[1])
            if kind == "text":
                _text(page, pages[min(index, 2)][1].words, pages[min(index, 2)][0].pixel_size)
            elif kind == "tiny":  # a card-sized page whose only content is a 500 x 700 px picture (150 dpi)
                document.delete_page(-1)
                page = document.new_page(width=240, height=336)
                page.insert_image(page.rect, stream=_png((500, 700)))
            else:
                page.insert_image(RECT, stream=image or _png())
        document.save(path, deflate=True)
    return path


@pytest.fixture
def ocr_calls(monkeypatch):
    """Fake own OCR: every recognized image returns the sample page 2 words; records each call."""
    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    calls = []
    page, result = _pages()[1]

    def recognize(png, size):
        calls.append(size)
        sx, sy = size[0] / page.pixel_size[0], size[1] / page.pixel_size[1]
        return [dataclasses.replace(w, bbox_px=(w.bbox_px[0] * sx, w.bbox_px[1] * sy,
                                                w.bbox_px[2] * sx, w.bbox_px[3] * sy)) for w in result.words]
    monkeypatch.setitem(v2ocr.ENGINES, "own", recognize)
    return calls


@pytest.fixture
def renders(monkeypatch):
    """Count 300 dpi page renders (the 72 dpi shared-image digests and viewers are not counted)."""
    made = []
    original = pymupdf.Page.get_pixmap

    def get_pixmap(self, *args, **kwargs):
        if kwargs.get("dpi") == 300:
            made.append(self.number)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(pymupdf.Page, "get_pixmap", get_pixmap)
    return made


def _verdict(path, program):
    checklist = build_checklist(PROGRAMS[program], ApplicantDocInput(work_category=WorkCategory.EMPLOYEE))
    slot = find_slot(checklist, "resident_abstract")
    ocr = read_document(str(path), DocType.RESIDENT_ABSTRACT)
    _, check = assess_upload(path, slot, identity=Identity(sample.NAME, date.fromisoformat(sample.BIRTH)),
                             checklist=checklist, reader=lambda _p, _e: ocr)
    return ocr, check


def _never_fails_or_passes(check):
    assert check.status == "NEEDS_REVIEW", check.findings
    assert not [f.code for f in check.findings if f.severity == "FAIL"]


# ---------------------------------------------------------------- page images are made one at a time


def test_rendered_pages_are_made_when_read_not_all_up_front(tmp_path, ocr_calls, renders, monkeypatch):
    """Main rendered all 6 pages (Pixmap + PNG each) before the first page was read."""
    seen = []
    original = v2ocr.ENGINES["own"]
    monkeypatch.setitem(v2ocr.ENGINES, "own", lambda png, size: seen.append(len(renders)) or original(png, size))
    path = _pdf(tmp_path / "FAKE-mixed.pdf", ("text", "image", "image", "image", "image", "image"))
    ocr = read_document(str(path), DocType.RESIDENT_ABSTRACT)
    assert ocr.fallback_reason == "RENDER_RETRY:TEXT_RASTER_CONTENT" and ocr.page_count == 6
    assert seen == [1, 2, 3, 4, 5, 6]          # at the n-th read exactly n pages have been rendered
    assert renders == [0, 1, 2, 3, 4, 5]       # every page is still read, in order


def test_render_pages_hands_out_loaders_and_keeps_no_page_image(tmp_path, renders):
    path = _pdf(tmp_path / "FAKE-scan.pdf", ("image", "image", "image"))
    with localocr.render_pages(path) as (pages, loaders):
        assert len(pages) == len(loaders) == 3 and renders == []
        assert all(page.png is None and page.pixel_size is None for page in pages)
        png, size = loaders[1]()
        assert renders == [1] and png.startswith(b"\x89PNG") and size == (2480, 3509)
        assert pages[1].pixel_size == size and pages[1].png is None   # the list never holds the image


def test_concurrent_page_reads_keep_a_bounded_number_of_page_images(monkeypatch):
    """The real concurrent path asks for at most workers x PAGE_LOOKAHEAD pages ahead, on the caller's thread."""
    import threading
    from engine_v2.pipeline.ocr import OcrWord, own

    caller = threading.get_ident()
    loaded, finished, release = [], [], threading.Event()

    def recognize(png, size):
        release.wait(5)
        finished.append(png)
        return [OcrWord(png.decode(), .9, (0, 0, 1, 1))]
    monkeypatch.setattr(own, "recognize", recognize)
    monkeypatch.setattr(own, "prepare_page_workers", lambda pages: 2)

    def loader(index):
        def load():
            assert threading.get_ident() == caller      # PDF rendering stays on the caller's thread
            loaded.append(index)
            return f"page-{index}".encode(), (10, 10)
        return load
    reads = v2ocr.run_ocr_pages("own", [loader(index) for index in range(12)])
    first = next(reads)
    assert loaded == list(range(2 * v2ocr.PAGE_LOOKAHEAD))        # not all 12 pages
    release.set()
    results = [first()] + [read() for read in reads]
    assert [r.words[0].text for r in results] == [f"page-{index}" for index in range(12)]
    assert loaded == list(range(12))


def test_stopping_early_does_not_make_the_remaining_pages(monkeypatch):
    from engine_v2.pipeline.ocr import OcrWord, own

    loaded = []
    monkeypatch.setattr(own, "recognize", lambda png, size: [OcrWord("x", .9, (0, 0, 1, 1))])
    monkeypatch.setattr(own, "prepare_page_workers", lambda pages: 2)
    reads = v2ocr.run_ocr_pages("own", [lambda index=index: (loaded.append(index) or b"p", (10, 10))
                                        for index in range(12)])
    next(reads)()
    reads.close()
    assert len(loaded) <= 2 * v2ocr.PAGE_LOOKAHEAD + 1


# ---------------------------------------------------------------- over a limit: not read, officer review


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_mixed_abstract_over_the_page_limit_is_not_read_and_never_passes(tmp_path, ocr_calls, renders,
                                                                        monkeypatch, program):
    """Page 1 is a PASS-capable text layer. Over the limit no page is rendered or recognized, and the
    first-page text tier is not used either: the whole document goes to the officer."""
    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 3)
    path = _pdf(tmp_path / "FAKE-mixed.pdf", ("text", "image", "image", "image", "image"))
    ocr, check = _verdict(path, program)
    assert ocr_calls == [] and renders == []
    assert ocr.tier == "localocr" and ocr.engine == "none" and ocr.confidence == 0
    assert ocr.detected_doc_type == DocType.RESIDENT_ABSTRACT
    assert ocr.fallback_reason == "RENDER_RETRY_FAILED:TEXT_RASTER_CONTENT:RESOURCE_LIMIT_PAGES"
    assert ocr.fields["판독실패"] == localocr.workload_message("PAGES")
    assert "발급일" not in ocr.fields and ocr.issue_date is None      # nothing of page 1's text layer is used
    _never_fails_or_passes(check)


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_the_same_text_pages_pass_without_raster_pages(tmp_path, ocr_calls, program):
    """Control for the test above: the limit is what sends it to review, not the sample."""
    path = _pdf(tmp_path / "FAKE-text.pdf", ("text", "text", "text"))
    ocr, check = _verdict(path, program)
    assert ocr_calls == [] and ocr.tier == "pdftext"
    assert check.status == "PASS", check.findings


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_scan_over_the_page_limit_is_not_read_and_stops_the_tier_chain(tmp_path, ocr_calls, monkeypatch, program):
    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 3)
    path = _pdf(tmp_path / "FAKE-scan.pdf", ("image",) * 4)
    ocr, check = _verdict(path, program)
    assert ocr_calls == []
    assert ocr.tier == "none" and ocr.engine == "none" and ocr.confidence == 0 and ocr.detected_doc_type is None
    assert ocr.fallback_reason == "RESOURCE_LIMIT:PAGES" and ocr.page_count == 4
    assert ocr.fields["판독실패"] == localocr.workload_message("PAGES")
    _never_fails_or_passes(check)


@pytest.mark.parametrize("program", PROGRAM_CODES)
@pytest.mark.parametrize("kinds", [("image", "image", "image", "tiny"), ("text", "image", "image", "tiny")])
def test_unread_document_is_not_failed_for_a_small_picture(tmp_path, ocr_calls, monkeypatch, kinds, program):
    """IMAGE_RESOLUTION_TOO_LOW (FAIL) means 'small picture AND could not be read'. A document the guard did not
    try to read must not be failed for it (independent review, 11-27)."""
    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 3)
    ocr, check = _verdict(_pdf(tmp_path / "FAKE-small-page.pdf", kinds), program)
    assert ocr_calls == [] and limits.not_read_by_limit(ocr.fallback_reason)
    assert '"width":500' in ocr.fields["원본이미지크기"]          # the size evidence is still recorded
    _never_fails_or_passes(check)


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_time_budget_stop_is_not_failed_for_a_small_picture(tmp_path, ocr_calls, monkeypatch, program):
    ticks = iter([0, 0, 0])
    monkeypatch.setattr(v2ocr.time, "monotonic", lambda: next(ticks, limits.MAX_OCR_SECONDS + 1))
    ocr, check = _verdict(_pdf(tmp_path / "FAKE-slow-small.pdf", ("image", "image", "tiny")), program)
    assert len(ocr_calls) == 2 and ocr.fallback_reason == "RESOURCE_LIMIT:SECONDS"
    _never_fails_or_passes(check)


def test_page_limit_is_checked_before_any_page_image_is_decoded(tmp_path, monkeypatch):
    """Counting while decoding refused page 4 only after pages 1-3 had been decoded and PNG-encoded."""
    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 3)
    path = _pdf(tmp_path / "FAKE-scan.pdf", ("image",) * 4)

    def no_decode(*args, **kwargs):
        raise AssertionError("no page image may be decoded")
    monkeypatch.setattr(v2preprocess.pymupdf, "Pixmap", no_decode)
    with pytest.raises(limits.OcrWorkloadExceeded) as error:
        v2preprocess.preprocess(path)
    assert error.value.code == "PAGES"


def test_shared_image_digest_is_not_rendered_for_a_huge_page(tmp_path, monkeypatch):
    """Two 14400 x 14400 pt pages drawing one small picture: the 72 dpi digest render would be 207 MP each."""
    with pymupdf.open() as document:
        first = document.new_page(width=14400, height=14400)
        xref = first.insert_image(first.rect, stream=_png((1200, 1200)))
        second = document.new_page(width=14400, height=14400)
        second.insert_image(second.rect, xref=xref)
        document.save(tmp_path / "FAKE-shared.pdf", deflate=True)

    def no_render(self, *args, **kwargs):
        raise AssertionError("the page must not be rendered")
    monkeypatch.setattr(pymupdf.Page, "get_pixmap", no_render)
    with pytest.raises(limits.OcrWorkloadExceeded) as error:
        v2preprocess.preprocess(tmp_path / "FAKE-shared.pdf")
    assert error.value.code == "PAGE_PIXELS"


def test_render_retry_over_a_limit_keeps_the_fully_read_first_pass(tmp_path, monkeypatch):
    """Unclassified scan on a large-format page: every page was read once from its embedded picture; the optional
    300 dpi re-read would exceed the page limit, so it is skipped - the document is not labelled 'not read'."""
    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    calls = []
    monkeypatch.setitem(v2ocr.ENGINES, "own", lambda png, size: calls.append(size) or [])   # OCR finds no text
    with pymupdf.open() as document:
        page = document.new_page(width=6000, height=8400)        # 300 dpi render: 875 MP
        page.insert_image(page.rect, stream=_png((1500, 2100)))
        document.save(tmp_path / "FAKE-large-scan.pdf", deflate=True)
    ocr = read_document(str(tmp_path / "FAKE-large-scan.pdf"), DocType.RESIDENT_ABSTRACT)
    assert calls == [(1500, 2100)]                                # read once, never rendered at 300 dpi
    assert not limits.not_read_by_limit(ocr.fallback_reason)
    assert ocr.detected_doc_type is None and ocr.confidence == 0  # unclassified -> officer review, as before


def test_pages_at_the_limit_are_all_read(tmp_path, ocr_calls, monkeypatch):
    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 3)
    path = _pdf(tmp_path / "FAKE-scan.pdf", ("image",) * 3)
    ocr = read_document(str(path), DocType.RESIDENT_ABSTRACT)
    assert len(ocr_calls) == 3 and ocr.tier == "localocr" and not ocr.fallback_reason.startswith("RESOURCE_LIMIT")


def test_text_layer_pages_do_not_count_as_ocr_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 3)
    path = _pdf(tmp_path / "FAKE-text.pdf", ("text",) * 6)
    assert [page.source.value for page in v2preprocess.preprocess(path)] == ["text_layer"] * 6


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_huge_embedded_image_is_refused_before_it_is_decoded(tmp_path, ocr_calls, monkeypatch, program):
    """An 8000 x 8000 grey picture is about 70 KB in the PDF and 192 MB as RGB (main decoded it, then PNG, then BGR)."""
    path = _pdf(tmp_path / "FAKE-bomb.pdf", ("image",), image=_png((8000, 8000), "L"))
    assert path.stat().st_size < 200_000

    def no_decode(*args, **kwargs):
        raise AssertionError("the picture must not be decoded")
    monkeypatch.setattr(v2preprocess.pymupdf, "Pixmap", no_decode)
    ocr, check = _verdict(path, program)
    assert ocr_calls == []
    assert ocr.tier == "none" and ocr.fallback_reason == "RESOURCE_LIMIT:PAGE_PIXELS"
    assert ocr.fields["판독실패"] == localocr.workload_message("PAGE_PIXELS")
    _never_fails_or_passes(check)


@pytest.mark.parametrize("program", PROGRAM_CODES)
def test_large_format_page_is_not_rendered(tmp_path, ocr_calls, monkeypatch, program):
    """Text-layer 초본 page plus an A4-sized picture on a 5000 x 7000 pt page: a 300 dpi render would be
    608 MP (1.8 GB) per page. (The picture keeps its 150 dpi, so no business image-quality rule applies.)"""
    path = _pdf(tmp_path / "FAKE-large.pdf", ("text", "image"), page_size=(5000, 7000))

    def no_render(self, *args, **kwargs):  # never allocate it, on any version of the code
        raise AssertionError("the page must not be rendered")
    monkeypatch.setattr(pymupdf.Page, "get_pixmap", no_render)
    ocr, check = _verdict(path, program)
    assert ocr_calls == []
    assert ocr.fallback_reason == "RENDER_RETRY_FAILED:TEXT_RASTER_CONTENT:RESOURCE_LIMIT_PAGE_PIXELS"
    _never_fails_or_passes(check)


def test_document_pixel_budget_counts_every_ocr_page(tmp_path, ocr_calls, monkeypatch):
    monkeypatch.setattr(limits, "MAX_DOCUMENT_PIXELS", 3 * 1240 * 1754)
    assert len(v2preprocess.preprocess(_pdf(tmp_path / "three.pdf", ("image",) * 3))) == 3
    with pytest.raises(limits.OcrWorkloadExceeded) as error:
        v2preprocess.preprocess(_pdf(tmp_path / "four.pdf", ("image",) * 4))
    assert error.value.code == "DOCUMENT_PIXELS"
    ocr = read_document(str(tmp_path / "four.pdf"), DocType.RESIDENT_ABSTRACT)
    assert ocr_calls == [] and ocr.fallback_reason == "RESOURCE_LIMIT:DOCUMENT_PIXELS"


def test_oversized_photo_upload_is_refused_before_it_is_decoded(tmp_path, ocr_calls, monkeypatch):
    path = tmp_path / "FAKE-photo.png"
    path.write_bytes(_png((8000, 8000), "L"))
    monkeypatch.setattr(v2preprocess.pymupdf, "Pixmap", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    ocr = read_document(str(path), DocType.RESIDENT_ABSTRACT)
    assert ocr_calls == [] and ocr.tier == "none" and ocr.fallback_reason == "RESOURCE_LIMIT:PAGE_PIXELS"


def test_photo_too_large_for_the_image_library_goes_to_review_instead_of_a_server_error(tmp_path, ocr_calls,
                                                                                        monkeypatch):
    """14200 x 14200 (202 MP): PIL refuses to open it. Main raised out of read_document (HTTP 500)."""
    path = tmp_path / "FAKE-photo.png"
    path.write_bytes(_png((14200, 14200), "1"))
    monkeypatch.setattr(v2preprocess.pymupdf, "Pixmap", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    ocr, check = _verdict(path, DOUBLE_SAVINGS)
    assert ocr_calls == [] and ocr.tier == "none" and ocr.fallback_reason == "RESOURCE_LIMIT:PAGE_PIXELS"
    _never_fails_or_passes(check)


@pytest.mark.parametrize("program", PROGRAM_CODES)
@pytest.mark.parametrize("kinds, reason", [
    (("text", "image", "image"), "RENDER_RETRY_FAILED:TEXT_RASTER_CONTENT:RESOURCE_LIMIT_SECONDS"),
    (("image", "image", "image"), "RESOURCE_LIMIT:SECONDS"),
])
def test_read_over_the_time_budget_discards_the_pages_already_read(tmp_path, ocr_calls, monkeypatch, kinds,
                                                                  reason, program):
    """The clock passes the budget after the second page: the two pages read so far are not judged."""
    ticks = iter([0, 0, 0])   # generator start, check before page 1, check before page 2 - then past the budget
    monkeypatch.setattr(v2ocr.time, "monotonic", lambda: next(ticks, limits.MAX_OCR_SECONDS + 1))
    ocr, check = _verdict(_pdf(tmp_path / "FAKE-slow.pdf", kinds), program)
    assert len(ocr_calls) == 2
    assert ocr.fallback_reason == reason and ocr.confidence == 0 and ocr.engine == "none"
    assert ocr.fields["판독실패"] == localocr.workload_message("SECONDS")
    assert "발급일" not in ocr.fields and "전입일" not in ocr.fields
    _never_fails_or_passes(check)


def test_workload_error_is_not_a_page_error_or_an_unreadable_file():
    """ValueError would be swallowed as a page error (engine._load_pages) or end as 'file cannot be opened'."""
    assert not issubclass(limits.OcrWorkloadExceeded, (ValueError, OSError, RuntimeError))
    workload = limits.OcrWorkload()
    for _ in range(limits.MAX_OCR_PAGES):
        workload.add(2480, 3509)
    with pytest.raises(limits.OcrWorkloadExceeded) as error:
        workload.add(2480, 3509)
    assert error.value.code == "PAGES"
    with pytest.raises(limits.OcrWorkloadExceeded) as error:
        limits.OcrWorkload().add(limits.MAX_PAGE_PIXELS + 1, 1)
    assert error.value.code == "PAGE_PIXELS"
    limits.OcrWorkload().add(8192, 6144)       # a 50 MP-class phone photo and A4 at 600 dpi stay readable
    limits.OcrWorkload().add(4961, 7016)


def test_engine_load_pages_lets_the_workload_error_through(tmp_path, monkeypatch):
    from engine_v2 import engine as v2engine
    from engine_v2.schemas.models import DocType as V2Type, DocumentInput

    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 1)
    path = _pdf(tmp_path / "FAKE-scan.pdf", ("image", "image"))
    with pytest.raises(limits.OcrWorkloadExceeded):
        v2engine._load_pages(DocumentInput(doc_id="x", declared_type=V2Type.RESIDENT_ABSTRACT, file_path=str(path)), "own")


# ---------------------------------------------------------------- upload body is not read into memory at once


def test_upload_is_stored_in_chunks(tmp_path):
    from fastapi import UploadFile

    from demo.backend.api import documents

    content = bytes(range(256)) * 4096 * 3 + b"tail"          # 3 MB + 4 bytes
    sizes = []

    class Recording(UploadFile):
        async def read(self, size: int = -1) -> bytes:
            sizes.append(size)
            return await super().read(size)
    asyncio.run(documents._store_upload(Recording(io.BytesIO(content), filename="FAKE.pdf"), tmp_path / "out.pdf"))
    assert (tmp_path / "out.pdf").read_bytes() == content
    assert sizes and all(0 < size <= 1024 * 1024 for size in sizes)   # never the whole body in one read
    receive = getattr(documents, "_receive_upload", None)             # officer: staged outside the storage first
    if receive is not None:
        sizes.clear()
        staged = asyncio.run(receive(Recording(io.BytesIO(content), filename="FAKE.pdf")))
        assert documents.STORAGE not in staged.parents and all(0 < size <= 1024 * 1024 for size in sizes)
        documents._place_upload(staged, tmp_path / "placed.pdf")
        assert (tmp_path / "placed.pdf").read_bytes() == content and not staged.exists()
