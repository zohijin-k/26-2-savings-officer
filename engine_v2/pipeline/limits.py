"""OCR 작업량 상한 (11-27 CPU·메모리 보호).

문서 한 건의 자동 판독이 쓰는 CPU 시간과 메모리는 OCR로 읽는 쪽 수와 쪽 그림의 화소 수에 비례한다. 상한이 없으면
수십 KB짜리 파일(1비트 1억 화소 그림, 큰 용지 쪽, 수백 쪽 스캔)이 수 GB·수 분을 쓴다.

한도를 넘는 문서는 **일부만 읽지 않는다.** 그림을 펼치기(디코딩·렌더링) 전에 OcrWorkloadExceeded를 내고,
판독 계층(demo.backend.ocr.localocr.LocalOcr.read)이 그 문서 전체를 '자동 판독 안 함 → 담당자 확인' 결과로 바꾼다.
자동 적합(PASS)도 근거 없는 부적합(FAIL)도 내지 않고, 다음 계층의 첫 쪽 글자층 판독으로도 넘기지 않는다.

값의 측정 근거와 실패 처리 정책: .trellis/spec/backend/ocr-resource-limits.md
"""
from __future__ import annotations

import math

#: 문서 한 건에서 OCR로 읽는 쪽 수 (글자층으로 읽는 쪽은 세지 않는다).
#: 근거: 8코어 M2에서 300dpi A4 한 쪽이 깨끗한 합성본 0.7초·잡음 있는 스캔 2.2초(동시 4쪽) → 30쪽 21~65초.
#: 업로드 판독은 서버 이벤트 루프에서 돌아 그동안 그 서버의 다른 요청이 기다리므로, 한 건이 서버를 붙잡는 시간을
#: 약 1분으로 묶는다. 초본·건강보험·4대보험 서류의 통상 쪽 수(1~10쪽)보다 넉넉한 값이다.
MAX_OCR_PAGES = 30
#: OCR 입력 그림 한 장의 화소 수. A4 600dpi(3,480만)와 5,000만 화소급 사진(8192×6144 = 5,033만)까지 읽는다.
#: 근거: 판독 중인 쪽마다 디코딩한 그림(화소×3바이트, 6,000만 화소 = 180MB)과 그 PNG·원본 Pixmap이 함께 메모리에 있다.
MAX_PAGE_PIXELS = 60_000_000
#: 문서 한 건의 OCR 입력 화소 합: 300dpi A4 30쪽 분량(2.61억). 600dpi A4는 7쪽, 5,000만 화소 사진은 5장까지 읽는다.
#: 근거: 본문 그림을 그대로 읽는 경로(preprocess)는 모든 쪽의 PNG를 읽기 전에 만들어 두므로 합계가 곧 보관량이다.
MAX_DOCUMENT_PIXELS = 270_000_000


#: 문서 한 건의 쪽 판독(run_ocr_pages 한 번)에 쓰는 시간(초). 쪽과 쪽 사이에서만 확인한다(읽는 중인 쪽은 끝낸다).
#: 쪽 수·화소 한도 안에서도 내용이 비정상적으로 복잡한 쪽은 오래 걸린다: 가는 선 6만 개를 그린 합성 쪽 하나가
#: 검출 상자 상한(쪽당 2,000개)까지 인식해 33초 걸렸다(정상 쪽 0.7초) → 한도가 없으면 30쪽에 16분.
#: 정상 문서는 넘지 않게 잡는다: 잡음이 있는 300dpi 스캔 20쪽이 42~44초(쪽당 2.2초, 8코어 M2)라 30쪽은 약 65초이고,
#: 그 2.7배다. 서버 속도에 따라 달라지는 값이므로 안전망일 뿐이며, 넘으면 부적합이 아니라 담당자 확인이다.
MAX_OCR_SECONDS = 180


