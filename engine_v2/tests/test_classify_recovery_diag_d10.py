"""D10 (11-19): why a resident abstract is PAGES_DUPLICATED, page by page (synthetic only).

Numbers and fixed codes only: box and character counts, page-marker state, the replayed
production blank-page decision, image ink, size, dpi, text layer and the duplicate path.
"""
import io
from types import SimpleNamespace

import pytest

from engine_v2.extractors import resident_abstract
from engine_v2.tests.test_resident_abstract import build, header, page, row, table_head
from engine_v2.tools import classify_recovery_diag as tool


def _png(ink=0.0, size=(60, 80)):
    from PIL import Image
    image = Image.new('L', size, 255)
    dark = int(size[0] * size[1] * ink)
    image.putdata([0] * dark + [255] * (size[0] * size[1] - dark))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def _with_png(pages, inks):
    for (p, _), ink in zip(pages, inks):
        p.png = _png(ink) if ink is not None else b''
    return pages


def _two():
    pages = build()[:2]
    for p, result in pages:
        for word in result.words:
            if word.text in ('1/3', '2/3'):
                word.text = word.text.replace('/3', '/2')
    return pages


def _row(pages, path='synthetic.png', decision='FAIL'):
    row = tool.blank_row('0' * 16)
    row['form'], row['decision'] = 'RESIDENT_ABSTRACT', decision
    row['reasons'] = [['PAGES_DUPLICATED', 'FAIL']]
    tool.pages_duplicated_check(SimpleNamespace(resident=pages), path, row)
    tool.validate_row(row)
    return row


def _header_page(i, marker, extra=()):
    words = header(1, 1)
    for word in words:
        if word.text == '1/1':
            word.text = marker
    return page(i, words + list(extra))


@pytest.mark.parametrize('extra, content, keep', [
    ((), 'NO_CONTENT', 'BLANK_DUP_MARKER'),
    ('table', 'TABLE_ONLY', 'TABLE_ONLY_DUP_MARKER'),
])
def test_blank_third_page_states_replay_the_extractor(extra, content, keep):
    pages = _with_png(_two() + [_header_page(2, '2/2', table_head(21.1) if extra else ())], [.05, .06, 0.0])
    d10 = _row(pages)['d10']
    third = d10['pages'][2]
    assert (third['content'], third['keep'], third['counted'], third['marker'], third['repeat']) == (
        content, keep, 'X', 'O', 'O')
    assert d10['consistent'] == 'O' and d10['marker_dup'] == 'X' and d10['path'] == 'OTHER'
    assert third['ink'] == 0.0 and d10['pages'][0]['ink'] == pytest.approx(.05, abs=.001)
    assert [p['keep'] for p in d10['pages'][:2]] == ['CONTENT', 'CONTENT']
    assert resident_abstract.extract(pages).blank_pages == 1


def test_page_with_a_history_row_and_a_repeated_marker_is_a_marker_duplicate():
    third = _header_page(2, '2/2', table_head(21.1) + row(24.0, 3, '전북특별자치도 전주시 가상동', '2024-01-01'))
    d10 = _row(_with_png(_two() + [third], [.05, .06, .07]))['d10']
    assert d10['path'] == 'MARKER_DUP' and d10['marker_dup'] == 'O'
    assert [p['counted'] for p in d10['pages']] == ['O', 'O', 'O']
    assert d10['pages'][2]['content'] == 'TABLE_ROWS' and d10['pages'][2]['repeat'] == 'O'


def test_same_image_and_same_text_are_reported_by_page_index():
    pages = _two()
    from copy import deepcopy
    copy = page(2, deepcopy(pages[1][1].words))
    pages = _with_png(pages + [copy], [.05, .07, .07])
    d10 = _row(pages)['d10']
    assert d10['image_same'] == 'O' and d10['pages'][2]['same_image_as'] == 1
    assert d10['text_same'] == 'O' and d10['pages'][2]['same_text_as'] == 1
    assert d10['pages'][0]['same_image_as'] == -1


def test_unread_marker_counts_and_page_numbers_are_numbers_only():
    pages = _with_png(_two() + [_header_page(2, '읽기불가', table_head(21.1))], [.05, .06, None])
    d10 = _row(pages)['d10']
    third = d10['pages'][2]
    assert third['marker'] == 'X' and third['keep'] == 'TABLE_ONLY_NO_MARKER' and third['counted'] == 'O'
    assert third['ink'] == -1 and third['source'] == 'EMBEDDED' and third['dpi'] == 250
    assert (third['width'], third['height']) == (2066, 2923)
    assert third['hangul'] > 0 and third['boxes'] == len(pages[2][1].words)
    assert third['layer_chars'] == -1 and third['xref_shared'] == 'NA'


def test_pdf_facts_text_layer_render_ink_and_shared_image(tmp_path):
    import pymupdf
    path = tmp_path / 'synthetic.pdf'
    with pymupdf.open() as document:
        image = _png(.3)
        xref = None
        for index in range(3):
            pdf_page = document.new_page(width=200, height=280)
            if index < 2:
                if xref is None:
                    xref = pdf_page.insert_image(pdf_page.rect, stream=image)
                else:
                    pdf_page.insert_image(pdf_page.rect, xref=xref)
        document[2].insert_text((20, 40), 'ABC 123', fontsize=9)
        document.save(path)
    facts = tool._pdf_page_facts(path, 3)
    assert [f['images'] for f in facts] == [1, 1, 0]
    assert [f['xref_shared'] for f in facts] == ['O', 'O', 'NA']
    assert facts[2]['layer_chars'] == 6
    assert facts[0]['render_ink'] > .2 and facts[2]['render_ink'] < .05


def test_no_resident_pages_gives_an_empty_other_row():
    d10 = _row(None)['d10']
    assert d10 == dict(path='OTHER', marker_dup='X', image_same='X', text_same='X', consistent='NA', pages=[])


def test_summary_lines_and_free_text_rejected():
    rows = [_row(_with_png(_two() + [_header_page(2, '2/2')], [.05, .06, 0.0]))]
    lines = tool.summarize(rows, dict(counts={}))
    assert 'D10 1 0 0 0 1 0' in lines
    assert 'D10_DOC OTHER 3 FAIL 1' in lines
    assert any(line.startswith('D10_PAGE 1 3 ') and ' NO_CONTENT ' in line and ' BLANK_DUP_MARKER ' in line
               for line in lines.splitlines())
    d10 = rows[0]['d10']
    for change in (dict(path='free text'), dict(pages=[dict(d10['pages'][0], keep='because')]),
                   dict(pages=[dict(d10['pages'][0], ink=1.5)])):
        with pytest.raises(Exception):
            tool.validate_row(dict(rows[0], d10=dict(d10, **change)))
