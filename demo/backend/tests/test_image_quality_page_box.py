"""11-28: 원본 해상도 측정은 쪽 상자 크기만으로 '저해상도'가 되지 않는다 (가상 문서만).

배경: 화질 점수는 판독 성공 여부가 아니라 파일의 원본 그림 해상도(쪽을 덮는 그림의 화소 ÷ 쪽 크기 = DPI)로만 정한다.
그런데 쪽 상자가 실제 용지보다 큰 PDF(그림→PDF 변환이 화소 수를 72dpi 쪽 크기로 적은 것, A2·A1 쪽 상자)는 같은 그림이
A4 쪽에서는 250dpi인데 72~125dpi로 계산됐다. youth는 화질 미달이 부적합(FAIL)이라, 자동 판독이 신뢰도 0.95로 읽은
문서와 작업량 한도로 읽지도 않은 문서가 "이미지가 흐리거나 작아 읽을 수 없습니다"로 반려됐다(근거 없는 FAIL).

고친 규칙: 실제 용지(A3·타블로이드)보다 큰 쪽 상자는 A4에 맞춘 크기로도 재어 높은 쪽을 쓴다(그림 파일 등급 이하).
용지 크기 쪽과 그림 파일의 기준은 그대로다.
- 쪽 상자만 큰 문서는 화질 사유가 사라진다.
- 실제로 화소가 모자란 그림(A4에서도 150dpi 미만)은 쪽 상자와 무관하게 그대로 미달이다(완화 없음).
- 판독 실패·작업량 한도만으로는 화질 사유가 생기지 않는다(측정값이 없으면 중립).

사업별 정책은 그대로다: youth는 미달이면 FAIL, 두배적금은 담당자 확인.
"""
import io
from datetime import date
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from demo.backend.ocr import file_evidence, localocr, read_document
from demo.backend.rules import doc_check
from demo.backend.rules.doc_types import DocType
from demo.backend.rules.identity import Identity
from demo.backend.rules.programs import DOUBLE_SAVINGS, JOB_PACKAGE, PROGRAMS
from demo.backend.rules.required_docs import ApplicantDocInput, WorkCategory, build_checklist, find_slot
from demo.backend.upload_assessment import assess_upload
from engine_v2.pipeline import limits

A4, A3, A2, A1 = (595, 842), (842, 1191), (1191, 1684), (1684, 2384)
#: youth 저장소(범용 사업 API가 있는 쪽): 화질 미달은 FAIL. 두배적금 저장소: 담당자 확인(11-18 S5).
QUALITY_IS_FAIL = (Path(doc_check.__file__).resolve().parents[1] / "api" / "generic_officer.py").is_file()
LOW = "LOW_IMAGE_QUALITY"


def _scan_pdf(path, pixel_width, box, pages=1):
    """쪽마다 쪽 전체를 덮는 그림 한 장(가로 pixel_width 화소, A4 비율). box=None이면 화소 수 = 쪽 크기(72dpi 변환 PDF)."""
    size = (pixel_width, round(pixel_width * 842 / 595))
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, "PNG")
    width, height = box or size
    with pymupdf.open() as document:
        for _ in range(pages):
            document.new_page(width=width, height=height).insert_image(
                pymupdf.Rect(0, 0, width, height), stream=buffer.getvalue())
        document.save(path, deflate=True)
    return path


def _bitmap_pdf(path, pixels, box=None, rotation=0):
    """임의 크기 그림 한 장이 쪽 전체를 덮는 PDF. box=None이면 화소 수 = 쪽 크기(72dpi 변환 PDF)."""
    buffer = io.BytesIO()
    Image.new("RGB", pixels, "white").save(buffer, "PNG")
    width, height = box or pixels
    with pymupdf.open() as document:
        page = document.new_page(width=width, height=height)
        page.insert_image(pymupdf.Rect(0, 0, width, height), stream=buffer.getvalue(), keep_proportion=False)
        page.set_rotation(rotation)
        document.save(path, deflate=True)
    return path


def _verdict(path, program):
    checklist = build_checklist(PROGRAMS[program], ApplicantDocInput(work_category=WorkCategory.EMPLOYEE))
    slot = find_slot(checklist, "resident_abstract")
    return assess_upload(path, slot, identity=Identity("가상인", date(1999, 1, 1)), checklist=checklist,
                         reader=read_document)


def _quality_finding(check):
    return next((f for f in check.findings if f.code == LOW), None)


# ---------------------------------------------------------------- 측정


@pytest.mark.parametrize("box", [A4, (612, 792), (612, 1008), (720, 864), A3, (1191, 842), (792, 1224), (858, 1248)])
def test_real_sheet_sizes_are_measured_by_their_own_page_size(box):
    assert file_evidence.sheet_scale(*box) == 1.0


@pytest.mark.parametrize("box", [(860, 1191), (842, 1250), A2, A1, (2066, 2923), (2923, 2066), (3024, 4032)])
def test_page_boxes_larger_than_a3_are_measured_as_a4(box):
    scale = file_evidence.sheet_scale(*box)
    short, long = sorted(box)
    assert scale < 1 and short * scale <= 595 + 1e-6 and long * scale <= 842 + 1e-6
    assert abs(short * scale - 595) < 1e-6 or abs(long * scale - 842) < 1e-6


