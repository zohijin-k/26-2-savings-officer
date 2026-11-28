"""Original bitmap size and independently readable page markers, without type guesses."""
import json
import math
from pathlib import Path
import re


# Narrow provisional product boundary, documented in task design (not an OCR limit).
MIN_SHORT_EDGE = 600
MIN_LONG_EDGE = 800

#: 11-28: 쪽 크기로 해상도(DPI)를 잴 수 있는 가장 큰 용지 = A3(842×1191pt)·타블로이드(792×1224pt), 오차 2%.
#: 스캐너와 대상 서식이 쓰는 용지는 그 이하다. 그보다 큰 쪽 상자는 실제 용지가 아니라 PDF를 만든 도구가 정한 값이다
#: (그림→PDF 변환이 화소 수를 72dpi 쪽 크기로 적는 경우 등: 2066×2923px 그림 → 2066×2923pt 쪽 = '72dpi').
MAX_SHEET_SHORT_PT = 842 * 1.02
MAX_SHEET_LONG_PT = 1224 * 1.02
_A4_SHORT_PT, _A4_LONG_PT = 595.0, 842.0


def sheet_scale(width_pt: float, height_pt: float) -> float:
    """쪽 상자를 A4에 맞게 줄이는 배율. 실제 용지 크기(A3·타블로이드 이하)는 1 = 쪽 크기 그대로 잰다."""
    short, long = sorted((float(width_pt), float(height_pt)))
    if short <= 0 or (short <= MAX_SHEET_SHORT_PT and long <= MAX_SHEET_LONG_PT):
        return 1.0
    return min(_A4_SHORT_PT / short, _A4_LONG_PT / long)


def _pixel_band(short_edge: int) -> float:
    """그림 파일의 짧은 변 화소 등급(물리 크기를 모르는 그림의 기존 기준)."""
    return .9 if short_edge >= 1400 else .75 if short_edge >= 1000 else .55 if short_edge >= 700 else .35


def _dpi_band(dpi: float) -> float:
    """PDF 쪽을 덮는 원본 그림의 DPI 등급(기존 기준)."""
    return .9 if dpi >= 200 else .7 if dpi >= 150 else .5


def _page_bitmap_score(image, page) -> float | None:
    """쪽을 덮는 원본 그림 한 장의 해상도 점수. 잴 수 없으면 None(중립).

    실제 용지 크기 쪽: 그림 화소 ÷ 쪽 크기 = DPI 등급 그대로(전과 같음).
    용지보다 큰 쪽 상자(11-28): 쪽 상자 숫자만으로 미달이 되지 않게, 같은 그림을 A4 쪽에 놓았을 때의 DPI 등급까지
    올려 준다. 다만 그 그림을 그림 파일로 올렸을 때의 등급(짧은 변 화소)을 넘지 않는다 — PDF로 감쌌다고 그림보다
    높게 치지 않는다(좁고 긴 띠 그림 등). 전의 점수보다 낮아지는 경우는 없다.
    """
    # The original pixel-width axis can be rotated in the PDF. Its transform vector, rather than the
    # enclosing box width, preserves the same physical DPI for rotated scans.
    width_pt = math.hypot(*image["transform"][:2])
    if width_pt <= 0:
        return None
    score = _dpi_band(image["width"] / (width_pt / 72))
    scale = sheet_scale(page.rect.width, page.rect.height)
    if 0 < scale < 1:
        fitted = _dpi_band(image["width"] / (width_pt * scale / 72))
        score = max(score, min(fitted, _pixel_band(min(image["width"], image["height"]))))
    return score


def _dominant_image(page):
    import pymupdf

    images = [image for image in page.get_image_info() if
              pymupdf.Rect(image["bbox"]).get_area() >= .9 * page.rect.get_area()]
    return max(images, key=lambda item: item["width"] * item["height"]) if images else None


def original_image_sizes(file_path: str) -> list[dict[str, int]]:
    path = Path(file_path)
    try:
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            from PIL import Image
            try:
                with Image.open(path) as image:
                    width, height = image.size
            except Image.DecompressionBombError:
                return []  # 11-27: PIL이 거부하는 초대형 그림. 크기 근거 없음(판독 계층이 작업량 한도로 담당자 확인에 보낸다).
            return [{"page": 0, "width": width, "height": height}]
        if path.suffix.lower() == ".pdf":
            import pymupdf
            from engine_v2.pipeline.preprocess import TEXT_LAYER_MIN_CHARS
            sizes = []
            with pymupdf.open(path) as doc:
                if doc.needs_pass:
                    return []
                for index, page in enumerate(doc):
                    if len(page.get_text().strip()) >= TEXT_LAYER_MIN_CHARS:
                        continue  # A scalable text-layer page is not limited by its background bitmap.
                    # Only a dominant source bitmap, never a rendered/upscaled page.
                    image = _dominant_image(page)
                    if image is not None:
                        sizes.append({"page": index, "width": image["width"], "height": image["height"]})
            return sizes
    except (OSError, ValueError, RuntimeError):
        pass  # Reading/format failures retain the existing unreadable-file path.
    return []


