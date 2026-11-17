"""Synthetic-only verification of the classification recovery diagnostics."""
import io
import json

import pytest

from engine_v2.tools import classify_recovery_diag as tool

SENTINEL = 'secret'
PAYMENT_TITLE = ('건강보험료', '납부확인서')
INSURANCE_TITLE = ('4대', '사회보험', '확인용', '가입자', '가입내역', '확인서')


# ---------------------------------------------------------------- synthetic inputs


def _picture(width=600, height=848):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    for row in range(8):
        draw.rectangle((40, 60 + row * 90, 40 + 60 * (row % 5 + 3), 80 + row * 90), fill='black')
    return image


def _png(image):
    data = io.BytesIO()
    image.save(data, 'PNG')
    return data.getvalue()


def _image_page(document, image=None):
    page = document.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=_png(image or _picture()))
    return page


def _raw_page(document, xrefs):
    page = document.new_page(width=595, height=842)
    names = ' '.join(f'/Im{i} {x} 0 R' for i, x in enumerate(xrefs))
    document.xref_set_key(page.xref, 'Resources', f'<< /XObject << {names} >> >>')
    content = document.get_new_xref()
    document.update_object(content, '<< >>')
    document.update_stream(content, '\n'.join(f'q 595 0 0 842 0 0 cm 0 g /Im{i} Do Q'
                                              for i in range(len(xrefs))).encode())
    document.xref_set_key(page.xref, 'Contents', f'{content} 0 R')


def _stencil(document, image):
    mask = image.convert('L').point(lambda v: 255 if v > 160 else 0).convert('1')
    xref = document.get_new_xref()
    document.update_object(xref, f'<< /Type /XObject /Subtype /Image /Width {mask.width} /Height {mask.height} '
                                 '/ImageMask true /BitsPerComponent 1 >>')
    document.update_stream(xref, mask.tobytes())
    return xref


def _rgb(document, image):
    xref = document.get_new_xref()
    document.update_object(xref, f'<< /Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} '
                                 '/ColorSpace /DeviceRGB /BitsPerComponent 8 >>')
    document.update_stream(xref, image.convert('RGB').tobytes())
    return xref


def build(path, kind):
    import pymupdf
    from PIL import Image
    document = pymupdf.open()
    if kind == 'plain':
        _image_page(document)
    elif kind == 'hidden':
        page = _image_page(document)
        page.insert_text((40, 60), 'Xq3 zz9 lorem ipsum dolor sit amet consectetur adipiscing 12345 6789',
                         fontsize=8, render_mode=3, fontname='helv')
    elif kind == 'few':
        page = _image_page(document)
        page.insert_text((500, 820), '1 / 1', fontsize=8, fontname='helv')
    elif kind == 'later':
        _image_page(document)
        document.new_page(width=595, height=842).insert_text(
            (40, 80), 'Page two text layer content ' * 4, fontsize=9, fontname='helv')
    elif kind == 'stencil':
        _raw_page(document, [_stencil(document, _picture())])
    elif kind == 'mrc':
        paper = Image.new('RGB', (1200, 1696), (236, 232, 222))
        _raw_page(document, [_rgb(document, paper), _stencil(document, _picture())])
    elif kind == 'smask':
        gray = _picture().convert('L')
        alpha = gray.point(lambda v: 255 - v)
        rgba = Image.merge('RGBA', (Image.new('L', gray.size, 0),) * 3 + (alpha,))
        document.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=_png(rgba))
    else:
        raise AssertionError(kind)
    document.save(path)
    document.close()
    return path


@pytest.fixture
def fake_ocr(monkeypatch):
    """Content-aware fake: a uniform bitmap has no words; anything else carries the title."""
    from engine_v2.pipeline import ocr as v2ocr
    from engine_v2.pipeline.ocr import OcrWord
    state = dict(title=PAYMENT_TITLE, calls=0)

    def recognize(png, size):
        import numpy as np
        from PIL import Image
        state['calls'] += 1
        gray = np.asarray(Image.open(io.BytesIO(png)).convert('L'))
        if int(gray.max()) - int(gray.min()) < 30:
            return []
        width = size[0]
        return [OcrWord(text, .99, (width * (.2 + .1 * i), 40, width * (.28 + .1 * i), 70))
                for i, text in enumerate(state['title'])]
    monkeypatch.setitem(v2ocr.ENGINES, 'own', recognize)
    monkeypatch.setattr(tool.timing, 'own_available', lambda: True)
    return state


def rows(out):
    return [json.loads(line) for line in (out / 'rows.jsonl').read_text().splitlines()]


# ---------------------------------------------------------------- candidates