@pytest.mark.parametrize("box", [A4, A2, A1, None])
def test_the_same_good_bitmap_scores_the_same_on_any_page_box(tmp_path, box):
    """2066px 그림(A4에서 250dpi). 수정 전: A2 125dpi·A1 88dpi·72dpi 쪽 → 0.5(미달)."""
    assert file_evidence.objective_image_quality(str(_scan_pdf(tmp_path / "FAKE.pdf", 2066, box))) == .9


@pytest.mark.parametrize("box", [A4, A2, A1, None])
@pytest.mark.parametrize("pixel_width", [827, 1158])
def test_a_bitmap_below_the_a4_standard_stays_low_on_any_page_box(tmp_path, box, pixel_width):
    """827px(A4에서 100dpi)·1158px(140dpi): 기준(150dpi) 미달은 쪽 상자가 커도 그대로다."""
    assert file_evidence.objective_image_quality(str(_scan_pdf(tmp_path / "FAKE.pdf", pixel_width, box))) == .5


@pytest.mark.parametrize("pixel_width, expected", [(1239, .5), (1240, .7), (1652, .7), (1653, .9)])
def test_oversized_page_uses_the_a4_dpi_bands(tmp_path, pixel_width, expected):
    """A4의 4배 쪽 상자(2380×3368pt): A4 폭(595pt = 8.264in) 기준 150·200dpi 경계가 그대로 적용된다."""
    path = _scan_pdf(tmp_path / "FAKE.pdf", pixel_width, (2380, 3368))
    assert file_evidence.objective_image_quality(str(path)) == expected


@pytest.mark.parametrize("pixels, box", [((600, 5000), None), ((300, 2000), None), ((5000, 600), None),
                                         ((650, 4333), (300, 2000))])
def test_a_pdf_wrapper_never_scores_above_the_bitmap_itself(tmp_path, pixels, box):
    """좁고 긴 띠 그림: A4에 맞춘 DPI는 높게 나오지만 그림 파일로는 미달(짧은 변 700px 미만)이다 → 전과 같은 점수."""
    path = _bitmap_pdf(tmp_path / "FAKE.pdf", pixels, box)
    before = file_evidence._dpi_band(pixels[0] / ((box or pixels)[0] / 72))      # 수정 전 규칙: 쪽 상자 DPI
    assert file_evidence.objective_image_quality(str(path)) == before
    Image.new("RGB", pixels, "white").save(tmp_path / "FAKE.png")
    assert file_evidence.objective_image_quality(str(tmp_path / "FAKE.png")) == .35


@pytest.mark.parametrize("pixels, box, rotation", [((2923, 2066), None, 0), ((2923, 2066), (1684, 1191), 0),
                                                   ((2066, 2923), A2, 90), ((2066, 2923), None, 270)])
def test_landscape_and_rotated_oversized_pages_keep_the_good_bitmap_score(tmp_path, pixels, box, rotation):
    assert file_evidence.objective_image_quality(str(_bitmap_pdf(tmp_path / "FAKE.pdf", pixels, box, rotation))) == .9


def test_phone_screenshot_pdf_scores_as_its_a4_fit(tmp_path):
    """1080×1920px(72dpi 쪽): A4에 맞추면 164dpi → 0.7, 그림 파일로는 0.75. 낮은 쪽인 0.7."""
    assert file_evidence.objective_image_quality(str(_bitmap_pdf(tmp_path / "FAKE.pdf", (1080, 1920)))) == .7


def test_the_lowest_page_decides_across_mixed_page_sizes(tmp_path):
    good, low = _scan_pdf(tmp_path / "good.pdf", 2066, A1), _scan_pdf(tmp_path / "low.pdf", 827, A4)
    for order in ((good, low), (low, good)):
        with pymupdf.open() as merged:
            for part in order:
                with pymupdf.open(part) as source:
                    merged.insert_pdf(source)
            merged.save(tmp_path / "merged.pdf")
        assert file_evidence.objective_image_quality(str(tmp_path / "merged.pdf")) == .5


def test_a3_sheet_keeps_its_physical_dpi(tmp_path):
    """A3 용지(실제 스캔 가능 크기)는 쪽 크기 그대로 잰다: 1403px = 120dpi → 미달 유지. A4 쪽이면 170dpi."""
    assert file_evidence.objective_image_quality(str(_scan_pdf(tmp_path / "FAKE-a3.pdf", 1403, A3))) == .5
    assert file_evidence.objective_image_quality(str(_scan_pdf(tmp_path / "FAKE-a4.pdf", 1403, A4))) == .7


# ---------------------------------------------------------------- 판정: 읽지 않은 문서


@pytest.fixture
def over_page_limit(monkeypatch):
    """OCR 엔진 없이 작업량 한도 경로를 낸다: 스캔 3쪽이면 쪽 수 한도(2쪽) 초과 → 한 쪽도 읽지 않는다."""
    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    monkeypatch.setattr(limits, "MAX_OCR_PAGES", 2)


