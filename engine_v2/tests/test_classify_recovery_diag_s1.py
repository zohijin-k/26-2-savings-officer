"""S1 shadow: two abstract pages printed side by side on one sheet (synthetic words only)."""
from engine_v2.pipeline.ocr import OcrResult
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.tests.test_resident_abstract import H, W, header, row, table_head
from engine_v2.tools import classify_recovery_diag as tool


def _half(words, left):
    """Squeeze a portrait page into the left or right half of a sheet (page-% coordinates)."""
    out = []
    for word in words:
        x0, y0, x1, y1 = word.bbox_px
        shift = 0 if left else W / 2
        out.append(type(word)(word.text, word.confidence, (x0 / 2 + shift, y0, x1 / 2 + shift, y1)))
    return out


def _page(index, total, doc_no='1234-5678-9012-34567'):
    words = header(index, total) + table_head(31.8) + row(34.4, index, '전북특별자치도 전주시 가상동', '2020-01-01')
    for word in words:
        if word.text.startswith('문서확인번호'):
            word.text = f'문서확인번호 : {doc_no}'
    return words


def sheet(*pages):
    words = []
    for left, page in zip((True, False), pages):
        words += _half(page, left)
    return PageImage(0, PageSource.EMBEDDED, (842.0, 595.0), pixel_size=(W, H)), OcrResult('own', words)


def test_two_up_sheet_with_both_markers_merges_to_a_complete_set():
    sheets = tool.sheet_markers([sheet(_page(1, 2), _page(2, 2))])
    assert sheets[0][1] is True and sheets[0][0] == [(1, 2), (2, 2)]
    # Production reads only the right-hand marker (x0 > 70): one sheet, marker 2/2 -> PAGES_INCOMPLETE.
    assert tool.s1_result(sheets, [(2, 2)]) == ('COMPLETE', [(1, 2), (2, 2)])


def test_merged_sets_keep_missing_and_duplicate_pages():
    one = tool.sheet_markers([sheet(_page(1, 3), _page(2, 3))])
    assert tool.s1_result(one, [(2, 3)])[0] == 'INCOMPLETE'
    # 1/2 twice and no 2/2: missing is checked first, as in production (PAGES_INCOMPLETE).
    twice = tool.sheet_markers([sheet(_page(1, 2), _page(1, 2))])
    assert tool.s1_result(twice, [(1, 2)])[0] == 'INCOMPLETE'
    single = (PageImage(1, PageSource.EMBEDDED, (595.0, 842.0), pixel_size=(W, H)), OcrResult('own', _page(2, 2)))
    duplicated = tool.sheet_markers([sheet(_page(1, 2), _page(1, 2)), single])
    assert tool.s1_result(duplicated, [(1, 2), (2, 2)])[0] == 'DUPLICATED'


def test_different_document_numbers_are_never_merged():
    sheets = tool.sheet_markers([sheet(_page(1, 2), _page(2, 2, doc_no='9999-5678-9012-34567'))])
    assert tool.s1_result(sheets, [(2, 2)]) == ('DOC_NO_DIFFERS', None)


def test_single_page_and_body_text_markers_are_not_multi():
    single = _page(1, 1)
    sheets = tool.sheet_markers([(PageImage(0, PageSource.EMBEDDED, (595.0, 842.0), pixel_size=(W, H)),
                                  OcrResult('own', single + row(45.0, 2, '본문 1/2 가상', '2021-01-01')))])
    assert sheets[0][1] is False
    assert tool.s1_result(sheets, [(1, 1)]) == ('NOT_MULTI', None)


def test_row_validation_accepts_only_s1_codes():
    row = tool.blank_row('0' * 16)
    tool.validate_row(dict(row, s1=dict(sheets='M1', result='COMPLETE', decision='PASS')))
    for bad in (dict(sheets='M9', result='COMPLETE', decision=None), dict(sheets='M1', result='free', decision=None)):
        try:
            tool.validate_row(dict(row, s1=bad))
        except Exception:
            continue
        raise AssertionError(bad)


def test_shadow_turns_the_two_up_incomplete_fail_into_a_page_complete_verdict(tmp_path):
    import json
    from types import SimpleNamespace
    from demo.backend.ocr.localocr import _from_resident
    from engine_v2.extractors import resident_abstract
    from engine_v2.schemas.models import DocType as V2Type
    pages = [sheet(_page(1, 2), _page(2, 2))]
    ocr = _from_resident(resident_abstract.extract(pages), pages, resident_abstract, V2Type)
    assert json.loads(ocr.fields['쪽표기자료'])['markers'] == [[2, 2]]
    path = tmp_path / 'sheet.pdf'
    path.write_bytes(b'%PDF-1.7')
    row = tool.blank_row('0' * 16)
    row['form'] = 'RESIDENT_ABSTRACT'
    row['decision'], row['reasons'] = tool._assess(path, 'RESIDENT_ABSTRACT', ocr)
    # 11-18 S1 in production: the 2-up sheet already counts both markers (was FAIL PAGES_INCOMPLETE).
    assert row['decision'] == 'NEEDS_REVIEW' and not any(code == 'PAGES_INCOMPLETE' for code, _ in row['reasons'])
    tool.resident_sheet_shadow(SimpleNamespace(resident=pages), path, row, ocr)
    assert row['s1']['sheets'] == 'M1' and row['s1']['result'] == 'COMPLETE'
    # The synthetic sheet lacks an applicant line and repeated header values, so it stays under review.
    assert row['s1']['decision'] == 'NEEDS_REVIEW'
    tool.validate_row(row)