def test_candidates_only_add_insurance4_to_unclassified_inputs():
    from demo.backend.ocr import pdftext
    from demo.backend.rules.doc_types import DocType
    broken = '4대 사회보험\n확인용 가입자 가입내역 확인서'
    other = '4대 사회보험\n제출용 가입자 가입내역 확인서'
    apart = '가입자 가입내역 확인서 …… 4대 사회보험'
    assert pdftext.classify_with_evidence(broken)[0] is None
    for name, expected in (('N', (True, False, False)), ('W', (True, True, False)), ('E', (True, True, True))):
        assert tuple(tool.candidate_fires(name, text) for text in (broken, other, apart)) == expected
        classify = tool.candidate_classifier(name, pdftext.classify_with_evidence)
        assert classify(broken)[0] is DocType.INSURANCE_4
        # Existing keyword classifications are untouched, including texts that also fire the candidate.
        assert classify('건강보험료 납부확인서 ' + broken)[0] is DocType.NHIS_PAYMENT
        assert classify('아무 관련 없는 글')[0] is None
    with pytest.raises(ValueError):
        tool.candidate_fires('Z', broken)


# ---------------------------------------------------------------- run


def test_run_records_exit_and_cause_for_each_reproduced_condition(tmp_path, fake_ocr, capsys):
    root = tmp_path / 'FAKE-input' / f'{SENTINEL}-person'
    root.mkdir(parents=True)
    kinds = ('plain', 'hidden', 'few', 'later', 'stencil', 'mrc', 'smask')
    for kind in kinds:
        build(root / f'{SENTINEL}-{kind}.pdf', kind)
    out = tmp_path / 'out'
    assert tool.main(['run', '--root', str(tmp_path / 'FAKE-input'), '--out', str(out)]) == 0
    printed = capsys.readouterr().out
    by_cause = {}
    for row in rows(out):
        by_cause.setdefault(row['cause'], []).append(row)
    assert {k: len(v) for k, v in by_cause.items()} == {
        None: 1, 'HIDDEN_TEXT_LAYER': 1, 'FEW_CHARS_DISCARD': 1, 'FIRST_IMAGE_LATER_TEXT': 1,
        'PREPROCESS_ERROR': 1, 'BACKGROUND_ONLY': 2}
    assert by_cause[None][0]['form'] == 'NHIS_PAYMENT' and by_cause[None][0]['exit'] == 'L_RESULT'
    assert by_cause['FEW_CHARS_DISCARD'][0]['exit'] == 'T_RECLASS_DISCARD'
    assert by_cause['FEW_CHARS_DISCARD'][0]['reclass'] == 'NHIS_PAYMENT'
    assert by_cause['HIDDEN_TEXT_LAYER'][0]['exit'] == 'T_RECLASS_NONE'
    assert by_cause['FIRST_IMAGE_LATER_TEXT'][0]['exit'] == 'I_TEXT_PAGE'
    assert by_cause['PREPROCESS_ERROR'][0]['exceptions'] == {'preprocess': 'ValueError'}
    assert {r['struct']['main'] for r in by_cause['BACKGROUND_ONLY']} == {'RGB', 'SMASK'}
    # The 300 dpi batch_assess reading recovers every unclassified condition.
    assert all(r['scan'] == 'NHIS_PAYMENT' for r in rows(out) if r['form'] == 'X')
    assert 'XCAUSE PREPROCESS_ERROR 1' in printed and 'XEXC preprocess ValueError 1' in printed
    summary = (out / 'summary.txt').read_text()
    for text in (printed, summary, (out / 'run.json').read_text()):
        assert SENTINEL not in text and 'FAKE-input' not in text and str(tmp_path) not in text
        assert not any(row['key'] in text for row in rows(out))


def test_g1_shadow_counts_only_unclassified_insurance_titles(tmp_path, fake_ocr):
    from demo.backend.ocr import pdftext
    original = pdftext.classify_with_evidence
    root = tmp_path / 'root'
    root.mkdir()
    build(root / 'a.pdf', 'plain')
    fake_ocr['title'] = INSURANCE_TITLE
    out = tmp_path / 'out'
    assert tool.run(root, out) == 0
    (row,) = rows(out)
    assert row['form'] == 'X'
    assert row['g1'] == {'N': 'INSURANCE_4', 'W': 'INSURANCE_4', 'E': 'INSURANCE_4'}
    assert all(value in tool.DECISIONS for value in row['g1_decision'].values())
    assert 'G1 N 0 0 1 0 1' in (out / 'summary.txt').read_text()
    assert pdftext.classify_with_evidence is original


def test_classified_documents_never_rerun_for_g1(tmp_path, fake_ocr):
    root = tmp_path / 'root'
    root.mkdir()
    build(root / 'a.pdf', 'plain')
    out = tmp_path / 'out'
    tool.run(root, out)
    (row,) = rows(out)
    assert row['form'] == 'NHIS_PAYMENT'
    assert row['g1'] == {'N': 'NHIS_PAYMENT', 'W': 'NHIS_PAYMENT', 'E': 'NHIS_PAYMENT'}
    assert row['g1_decision'] == {'N': None, 'W': None, 'E': None}
    assert row['struct'] is None and row['scan'] is None


