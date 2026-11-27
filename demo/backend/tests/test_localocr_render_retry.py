"""O1: LocalOcr re-reads undecided PDFs from 300 dpi renderings (synthetic PDFs, fake OCR)."""
import io

import pytest

from engine_v2.tests.test_classify_recovery_diag import PAYMENT_TITLE, build


@pytest.fixture
def fake_engine(monkeypatch):
    """Uniform bitmaps have no words; anything else carries the payment title."""
    from engine_v2.pipeline import ocr as v2ocr
    from engine_v2.pipeline.ocr import OcrWord
    calls = []

    def recognize(png, size):
        import numpy as np
        from PIL import Image
        calls.append(size)
        gray = np.asarray(Image.open(io.BytesIO(png)).convert('L'))
        if int(gray.max()) - int(gray.min()) < 30:
            return []
        return [OcrWord(text, .99, (size[0] * (.2 + .1 * i), 40, size[0] * (.28 + .1 * i), 70))
                for i, text in enumerate(PAYMENT_TITLE)]
    monkeypatch.setitem(v2ocr.ENGINES, 'own', recognize)
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    return calls


@pytest.mark.parametrize('kind, code', [
    ('hidden', 'TEXT_RECLASS_NONE'),         # hidden text layer, no keyword
    ('few', 'TEXT_RECLASS_DISCARD'),         # 1-49 characters on the first page
    ('later', 'IMAGE_TEXT_PAGE'),            # first page image, later text page
    ('stencil', 'IMAGE_PREPROCESS_ERROR'),   # ImageMask cannot be extracted
    ('mrc', 'IMAGE_OCR_EMPTY'),              # largest covering image is the blank background
    ('smask', 'IMAGE_OCR_EMPTY'),            # transparency ignored by extraction
])
def test_undecided_pdfs_are_recovered_with_a_reason_code(tmp_path, fake_engine, kind, code):
    from demo.backend.ocr import read_document
    result = read_document(str(build(tmp_path / f'{kind}.pdf', kind)), None)
    assert result.detected_doc_type is not None and result.detected_doc_type.name == 'NHIS_PAYMENT'
    assert result.tier == 'localocr'
    assert result.fallback_reason == f'RENDER_RETRY:{code}'


def test_decided_documents_never_take_the_retry(tmp_path, fake_engine):
    from demo.backend.ocr import read_document
    result = read_document(str(build(tmp_path / 'plain.pdf', 'plain')), None)
    assert result.detected_doc_type.name == 'NHIS_PAYMENT' and result.fallback_reason == ''
    assert len(fake_engine) == 1  # one embedded page, no rendering


def test_retry_that_finds_nothing_keeps_the_previous_outcome(tmp_path, monkeypatch):
    from demo.backend.ocr import read_document
    from engine_v2.pipeline import ocr as v2ocr
    monkeypatch.setitem(v2ocr.ENGINES, 'own', lambda png, size: [])
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    result = read_document(str(build(tmp_path / 'stencil.pdf', 'stencil')), None)
    assert result.detected_doc_type is None and result.tier == 'none' and result.fallback_reason == ''


def test_swallowed_reader_exceptions_leave_only_the_class_name(tmp_path, fake_engine, monkeypatch):
    from demo.backend.ocr import localocr, read_document

    def broken(self, file_path, engine):
        raise RuntimeError('secret document text must not appear')
    monkeypatch.setattr(localocr.LocalOcr, '_read', broken)
    result = read_document(str(build(tmp_path / 'plain.pdf', 'plain')), None)
    assert result.fallback_reason == 'LOCALOCR_EXCEPTION:RuntimeError'
    assert 'secret' not in result.fallback_reason


def _text_report(path, logo=False):
    """Three text-layer pages that no reader recognizes (optionally a small logo on page 1)."""
    import pymupdf
    from PIL import Image
    document = pymupdf.open()
    for index in range(3):
        page = document.new_page(width=595, height=842)
        page.insert_text((40, 60), f'Quarterly activity report page {index + 1} ' + 'lorem ipsum dolor sit amet ' * 4,
                         fontsize=8, fontname='helv')
        if logo and index == 0:
            buffer = io.BytesIO()
            Image.new('RGB', (120, 60), (20, 60, 120)).save(buffer, 'PNG')
            page.insert_image(pymupdf.Rect(460, 30, 560, 80), stream=buffer.getvalue())
    document.save(path)
    return path


@pytest.mark.parametrize('logo', [False, True])
def test_text_pdfs_without_a_cover_image_are_never_rendered(tmp_path, fake_engine, logo):
    """TEXT_RECLASS_* retries only read pictures behind a text layer; plain text PDFs skip the 300 dpi OCR."""
    from demo.backend.ocr import localocr, read_document
    path = _text_report(tmp_path / 'report.pdf', logo)
    assert not localocr.page_has_cover_image(path)
    result = read_document(str(path), None)
    assert fake_engine == []  # no page was rendered or recognized
    assert 'RENDER_RETRY' not in result.fallback_reason and result.detected_doc_type is None


def test_cover_image_counts_tiles_and_ignores_encryption(tmp_path):
    import pymupdf
    from PIL import Image
    from demo.backend.ocr.localocr import page_has_cover_image
    buffer = io.BytesIO()
    Image.new('RGB', (100, 100), (200, 200, 200)).save(buffer, 'PNG')
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_image(pymupdf.Rect(0, 0, 595, 421), stream=buffer.getvalue(), keep_proportion=False)
    page.insert_image(pymupdf.Rect(0, 421, 595, 842), stream=buffer.getvalue(), keep_proportion=False)
    document.save(tmp_path / 'tiles.pdf')
    assert page_has_cover_image(tmp_path / 'tiles.pdf')
    document.save(tmp_path / 'locked.pdf', encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw='x', owner_pw='y')
    assert not page_has_cover_image(tmp_path / 'locked.pdf')
