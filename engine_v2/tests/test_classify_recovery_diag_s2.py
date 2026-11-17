"""S2 shadow: sheets uploaded sideways are re-read rotated (synthetic image, orientation-aware fake OCR)."""
import io
import json

import pytest

from engine_v2.tools import classify_recovery_diag as tool

TITLE = ['건강보험료', '납부확인서'] + ['가상합성시험문서입니다'] * 6   # > S2_MIN_HANGUL characters upright


def _sheet(angle):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (600, 848), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 70, 70), fill='black')               # orientation marker: top-left when upright
    for row in range(6):
        draw.rectangle((120, 150 + row * 90, 400, 170 + row * 90), fill='gray')
    return image.rotate(angle, expand=True)


def _pdf(path, angle):
    import pymupdf
    image = _sheet(angle)
    data = io.BytesIO()
    image.save(data, 'PNG')
    with pymupdf.open() as document:
        width, height = (842, 595) if angle in (90, 270) else (595, 842)
        page = document.new_page(width=width, height=height)
        page.insert_image(page.rect, stream=data.getvalue())
        document.save(path)
    return path


@pytest.fixture
def upright_only(monkeypatch):
    """Reads the title only when the dark marker sits in the top-left corner."""
    import numpy as np
    from PIL import Image
    from engine_v2.pipeline import ocr as v2ocr
    from engine_v2.pipeline.ocr import OcrWord

    def recognize(png, size):
        gray = np.asarray(Image.open(io.BytesIO(png)).convert('L'))
        h, w = gray.shape
        corner = gray[: h // 10, : w // 10]
        if corner.size == 0 or corner.mean() > 128:
            return [OcrWord('잡음', .3, (0, 0, 10, 10))]
        return [OcrWord(text, .95, (w * .2, 40 + 30 * i, w * .6, 60 + 30 * i)) for i, text in enumerate(TITLE)]
    monkeypatch.setitem(v2ocr.ENGINES, 'own', recognize)
    monkeypatch.setattr(tool.timing, 'own_available', lambda: True)


def _row(tmp_path, angle):
    root = tmp_path / f'root{angle}'
    root.mkdir()
    _pdf(root / 'a.pdf', angle)
    out = tmp_path / f'out{angle}'
    tool.run(root, out)
    (row,) = [json.loads(line) for line in (out / 'rows.jsonl').read_text().splitlines()]
    return row, (out / 'summary.txt').read_text()


@pytest.mark.parametrize('angle', [90, 270])
def test_sideways_sheet_is_recovered_by_rotation(tmp_path, upright_only, angle):
    row, summary = _row(tmp_path, angle)
    assert row['form'] == 'X'
    assert row['s2']['tried'] == 1 and row['s2']['better'] == 'B1' and row['s2']['form'] == 'NHIS_PAYMENT'
    assert 'S2 1 1 1 0 1 ' in summary


def test_upright_sheet_is_never_rotated(tmp_path, upright_only):
    row, _ = _row(tmp_path, 0)
    assert row['form'] == 'NHIS_PAYMENT' and row['s2']['tried'] == 0 and row['s2']['better'] == 'B0'


def test_unreadable_sheet_stays_unreadable(tmp_path, monkeypatch):
    from engine_v2.pipeline import ocr as v2ocr
    from engine_v2.pipeline.ocr import OcrWord
    monkeypatch.setitem(v2ocr.ENGINES, 'own', lambda png, size: [OcrWord('흐림', .2, (0, 0, 5, 5))])
    monkeypatch.setattr(tool.timing, 'own_available', lambda: True)
    row, _ = _row(tmp_path, 0)
    assert row['s2']['tried'] == 1 and row['s2']['better'] == 'B0' and row['s2']['decision'] is None