@pytest.mark.parametrize("program", [DOUBLE_SAVINGS, JOB_PACKAGE])
@pytest.mark.parametrize("box", [A2, A1, None])
def test_unread_document_with_a_good_bitmap_is_not_failed_for_quality(tmp_path, over_page_limit, program, box):
    """한도로 읽지 않았고 그림 화소도 충분하다: 화질 사유 없음, 부적합 없음(수정 전 youth: LOW_IMAGE_QUALITY FAIL)."""
    ocr, check = _verdict(_scan_pdf(tmp_path / "FAKE.pdf", 2066, box, pages=3), program)
    assert limits.not_read_by_limit(ocr.fallback_reason) and ocr.image_quality == .9
    assert _quality_finding(check) is None
    assert check.status == "NEEDS_REVIEW" and not [f.code for f in check.findings if f.severity == "FAIL"]


@pytest.mark.parametrize("program", [DOUBLE_SAVINGS, JOB_PACKAGE])
@pytest.mark.parametrize("box", [A4, A1])
def test_unread_document_with_a_measured_low_bitmap_keeps_the_program_policy(tmp_path, over_page_limit, program, box):
    """읽지 않았어도 그림이 실제로 기준 미달(827px)이면 사업 정책 그대로: youth FAIL, 두배적금 담당자 확인."""
    ocr, check = _verdict(_scan_pdf(tmp_path / "FAKE.pdf", 827, box, pages=3), program)
    assert limits.not_read_by_limit(ocr.fallback_reason) and ocr.image_quality == .5
    finding = _quality_finding(check)
    assert finding is not None
    assert (finding.severity, check.status) == (("FAIL", "FAIL") if QUALITY_IS_FAIL else ("NEEDS_REVIEW", "NEEDS_REVIEW"))
    if QUALITY_IS_FAIL:
        # 저장되는 근거: 판독 결과가 아니라 파일 측정값이라는 것과, 읽지 않은 문서라는 것을 담당자에게 구분해 남긴다.
        assert "화질 사유 근거" in finding.detail and "827×" in finding.detail
        assert "자동 판독하지 않았습니다" in finding.detail


# ---------------------------------------------------------------- 판정: 판독 실패만 있는 문서


@pytest.mark.parametrize("program", [DOUBLE_SAVINGS, JOB_PACKAGE])
@pytest.mark.parametrize("box", [A4, A2, None])
def test_reading_failure_alone_never_becomes_a_quality_reason(tmp_path, monkeypatch, program, box):
    """판독 계층이 예외로 끝났다(화질은 확인하지 못함). 그림 화소가 충분하면 화질 사유도 부적합도 없다."""
    monkeypatch.setenv("ENGINE_V2_OCR", "own")

    def broken(self, file_path, engine):
        raise RuntimeError("synthetic engine failure")
    monkeypatch.setattr(localocr.LocalOcr, "_read", broken)
    ocr, check = _verdict(_scan_pdf(tmp_path / "FAKE.pdf", 2066, box, pages=2), program)
    assert ocr.tier == "none" and ocr.detected_doc_type is None and ocr.image_quality == .9
    assert _quality_finding(check) is None
    assert check.status == "NEEDS_REVIEW" and not [f.code for f in check.findings if f.severity == "FAIL"]


def test_quality_reason_of_a_readable_size_document_names_the_file_measurement(tmp_path, monkeypatch):
    """한도와 무관한 저해상도 문서: 화질 사유의 근거는 파일 측정값이다(youth: 담당자용 detail에 남긴다)."""
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    _, check = _verdict(_scan_pdf(tmp_path / "FAKE.pdf", 827, A4, pages=1), JOB_PACKAGE)
    finding = _quality_finding(check)
    assert finding is not None
    if QUALITY_IS_FAIL:
        assert finding.severity == "FAIL" and check.status == "FAIL"
        assert "화질 사유 근거" in finding.detail and "1쪽 827×1170px" in finding.detail
        assert "자동 판독하지 않았습니다" not in finding.detail  # 한도로 건너뛴 문서가 아니다
    else:
        assert finding.severity == "NEEDS_REVIEW" and check.status == "NEEDS_REVIEW"


def test_quality_reason_points_at_the_smallest_bitmap_page(tmp_path, monkeypatch):
    """여러 쪽 가운데 뒤쪽 한 쪽만 저해상도여도 근거에는 그 쪽이 나온다(앞의 정상 쪽을 근거로 보여 주지 않는다)."""
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    good, low = _scan_pdf(tmp_path / "good.pdf", 2066, A4, pages=3), _scan_pdf(tmp_path / "low.pdf", 827, A4)
    with pymupdf.open() as merged:
        for part in (good, low):
            with pymupdf.open(part) as source:
                merged.insert_pdf(source)
        merged.save(tmp_path / "FAKE-merged.pdf")
    ocr, check = _verdict(tmp_path / "FAKE-merged.pdf", JOB_PACKAGE)
    finding = _quality_finding(check)
    assert ocr.image_quality == .5 and finding is not None
    if QUALITY_IS_FAIL:
        assert "4장 중 가장 작은 것은 4쪽 827×1170px" in finding.detail
