"""11-28: OCR 입력 PNG 인코더를 바꿔도(GIL을 놓는 OpenCV) 판독이 보는 화소는 MuPDF 인코더와 같다 (가상 그림만).

`engine_v2.pipeline.preprocess.encode_png`은 판독 스레드가 다른 요청을 멈추지 않게 하려는 변경이다. PNG는 무손실이라
바이트(압축)는 달라도 디코딩한 화소가 같아야 하고, 그러면 인식 입력도 인식 결과도 같다.
"""
import io
import sys

import pymupdf
import pytest
from PIL import Image

from engine_v2.pipeline import preprocess as v2preprocess


def _noisy(size=(413, 585), mode="RGB"):
    import random
    random.seed(7)
    image = Image.new(mode, size)
    image.putdata([tuple(random.randrange(256) for _ in range(len(mode))) if len(mode) > 1 else random.randrange(256)
                   for _ in range(size[0] * size[1])])
    return image


def _pixmap(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return pymupdf.Pixmap(buffer.getvalue())


def _decoded(png):
    with Image.open(io.BytesIO(png)) as image:
        return image.mode, image.size, image.convert("RGB").tobytes()


@pytest.mark.parametrize("size", [(413, 585), (1, 1), (7, 3), (1241, 17)])
def test_opencv_png_decodes_to_the_same_pixels_as_the_mupdf_png(size):
    pytest.importorskip("cv2")           # OCR 엔진이 설치된 환경에서만 이 인코더가 쓰인다
    pix = _pixmap(_noisy(size))
    ours, reference = v2preprocess.encode_png(pix), pix.tobytes("png")
    assert ours != reference                                    # 다른 인코더가 실제로 쓰였다
    assert _decoded(ours) == _decoded(reference) == ("RGB", size, _noisy(size).tobytes())


def test_recognizer_input_array_is_identical():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    pix = _pixmap(_noisy())
    arrays = [cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
              for png in (v2preprocess.encode_png(pix), pix.tobytes("png"))]
    assert arrays[0].shape == (585, 413, 3) and np.array_equal(arrays[0], arrays[1])


@pytest.mark.parametrize("mode", ["L", "RGBA"])
def test_pixmaps_that_are_not_plain_rgb_keep_the_mupdf_encoder(mode):
    pix = _pixmap(_noisy((31, 17), mode))
    assert v2preprocess.encode_png(pix) == pix.tobytes("png")


def test_without_opencv_the_mupdf_encoder_is_used(monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", None)               # import cv2 → ImportError
    pix = _pixmap(_noisy((31, 17)))
    assert v2preprocess.encode_png(pix) == pix.tobytes("png")


def test_scan_page_and_photo_inputs_decode_to_the_original_bitmap(tmp_path):
    """전처리 결과(스캔 PDF의 본문 그림, 사진 업로드)가 원본 그림의 화소 그대로다."""
    source = _noisy((620, 877))
    buffer = io.BytesIO()
    source.save(buffer, "PNG")
    with pymupdf.open() as document:
        document.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=buffer.getvalue())
        document.save(tmp_path / "FAKE-scan.pdf")
    source.save(tmp_path / "FAKE-photo.png")
    for name in ("FAKE-scan.pdf", "FAKE-photo.png"):
        (page,) = v2preprocess.preprocess(tmp_path / name)
        assert page.pixel_size == (620, 877)
        assert _decoded(page.png) == ("RGB", (620, 877), source.tobytes())
