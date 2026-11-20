"""D11 (11-19): page-image source of every document (synthetic only, codes and counts only).

EMBEDDED pages are read from the embedded main image, not the page as displayed. D11 counts pages whose
main image is shared with another page, whose image does not show in the render, or whose OCR-input ink
differs strongly from the render ink.
"""
import io
from types import SimpleNamespace

import pymupdf
import pytest

from engine_v2.pipeline.preprocess import preprocess
from engine_v2.tools import classify_recovery_diag as tool


def _png(ink, size=(200, 280)):
    """Grey image whose top ``ink`` share of rows is black."""
    from PIL import Image
    image = Image.new('L', size, 255)
    dark = int(size[0] * size[1] * ink)
    image.putdata([0] * dark + [255] * (size[0] * size[1] - dark))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def _pdf(path, pages):
    """``pages``: (image ink or None, white cover height share from the top, image key) per page."""
    with pymupdf.open() as document:
        xrefs = {}
        for ink, cover, key in pages:
            page = document.new_page(width=200, height=280)
            if ink is not None:
                if key in xrefs:
                    page.insert_image(page.rect, xref=xrefs[key])
                else:
                    xrefs[key] = page.insert_image(page.rect, stream=_png(ink))
            if cover:
                page.draw_rect(pymupdf.Rect(0, 0, 200, 280 * cover), color=(1, 1, 1), fill=(1, 1, 1))
        document.save(path)
    return path


def _row(path, form='RESIDENT_ABSTRACT', decision='NEEDS_REVIEW'):
    row = tool.blank_row('0' * 16)
    row['form'], row['decision'] = form, decision
    tool.page_source_check(SimpleNamespace(images=preprocess(path)), path, row)
    tool.validate_row(row)
    return row


def test_shared_main_image_is_counted(tmp_path):
    d11 = _row(_pdf(tmp_path / 'a.pdf', [(.3, 0, 'A'), (.3, 0, 'A'), (.3, 0, 'B')]))['d11']
    assert d11['embedded'] == 3 and d11['shared'] == 'O'
    assert d11['hidden'] == 'X' and d11['ratio'] == 'X'
    assert sum(d11['bins'].values()) == 3 and d11['bins']['NA'] == 0


def test_image_that_does_not_show_is_hidden(tmp_path):
    d11 = _row(_pdf(tmp_path / 'a.pdf', [(.3, 1, 'A')]))['d11']
    assert (d11['embedded'], d11['shared'], d11['hidden'], d11['ratio']) == (1, 'X', 'O', 'X')
    assert d11['bins']['NA'] == 1  # nothing rendered: no ratio


def test_strongly_different_ink_is_a_ratio_page(tmp_path):
    # Image ink .3 (top rows); the top quarter is covered in the render: render ink about .05.
    d11 = _row(_pdf(tmp_path / 'a.pdf', [(.3, .25, 'A')]))['d11']
    assert (d11['shared'], d11['hidden'], d11['ratio']) == ('X', 'X', 'O') and d11['bins']['R3P'] == 1


def test_ordinary_embedded_and_text_pages(tmp_path):
    d11 = _row(_pdf(tmp_path / 'a.pdf', [(.3, 0, 'A')]))['d11']
    assert (d11['embedded'], d11['shared'], d11['hidden'], d11['ratio']) == (1, 'X', 'X', 'X')
    text = tmp_path / 'text.pdf'
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((40, 60), 'synthetic text layer ' * 6, fontsize=9)
        document.save(text)
    d11 = _row(text)['d11']
    assert d11 == dict(embedded=0, shared='X', hidden='X', ratio='X', bins=dict.fromkeys(tool.D11_RATIO_BINS, 0))


def test_no_preprocessed_pages_gives_an_empty_row():
    row = tool.blank_row('0' * 16)
    tool.page_source_check(SimpleNamespace(images=None), 'synthetic.png', row)
    tool.validate_row(row)
    assert row['d11']['embedded'] == 0


@pytest.mark.parametrize('input_ink, render_ink, expected', [
    (.3, .001, 'NA'), (-1, .3, 'NA'), (.05, .3, 'R_LT033'), (.2, .3, 'R033_1'), (.3, .3, 'R1_3'),
    (.6, .3, 'R1_3'), (.9, .3, 'R3P')])
def test_ratio_bins(input_ink, render_ink, expected):
    assert tool.d11_ratio_bin(input_ink, render_ink) == expected


def test_summary_lines_by_form_and_decision_and_free_text_rejected(tmp_path):
    rows = [_row(_pdf(tmp_path / 'a.pdf', [(.3, 0, 'A'), (.3, 0, 'A')]), decision='FAIL'),
            _row(_pdf(tmp_path / 'b.pdf', [(.3, 1, 'A')]), form='NHIS_PAYMENT'),
            _row(_pdf(tmp_path / 'c.pdf', [(.3, 0, 'A')]), form='NHIS_PAYMENT')]
    lines = tool.summarize(rows, dict(counts={})).splitlines()
    assert 'D11 3 3 1 1 0 2' in lines
    assert 'D11_FORM_DECISION NHIS_PAYMENT NEEDS_REVIEW 2 0 1 0 1' in lines
    assert 'D11_FORM_DECISION RESIDENT_ABSTRACT FAIL 1 1 0 0 1' in lines
    assert any(line.startswith('D11_RATIO ') and line != 'D11_RATIO ' + ' '.join(tool.D11_RATIO_BINS)
               for line in lines)
    d11 = rows[0]['d11']
    for change in (dict(shared='yes'), dict(embedded=-1), dict(bins=dict(d11['bins'], R3P=99)),
                   dict(bins={'free': 2}), dict(note='x')):
        with pytest.raises(Exception):
            tool.validate_row(dict(rows[0], d11=dict(d11, **change)))


def test_a_failed_d11_shadow_is_a_valid_row():
    # A D11 exception keeps the baseline row and records only the stage name; the row must validate.
    row = tool.blank_row('0' * 16)
    row['form'], row['decision'], row['shadow_errors'] = 'NHIS_PAYMENT', 'NEEDS_REVIEW', ['D11']
    tool.validate_row(row)
    with pytest.raises(Exception):
        tool.validate_row(dict(row, shadow_errors=['D12']))
