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
    # 11-18 O2: production now takes E (both title fragments) when no keyword matches.
    assert [pdftext.classify_with_evidence(text)[0] for text in (broken, other, apart)] == [DocType.INSURANCE_4] * 3
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
    assert 'XCAUSE5 1 1 1 1 2 0' in printed
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
    # 11-18 O2: production classifies the interleaved title, so no candidate changes the form.
    assert row['form'] == 'INSURANCE_4'
    assert row['g1'] == {'N': 'INSURANCE_4', 'W': 'INSURANCE_4', 'E': 'INSURANCE_4'}
    assert row['g1_decision'] == {'N': None, 'W': None, 'E': None}
    assert 'G1 N 1 0 0 0 0' in (out / 'summary.txt').read_text()
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
    # 11-18 O1: production now re-reads the stencil PDF from a 300 dpi rendering and finds the form.
    assert 'CROSS NHIS_PAYMENT NHIS_PAYMENT 2' in printed
    assert 'XMATCH a_form_x matched 0 0' in printed
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


# ---------------------------------------------------------------- consent mark and payment table stages


@pytest.fixture(scope='module')
def payment_pages():
    """Synthetic government payment form with exact text-layer words as OCR output."""
    from copy import deepcopy
    from engine_v2.pipeline.ocr import OcrResult
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    from engine_v2.tools import documentai_corpus_v2 as v2
    source = next(s for s in v2.sources(0) if s.doc == 'nhis_payment')
    image, words, _ = v2.rendered(source)
    page = PageImage(0, PageSource.UPLOAD, (595.0, 842.0), png=b'', pixel_size=image.size)
    return page, deepcopy(words)


def _payment(payment_pages, cut):
    """Optionally lower the group-header boxes as the own engine did (band-cut reproduction)."""
    from copy import deepcopy
    from engine_v2.pipeline.ocr import OcrResult, OcrWord
    page, words = payment_pages
    height = page.pixel_size[1]
    changed = []
    for word in deepcopy(words):
        if cut and word.text.replace(' ', '') in ('고지금액', '납부금액'):
            x0, y0, x1, y1 = word.bbox_px
            word = OcrWord(word.text, word.confidence, (x0, y0, x1, y1 + .002 * height))
        changed.append(word)
    return [(page, OcrResult('own', changed))]


def test_payment_stage_names_the_header_band_cut_and_p1_recovers_it(payment_pages):
    from engine_v2.extractors import nhis_payment, nhis_payment_gov as gov
    original = gov._header_columns
    clean = _payment(payment_pages, cut=False)
    assert tool.payment_table_stage(clean, nhis_payment.extract(clean)) == ('GOV', 'TABLE_OK', 'NONE')
    cut = _payment(payment_pages, cut=True)
    result = nhis_payment.extract(cut)
    assert not {c.name: c.passed for c in result.validations}['payment_component_headers']
    assert tool.payment_table_stage(cut, result) == ('GOV', 'HEADER', 'HEADER_BAND_CUT')
    with tool.p1_patch(.3):
        relaxed = {c.name: c.passed for c in nhis_payment.extract(cut).validations}
    assert relaxed['payment_component_headers'] and relaxed['payment_columns']
    with tool.p1_patch(.3):
        # The margin never breaks a reading that already passes.
        assert tool.payment_table_stage(clean, nhis_payment.extract(clean))[1] == 'TABLE_OK'
    assert gov._header_columns is original
    assert tool.payment_table_stage(None, None) == ('NOT_EXTRACTED', 'NOT_EXTRACTED', 'NONE')


def test_payment_evidence_and_reason_flags_are_codes_only():
    from demo.backend.ocr.base import OcrResult
    from engine_v2.extractors import payment_completeness, payment_period
    ocr = OcrResult(fields={payment_completeness.FIELD: json.dumps({'period_status': 'READABLE',
                                                                    'printed_total_observed': True}),
                            payment_period.FIELD: '{not json'})
    evidence = tool.payment_evidence(ocr)
    assert evidence['paging'] == 'ABSENT' and evidence['fallback'] == 'NA'
    assert evidence['period_status'] == 'O' and evidence['printed_total_observed'] == 'O'
    assert evidence['arithmetic_complete'] == 'X' and evidence['period'] == 'OTHER'
    flags = tool.payment_reason_flags([['MISSING_BILLING_MONTHS', 'NEEDS_REVIEW'],
                                       ['NHIS_PAYMENT_PAGING_UNCERTAIN', 'NEEDS_REVIEW']])
    assert flags == dict(paging_uncertain='O', missing_billing='NEEDS_REVIEW', pages_incomplete='X')


def test_c1_shadow_turns_only_the_consent_quality_fail_into_review():
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules import doc_check
    from demo.backend.rules.doc_types import DocType
    original = doc_check.ESSENTIAL_FIELD_UNREADABLE_CODES
    req = tool.timing.requirement('ADMIN_INFO_CONSENT')

    def finalize(code):
        ocr = OcrResult(detected_doc_type=DocType.ADMIN_INFO_CONSENT, confidence=.9, image_quality=.5)
        result = doc_check.CheckResult('NEEDS_REVIEW', [doc_check.CheckFinding(code, 'x', severity='NEEDS_REVIEW')])
        return doc_check.finalize_image_quality(req, ocr, result, 'pdf').status
    # 11-18 O4: C1 is production; the shadow patch is now a no-op for the consent codes.
    assert finalize('ADMIN_CONSENT_MARK_UNREADABLE') == 'NEEDS_REVIEW'
    assert finalize('REQUIRED_FIELD_UNREADABLE') == 'FAIL'
    with tool.c1_patch():
        assert finalize('ADMIN_CONSENT_MARK_UNREADABLE') == 'NEEDS_REVIEW'
        assert finalize('ADMIN_CONSENT_SIGNATURE_UNREADABLE') == 'NEEDS_REVIEW'
        assert finalize('REQUIRED_FIELD_UNREADABLE') == 'FAIL'
    assert doc_check.ESSENTIAL_FIELD_UNREADABLE_CODES is original


