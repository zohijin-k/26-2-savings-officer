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


def _both(pix):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    ours, reference = v2preprocess.encode_png(pix), pix.tobytes("png")
    decoded = [cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR) for png in (ours, reference)]
    return ours != reference, np.array_equal(decoded[0], decoded[1]), decoded[0].shape


def test_rendered_page_pixmap_is_pixel_identical(tmp_path):
    """300dpi 쪽 렌더링(글자·선·그림이 섞인 쪽)의 Pixmap도 같은 화소로 인코딩된다."""
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_text((40, 60), "SYNTHETIC 가상 문서 0123456789", fontname="korea", fontsize=14)
        page.draw_line((30, 100), (560, 130), color=(.2, .4, .8), width=.7)
        buffer = io.BytesIO()
        _noisy((120, 80)).save(buffer, "PNG")
        page.insert_image(pymupdf.Rect(40, 150, 280, 310), stream=buffer.getvalue())
        pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csRGB, alpha=False)
        used_opencv, identical, shape = _both(pix)
    assert used_opencv and identical and shape == (pix.height, pix.width, 3)


def test_jpeg_scan_embedded_in_a_pdf_is_pixel_identical(tmp_path):
    """스캐너가 만드는 JPEG 본문 그림(DCT)을 꺼낸 Pixmap."""
    buffer = io.BytesIO()
    _noisy((310, 438)).save(buffer, "JPEG", quality=80)
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buffer.getvalue())
        xref = page.get_images(full=True)[0][0]
        pix = pymupdf.Pixmap(document, xref)
        used_opencv, identical, shape = _both(pix)
    assert used_opencv and identical and shape == (438, 310, 3)


def test_three_component_non_rgb_image_is_left_to_mupdf_exactly_as_before(tmp_path):
    """성분이 셋이지만 RGB가 아닌 그림(Lab): 화소를 RGB로 잘못 읽지 않는다. 전처럼 MuPDF가 처리한다(PNG로 못 쓰면 오류)."""
    buffer = io.BytesIO()
    _noisy((40, 30)).save(buffer, "PNG")
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buffer.getvalue())
        xref = page.get_images(full=True)[0][0]
        document.xref_set_key(xref, "ColorSpace", "[/Lab << /WhitePoint [0.9505 1 1.089] /Range [-128 127 -128 127] >>]")
        document.save(tmp_path / "FAKE-lab.pdf")
    with pymupdf.open(tmp_path / "FAKE-lab.pdf") as document:
        pix = pymupdf.Pixmap(document, document[0].get_images(full=True)[0][0])
        assert pix.n == 3 and not pix.alpha and not v2preprocess._is_plain_rgb(pix)
        try:
            reference = pix.tobytes("png")
        except Exception as exc:  # noqa: BLE001 - MuPDF가 거절하면 우리도 같은 오류여야 한다
            with pytest.raises(type(exc)):
                v2preprocess.encode_png(pix)
        else:
            assert v2preprocess.encode_png(pix) == reference