class OcrWorkloadExceeded(Exception):
    """자동 판독 작업량 한도 초과 (code: PAGES | PAGE_PIXELS | DOCUMENT_PIXELS | SECONDS).

    ValueError가 아니다: 쪽 오류로 삼켜지거나(engine._load_pages) 다음 판독 계층으로 조용히 넘어가면 안 된다.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class OcrWorkload:
    """문서 한 건의 누적 OCR 작업량. ``add``는 그 쪽의 그림을 만들기(디코딩·렌더링) 전에 부른다."""

    def __init__(self) -> None:
        self.pages = 0
        self.pixels = 0

    def add(self, width: float, height: float) -> None:
        pixels = math.ceil(max(width, 0)) * math.ceil(max(height, 0))
        if pixels > MAX_PAGE_PIXELS:
            raise OcrWorkloadExceeded("PAGE_PIXELS")
        self.pages += 1
        if self.pages > MAX_OCR_PAGES:
            raise OcrWorkloadExceeded("PAGES")
        self.pixels += pixels
        if self.pixels > MAX_DOCUMENT_PIXELS:
            raise OcrWorkloadExceeded("DOCUMENT_PIXELS")


#: 한도 초과로 읽지 않은 결과의 대체 사유(fallback_reason)에 들어가는 표시. 'RESOURCE_LIMIT:<code>' 또는
#: 'RENDER_RETRY_FAILED:TEXT_RASTER_CONTENT:RESOURCE_LIMIT_<code>'.
NOT_READ_MARK = "RESOURCE_LIMIT"


def not_read_by_limit(fallback_reason: str | None) -> bool:
    """작업량 한도로 **읽기를 시도하지 않은** 결과인가. '읽어 보았으나 못 읽음'을 전제로 한 판정(원본 해상도 미달 등)은
    이런 결과에 적용하면 안 된다 — 읽지 않은 것을 못 읽은 것으로 단정하게 된다."""
    return NOT_READ_MARK in (fallback_reason or "")


def check_page_size(width: float, height: float) -> None:
    """그림 한 장(너비×높이 화소)이 쪽 화소 한도를 넘으면 OcrWorkloadExceeded("PAGE_PIXELS"). 누적 작업량에는 더하지 않는다."""
    if math.ceil(max(width, 0)) * math.ceil(max(height, 0)) > MAX_PAGE_PIXELS:
        raise OcrWorkloadExceeded("PAGE_PIXELS")


def check_elapsed(started: float) -> None:
    """``started``(time.monotonic) 뒤로 MAX_OCR_SECONDS를 넘었으면 OcrWorkloadExceeded("SECONDS")."""
    import time

    if time.monotonic() - started > MAX_OCR_SECONDS:
        raise OcrWorkloadExceeded("SECONDS")


def check_page_images(page, *, resources: bool = False) -> None:
    """쪽에 들어 있는 그림 가운데 화소 수가 한도를 넘는 것이 있으면 OcrWorkloadExceeded("PAGE_PIXELS").

    그림의 머리 정보(너비·높이)만 읽는다. 이 쪽을 OCR하려면 그 그림을 펼쳐야 하므로(본문 그림 찾기의
    ``get_image_info(xrefs=True)``와 렌더링 모두 그림을 디코딩한다: 20KB 파일의 1.44억 화소 그림 +127MB),
    화면에 작게 놓인 그림이라도 한도를 넘으면 그 문서는 읽지 않는다.

    ``resources=True``: 쪽에 그리지 않았어도 쪽 자원 목록에 올라 있는 그림까지 본다. ``get_image_info(xrefs=True)``는
    자원 목록의 모든 그림을 펼쳐 해시를 구하므로(그리지 않은 1.44억 화소 그림도), 그 호출 앞에서는 이렇게 확인한다.
    렌더링은 그리지 않은 그림을 펼치지 않으므로 렌더링 앞에서는 그린 그림만 본다.
    """
    sizes = [(info.get("width"), info.get("height")) for info in page.get_image_info()]
    if resources:
        sizes += [(item[2], item[3]) for item in page.get_images(full=True)]
    for width, height in sizes:
        if int(width or 0) * int(height or 0) > MAX_PAGE_PIXELS:
            raise OcrWorkloadExceeded("PAGE_PIXELS")


def release_page_cache() -> None:
    """MuPDF 전역 캐시(store)를 비운다. 쪽 그림을 하나 만들 때마다 부른다.

    MuPDF는 쪽을 그릴 때 디코딩한 그림을 전역 캐시(기본 256MB)에 두고 문서를 닫아도 놓지 않는다. 쪽마다 그림이
    다른 스캔 PDF에서는 다시 쓰이지 않는 그림이 쌓인다(20쪽 렌더링 +425MB → 쪽마다 비우면 +104MB, 시간 차이 없음).
    캐시일 뿐이라 렌더링 결과는 같다.
    """
    import pymupdf

    pymupdf.TOOLS.store_shrink(100)
