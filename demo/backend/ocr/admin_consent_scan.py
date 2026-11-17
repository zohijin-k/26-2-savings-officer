"""서식5 종이 스캔에서 인쇄 대비 잉크 흔적을 확인한다."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageOps

from ..forms import coords as form_coords

#: 동의 표시 칸에서 표시로 보는 추가 잉크 비율.
MARK_RATIO = 0.035
#: 위상 상관 표면의 최고점 세기(표준점수). 이 이상일 때만 위치 맞춤을 믿는다 (11-18 INNER_STRONG).
ALIGN_PEAK_STRONG = 20.0
#: 위치 맞춤 뒤 칸 테두리 인쇄 차이를 빼려고 칸 각 변에서 안쪽으로 줄이는 폭(pt).
INNER_INSET_PT = 2.0


def _page_image(path: Path, width: int) -> Image.Image:
    if path.suffix.lower() == ".pdf":
        import fitz

        with fitz.open(path) as pdf:
            page = pdf[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(width / page.rect.width, width / page.rect.width), alpha=False)
            return Image.open(BytesIO(pix.tobytes("png"))).convert("L")
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("L").copy()


def _extra_ink_ratio(scan: Image.Image, template: Image.Image, box: list[float], page_width: float, page_height: float) -> float:
    x0, y0, x1, y1 = box
    sx, sy = scan.width / page_width, scan.height / page_height
    crop = (max(0, int(x0 * sx)), max(0, int(y0 * sy)), min(scan.width, int(x1 * sx)), min(scan.height, int(y1 * sy)))
    scan_part, template_part = scan.crop(crop), template.crop(crop)
    diff = ImageChops.difference(scan_part, template_part)
    # Ink added to a blank template is darker than the corresponding printed template pixel.
    dark = sum(1 for value in diff.getdata() if value > 45)
    return dark / max(1, diff.width * diff.height)


def _phase_shift(scan: Image.Image, template: Image.Image) -> tuple[int, int, float]:
    """스캔을 원본 서식에 맞추는 평행 이동(원본 그림 화소)과 위상 상관 최고점 세기."""
    import numpy as np

    size = (template.width // 2, template.height // 2)
    a = 255.0 - np.asarray(scan.resize(size, Image.Resampling.BILINEAR), dtype=np.float64)
    b = 255.0 - np.asarray(template.resize(size, Image.Resampling.BILINEAR), dtype=np.float64)
    a -= a.mean()
    b -= b.mean()
    cross = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    cross /= np.abs(cross) + 1e-9
    surface = np.real(np.fft.ifft2(cross))
    y, x = np.unravel_index(int(np.argmax(surface)), surface.shape)
    if y > surface.shape[0] // 2:
        y -= surface.shape[0]
    if x > surface.shape[1] // 2:
        x -= surface.shape[1]
    strength = float((surface.max() - surface.mean()) / (surface.std() or 1.0))
    return 2 * int(x), 2 * int(y), strength


def _marks(scan, template, spec, page_width, page_height, inset=0.0) -> list[str]:
    selected = []
    for key, label in (("agree.동의함", "동의함"), ("agree.동의하지 않음", "동의하지 않음")):
        field = spec.fields.get(key)
        if not field:
            continue
        x0, y0, x1, y1 = field["box"]
        box = [x0 + inset, y0 + inset, x1 - inset, y1 - inset]
        if _extra_ink_ratio(scan, template, box, page_width, page_height) > MARK_RATIO:
            selected.append(label)
    return selected


def inspect_admin_consent_scan(path_value: str) -> dict[str, str]:
    """Return safe checklist observations only; never stores an image or OCR value."""
    spec = form_coords.load("서식5")
    if spec is None or not spec.available:
        return {"동의여부": "확인필요", "서명잉크확인": "확인필요"}
    import fitz

    with fitz.open(spec.template) as template_pdf:
        page = template_pdf[0]
        page_width, page_height = page.rect.width, page.rect.height
        width = 1200
        pix = page.get_pixmap(matrix=fitz.Matrix(width / page_width, width / page_width), alpha=False)
        template_image = Image.open(BytesIO(pix.tobytes("png"))).convert("L")
    try:
        scan = _page_image(Path(path_value), width)
        scan = scan.resize(template_image.size)
    except Exception:
        return {"동의여부": "확인필요", "서명잉크확인": "확인필요"}

    selected = _marks(scan, template_image, spec, page_width, page_height)
    try:
        dx, dy, strength = _phase_shift(scan, template_image)
    except Exception:  # noqa: BLE001 - 위치 맞춤을 못 하면 지금 판독을 그대로 쓴다
        strength = 0.0
    if strength >= ALIGN_PEAK_STRONG:
        # 위치가 확실히 맞을 때만, 옮긴 스캔의 칸 안쪽(테두리 인쇄 차이 제외)으로 표시를 다시 센다.
        # 표시가 정확히 하나가 아니면 지금처럼 확인필요다. 상관이 약하면 지금 판독을 그대로 둔다.
        moved = scan.transform(scan.size, Image.Transform.AFFINE, (1, 0, dx, 0, 1, dy), fillcolor=255)
        selected = _marks(moved, template_image, spec, page_width, page_height, inset=INNER_INSET_PT)
    signature = spec.fields.get("signature")
    signed = bool(signature and _extra_ink_ratio(scan, template_image, signature["box"], page_width, page_height) > 0.012)
    return {
        "동의여부": selected[0] if len(selected) == 1 else "확인필요",
        "서명잉크확인": "있음" if signed else "확인필요",
    }