def _consent_pdf(path, *, mark=None, raster_dpi=None, shift_pt=0):
    import pymupdf
    from demo.backend.forms import coords
    spec = coords.load('서식5')
    with pymupdf.open(spec.template) as document:
        page = document[0]
        if mark:
            box = pymupdf.Rect(*spec.fields[mark]['box'])
            page.draw_line((box.x0 + 1, box.y0 + 1), (box.x1 - 1, box.y1 - 1), color=(0, 0, 0), width=1.3)
            page.draw_line((box.x0 + 1, box.y1 - 1), (box.x1 - 1, box.y0 + 1), color=(0, 0, 0), width=1.3)
        if raster_dpi is None:
            document.save(path)
            return path
        pix = page.get_pixmap(dpi=raster_dpi, alpha=False)
        width, height = page.rect.width, page.rect.height
    from PIL import Image
    image = Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')
    canvas = Image.new('RGB', image.size, 'white')
    canvas.paste(image, (int(shift_pt * image.width / width), int(shift_pt * image.width / width)))
    with pymupdf.open() as out:
        out.new_page(width=width, height=height).insert_image(pymupdf.Rect(0, 0, width, height), stream=_png(canvas))
        out.save(path)
    return path


def test_consent_stage_reproduces_production_and_flags_print_differences(tmp_path):
    from demo.backend.ocr.admin_consent_scan import inspect_admin_consent_scan
    vector = _consent_pdf(tmp_path / 'vector.pdf', mark='agree.동의함')
    stage = tool.consent_stage(vector)
    assert inspect_admin_consent_scan(str(vector))['동의여부'] == '동의함'
    assert (stage['mark'], stage['aligned'], stage['shift'], stage['peak']) == (
        'MARK_AGREE', 'ALIGNED_AGREE', 'S_LE_3', 'PEAK_STRONG')
    blank = _consent_pdf(tmp_path / 'blank.pdf', raster_dpi=300)
    stage = tool.consent_stage(blank)
    # A blank raster of the printed form already exceeds the production ink ratio in both boxes.
    assert inspect_admin_consent_scan(str(blank))['동의여부'] == '확인필요'
    assert stage['mark'] == 'MARK_BOTH' and stage['agree_ratio'] == 'R_GE3_5'
    assert stage['aligned_inner'] == 'INNER_NONE' and stage['inner_strong'] in ('STRONG_NONE', 'STRONG_HOLD')
    moved = tool.consent_stage(_consent_pdf(tmp_path / 'moved.pdf', raster_dpi=300, shift_pt=8))
    assert moved['shift'] in ('S_3_10', 'S_GT_10')
    # Wrong-pass direction: a blank form must never read as a single mark.
    assert moved['aligned_inner'] not in ('INNER_AGREE', 'INNER_DISAGREE')
    assert moved['inner_strong'] not in ('STRONG_AGREE', 'STRONG_DISAGREE')
    assert tool.consent_stage(tmp_path / 'missing.pdf')['load'] == 'LOAD_ERROR'


def test_run_adds_consent_and_payment_rows(tmp_path, fake_ocr):
    consent_root, payment_root = tmp_path / 'consent', tmp_path / 'payment'
    consent_root.mkdir()
    payment_root.mkdir()
    _consent_pdf(consent_root / 'consent.pdf', raster_dpi=100)
    build(payment_root / 'payment.pdf', 'plain')
    fake_ocr['title'] = ('행정정보', '공동이용', '사전동의서')
    tool.run(consent_root, tmp_path / 'out_consent')
    (consent,) = rows(tmp_path / 'out_consent')
    assert consent['form'] == 'ADMIN_INFO_CONSENT' and consent['shadow_errors'] == []
    # 100 dpi original: low quality; the mark cannot be read. 11-18 O4 (C1 in production): review, not FAIL.
    assert consent['consent']['quality'] == 'Q05' and consent['consent']['mark'] == 'MARK_BOTH'
    assert consent['decision'] == 'NEEDS_REVIEW' and consent['c1'] == 'NEEDS_REVIEW'
    assert consent['payment'] is None and consent['p1'] is None
    summary = (tmp_path / 'out_consent' / 'summary.txt').read_text()
    assert 'C1_FAIL_TO_REVIEW 0' in summary and 'CONSENT_COUNT 1' in summary
    assert any(line.startswith('CONSENT_VARIANT INNER_STRONG ') for line in summary.splitlines())
    fake_ocr['title'] = PAYMENT_TITLE
    tool.run(payment_root, tmp_path / 'out_payment')
    (payment,) = rows(tmp_path / 'out_payment')
    assert payment['form'] == 'NHIS_PAYMENT' and payment['shadow_errors'] == []
    assert payment['payment']['route'] == 'LEGACY' and payment['payment']['stage'] == 'HEADER'
    # P1 wraps only the government-form header call, so a legacy reading is copied unchanged.
    assert all(value['decision'] == payment['decision'] for value in payment['p1'].values())
    assert payment['consent'] is None and payment['c1'] is None
    summary = (tmp_path / 'out_payment' / 'summary.txt').read_text()
    assert 'PAYMENT_COUNT 1' in summary and 'P1 m01 0 0 0 0 0' in summary
