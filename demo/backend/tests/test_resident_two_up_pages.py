"""S1 (held): two abstract pages printed side by side on one sheet (synthetic words only)."""
import json

from engine_v2.extractors import resident_abstract
from engine_v2.pipeline.ocr import OcrResult
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.schemas.models import DocType as V2Type
from engine_v2.tests.test_classify_recovery_diag_s1 import _page, sheet
from engine_v2.tests.test_resident_abstract import H, W, row

from ..ocr.localocr import _from_resident
from ..rules.doc_check import _check_resident_pages
from .run_p8_localocr_scenarios import abstract_slot


def _codes(pages):
    ocr = _from_resident(resident_abstract.extract(pages), pages, resident_abstract, V2Type)
    ocr.confidence = .95
    return [f.code for f in _check_resident_pages(ocr, abstract_slot())], json.loads(ocr.fields['쪽표기자료'])


def test_two_up_sheet_with_both_markers_is_complete():
    codes, data = _codes([sheet(_page(1, 2), _page(2, 2))])
    assert codes == [] and data['sheets'] == [[[1, 2], [2, 2]]]


def test_single_marker_sheet_still_misses_a_page():
    single = [(PageImage(0, PageSource.EMBEDDED, (595.0, 842.0), pixel_size=(W, H)), OcrResult('own', _page(1, 2)))]
    codes, data = _codes(single)
    assert codes == ['PAGES_INCOMPLETE'] and 'sheets' not in data


def test_same_marker_twice_is_duplicated_or_missing():
    assert _codes([sheet(_page(1, 2), _page(1, 2))])[0] == ['PAGES_INCOMPLETE']
    page_two = (PageImage(1, PageSource.EMBEDDED, (595.0, 842.0), pixel_size=(W, H)), OcrResult('own', _page(2, 2)))
    assert _codes([sheet(_page(1, 2), _page(1, 2)), page_two])[0] == ['PAGES_DUPLICATED']


def test_body_text_marker_is_not_a_page_marker():
    words = _page(1, 1) + row(45.0, 2, '본문 1/2 가상', '2021-01-01')
    codes, data = _codes([(PageImage(0, PageSource.EMBEDDED, (595.0, 842.0), pixel_size=(W, H)), OcrResult('own', words))])
    assert codes == [] and 'sheets' not in data and data['markers'] == [[1, 1]]
