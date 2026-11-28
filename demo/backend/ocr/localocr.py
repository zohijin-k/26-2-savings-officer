"""Tier1.5 — 로컬 OCR 판독 (engine_v2).

Tier2(pdftext)는 텍스트 레이어가 있는 PDF만 읽는다. 그런데 실측(2026-11-10)해 보니
신청자가 정부24에서 받아 올리는 초본은 **브라우저 "PDF로 저장" 본이라 글자가 전부
이미지**다. Tier2는 이걸 못 읽고 신뢰도 0 → 전부 담당자 큐로 갔다.

이 계층은 그 공백을 메운다.
  - 서류 이미지를 **외부로 보내지 않고** 이 서버 안에서 OCR한다 (개인정보).
  - 초본/등본은 engine_v2 추출기로 구조를 읽는다: 성명·생년월일·발급일·주소이력,
    그리고 쪽 간 일치·순번 연속 같은 **서류 내부 검증**으로 신뢰도를 매긴다.
  - 건강보험료 납부·자격득실확인서는 텍스트 PDF와 이미지 PDF 모두 engine_v2 추출기를 쓴다.
  - 취업지원패키지 추가서류(결제영수증·응시확인서·성적표·면접확인서)도 텍스트 PDF와 이미지 모두
    engine_v2 추출기(receipt·exam_docs·interview_confirmation)를 쓴다.
  - 그 밖의 서류는 OCR 텍스트에 Tier2의 정규식 추출을 그대로 적용한다.

처리하지 않는 파일(→ None, 다음 계층으로):
  - 지원 전용 추출기 밖의 텍스트 PDF: Tier2가 판독한다. 키워드 미판별 주민등록표는 좌표 제목을 확인한다.
  - 암호 PDF·없는 파일: Tier2가 공고문 문구로 '미비'를 낸다
  - OCR 엔진이 설치돼 있지 않은 서버: 조용히 건너뛴다 (데모가 멈추지 않는 원칙)

OCR 엔진 선택: 환경변수 ENGINE_V2_OCR = own | applevision | easyocr | paddle | off
  명시한 값이 우선이며, 기본값은 macOS를 포함해 own.
  기본 선택에서 own 모델 파일이 없을 때에만 easyocr로 대체한다.
  명시한 own의 모델 누락이나 추론 오류는 다른 OCR 엔진으로 대체하지 않는다.
  대체 사유는 engine_decision() 반환값과 경고 로그에만 남긴다.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from ..rules.doc_types import DocType
from .base import BBox, OcrResult
from engine_v2.pipeline.privacy import mask_rrn

NAME = "localocr"
ENGINE_ENV = "ENGINE_V2_OCR"

#: Tier2 신뢰도 공식은 '정확한 텍스트'를 전제로 한다. OCR 텍스트에는 그 근거가 없으므로,
#: 서류 내부 검증이 없는 서류는 엔진 임계값(0.85) 아래로 묶어 담당자 확인으로 보낸다.
GENERIC_CONFIDENCE_CAP = 0.8

#: 11-26 임시 안전장치 (Phase 1). OCR로 읽은(글자층이 아닌 쪽이 하나라도 있는) 주민등록초본은 자동 적합(PASS)을
#: 내지 않는다. 마지막 이력까지 빠짐없이 읽었는지(문서 완결성)를 독립적으로 확인할 검증된 기준이 아직 없기 때문이다:
#: 이미지에서 마지막 이력 줄들이 빠지고 '이하 여백'만 남은 초본은 순번·끝 표시만으로는 정상 초본과 구분되지 않는다.
#: 적용 범위: 이 모듈 _from_resident가 만드는 초본 결과 중 OCR 쪽이 있는 것 → 주소이력불확실사유 SCAN_UNVERIFIED
#: (→ doc_check ADDRESS_HISTORY_INCOMPLETE, 확인필요; 전입일·현주소시도·주소변동내역은 '불확실'로 두어 자동 판정에 쓰지 않는다).
#: 신뢰도는 낮추지 않으므로 발급일 등 확정 FAIL은 그대로 FAIL이다.
#: 바꾸지 않는 것: 글자층 PDF 판독(pdftext, 글자층 좌표 판독), 등본·그 밖의 서류, 사업별 규칙, 다른 검증.
#: 해제 조건: .trellis/spec/backend/resident-scan-completeness.md의 '자동 PASS 재허용 조건'을 독립 표본으로 충족할 때.
SCAN_ABSTRACT_REVIEW_GUARD = True

_REPO_ROOT = Path(__file__).resolve().parents[3]
_logger = logging.getLogger(__name__)

#: 1차 경로가 서식을 정하지 못한 PDF를 다시 읽는 렌더링 해상도.
#: batch_assess(A-스캔)와 같은 방식: 모든 층·투명도를 합성한 RGB, 알파 없음.
RENDER_RETRY_DPI = 300
#: 대체 판독 사유 코드. 결과의 fallback_reason에 ``RENDER_RETRY:<코드>``로 남는다(담당자 화면 전용).
RETRY_CODES = (
    "IMAGE_UNCLASSIFIED",       # 그림 길: OCR 글자는 있으나 서식 단서 없음
    "IMAGE_OCR_EMPTY",          # 그림 길: OCR 글자 0 (큰 배경 그림만 꺼낸 경우 포함)
    "IMAGE_PREPROCESS_ERROR",   # 그림 길: 본문 그림 꺼내기 오류 (흑백 마스크 등)
    "IMAGE_TEXT_PAGE",          # 그림 길: 첫 쪽은 그림, 뒤쪽에 글자층
    "TEXT_RECLASS_NONE",        # 글자층 길: 모든 쪽 다시 판별도 실패 (숨은 글자층 포함)
    "TEXT_RECLASS_DISCARD",     # 글자층 길: 모든 쪽 다시 판별 결과가 이 계층 담당 밖이라 버려짐
    "TEXT_RASTER_CONTENT",      # 글자층 길: 초본인데 그림·숨은 글자·글자 없는 쪽이 있어 글자층만으로 다 읽지 못함 (11-27)
)
#: 글자층 길 사유. 숨은 글자층·짧은 글자층 뒤의 그림을 읽으려는 대체 판독이므로 쪽을 덮는 그림이 있거나
#: 숨은 글자층이 있는 PDF만 다시 읽는다(page_has_cover_image·page_has_hidden_text). 그림 없는 글자층 PDF는
#: 렌더링해도 같은 글자층이 보일 뿐인데 모든 쪽을 300dpi OCR하면 10쪽 무관 글자 PDF가 0.1초에서 32초가 된다(11-27 실측).
TEXT_RETRY_CODES = ("TEXT_RECLASS_NONE", "TEXT_RECLASS_DISCARD")
_CLASS_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
#: get_bboxlog 항목 중 그림(래스터·마스크)과 보이지 않게 그린 글자(렌더 모드 3, 스캔 위 숨은 글자층).
_RASTER_KINDS = ("fill-image", "fill-imgmask")
_HIDDEN_TEXT_KINDS = ("ignore-text",)
_VISIBLE_TEXT_KINDS = ("fill-text", "stroke-text")


def _page_draw_kinds(path: Path) -> list[set[str]]:
    """쪽마다 그리는 항목 종류 (PyMuPDF get_bboxlog). 내용·좌표는 읽지 않는다. 암호 PDF는 빈 목록."""
    import pymupdf

    with pymupdf.open(path) as document:
        if document.needs_pass:
            return []
        return [{kind for kind, _ in page.get_bboxlog()} for page in document]


def raster_content_pages(path: Path) -> list[int]:
    """11-27: 보이는 글자층만으로는 내용을 다 읽었다고 할 수 없는 쪽 번호(0부터).

    PdfText는 첫 쪽 글자층만 읽는다. 그림으로 넣은 뒤쪽(스캔), 잘린 하단, 그림으로 넣은 표, 스캔 위 숨은
    글자층은 그 경로에서 읽히지 않거나 OCR 글자를 원본 글자층처럼 믿게 된다. 그래서 다음 중 하나라도 있는 쪽은
    그림 내용이 있는 쪽으로 본다. 면적 기준은 쓰지 않는다(작은 그림도 표 한 부분을 담을 수 있다):
      - 그림(래스터·마스크)을 그린다 (크기 무관, 직인·바코드 그림도 포함 → 담당자 확인 쪽으로 기운다),
      - 보이지 않게 그린 글자가 있다 (숨은 글자층),
      - 보이는 글자가 하나도 없다 (빈 쪽·윤곽선으로 그린 글자 포함).
    """
    return [index for index, kinds in enumerate(_page_draw_kinds(path))
            if kinds & {*_RASTER_KINDS, *_HIDDEN_TEXT_KINDS} or not kinds & set(_VISIBLE_TEXT_KINDS)]


def page_has_hidden_text(path: Path) -> bool:
    """보이지 않게 그린 글자(숨은 글자층)가 있는 쪽이 하나라도 있는가. 면적과 무관한 숨은 글자층 신호."""
    return any(kinds & set(_HIDDEN_TEXT_KINDS) for kinds in _page_draw_kinds(path))


def page_has_cover_image(path: Path) -> bool:
    """그림(래스터, 인라인 포함)이 쪽 면적의 MAIN_IMAGE_MIN_COVERAGE 이상을 덮는 쪽이 하나라도 있는가.

    preprocess가 본문 그림으로 보는 기준과 같은 비율이다. 여러 조각 그림은 면적을 더한다(겹침은
    넉넉하게 세어 대체 판독 쪽으로 기운다). 암호 PDF는 False.
    """
    import pymupdf
    from engine_v2.pipeline.preprocess import MAIN_IMAGE_MIN_COVERAGE

    with pymupdf.open(path) as document:
        if document.needs_pass:
            return False
        for page in document:
            area = page.rect.width * page.rect.height
            if area <= 0:
                continue
            covered = sum((pymupdf.Rect(info["bbox"]) & page.rect).get_area()
                          for info in page.get_image_info())
            if covered / area >= MAIN_IMAGE_MIN_COVERAGE:
                return True
    return False


def exception_code(exc: BaseException) -> str:
    """예외 클래스 이름만 돌려준다. 예외 문장(서류 내용이 섞일 수 있음)은 읽지 않는다."""
    name = type(exc).__name__
    return name if _CLASS_NAME.fullmatch(name) else "OTHER"


@contextmanager
def render_pages(path: Path):
    """모든 쪽을 300dpi로 렌더링해 읽을 준비를 한다 (engine_v2.tools.batch_assess._inspect와 같은 렌더링).

    ``(쪽 목록, 쪽 그림을 만드는 함수 목록)``을 내준다. 11-27 자원 보호: 쪽 그림은 미리 만들지 않고, 그 쪽을 읽을
    차례에 함수가 만들어 ``(png, 화소 크기)``로 돌려준다(run_ocr_pages가 작업 수만큼만 앞서 부른다). 그림은 쪽
    목록에 보관하지 않으므로 메모리가 쪽 수에 비례해 늘지 않는다 — 전에는 모든 쪽의 Pixmap·PNG를 먼저 만들어 두었다
    (20쪽 +425MB). 쪽 목록의 화소 크기는 그 쪽 그림을 만들 때 채워진다. 암호 PDF는 빈 목록.

    쪽 수·쪽 크기가 한도(engine_v2.pipeline.limits)를 넘으면 한 쪽도 렌더링하기 전에 OcrWorkloadExceeded를 낸다.
    """
    import pymupdf
    from engine_v2.pipeline.limits import OcrWorkload, check_page_images, release_page_cache
    from engine_v2.pipeline.preprocess import PageImage, PageSource, encode_png

    with pymupdf.open(path) as document:
        if document.needs_pass:
            yield [], []
            return
        workload = OcrWorkload()
        pages = []
        for index, page in enumerate(document):
            workload.add(page.rect.width * RENDER_RETRY_DPI / 72, page.rect.height * RENDER_RETRY_DPI / 72)
            check_page_images(page)  # 렌더링은 쪽의 그림을 펼친다: 그림 크기도 미리 확인한다.
            pages.append(PageImage(index, PageSource.RENDER, (page.rect.width, page.rect.height), dpi=RENDER_RETRY_DPI))

        def loader(image):
            def load():
                pix = document[image.page].get_pixmap(dpi=RENDER_RETRY_DPI, colorspace=pymupdf.csRGB, alpha=False)
                image.pixel_size = (pix.width, pix.height)
                png = encode_png(pix)  # 11-28: GIL을 놓는 인코더(화소는 같다)
                del pix
                release_page_cache()
                return png, image.pixel_size
            return load

        yield pages, [loader(image) for image in pages]


def engine_decision() -> tuple[str, str]:
    """선택한 엔진과 대체 사유(대체 없으면 빈 문자열). 모델 로드·검증·로그 없음."""
    configured = os.environ.get(ENGINE_ENV)
    if configured:
        return configured, ""

    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from engine_v2.pipeline.ocr import own
    from engine_v2.tools.fetch_own_models import ASSETS

    # 실제 own 로더의 디렉터리와 고정 자산 목록을 따른다. 해시/추론 오류는 대체하지 않는다.
    if all((own.MODEL_DIR / name).is_file() for name in ASSETS):
        return "own", ""
    return "easyocr", "own 모델 파일 없음: easyocr로 대체"


def _engine_name() -> str:
    return engine_decision()[0]


def preload_own() -> str:
    """서버 시작 때 own 모델(쪽 작업 세션 포함)을 미리 불러 첫 요청 지연을 없앤다.

    자동 스레드(OWN_OCR_* 미설정)일 때는 한 쪽씩 읽는 세션(intra 4)과 쪽 동시 읽기 세션
    (3쪽 이상: intra 2, 작업 수만큼; 2쪽: intra 4 두 개, 코어가 허락할 때)을 함께 불러온다.

    결과 코드만 돌려준다: LOADED / SKIPPED(own이 아님) / FAILED.
    실패해도 아무것도 바꾸지 않는다. 그때는 지금처럼 첫 OCR 호출이 불러오고
    같은 오류를 그 자리에서 낸다(세션 캐시는 실패를 기억하지 않는다).
    """
    try:
        if engine_decision()[0] != "own":
            return "SKIPPED"
        import io

        from PIL import Image
        from engine_v2.pipeline.ocr import own

        own.sessions()
        own.prepare_page_workers(own.MAX_PAGE_WORKERS)
        own.prepare_page_workers(2)  # 2쪽 문서용 세션(자동·코어 8개 이상: intra 4 두 개, 그 밖은 이미 불러온 것)
        # 빈 그림 한 장으로 판독 경로의 지연 import(cv2·pyclipper)와 첫 실행 준비를 끝낸다.
        blank = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(blank, format="PNG")
        own.recognize(blank.getvalue(), (32, 32))
        return "LOADED"
    except Exception as exc:  # noqa: BLE001 - 시작은 막지 않는다
        _logger.warning("own 모델 미리 불러오기 실패(첫 호출 때 불러옴): %s", exception_code(exc))
        return "FAILED"


def _import_v2():
    """engine_v2는 지연 import 한다 — OCR을 안 쓰는 경로에서 의존성을 요구하지 않도록."""
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from engine_v2.extractors import resident_abstract
    from engine_v2.extractors import nhis_acquisition_loss, nhis_payment
    from engine_v2.extractors import insurance_4
    from engine_v2.engine import _load_pages
    from engine_v2.pipeline.ocr import run_ocr
    from engine_v2.pipeline.preprocess import PageSource, preprocess
    from engine_v2.schemas.models import DocType as V2DocType, DocumentInput

    return resident_abstract, nhis_payment, nhis_acquisition_loss, run_ocr, PageSource, preprocess, V2DocType, DocumentInput, _load_pages, insurance_4


def _read_pages(run_ocr, engine: str, page_images, loaders=None):
    """쪽마다 읽기 함수를 쪽 순서대로 낸다. 여러 쪽 own은 동시에 읽는다(engine_v2 run_ocr_pages).

    ``loaders``: render_pages가 준 쪽 그림 함수 목록(11-27 늦은 렌더링). 없으면 쪽이 들고 있는 png를 읽는다.
    """
    from engine_v2.pipeline.ocr import run_ocr_pages
    images = loaders if loaders is not None else [(p.png, p.pixel_size) for p in page_images]
    return run_ocr_pages(engine, images, run=run_ocr)


def _quality(pages) -> float:
    """해상도로 화질을 근사한다 (엔진 IMAGE_QUALITY_THRESHOLD 0.6과 비교)."""
    raster = [p for p in pages if getattr(p, "source", None) != "text_layer"]
    if not raster:
        return 1.0  # Scalable text has no raster DPI, even in synthetic adapters.
    dpis = [p.dpi for p in raster if p.dpi]
    if not dpis:
        return 0.75  # 사진 업로드: 물리 크기를 몰라 중간값
    low = min(dpis)
    return 0.9 if low >= 200 else 0.7 if low >= 150 else 0.5


def _demo_bbox(v2_bbox) -> BBox | None:
    if v2_bbox is None:
        return None
    return BBox(v2_bbox.page, v2_bbox.x0, v2_bbox.y0, v2_bbox.x1, v2_bbox.y1)


def _entry_bbox(entry, pages) -> BBox | None:
    """주소이력 한 건의 위치 (전입일 하이라이트용)."""
    if not entry.words:
        return None
    page = next(p for p, _ in pages if p.page == entry.page)
    ws = [w for w in entry.words if w.page == entry.page]
    x0, y0 = page.px_to_pt(min(w.px[0] for w in ws), min(w.px[1] for w in ws))
    x1, y1 = page.px_to_pt(max(w.px[2] for w in ws), max(w.px[3] for w in ws))
    return BBox(entry.page, round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))


def _shared_image_groups(pages, marker_pages) -> list[list[int] | None] | None:
    """11-19 D10: per counted page (marker_pages order), [image group, render number] when its
    embedded main image (same xref) is also read as another page of this PDF, else None. None when
    no page shares one.

    The same xref gives the same OCR input twice even when the rendered pages differ; the page check
    then reviews a marker repeated across different renders of one image (PAGE_IMAGE_SHARED). Numbers
    only (group and render numbers, never the xref or digest).
    """
    if not marker_pages:
        return None
    seen = {page.page: (getattr(page, "image_xref", None), getattr(page, "render_digest", None))
            for page, _ in pages}
    shared = sorted({xref for xref, digest in seen.values() if xref is not None and digest is not None})
    if not shared:
        return None
    renders: list[str] = []  # render numbers in page order
    for xref, digest in seen.values():
        if xref in shared and digest is not None and digest not in renders:
            renders.append(digest)
    groups: list[list[int] | None] = []
    for number in marker_pages:
        xref, digest = seen.get(number, (None, None))
        groups.append([shared.index(xref), renders.index(digest)] if xref in shared and digest else None)
    return groups


def _number_column_ordinals(pages, ra) -> set[int]:
    """주소 이력 구역의 순번 칸(x < COL_NO_MAX_X)에 보이는 1~3자리 번호. 표를 찾았는지와 무관하게 모은다.

    쪽마다 이력 표 끝(추출기 _table_end와 같은 정의: '이하 여백' 줄 또는 순번 칸의 '병역' 구역 머리글) 아래는
    다른 구역이므로 세지 않는다 (11-21: 끝 뒤 구역은 확인필요 사유를 더하지 않는다). 추출기처럼 쪽마다 따로
    자르며, 앞 쪽의 구역 머리글이 뒤 쪽 이력을 가리지 않는다.
    """
    from engine_v2.pipeline.layout import group_lines, normalize

    seen: set[int] = set()
    for page, result in pages:
        lines = group_lines(normalize(result.words, page.page, page.pixel_size))
        end = ra._table_end(lines, ra.HEADER_MAX_Y)
        for line in lines:
            for word in line:
                if word.x0 < ra.COL_NO_MAX_X and ra.HEADER_MAX_Y < word.cy < end:
                    if found := re.match(r"(\d{1,3})(?!\d)", word.text.strip()):
                        seen.add(int(found.group(1)))
    return seen


def _history_end_label(ex) -> str:
    """11-26: 주소 이력 끝을 무엇으로 확인했는지 (근거 종류와 쪽 번호만, 값 없음)."""
    kind, page = getattr(ex, "history_end", "NONE"), getattr(ex, "history_end_page", None)
    if kind == "BLANK_MARKER":
        return f"이하 여백 ({page}쪽)"
    if kind == "NEXT_SECTION":
        return f"다음 구역(병역사항) 시작 ({page}쪽)"
    return "확인되지 않음" if ex.history else "이력 없음"


def _from_resident(ex, pages, ra, v2types, final_type: DocType | None = None) -> OcrResult:
    """engine_v2 초본 추출 결과 → 데모 OcrResult (필드 이름은 데모 규칙이 쓰는 그대로).

    final_type: 호출자가 결과에 매길 최종 서류 종류(본문 분류). 11-27: 추출기 머리 제목 판별이 초본을 못 찾아도
    최종 종류가 초본이면 초본 검증(주소 날짜·이력 누락 사유·SCAN_ABSTRACT_REVIEW_GUARD)을 똑같이 적용한다.
    전에는 추출기 판별만 보아, 본문 분류로 초본이 된 스캔이 안전장치 없이 전입일·현주소시도를 내보냈다.
    """
    # 둘 중 하나라도 초본이면 초본 검증을 적용한다 (검증을 빼는 쪽으로는 바꾸지 않는다).
    abstract = ex.detected_type == v2types.RESIDENT_ABSTRACT or final_type == DocType.RESIDENT_ABSTRACT
    detected = DocType.RESIDENT_ABSTRACT if abstract else DocType.RESIDENT_CERTIFICATE
    f = ex.fields
    fields: dict[str, str] = {}
    bboxes: dict[str, BBox] = {}

    page_data = {"markers": ex.page_markers, "confidence": ex.page_marker_confidence}
    if getattr(ex, "blank_pages", 0):
        page_data["blank_pages"] = ex.blank_pages  # 쪽 수 확인에서 뺀 내용 없는 쪽
    if getattr(ex, "sheet_markers", None):
        page_data["sheets"] = ex.sheet_markers  # 한 장에 여러 쪽(모아찍기)의 쪽표기
    shared = _shared_image_groups(pages, getattr(ex, "marker_pages", None))
    if shared is not None:
        page_data["image_groups"] = shared  # 같은 주 그림(xref)을 읽은 쪽 묶음 (D10)
    fields["쪽표기자료"] = json.dumps(page_data)
    from engine_v2.extractors.address_dates import assess
    if abstract:
        fields["주소날짜검증자료"] = json.dumps(assess(pages, type_confidence=ex.type_confidence), ensure_ascii=False)

    for v2key, label in (
        ("issue_date", "발급일"), ("name", "성명"), ("birth_date", "생년월일"),
        ("applicant_name", "초본신청인성명"),
        ("applicant_birth_date", "초본신청인생년월일"),
        ("address_history_count", "주소이력건수"),
    ):
        if v2key in f:
            v = f[v2key].value
            fields[label] = v.isoformat() if isinstance(v, date) else str(v)
            if (b := _demo_bbox(f[v2key].bbox)) is not None:
                bboxes[label] = b

    # 데모 배점의 '도 거주기간'은 "전북 최종 전입일 → 공고일 역산"이다.
    # engine_v2는 주소이력 전체에서 전북 연속 거주가 시작된 건을 찾는다
    # (전라북도 → 전북특별자치도 명칭 변경, 세대주 변경 등으로 끊기지 않음).
    start = ra.trailing_residence_start(ex.history, "전북")
    if start:
        fields["전입일"] = start.isoformat()
        entry = next((e for e in ex.history if e.effective == start), None)
        if entry and (b := _entry_bbox(entry, pages)):
            bboxes["전입일"] = b

    if ex.history:
        fields["현주소시도"] = ra.resolved_sido(ex.history, len(ex.history) - 1) or "판별불가"
        fields["주소이력건수"] = str(len(ex.history))
        if len(ex.history) == 1:
            fields["과거주소미포함의심"] = "true"
        # 이력이 2건 이상이면 '주소변동내역 포함'으로 본다. 1건 이하는 단정하지 않는다
        # (미포함으로 단정하면 doc_check가 부적합을 낸다 — 오독일 때 신청자가 억울해진다).
        if len(ex.history) >= 2:
            fields["주소변동내역"] = "포함"

    # 주소 이력 누락 의심 (공통, 두 사업 같은 코드): 아래 사유가 하나라도 있으면 전입일(과 사유에 따라
    # 주소이력건수·현주소시도·주소변동내역)을 '불확실'로 두고 doc_check가 ADDRESS_HISTORY_INCOMPLETE(확인필요)를 낸다.
    # 신뢰도는 낮추지 않는다: 발급일 등 확정 FAIL을 보류로 바꾸지 않기 위해서다.
    #   NUMBER_GAP        (11-18) 순번이 1..N으로 빈틈·중복 없이 이어지지 않음 (메모 줄 순번 포함)
    #   NUMBER_UNREADABLE (11-18) 번호 없는 이력이 있어 연속성 확인 불가
    #   EMPTY_PAGE        (11-18) 표 머리글은 찾았는데 이력 줄을 0건 읽은 쪽
    #   NUMBER_START      (11-26) 읽은 이력 번호가 1로 시작하지 않음 (첫 쪽 표를 못 찾아 앞 이력이 빠짐)
    #   UNREAD_ROWS       (11-26) 순번 칸에 마지막 건보다 큰 번호가 보임 (표를 못 찾은 쪽의 이력이 빠짐)
    #   TABLE_NOT_FOUND·ROWS_UNREADABLE (11-21) 후속 쪽 표 미확인·후속 이력 판독 불완전 (추출기 history_table_issues)
    #   END_UNCONFIRMED   (11-26) 스캔에서 마지막 건 아래 끝 표시(이하 여백·다음 구역)를 확인하지 못함
    #   SCAN_UNVERIFIED   (11-26) 스캔 초본 완결성 자동 확인 제한 (SCAN_ABSTRACT_REVIEW_GUARD)
    if abstract:
        # OCR로 읽은 쪽이 있으면 스캔(사진)본이다. 모든 쪽이 글자층일 때만 글자층 판독이다 (_pages_engine과 같은 기준).
        scanned = any(page.source.value != "text_layer" for page, _ in pages)
        numbers = sorted(entry.no for entry in ex.history if entry.no is not None)
        uncertain = [code for code, hit in (
            ("NUMBER_GAP", getattr(ex, "history_numbers", "NA") == "GAP"),
            ("NUMBER_UNREADABLE", getattr(ex, "history_numbers", "NA") == "UNREADABLE"),
            ("EMPTY_PAGE", getattr(ex, "history_empty_page", False)),
            ("NUMBER_START", bool(numbers) and numbers[0] != 1),
            ("UNREAD_ROWS", bool(numbers) and any(seen > numbers[-1]
                                                  for seen in _number_column_ordinals(pages, ra))),
            # 11-26: 마지막 건 바로 아래 단독 '이하 여백'으로 이력 끝을 확인하지 못함 (끝 이력 누락·하단 잘림 가능).
            ("END_UNCONFIRMED", scanned and bool(ex.history)
             and getattr(ex, "history_end", "NONE") not in ("BLANK_MARKER", "NEXT_SECTION")),
            ("SCAN_UNVERIFIED", scanned and SCAN_ABSTRACT_REVIEW_GUARD),
        ) if hit]
        # 담당자 감사·진단용 끝 근거: 근거 종류와 쪽 번호만 남긴다 (값 없음).
        fields["주소이력끝근거"] = _history_end_label(ex)
        table_issues = getattr(ex, "history_table_issues", [])
        uncertain.extend(table_issues)
        if uncertain:
            fields["주소이력상태"] = "불확실"
            fields["주소이력불확실사유"] = ",".join(uncertain)
            # 11-26 사유(END_UNCONFIRMED·SCAN_UNVERIFIED)만 있으면 읽은 줄 수(주소이력건수)는 그대로 둔다:
            # 자동 판정에 쓰이는 전입일·현주소시도만 '불확실'로 두고, 1건 초본 안내(PAST_ADDRESS_OMISSION_SUSPECTED)는 유지한다.
            count_uncertain = bool(set(uncertain) - {"END_UNCONFIRMED", "SCAN_UNVERIFIED"})
            for label in ("전입일", "주소이력건수"):
                if label == "주소이력건수" and not count_uncertain:
                    continue
                if label in fields:
                    fields[label] = "불확실"
                bboxes.pop(label, None)
            if table_issues or {"END_UNCONFIRMED", "SCAN_UNVERIFIED"} & set(uncertain):
                for label in ("현주소시도", "주소변동내역"):
                    if label in fields:
                        fields[label] = "불확실"

    passed = sum(v.passed for v in ex.validations)
    fields["판독검증"] = f"{passed}/{len(ex.validations)} 통과"
    failed = [v.name for v in ex.validations if not v.passed]
    if failed:
        fields["판독검증실패"] = ", ".join(failed)

    # 신뢰도 = 핵심 필드 신뢰도의 최솟값. 필드 신뢰도는 OCR 점수가 아니라 검증 통과율이다.
    key = [f[k].confidence for k in ("issue_date", "name", "birth_date") if k in f]
    confidence = min([ex.type_confidence, *key]) if "issue_date" in f else 0.5
    if any(not validation.passed and validation.name.startswith(("history", "occurred"))
           and validation.name != "history_tables_readable"
           for validation in ex.validations):
        confidence = min(confidence, .4)
        fields["판독경고"] = "주소 이력의 순번 또는 날짜를 완전히 확인하지 못했습니다."

    return _business_resident_marks(OcrResult(
        detected_doc_type=detected,
        confidence=round(confidence, 2),
        image_quality=_quality([p for p, _ in pages]),
        issue_date=f["issue_date"].value if "issue_date" in f else None,
        fields=fields,
        bboxes=bboxes,
        page_count=len(pages),
        tier=NAME,
        classification_confidence=ex.type_confidence,
        classification_evidence=ex.classification_evidence,
    ), "\n".join(r.text for _, r in pages))


def _business_resident_marks(result: OcrResult, text: str) -> OcrResult:
    """사업별 초본 표시 (공통 _from_resident 밖). 두배적금: 인쇄된 '열람용' 표시를 담당자 확인으로 남긴다 (11-18 S3)."""
    from .pdftext import mark_viewing_copy
    return mark_viewing_copy(result, text)


def ensure_nhis_required_fields(result: OcrResult) -> OcrResult:
    """Keep supported NHIS forms complete after final header-value safety."""
    if (result.tier == "fixture" or not (
            result.detected_doc_type == DocType.NHIS_ACQUISITION_LOSS or
            (result.detected_doc_type in {DocType.NHIS_QUALIFICATION, DocType.NHIS_PAYMENT} and
             "양식판독상태" in result.fields))):
        return result
    from engine_v2.pipeline.field_safety import remove_header_only_fields

    for key in remove_header_only_fields(result.fields):
        result.bboxes.pop(key, None)
    missing = []
    required = ("성명", "생년월일", "발급일")
    if result.detected_doc_type == DocType.NHIS_PAYMENT:
        required += ("사업장명칭", "납부자번호", "문서확인번호", "조회기간", "납부총액", "용도구분")
    for label in required:
        value = str(result.fields.get(label) or "").strip()
        valid = label in result.fields if label == "사업장명칭" else bool(value)
        if label in {"생년월일", "발급일"}:
            try:
                date.fromisoformat(value[:10])
            except ValueError:
                valid = False
        if not valid:
            missing.append(label)
    if not missing:
        return result
    failed = [value.strip() for value in result.fields.get("판독검증실패", "").split(",") if value.strip()]
    added = [f"{label}_required" for label in missing if f"{label}_required" not in failed]
    counts = re.fullmatch(r"(\d+)/(\d+) 통과", result.fields.get("판독검증", ""))
    passed, total = (int(counts[1]), int(counts[2])) if counts else (0, 0)
    result.fields["판독검증"] = f"{passed}/{total + len(added)} 통과"
    result.fields["판독검증실패"] = ", ".join([*failed, *added])
    result.confidence = min(result.confidence, 0.4)
    if "양식판독상태" in result.fields:
        result.fields["양식판독상태"] = "불완전"
    if "발급일" in missing:
        result.issue_date = None
    return result


def ensure_business_required_fields(result: OcrResult) -> OcrResult:
    """Retain the proof completeness gate after shared field safety filtering."""
    if result.detected_doc_type != DocType.BIZ_REG_PROOF or result.tier == "fixture":
        return result
    from engine_v2.extractors.business_registration import (
        REQUIRED_FIELDS, BUSINESS_NUMBER_RE, representative_name, LABEL_VALUES,
    )
    from engine_v2.extractors.job_common import brn_is_valid
    from engine_v2.pipeline.field_safety import remove_header_only_fields

    for key in remove_header_only_fields(result.fields):
        result.bboxes.pop(key, None)
    number = result.fields.get("사업자등록번호", "")
    valid_number = bool(BUSINESS_NUMBER_RE.fullmatch(number)) and brn_is_valid(number)
    code = int(number[4:6]) if valid_number else 0
    if not valid_number or not (1 <= code <= 79 or 90 <= code <= 99) or "법인" in result.fields.get("과세유형", ""):
        result.fields.pop("생년월일", None)
        result.bboxes.pop("생년월일", None)
    missing = []
    for key in REQUIRED_FIELDS:
        value = result.fields.get(key, "")
        valid = bool(value.strip()) and re.sub(r"\s+", "", value) not in LABEL_VALUES
        if key in {"생년월일", "개업일", "사업자등록일", "발급일"}:
            try:
                date.fromisoformat(value)
            except ValueError:
                valid = False
        elif key == "성명":
            valid = representative_name(value) is not None
        elif key == "사업자등록번호":
            valid = valid_number
        elif key in {"업태", "종목"}:
            try:
                items = json.loads(value)
                valid = isinstance(items, list) and bool(items) and all(
                    isinstance(item, str) and item.strip() and re.sub(r"\s+", "", item) not in LABEL_VALUES
                    for item in items)
            except (ValueError, TypeError):
                valid = False
        elif key == "공동사업자유무":
            valid = value in {"있음", "없음"}
        if not valid:
            missing.append(key)
    if not missing:
        return result
    failed = [value.strip() for value in result.fields.get("판독검증실패", "").split(",") if value.strip()]
    added = [f"{key}_required" for key in missing if f"{key}_required" not in failed]
    counts = re.fullmatch(r"(\d+)/(\d+) 통과", result.fields.get("판독검증", ""))
    passed, total = (int(counts[1]), int(counts[2])) if counts else (0, 0)
    result.fields["판독검증"] = f"{passed}/{total + len(added)} 통과"
    result.fields["판독검증실패"] = ", ".join([*failed, *added])
    result.fields["양식판독상태"] = "불완전"
    result.confidence = min(result.confidence, .4)
    if "발급일" in missing:
        result.issue_date = None
    return result


def _identity_source_confidence(ex, pages, *, include_issue=False) -> float:
    """Preserve observed confidence inside the existing identity value boxes.

    Extracted-field confidence primarily reflects structural checks. Fresh
    work eligibility also needs reliable applicant identity tokens. Compare
    geometry only: redacted/erased resident-number words retain their bounds.
    Unrelated low-confidence seals and notices do not contribute.
    """
    keys = [key for key in ("성명",) if key in ex.fields]
    birth = next((key for key in ("생년월일", "생년월일표기") if key in ex.fields), None)
    if birth:
        keys.append(birth)
    if include_issue and "발급일" in ex.fields:
        keys.append("발급일")
    confidence = 1.0
    for key in keys:
        box = ex.fields[key].bbox
        if box is None:
            confidence = min(confidence, .4)
            continue
        source = []
        for page, result in pages:
            if page.page != box.page:
                continue
            for word in result.words:
                x0,y0,x1,y1 = word.bbox_px
                cx,cy = page.px_to_pt((x0+x1)/2,(y0+y1)/2)
                # Field boxes are rounded to 0.1pt by the shared extractor.
                if box.x0-.1 <= cx <= box.x1+.1 and box.y0-.1 <= cy <= box.y1+.1:
                    source.append(word.confidence)
        confidence = min(confidence,min(source,default=.4))
    return confidence


def _from_business_proof(ex, pages, classification_evidence="") -> OcrResult:
    fields = {}
    bboxes = {}
    for key, extracted in ex.fields.items():
        value = extracted.value
        if isinstance(value, date):
            fields[key] = value.isoformat()
        elif isinstance(value, list):
            fields[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        elif isinstance(value, bool):
            fields[key] = "있음" if value else "없음"
        else:
            fields[key] = str(value)
        if (box := _demo_bbox(extracted.bbox)) is not None:
            bboxes[key] = box
    fields["판독검증"] = f"{sum(check.passed for check in ex.validations)}/{len(ex.validations)} 통과"
    failed = [check.name for check in ex.validations if not check.passed]
    if failed:
        fields["판독검증실패"] = ", ".join(failed)
    if ex.warnings:
        fields["판독경고"] = " ".join(ex.warnings)
    fields["양식판독상태"] = "완전" if ex.structure_complete else "불완전"
    issue = ex.fields.get("발급일")
    source_confidence = _identity_source_confidence(ex,pages,include_issue=True)
    fields["근로근거신뢰도"] = str(source_confidence)
    confidence = min(min((value.confidence for value in ex.fields.values()), default=.4), source_confidence)
    return ensure_business_required_fields(OcrResult(
        detected_doc_type=DocType.BIZ_REG_PROOF if ex.detected_type.value == "biz_reg_proof" else None,
        confidence=min(confidence, ex.type_confidence, 1 if ex.structure_complete else .4),
        image_quality=_quality([page for page, _ in pages]),
        issue_date=issue.value if issue else None, fields=fields, bboxes=bboxes,
        page_count=len(pages), tier=NAME, engine=_pages_engine(pages),
        classification_evidence=classification_evidence,
        classification_confidence=ex.type_confidence,
    ))


def _from_nhis(ex, pages, v2types, classification_evidence: str = "",
               detected_override: DocType | None = None, *, payment_page_count: int | None = None) -> OcrResult:
    """engine_v2 건강보험 판독 결과를 신청자·담당자 화면 계약으로 옮긴다."""
    fields: dict[str, str] = {}
    bboxes: dict[str, BBox] = {}
    for key, value in ex.fields.items():
        rendered = value.value.isoformat() if isinstance(value.value, date) else str(value.value)
        fields[key] = rendered
        if (box := _demo_bbox(value.bbox)) is not None:
            bboxes[key] = box
    validations = ex.validations
    fields["판독검증"] = f"{sum(v.passed for v in validations)}/{len(validations)} 통과"
    failed = [v.name for v in validations if not v.passed]
    if failed:
        fields["판독검증실패"] = ", ".join(failed)
    if ex.warnings:
        fields["판독경고"] = " ".join(ex.warnings)
    work_form = ex.detected_type.value in {"nhis_acquisition_loss", "daily_work_record"}
    source_confidence = _identity_source_confidence(ex,pages,include_issue=work_form)
    confidence = min((field.confidence for field in ex.fields.values()), default=0.5)
    if work_form:
        fields["근로근거신뢰도"] = str(source_confidence)
    if not pages or not all(result.engine == "jbai" for _,result in pages):
        confidence = min(confidence, source_confidence)
    structure_complete = getattr(ex, "structure_complete", None)
    if structure_complete is not None:
        fields["양식판독상태"] = "완전" if structure_complete else "불완전"
        if not structure_complete:
            confidence = min(confidence, 0.4)
    detected_map = {
        v2types.NHIS_PAYMENT: DocType.NHIS_PAYMENT,
        v2types.NHIS_QUALIFICATION: DocType.NHIS_QUALIFICATION,
        v2types.NHIS_ACQUISITION_LOSS: DocType.NHIS_ACQUISITION_LOSS,
    }
    detected = detected_override or detected_map.get(ex.detected_type)
    if detected == DocType.NHIS_PAYMENT:
        from engine_v2.extractors.nhis_payment import has_failed_payment_validation
        from engine_v2.extractors.payment_period import FIELD, collect

        fields[FIELD] = json.dumps(collect(pages, ex), ensure_ascii=False, separators=(",", ":"))
        from engine_v2.extractors import payment_paging, payment_completeness

        fields[payment_paging.FIELD] = json.dumps(
            payment_paging.collect(pages, uploaded_page_count=payment_page_count),
            ensure_ascii=False, separators=(",", ":"))
        fields[payment_completeness.FIELD] = json.dumps(
            payment_completeness.collect(pages, ex), ensure_ascii=False, separators=(",", ":"))

        if has_failed_payment_validation(fields):
            confidence = min(confidence, .4)
        if fields.get("구성머리글상태") == "불완전":
            confidence = min(confidence, .4)  # 11-19 (T3): partly read 보수외소득월액 sub-header
    if (detected == DocType.NHIS_ACQUISITION_LOSS and
            any(v.name == "document_confirmation_number_consistent" and not v.passed
                for v in validations)):
        # Keep the confirmation value internal; only the acquisition-loss
        # extractor's boolean cross-page comparison affects review confidence.
        confidence = min(confidence, 0.4)
    if detected == DocType.NHIS_ACQUISITION_LOSS and "변동내역" in fields:
        covered = next((validation.passed for validation in validations
                        if validation.name == "recent_five_years_covered"), None)
        history_text = fields.get("자격이력자료")
        if type(covered) is bool and history_text:
            try:
                history = json.loads(history_text)
                # Preserve the extractor's tri-state; legacy readers only
                # supplied a boolean validation and still need this fallback.
                history.setdefault("recent_five_years_covered", covered)
                fields["자격이력자료"] = json.dumps(history, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                pass
    issue = ex.fields.get("발급일")
    issue_date = None
    if issue:
        try:
            issue_date = date.fromisoformat(str(issue.value)[:10])
        except ValueError:
            pass
    return ensure_nhis_required_fields(OcrResult(
        detected_doc_type=detected,
        confidence=round(min(confidence, ex.type_confidence), 2),
        image_quality=_quality([page for page, _ in pages]),
        issue_date=issue_date,
        fields=fields,
        bboxes=bboxes,
        page_count=len(pages),
        tier=NAME,
        classification_evidence=classification_evidence,
        classification_confidence=0.95 if detected else 0.0,
    ))


def _from_insurance4(ex, pages, classification_evidence: str = "") -> OcrResult:
    """4대보험 결과를 데모 필드 계약으로 변환한다."""
    from engine_v2.extractors import insurance_workplace as workplace, nhis_common

    fields: dict[str, str] = {}
    bboxes: dict[str, BBox] = {}
    for key in ("성명", "생년월일", "발급일", "문서확인번호", "발급번호",
                "가입내역", "보험별가입여부", "보험별가입자종별", "근로관련가입여부",
                "근로관련최초취득일", "근로관련최근취득일", "사업장명칭목록", "추가첨부쪽",
                workplace.COUNT_FIELD, workplace.STATE_FIELD, workplace.REASON_FIELD, workplace.PROOF_FIELD):
        extracted = ex.fields.get(key)
        if extracted is None:
            continue
        value = extracted.value
        fields[key] = value.isoformat() if isinstance(value, date) else str(value)
        if (box := _demo_bbox(extracted.bbox)) is not None:
            bboxes[key] = box
    for row in ex.rows:
        prefix = row.insurance_type
        row_values = {
            f"{prefix} 가입자종별": row.subscriber_category,
            f"{prefix} 사업장관리번호": row.management_number,
            f"{prefix} 사업장명칭": row.workplace_name,
            f"{prefix} 자격취득일": row.acquired.isoformat() if row.acquired else "",
            f"{prefix} 신고접수일": row.received.isoformat() if row.received else "",
            f"{prefix} 상태": row.status,
        }
        row_box = _demo_bbox(row.bbox)
        for key, value in row_values.items():
            fields[key] = value
            box = row_box
            if key == f"{prefix} 사업장명칭" and row.workplace_words:
                box = _demo_bbox(nhis_common.bbox(row.workplace_words, {page.page: page for page, _ in pages}))
            if box is not None:
                bboxes[key] = box
    validations = list(ex.validations)
    structure_complete = getattr(ex, "structure_complete", None)
    if getattr(ex, "form_kind", None) == "portal":
        from engine_v2.pipeline.field_safety import remove_header_only_fields
        from engine_v2.extractors.nhis_common import Validation

        for key in remove_header_only_fields(fields):
            bboxes.pop(key, None)
        missing = [label for label in ("성명", "생년월일", "발급일") if not fields.get(label)]
        validations.extend(Validation(f"{label}_required", False) for label in missing)
        if missing:
            structure_complete = False
    if structure_complete is not None:
        fields["양식판독상태"] = "완전" if structure_complete else "불완전"
    fields["판독검증"] = f"{sum(item.passed for item in validations)}/{len(validations)} 통과"
    failed = [item.name for item in validations if not item.passed]
    if failed:
        fields["판독검증실패"] = ", ".join(failed)
    if ex.warnings:
        fields["판독경고"] = " ".join(ex.warnings)
    issue = ex.fields.get("발급일")
    issue_date = date.fromisoformat(str(issue.value)) if issue else None
    source_confidence = _identity_source_confidence(ex,pages,include_issue=True)
    fields["근로근거신뢰도"] = str(source_confidence)
    confidence = min(min((field.confidence for field in ex.fields.values()), default=0.5), source_confidence)
    if structure_complete is False:
        confidence = min(confidence, 0.4)
    detected = DocType.INSURANCE_4 if ex.detected_type.value == "insurance_4" else None
    return OcrResult(
        detected_doc_type=detected,
        confidence=round(min(confidence, ex.type_confidence), 2),
        image_quality=_quality([page for page, _ in pages]),
        issue_date=issue_date,
        fields=fields,
        bboxes=bboxes,
        page_count=len(pages),
        tier=NAME,
        classification_evidence=classification_evidence,
        classification_confidence=0.97 if detected else 0.0,
    )


def _from_supported_form(extractor, pages, v2types, evidence, detected):
    from engine_v2.extractors.attached_pages import extract_form
    ex, scoped = extract_form(extractor.extract, pages)
    if detected == DocType.NHIS_PAYMENT:
        result = _from_nhis(ex, scoped, v2types, evidence, detected, payment_page_count=len(pages))
    else:
        result = (_from_insurance4(ex, scoped, evidence) if detected == DocType.INSURANCE_4
                  else _from_nhis(ex, scoped, v2types, evidence, detected))
    result.page_count = len(pages)
    result.engine = _pages_engine(scoped)
    from .pdftext import mark_viewing_copy
    return mark_viewing_copy(result, "\n".join(r.text for _, r in pages))


#: 취업지원패키지 추가서류 → (engine_v2 추출기 모듈, engine_v2 서류 종류 값)
_JOB_DOCS: dict[DocType, tuple[str, str]] = {
    DocType.PAYMENT_RECEIPT: ("receipt", "receipt"),
    DocType.EXAM_CONFIRMATION: ("exam_docs", "exam_admission"),
    DocType.EXAM_TRANSCRIPT: ("exam_docs", "exam_score"),
    DocType.INTERVIEW_CONFIRMATION: ("interview_confirmation", "interview_confirm"),
}
#: OCR에서 이 필드가 하나라도 없으면 신뢰도 0.5; 글자층의 확정된 부재는 0.9로 둔다.
_JOB_REQUIRED = {
    "receipt": ("결제금액", "결제일"),
    "exam_admission": ("성명", "응시일"),
    "exam_score": ("성명", "응시일"),
    "interview_confirm": ("성명", "회사명", "면접일"),
}
#: 데모 발급일(issue_date)로 넘길 날짜: 서류에 적힌 발급일이 없으면 그 서류의 기준 날짜
_JOB_ISSUE_FIELDS = {
    "receipt": ("발급일", "결제일"),
    "exam_admission": ("발급일", "응시일"),
    "exam_score": ("발급일", "응시일"),
    "interview_confirm": ("발급일", "확인일", "면접일"),
}


def _job_extractor(detected: DocType):
    """패키지 서류 추출기도 지연 import 한다."""
    import importlib

    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    return importlib.import_module(f"engine_v2.extractors.{_JOB_DOCS[detected][0]}").extract


def _pages_engine(pages) -> str:
    """모든 쪽이 글자층일 때만 pdftext, 그 밖에는 실제 OCR 결과의 엔진."""
    return next((result.engine for page, result in pages
                 if page.source.value != "text_layer"), "pdftext")


def _from_job_doc(ex, pages, classification_evidence: str = "",
                  detected_override: DocType | None = None) -> OcrResult:
    """engine_v2 패키지 서류 판독 결과를 데모 필드 계약으로 옮긴다 (필드 이름은 데모 규칙이 쓰는 그대로)."""
    fields: dict[str, str] = {}
    bboxes: dict[str, BBox] = {}
    for key, value in ex.fields.items():
        fields[key] = value.value.isoformat() if isinstance(value.value, date) else str(value.value)
        if (box := _demo_bbox(value.bbox)) is not None:
            bboxes[key] = box
    validations = ex.validations
    fields["판독검증"] = f"{sum(v.passed for v in validations)}/{len(validations)} 통과"
    failed = [v.name for v in validations if not v.passed]
    if failed:
        fields["판독검증실패"] = ", ".join(failed)
    if ex.warnings:
        fields["판독경고"] = " ".join(ex.warnings)
    v2type = ex.detected_type.value
    required = _JOB_REQUIRED.get(v2type, ())
    text_only = all(page.source.value == "text_layer" for page, _ in pages)
    if required and all(name in ex.fields for name in required):
        confidence = min(ex.fields[name].confidence for name in required)
    else:
        # 글자층의 빈 항목은 확정된 부재이며, OCR의 빈 항목은 미판독일 수 있다.
        confidence = 0.9 if text_only else 0.5
    issue = next((ex.fields[name] for name in _JOB_ISSUE_FIELDS.get(v2type, ()) if name in ex.fields), None)
    if v2type == "interview_confirm" and "발급일" in ex.fields:
        confidence = min(confidence, ex.fields["발급일"].confidence)
    detected = detected_override or next((demo for demo, (_, value) in _JOB_DOCS.items() if value == v2type), None)
    return OcrResult(
        detected_doc_type=detected,
        confidence=round(min(confidence, ex.type_confidence), 2),
        image_quality=1.0 if text_only else _quality([page for page, _ in pages]),
        issue_date=issue.value if issue is not None and isinstance(issue.value, date) else None,
        fields=fields,
        bboxes=bboxes,
        page_count=len(pages),
        tier=NAME,
        engine=_pages_engine(pages),
        classification_evidence=classification_evidence,
        classification_confidence=0.95 if detected else 0.0,
    )


def _generic(pages, path: Path) -> OcrResult | None:
    """초본·등본이 아닌 서류: OCR 텍스트에 Tier2 정규식을 적용한다.

    서류 종류를 알아보지 못했으면 None — 이 계층이 확신 없는 결과로 Tier2의 화면 캡처·화질
    판정을 덮어쓰지 않게 한다.
    """
    from . import pdftext

    text = "\n".join(r.text for _, r in pages)
    if pdftext.classify(text) is None:
        return None
    result = pdftext.read_page_text(text, None, 0)
    result.confidence = min(result.confidence, GENERIC_CONFIDENCE_CAP)
    result.image_quality = _quality([p for p, _ in pages])
    result.page_count = len(pages)
    result.tier = NAME
    if path.suffix.lower() != ".pdf":
        _merge_image_heuristics(result, path)
    return result


def _merge_image_heuristics(result: OcrResult, path: Path) -> None:
    """사진 업로드는 Tier2의 화면 캡처·화질 휴리스틱을 그대로 가져온다."""
    from . import pdftext

    img = pdftext._read_image(path)
    if img is not None and not img.is_encrypted:
        result.is_screen_capture = img.is_screen_capture
        result.image_quality = min(result.image_quality, img.image_quality)


def _text_layer_pages(path: Path) -> list:
    """모든 쪽을 글자층 단어로만 만든다(OCR 없음). engine._load_pages의 글자층 쪽과 같은 300dpi 좌표계.

    raster_content_pages가 빈 PDF(모든 쪽에 보이는 글자가 있고 그림·숨은 글자가 없음)에만 쓴다. 50자 미만의 짧은 쪽도
    글자층 그대로 읽는다 — 짧은 마지막 쪽 때문에 OCR이 필요해지거나, OCR이 없는 서버에서 쪽 확인을 건너뛰지 않게.
    """
    import pymupdf
    from engine_v2.pipeline.ocr import OcrResult as V2OcrResult, OcrWord
    from engine_v2.pipeline.preprocess import PageImage, PageSource

    scale = 300 / 72
    pages = []
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            image = PageImage(index, PageSource.TEXT_LAYER, (page.rect.width, page.rect.height),
                              pixel_size=(round(page.rect.width * scale), round(page.rect.height * scale)),
                              text=mask_rrn(page.get_text("text")).strip())
            words = [OcrWord(text, 1.0, (x0 * scale, y0 * scale, x1 * scale, y1 * scale))
                     for x0, y0, x1, y1, text, *_ in page.get_text("words", sort=True) if text.strip()]
            pages.append((image, V2OcrResult("text_layer", words)))
    return pages


def _with_text_page_markers(classified: OcrResult, path: Path) -> OcrResult | None:
    """11-27: 그림 없는 글자층 초본. 판독은 그대로 Tier2(PdfText, 첫 쪽 글자층) 결과를 쓰되, 모든 쪽 글자층의
    쪽표기(n/N)를 _from_resident와 같은 방식으로 붙여 doc_check _check_resident_pages가 빠진 쪽·중복 쪽·다른 쪽을 보게 한다.

    PdfText는 첫 쪽만 읽으므로 2/3쪽이 빠진 초본도 첫 쪽만으로 적합이 됐다. 쪽표기를 하나도 못 찾으면(쪽표기 없는 서식)
    완결성 근거가 없을 뿐 반대 근거도 없으므로 지금까지처럼 None을 돌려 Tier2가 그대로 판독한다. OCR은 쓰지 않는다.
    """
    ra, *_, v2types, _, _, _ = _import_v2()
    pages = _text_layer_pages(path)
    page_data = json.loads(_from_resident(ra.extract(pages), pages, ra, v2types,
                                         DocType.RESIDENT_ABSTRACT).fields["쪽표기자료"])
    if not any(page_data.get("markers") or ()) and not page_data.get("sheets"):
        return None  # 쪽표기를 하나도 읽지 못함([None]뿐인 경우 포함): 근거 없음 → 지금까지처럼 Tier2
    classified.fields["쪽표기자료"] = json.dumps(page_data)
    classified.engine = "pdftext"  # 필드·쪽표기 모두 글자층 판독이다 (LocalOcr.read가 OCR 엔진 이름을 덮어쓰지 않게).
    return classified


def workload_message(code: str) -> str:
    """11-27 자원 보호: 작업량 한도를 넘어 자동 판독하지 않은 문서에 남기는 담당자용 문구 (한도 값은 limits에서)."""
    from engine_v2.pipeline import limits

    reason = {
        "PAGES": f"OCR로 읽어야 할 쪽이 {limits.MAX_OCR_PAGES}쪽을 넘어 자동으로 읽지 않았습니다.",
        "PAGE_PIXELS": f"쪽 그림이 {limits.MAX_PAGE_PIXELS // 10_000:,}만 화소를 넘어 자동으로 읽지 않았습니다.",
        "DOCUMENT_PIXELS": (f"문서의 쪽 그림 합계가 {limits.MAX_DOCUMENT_PIXELS / 100_000_000:g}억 화소를 넘어 "
                            "자동으로 읽지 않았습니다."),
        "SECONDS": f"자동 판독이 {limits.MAX_OCR_SECONDS}초 안에 끝나지 않아 중단했습니다.",
    }.get(code, "자동 판독 작업량 한도를 넘어 자동으로 읽지 않았습니다.")
    return f"{reason} 일부만 읽은 결과는 쓰지 않으며 담당자가 원본 전체를 확인합니다."


def _workload_review_result(exc, path: Path) -> OcrResult:
    """11-27: 작업량 한도(engine_v2.pipeline.limits)를 넘은 문서의 담당자 확인 결과.

    자동 판독 실패(read_document의 '판독실패' 결과)와 같은 모양이라 뒤의 판정이 그대로 담당자 확인으로 보낸다:
    서류 종류 미판별·신뢰도 0 → 자동 적합도, 읽지 않은 내용에 근거한 부적합도 없다. LocalOcr.read가 None 대신 이 결과를
    돌려주므로 다음 계층(첫 쪽 글자층만 읽는 Tier2)으로 넘어가지 않는다.
    """
    page_count = 1
    if path.suffix.lower() == ".pdf":
        try:
            import pymupdf

            with pymupdf.open(path) as document:
                page_count = max(1, document.page_count)
        except Exception:  # noqa: BLE001 - 쪽 수는 담당자 화면 참고값이다
            pass
    return OcrResult(
        detected_doc_type=None,
        confidence=0.0,
        image_quality=1.0,  # 판독을 하지 않았을 뿐 화질 측정이 아니다 (원본 해상도 판정은 file_evidence가 따로 한다).
        fields={"판독실패": workload_message(exc.code)},
        page_count=page_count,
        tier="none",
        engine="none",
        fallback_reason=f"RESOURCE_LIMIT:{exc.code}",
    )


def _abstract_review_result(classified: OcrResult, reason: str, message: str = "") -> OcrResult:
    """11-27: 글자층 초본을 끝까지 읽지 못했을 때의 담당자 확인 결과. 첫 쪽 글자층(Tier2) 판독으로 되돌아가지 않는다."""
    return OcrResult(
        detected_doc_type=DocType.RESIDENT_ABSTRACT,
        confidence=0.0,
        image_quality=1.0,
        fields={"판독실패": message or "초본 전체를 자동으로 읽지 못해 담당자가 원본 전체를 확인합니다."},
        page_count=classified.page_count,
        tier=NAME,
        engine="none",
        classification_confidence=0.0,
        classification_evidence=classified.classification_evidence,
        fallback_reason=f"RENDER_RETRY_FAILED:{reason}",
    )


def _tier2_can_read(path: Path) -> bool:
    """Tier2와 **같은 기준**으로 경계를 긋는다: 암호이거나 첫 쪽에 글자가 하나라도 있으면 Tier2 몫."""
    import fitz

    try:
        with fitz.open(path) as doc:
            if doc.needs_pass or doc.page_count == 0:
                return True
            return bool("".join(mask_rrn(doc[0].get_text()).split()))
    except Exception:  # noqa: BLE001 - 못 여는 파일은 Tier2가 '열 수 없음'으로 처리
        return True


class LocalOcr:
    name = NAME

    def read(self, file_path: str, expected: DocType | None) -> OcrResult | None:
        del expected  # 종류는 슬롯 기대값이 아니라 본문 OCR 결과로 먼저 고른다.
        engine, reason = engine_decision()
        if reason:
            _logger.warning("%s", reason)
        from engine_v2.pipeline.limits import OcrWorkloadExceeded

        try:
            result = self._read(file_path, engine)
        except OcrWorkloadExceeded as exc:
            # 11-27: 한도를 넘은 문서는 읽지 않는다. 예외를 밖으로 내면 read_document가 다음 계층(첫 쪽 글자층만 읽는
            # Tier2)으로 넘기므로 여기서 담당자 확인 결과로 바꾼다.
            _logger.warning("OCR 작업량 한도 초과로 자동 판독하지 않음: %s", exc.code)
            result = _workload_review_result(exc, Path(file_path))
        if result is not None and not result.engine:
            result.engine = engine
        return result

    def _read(self, file_path: str, engine: str) -> OcrResult | None:
        path = Path(file_path)
        if not path.exists() or path.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
            return None

        text_pdf = path.suffix.lower() == ".pdf" and _tier2_can_read(path)

        from . import pdftext

        if text_pdf:
            # 텍스트 레이어는 바로 읽어 분류한 다음, 지원되는 NHIS 유형이면 그 추출기를 고른다.
            classified = pdftext._read_pdf(path)
            if classified is None:
                return None
            detected = classified.detected_doc_type
            if detected == DocType.RESIDENT_ABSTRACT:
                # 11-27: 첫 쪽 글자층이 초본이라도 그림 내용이 있는 쪽이 있으면 Tier2(첫 쪽 글자층만 읽음)에 넘기지 않고,
                # 그림 없는 글자층이면 모든 쪽 쪽표기를 붙인다. 어떤 오류도 Tier2의 첫 쪽 판독으로 이어지지 않게 여기서 받는다
                # (LocalOcr 예외는 read_document가 다음 계층으로 넘기므로).
                try:
                    if raster_content_pages(path):
                        return self._read_raster_abstract(path, engine, classified)
                    return _with_text_page_markers(classified, path)
                except Exception as exc:  # noqa: BLE001
                    return _abstract_review_result(classified, f"TEXT_ABSTRACT:{exception_code(exc)}")
            if (detected not in (DocType.NHIS_PAYMENT, DocType.NHIS_ACQUISITION_LOSS, DocType.INSURANCE_4, DocType.BIZ_REG_PROOF, DocType.DAILY_WORK_RECORD)
                    and detected not in _JOB_DOCS and detected != DocType.NHIS_QUALIFICATION and detected is not None
                    and detected != DocType.RESIDENT_ABSTRACT):
                return None  # 그 밖의 텍스트 PDF는 Tier2가 이미 분류·판독한다.
            if detected == DocType.NHIS_QUALIFICATION:
                from engine_v2.extractors.nhis_qualification import is_notification
                import pymupdf

                with pymupdf.open(path) as document:
                    if not is_notification(" ".join(mask_rrn(page.get_text()) for page in document)):
                        return None  # Other qualification forms retain their PdfText reader.
        elif engine == "off":
            return None

        try:
            ra, payment_extractor, acquisition_extractor, run_ocr, PageSource, preprocess, v2types, V2DocumentInput, load_pages, insurance4_extractor = _import_v2()
        except ImportError:
            return None

        if text_pdf:
            v2type = v2types(_JOB_DOCS[detected][1]) if detected in _JOB_DOCS else {
                DocType.NHIS_PAYMENT: v2types.NHIS_PAYMENT,
                DocType.NHIS_QUALIFICATION: v2types.NHIS_QUALIFICATION,
                DocType.NHIS_ACQUISITION_LOSS: v2types.NHIS_ACQUISITION_LOSS,
                DocType.INSURANCE_4: v2types.INSURANCE_4,
                DocType.BIZ_REG_PROOF: v2types.BIZ_REG_PROOF,
                DocType.DAILY_WORK_RECORD: v2types.DAILY_WORK_RECORD,
            }.get(detected, v2types.UNKNOWN)
            input_doc = V2DocumentInput(doc_id="demo", declared_type=v2type, file_path=str(path))
            if detected in {DocType.INSURANCE_4, DocType.NHIS_PAYMENT, DocType.NHIS_ACQUISITION_LOSS, DocType.NHIS_QUALIFICATION}:
                pages = load_pages(input_doc, engine, allow_page_errors=True)
            else:
                pages = load_pages(input_doc, engine)
            if isinstance(pages, str):
                return None  # OCR 엔진이 없어도 다음 계층이 판독을 이어받는다.
            if detected is None:
                detected, evidence = pdftext.classify_pages_with_evidence(pages)
                if detected == DocType.DAILY_WORK_RECORD:
                    from engine_v2.extractors import daily_work_record
                    result = _from_nhis(daily_work_record.extract(pages), pages, v2types, evidence, detected)
                    result.engine = _pages_engine(pages)
                    return result
                if detected not in (DocType.RESIDENT_ABSTRACT, DocType.RESIDENT_CERTIFICATE):
                    # 첫 쪽 글자층으로도, 모든 쪽 다시 판별로도 이 계층이 맡을 서식을 정하지 못했다.
                    # 숨은 글자층·짧은 글자층 뒤의 그림을 A-스캔과 같은 렌더링으로 한 번 더 읽는다.
                    return self._render_retry(path, engine, "TEXT_RECLASS_NONE" if detected is None
                                              else "TEXT_RECLASS_DISCARD")
                if detected == DocType.RESIDENT_ABSTRACT and (raster := set(raster_content_pages(path))) and any(
                        page.source == PageSource.TEXT_LAYER and page.page in raster for page, _ in pages):
                    # 11-27: 그림 내용이 있는 쪽을 글자층 단어(숨은 글자층 등)로 읽었으면 보이는 그대로(렌더링) 다시 읽는다.
                    # 그런 쪽을 이미 OCR로 읽었다면 스캔 초본으로 안전장치가 적용되므로 다시 읽지 않는다.
                    return self._read_raster_abstract(path, engine, classified)
                # Coordinate fallback changes classification only. Fields still
                # use the established resident reader and review rules.
                result = _from_resident(ra.extract(pages), pages, ra, v2types, detected)
                result.detected_doc_type = detected
                result.classification_evidence = evidence
                result.classification_confidence = .95
                result.engine = _pages_engine(pages)
                return result
            if detected == DocType.BIZ_REG_PROOF:
                from engine_v2.extractors import business_registration
                result = _from_business_proof(business_registration.extract(pages), pages, classified.classification_evidence)
            elif detected == DocType.DAILY_WORK_RECORD:
                from engine_v2.extractors import daily_work_record
                result = _from_nhis(daily_work_record.extract(pages), pages, v2types,
                                    classified.classification_evidence, detected)
            elif detected in _JOB_DOCS:
                result = _from_job_doc(_job_extractor(detected)(pages), pages,
                                       classified.classification_evidence, detected)
            elif detected == DocType.INSURANCE_4:
                result = _from_supported_form(insurance4_extractor, pages, v2types,
                                              classified.classification_evidence, detected)
            else:
                extractor = payment_extractor if detected == DocType.NHIS_PAYMENT else acquisition_extractor
                if detected == DocType.NHIS_QUALIFICATION:
                    from engine_v2.extractors import nhis_qualification
                    extractor = nhis_qualification
                result = _from_supported_form(extractor, pages, v2types,
                                              classified.classification_evidence, detected)
            result.engine = result.engine or _pages_engine(pages)
            return result

        try:
            page_images = preprocess(path)
        except ValueError:
            return self._render_retry(path, engine, "IMAGE_PREPROCESS_ERROR")
        if any(p.source == PageSource.TEXT_LAYER for p in page_images):
            return self._render_retry(path, engine, "IMAGE_TEXT_PAGE")

        pages = []
        for p, read in zip(page_images, _read_pages(run_ocr, engine, page_images)):
            r = read()
            if r.error:
                return None  # 엔진 미설치 등 → 다음 계층
            pages.append((p, r))
        return self._from_ocr_pages(pages, page_images, path, engine, retry=True)

    def _render_retry(self, path: Path, engine: str, code: str) -> OcrResult | None:
        """1차 경로가 서식을 정하지 못한 PDF만 300dpi 렌더링 OCR로 한 번 더 판별한다.

        서식을 찾았을 때만 결과를 돌려주고 사유 코드를 남긴다. 못 찾으면 None으로
        지금까지와 같이 다음 계층에 넘긴다. 다시 읽은 결과에서는 또 대체하지 않는다.
        """
        if path.suffix.lower() != ".pdf" or engine == "off" or code not in RETRY_CODES:
            return None
        if code in TEXT_RETRY_CODES and not (page_has_cover_image(path) or page_has_hidden_text(path)):
            return None
        run_ocr = _import_v2()[3]
        # 11-27: 쪽 그림은 읽을 차례에 만들고 읽은 뒤 놓는다(render_pages). 문서는 모든 쪽을 읽을 때까지 열어 둔다.
        with render_pages(path) as (page_images, loaders):
            if not page_images:
                return None
            pages = []
            reads = _read_pages(run_ocr, engine, page_images, loaders)
            try:
                for page, reader in zip(page_images, reads):
                    read = reader()
                    if read.error:
                        return None
                    pages.append((page, read))
            finally:
                getattr(reads, "close", lambda: None)()  # 중간에 그만두면 시작하지 않은 쪽은 만들지도 읽지도 않는다.
        result = self._from_ocr_pages(pages, page_images, path, engine, retry=False)
        if result is None or result.detected_doc_type is None:
            return None
        result.fallback_reason = f"RENDER_RETRY:{code}"
        return result

    def _read_raster_abstract(self, path: Path, engine: str, classified: OcrResult) -> OcrResult:
        """11-27: 그림 내용이 있는 쪽이 섞인 글자층 초본을 보이는 그대로(300dpi 렌더링) 모든 쪽 OCR로 읽는다.

        렌더링 쪽은 글자층이 아니므로 _from_resident가 스캔 초본으로 보고 SCAN_ABSTRACT_REVIEW_GUARD가 적용된다
        (쪽표기·순번·발급일 등 다른 검증도 모든 쪽에 대해 돈다). 읽지 못하면(OCR 없음·오류·초본이 아닌 결과)
        다음 계층(첫 쪽 글자층만 읽는 Tier2)에 넘기지 않고 담당자 확인 결과를 돌려준다.
        """
        from engine_v2.pipeline.limits import OcrWorkloadExceeded

        try:
            result = self._render_retry(path, engine, "TEXT_RASTER_CONTENT")
        except OcrWorkloadExceeded as exc:  # 11-27: 한도 초과 → 한 쪽도 읽지 않고 담당자 확인 (사유를 따로 남긴다)
            return _abstract_review_result(classified, f"TEXT_RASTER_CONTENT:RESOURCE_LIMIT_{exc.code}",
                                           workload_message(exc.code))
        except Exception as exc:  # noqa: BLE001 - 어떤 오류도 Tier2의 첫 쪽 판독으로 이어지면 안 된다
            return _abstract_review_result(classified, f"TEXT_RASTER_CONTENT:{exception_code(exc)}")
        if result is None:  # OCR 없음·OCR 오류·서식 판별 실패
            return _abstract_review_result(classified, "TEXT_RASTER_CONTENT:NO_RESULT")
        if result.detected_doc_type != DocType.RESIDENT_ABSTRACT:  # 글자층은 초본, 보이는 내용은 다른 서류: 담당자 확인
            return _abstract_review_result(classified, "TEXT_RASTER_CONTENT:NOT_ABSTRACT")
        # 믿을 수 있는 글자층이 있는 문서를 OCR로 다시 읽은 결과다(직인·바코드 그림 하나로도 이 길을 탄다). 이 문서는
        # 안전장치로 자동 PASS가 없고, OCR 오독으로 확정 FAIL(본인 불일치·발급일·쪽 누락)을 내지 않도록 신뢰도를
        # 엔진 임계값 아래(0.4)로 묶어 확정 사유도 담당자 확인으로 보낸다.
        result.confidence = min(result.confidence, .4)
        return result

    def _from_ocr_pages(self, pages, page_images, path: Path, engine: str, *, retry: bool) -> OcrResult | None:
        """OCR한 쪽들로 서식을 판별하고 그 서식의 판독기를 고른다."""
        from . import pdftext

        ra, payment_extractor, acquisition_extractor, _, _, _, v2types, _, _, insurance4_extractor = _import_v2()
        text = "\n".join(result.text for _, result in pages)
        detected, evidence = pdftext.classify_pages_with_evidence(pages)
        if detected is None:
            code = "IMAGE_UNCLASSIFIED" if text.strip() else "IMAGE_OCR_EMPTY"
            retry_error = None
            if retry:
                from engine_v2.pipeline.limits import OcrWorkloadExceeded

                try:
                    recovered = self._render_retry(path, engine, code)
                except OcrWorkloadExceeded:
                    # 11-27: 다시 읽기가 작업량 한도를 넘는다 → 다시 읽지 않는다. 1차 판독은 모든 쪽을 읽은 결과이므로
                    # 지금까지 '다시 읽어도 서식을 못 찾았을 때'와 똑같이 처리한다(읽지 않은 문서로 표시하지 않는다).
                    recovered = None
                except Exception as exc:  # noqa: BLE001 - 사유만 남기고 1차 결과를 유지한다
                    recovered, retry_error = None, exc
                if recovered is not None:
                    return recovered
            # Do not discard successfully read words and independent folios just
            # because damaged title glyphs cannot establish a document type.
            from .file_evidence import independent_page_markers
            markers = independent_page_markers(pages)
            if markers is None:
                if retry_error is not None:
                    raise retry_error  # read_document가 예외 클래스 이름을 대체 사유로 남긴다.
                return None  # Keep prior fallback results when there is no new usable evidence.
            fields = {"독립쪽표기자료": json.dumps(markers)}
            result = OcrResult(fields=fields, page_count=len(pages), tier=NAME,
                               engine=engine, image_quality=_quality(page_images),
                               classification_evidence=evidence)
            if retry_error is not None:
                result.fallback_reason = f"RENDER_RETRY_ERROR:{exception_code(retry_error)}"
            if path.suffix.lower() != ".pdf":
                _merge_image_heuristics(result, path)
            return result

        if detected == DocType.BIZ_REG_PROOF:
            from engine_v2.extractors import business_registration
            result = _from_business_proof(business_registration.extract(pages), pages, evidence)
            if path.suffix.lower() != ".pdf":
                _merge_image_heuristics(result, path)
            return result

        if detected == DocType.DAILY_WORK_RECORD:
            from engine_v2.extractors import daily_work_record
            result = _from_nhis(daily_work_record.extract(pages), pages, v2types, evidence, detected)
            if path.suffix.lower() != ".pdf":
                _merge_image_heuristics(result, path)
            return result

        if detected in _JOB_DOCS:
            result = _from_job_doc(_job_extractor(detected)(pages), pages, evidence, detected)
            if path.suffix.lower() != ".pdf":
                _merge_image_heuristics(result, path)
            return result

        if detected == DocType.NHIS_QUALIFICATION:
            from engine_v2.extractors import nhis_qualification
            if nhis_qualification.is_notification(text):
                result = _from_supported_form(nhis_qualification, pages, v2types, evidence, detected)
                if path.suffix.lower() != ".pdf":
                    _merge_image_heuristics(result, path)
                return result

        if detected in (DocType.NHIS_PAYMENT, DocType.NHIS_ACQUISITION_LOSS, DocType.INSURANCE_4):
            if detected == DocType.INSURANCE_4:
                result = _from_supported_form(insurance4_extractor, pages, v2types, evidence, detected)
            else:
                extractor = payment_extractor if detected == DocType.NHIS_PAYMENT else acquisition_extractor
                result = _from_supported_form(extractor, pages, v2types, evidence, detected)
            if path.suffix.lower() != ".pdf":
                _merge_image_heuristics(result, path)
            return result

        if detected in (DocType.RESIDENT_ABSTRACT, DocType.RESIDENT_CERTIFICATE):
            ex = ra.extract(pages)
            result = _from_resident(ex, pages, ra, v2types, detected)
            result.detected_doc_type = detected
            result.classification_evidence = evidence
            result.classification_confidence = 0.95
            if path.suffix.lower() != ".pdf":
                _merge_image_heuristics(result, path)
            return result

        result = _generic(pages, path)
        if result is not None:
            result.detected_doc_type = detected
            result.classification_evidence = evidence
            result.classification_confidence = 0.95
        return result
