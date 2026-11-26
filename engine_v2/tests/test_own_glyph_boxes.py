"""Glyph-sized detection boxes follow the page text angle, not the glyph shape (11-26).

Model-free contracts for own._align_glyph_boxes, plus one model-gated check on a fictitious scanned
resident abstract where a tilted box made the real PP-OCRv5 recognizer read history number "7" as "1".
"""
import io
import math
import re
from pathlib import Path

import numpy as np
import pytest

from engine_v2.pipeline.ocr import own


def rect(cx, cy, w, h, deg):
    """Corners [tl, tr, br, bl] of a w x h rectangle centred at (cx, cy) rotated by deg."""
    t = math.radians(deg)
    r = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    pts = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]) @ r.T
    return (pts + [cx, cy]).astype(np.float32)


def lines(deg=0.0, n=5):
    return [rect(400, 100 + 60 * i, 300, 30, deg) for i in range(n)]


def test_tilted_glyph_box_is_reframed_upright_and_encloses_the_detection():
    glyph = rect(100, 500, 22, 24, 26)  # observed: "7" box at +26 deg on an upright page
    out = own._align_glyph_boxes(lines() + [glyph], (2066, 2923))
    box = out[-1]
    assert own._box_angle(box) == pytest.approx(0, abs=1e-3)
    assert box[0][0] <= glyph[:, 0].min() + 1e-3 and box[2][0] >= glyph[:, 0].max() - 1e-3
    assert box[0][1] <= glyph[:, 1].min() + 1e-3 and box[2][1] >= glyph[:, 1].max() - 1e-3
    assert box[0][0] < box[1][0] and box[1][1] < box[2][1]  # [tl, tr, br, bl] order kept


def test_line_boxes_and_upright_glyphs_are_unchanged():
    upright = rect(100, 500, 22, 24, 1.5)  # within GLYPH_ANGLE_TOLERANCE
    tilted_line = rect(400, 700, 300, 30, 20)  # an elongated box keeps its own angle
    boxes = lines() + [upright, tilted_line]
    out = own._align_glyph_boxes(boxes, (2066, 2923))
    for before, after in zip(boxes, out):
        assert after is before


def test_no_line_boxes_means_no_reference_angle_and_no_change():
    boxes = [rect(100, 500, 22, 24, 26), rect(200, 500, 30, 30, 40)]
    assert own._align_glyph_boxes(boxes, (2066, 2923)) == boxes


def test_skewed_page_reframes_glyph_to_the_page_angle_not_to_zero():
    out = own._align_glyph_boxes(lines(2.0) + [rect(100, 500, 22, 24, 30)], (2066, 2923))
    assert own._box_angle(out[-1]) == pytest.approx(2.0, abs=1e-3)


def test_reframed_box_is_clipped_to_the_image():
    out = own._align_glyph_boxes(lines() + [rect(5, 5, 20, 20, 30)], (2066, 2923))
    assert out[-1].min() >= 0 and out[-1][:, 0].max() <= 2065 and out[-1][:, 1].max() <= 2922


FONT = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")


@pytest.mark.skipif(not FONT.exists() or not all((own.MODEL_DIR / n).is_file()
                                                for n in ("det.onnx", "rec.onnx", "korean_dict.txt")),
                    reason="needs pinned own models and the synthetic-scan font")
def test_real_onnx_reads_number_column_of_synthetic_scan(tmp_path):
    """Fictitious 3-page abstract rendered as an image-only PDF, read through preprocess + own."""
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont
    from engine_v2.pipeline.preprocess import preprocess
    from engine_v2.tests import p2_resident_samples as rs

    path = tmp_path / "scan.pdf"
    with pymupdf.open() as doc:
        for page, result in rs.resident():
            im = Image.new("RGB", page.pixel_size, "white"); d = ImageDraw.Draw(im)
            for w in result.words:
                (x0, y0, x1, y1) = w.bbox_px
                d.text((x0, y0), w.text, font=ImageFont.truetype(str(FONT), max(12, int((y1 - y0) * .85))), fill="black")
            buf = io.BytesIO(); im.save(buf, format="PNG")
            doc.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=buf.getvalue())
        doc.save(path)
    numbers = []
    for page in preprocess(str(path)):
        W = page.pixel_size[0]
        numbers += [w.text for w in own.recognize(page.png, page.pixel_size)
                    if w.bbox_px[0] / W * 100 < 11.5 and re.fullmatch(r"\d{1,3}", w.text.strip())]
    assert numbers == [str(n) for n in range(1, 12)]