def test_wrappers_do_not_change_the_production_reading(tmp_path, fake_ocr):
    from demo.backend import ocr as demo_ocr
    paths = [build(tmp_path / f'{kind}.pdf', kind) for kind in ('plain', 'hidden', 'few', 'later', 'stencil')]

    def snapshot(path):
        result = demo_ocr.read_document(str(path), None)
        return (result.detected_doc_type, result.tier, result.confidence, result.image_quality,
                sorted(result.fields.items()), result.page_count, result.engine)
    plain = [snapshot(path) for path in paths]
    trace = tool.Trace()
    with tool.instrument(trace):
        trace.active = trace.capture = True
        wrapped = [snapshot(path) for path in paths]
    assert wrapped == plain


def test_run_refuses_existing_output_and_bad_arguments(tmp_path, fake_ocr, capsys):
    root = tmp_path / 'root'
    root.mkdir()
    out = tmp_path / 'out'
    out.mkdir()
    assert tool.main(['run', '--root', str(root), '--out', str(out)]) == 2
    assert capsys.readouterr().out.strip() == 'ERROR OUT_EXISTS'
    assert tool.main(['run', '--root', str(root), '--out', str(tmp_path / 'o2'), '--forms', 'X']) == 2
    assert capsys.readouterr().out.strip() == 'ERROR ARGUMENT_ERROR'
    assert tool.main(['nonsense']) == 2


def test_skipped_documents_keep_fixed_codes(tmp_path, fake_ocr):
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'broken.pdf').write_bytes(b'%PDF-1.7 not really')
    out = tmp_path / 'out'
    tool.run(root, out)
    (row,) = rows(out)
    assert row['code'] == 'OPEN_ERROR' and row['form'] == 'X' and row['exit'] is None


def test_validate_row_rejects_free_text():
    row = tool.blank_row('0' * 16)
    tool.validate_row(row)
    for field, value in (('exit', 'free text'), ('cause', 'X'), ('exceptions', {'local': 'bad name!'}),
                         ('key', '/abs/path')):
        broken = dict(row, **{field: value})
        with pytest.raises(Exception):
            tool.validate_row(broken)


# ---------------------------------------------------------------- crosstab


def test_crosstab_joins_existing_timing_and_scan_rows_by_key(tmp_path, fake_ocr, capsys):
    from engine_v2.tools import batch_assess, doc_timing
    root = tmp_path / 'FAKE-input'
    (root / f'{SENTINEL}-folder').mkdir(parents=True)
    build(root / f'{SENTINEL}-folder' / f'{SENTINEL}-plain.pdf', 'plain')
    build(root / f'{SENTINEL}-folder' / f'{SENTINEL}-stencil.pdf', 'stencil')
    timing_out, scan_out = tmp_path / 'timing', tmp_path / 'scan'
    doc_timing.run(root, timing_out, warmup=0)
    batch_assess.run(root, scan_out)
    capsys.readouterr()
    assert tool.main(['crosstab', '--timing', str(timing_out / 'rows.jsonl'),
                      '--scan', str(scan_out / 'results.jsonl')]) == 0
    printed = capsys.readouterr().out
    assert 'MATCH 2 2 2 0 0' in printed
    assert 'CROSS NHIS_PAYMENT NHIS_PAYMENT 1' in printed
    assert 'CROSS X NHIS_PAYMENT 1' in printed
    assert 'XTIER none NONE 0 1 1' in printed
    assert 'FALLBACK NOT_RECORDED' in printed and 'ROOT_MISMATCH' not in printed
    assert SENTINEL not in printed and str(tmp_path) not in printed


def test_crosstab_warns_when_roots_differ_and_rejects_bad_rows(tmp_path, fake_ocr, capsys):
    from engine_v2.tools import batch_assess, doc_timing
    a, b = tmp_path / 'a' / 'inner', tmp_path / 'b'
    a.mkdir(parents=True)
    b.mkdir()
    build(a / 'x.pdf', 'plain')
    build(b / 'x.pdf', 'plain')
    doc_timing.run(tmp_path / 'a', tmp_path / 'timing', warmup=0)
    batch_assess.run(b, tmp_path / 'scan')
    capsys.readouterr()
    assert tool.main(['crosstab', '--timing', str(tmp_path / 'timing' / 'rows.jsonl'),
                      '--scan', str(tmp_path / 'scan' / 'results.jsonl')]) == 0
    assert 'WARNING ROOT_MISMATCH' in capsys.readouterr().out
    bad = tmp_path / 'bad.jsonl'
    bad.write_text('{"key": "nope"}\n')
    assert tool.main(['crosstab', '--timing', str(bad), '--scan', str(tmp_path / 'scan' / 'results.jsonl')]) == 2
    assert capsys.readouterr().out.strip() == 'ERROR INPUT_INVALID'