def objective_image_quality(file_path: str, *, excluded_pages=()) -> float:
    """Original resolution proxy only; OCR success, blur and brightness are unused.

    Keep the established raw-image pixel and embedded-PDF DPI score bands.
    Scalable text and unmeasured sources are neutral, never inferred poor quality.
    """
    path = Path(file_path)
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        sizes = original_image_sizes(file_path)
        if not sizes:
            return 1.0
        return _pixel_band(min(sizes[0]["width"], sizes[0]["height"]))
    if path.suffix.lower() != ".pdf":
        return 1.0
    try:
        import pymupdf
        from engine_v2.pipeline.preprocess import TEXT_LAYER_MIN_CHARS

        scores = []
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                return 1.0  # The reader retains its separate unreadable-file evidence.
            for index, page in enumerate(doc, 1):
                if index in excluded_pages:
                    continue
                if len(page.get_text().strip()) >= TEXT_LAYER_MIN_CHARS:
                    scores.append(1.0)
                    continue
                image = _dominant_image(page)
                if image is None:
                    scores.append(1.0)  # Rendering cannot establish original resolution.
                    continue
                score = _page_bitmap_score(image, page)
                scores.append(1.0 if score is None else score)
        return min(scores, default=1.0)
    except (OSError, ValueError, RuntimeError):
        return 1.0


def normalize_image_quality(result, file_path):
    """Measure the same original pages as the established bounded form reader."""
    if result.is_encrypted or result.tier == "fixture":
        return result
    from ..rules.doc_types import DocType

    excluded = []
    if result.detected_doc_type in {DocType.INSURANCE_4, DocType.NHIS_PAYMENT,
                                    DocType.NHIS_ACQUISITION_LOSS, DocType.NHIS_QUALIFICATION}:
        try:
            pages = json.loads(result.fields.get("추가첨부쪽", "[]"))
            count = result.page_count
            if (isinstance(pages, list) and type(count) is int and
                    all(type(value) is int and 1 <= value <= count for value in pages) and
                    len(set(pages)) == len(pages) < count):
                excluded = pages
        except (ValueError, TypeError):
            pass
    result.image_quality = objective_image_quality(file_path, excluded_pages=excluded)
    return result


def attach_file_evidence(result, file_path):
    if not result.is_encrypted and result.tier != "fixture":
        sizes = original_image_sizes(file_path)
        if sizes:
            result.fields["원본이미지크기"] = json.dumps(sizes, separators=(",", ":"))
    return result


def independent_page_markers(pages):
    from engine_v2.extractors.nhis_common import page_lines
    from engine_v2.pipeline.layout import squash

    markers, confidences = [], []
    for page, result in pages:
        candidates = []
        # Top-right folio region; an arbitrary body fraction is not a page marker.
        for row in page_lines(page, result):
            selected = [w for w in row if w.x0 >= 70 and w.cy < 10]
            text = squash("".join(w.text for w in selected))
            match = re.fullmatch(r"([0-9]{1,2})[/／]([0-9]{1,2})", text)
            if match and 1 <= int(match[1]) <= int(match[2]):
                candidates.append(([int(match[1]), int(match[2])], min(w.conf for w in selected)))
        if len(candidates) != 1:
            return None
        marker, confidence = candidates[0]
        markers.append(marker)
        confidences.append(confidence)
    return {"markers": markers, "confidence": min(confidences)} if markers else None


def resolution_defect(ocr) -> dict[str, int] | None:
    from ..rules.doc_types import DocType
    from engine_v2.pipeline.limits import not_read_by_limit

    if not_read_by_limit(getattr(ocr, "fallback_reason", "")):
        # 11-27: 작업량 한도로 읽지 않은 문서다. '작은 그림이라 못 읽었다'(부적합)는 읽어 본 문서에만 내린다.
        return None
    try:
        sizes = json.loads(ocr.fields.get("원본이미지크기", "[]"))
        identity_forms = {DocType.RESIDENT_ABSTRACT, DocType.RESIDENT_CERTIFICATE,
                          DocType.INSURANCE_4, DocType.DAILY_WORK_RECORD,
                          DocType.NHIS_PAYMENT, DocType.NHIS_QUALIFICATION,
                          DocType.NHIS_ACQUISITION_LOSS, DocType.BIZ_REG_PROOF}
        essential_fields = ("성명", "생년월일", "발급일") if ocr.detected_doc_type in identity_forms else {
            DocType.PAYMENT_RECEIPT: ("결제금액", "결제일"),
            DocType.EXAM_CONFIRMATION: ("성명", "응시일"),
            DocType.EXAM_TRANSCRIPT: ("성명", "응시일"),
            DocType.INTERVIEW_CONFIRMATION: ("성명", "면접일", "회사명"),
        }.get(ocr.detected_doc_type, ())
        readable = sum(bool(ocr.fields.get(key) or key == "발급일" and ocr.issue_date)
                       for key in essential_fields)
        unreadable = (ocr.detected_doc_type is None or
                      bool(essential_fields) and readable * 2 < len(essential_fields))
        if not unreadable:
            return None
        for size in sizes:
            width, height = size["width"], size["height"]
            if type(width) is int and type(height) is int and 0 < min(width, height) < MIN_SHORT_EDGE and max(width, height) < MIN_LONG_EDGE:
                return size
    except (ValueError, TypeError, KeyError):
        pass
    return None
