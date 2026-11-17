"""O5: consent marks on rasters are read inside the checkbox only after a strong alignment."""
import io

import pymupdf

from ..forms import coords
from ..ocr import admin_consent_scan as consent


def _pdf(path, *, mark=None, raster_dpi=None, shift_pt=0):
    spec = coords.load("서식5")
    with pymupdf.open(spec.template) as document:
        page = document[0]
        if mark:
            box = pymupdf.Rect(*spec.fields[mark]["box"])
            page.draw_line((box.x0 + 1, box.y0 + 1), (box.x1 - 1, box.y1 - 1), color=(0, 0, 0), width=1.3)
            page.draw_line((box.x0 + 1, box.y1 - 1), (box.x1 - 1, box.y0 + 1), color=(0, 0, 0), width=1.3)
        if raster_dpi is None:
            document.save(path)
            return str(path)
        pix = page.get_pixmap(dpi=raster_dpi, alpha=False)
        width, height = page.rect.width, page.rect.height
    from PIL import Image
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    canvas = Image.new("RGB", image.size, "white")
    offset = int(shift_pt * image.width / width)
    canvas.paste(image, (offset, offset))
    data = io.BytesIO()
    canvas.save(data, "PNG")
    with pymupdf.open() as out:
        out.new_page(width=width, height=height).insert_image(pymupdf.Rect(0, 0, width, height), stream=data.getvalue())
        out.save(path)
    return str(path)


def test_vector_forms_keep_their_reading(tmp_path):
    assert consent.inspect_admin_consent_scan(_pdf(tmp_path / "agree.pdf", mark="agree.동의함"))["동의여부"] == "동의함"
    assert consent.inspect_admin_consent_scan(
        _pdf(tmp_path / "disagree.pdf", mark="agree.동의하지 않음"))["동의여부"] == "동의하지 않음"


def test_raster_mark_is_read_inside_the_aligned_box(tmp_path):
    # Before O5 a 300 dpi raster always read BOTH (printed borders differ from the vector template).
    path = _pdf(tmp_path / "raster-agree.pdf", mark="agree.동의함", raster_dpi=300, shift_pt=4)
    assert consent.inspect_admin_consent_scan(path)["동의여부"] == "동의함"


def test_blank_rasters_never_read_as_a_single_mark(tmp_path):
    for shift in (0, 4, 8):
        path = _pdf(tmp_path / f"blank-{shift}.pdf", raster_dpi=300, shift_pt=shift)
        assert consent.inspect_admin_consent_scan(path)["동의여부"] == "확인필요"


def test_weak_alignment_keeps_the_current_reading(tmp_path, monkeypatch):
    path = _pdf(tmp_path / "raster-agree.pdf", mark="agree.동의함", raster_dpi=300, shift_pt=4)
    monkeypatch.setattr(consent, "_phase_shift", lambda scan, template: (0, 0, consent.ALIGN_PEAK_STRONG - 1))
    assert consent.inspect_admin_consent_scan(path)["동의여부"] == "확인필요"  # unaligned reading: BOTH
