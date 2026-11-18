"""Synthetic-only verification of the localhost blind labeling tool."""
import json
import logging
import os
from pathlib import Path
import shutil

import pytest

from engine_v2.tools import doc_timing as timing
from engine_v2.tools import label_review as tool

SENTINEL = '가짜이름'
PORT = 8765
BASE = f'http://127.0.0.1:{PORT}'
FAIL_REASON = [['DOCUMENT_ISSUED_TOO_EARLY', 'FAIL']]


# ---------------------------------------------------------------- helpers


def row(key, decision='PASS', form='NHIS_PAYMENT', reasons=None, phase='measure', repeat=1, code='NONE',
        version=2):
    seconds = {name: 0.0 for name in timing.STAGES}
    seconds['total'] = 0.0
    if reasons is None:
        reasons = FAIL_REASON if decision == 'FAIL' else []
    result = dict(schema_version=version, key=key, engine='own', phase=phase, repeat=repeat, code=code, form=form,
                  text_layer='TEXT', pages=1, page_bin='1', first_image_later_text=0, tier='localocr',
                  decision=decision, ocr_pages=0, text_pages=1, cold_start=0.0, seconds=seconds,
                  reasons=reasons)
    if version == 1:
        del result['reasons']
    return result


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=True) + '\n' for r in rows), encoding='utf-8')
    return path


def text_pdf(path, name=SENTINEL):
    from engine_v2.tests.nhis_form_samples import text_pdf as acquisition
    return acquisition(path, name=name)


#: (decision, form) per synthetic document: 8 FAIL, 24 PASS over two forms, others outside both samples.
PLAN = ([('FAIL', 'NHIS_PAYMENT')] * 5 + [('FAIL', 'INSURANCE_4')] * 3 + [('PASS', 'NHIS_PAYMENT')] * 16 +
        [('PASS', 'INSURANCE_4')] * 8 + [('NEEDS_REVIEW', 'NHIS_PAYMENT')] * 2 + [('NOT_ASSESSED', 'X')])


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    for name in timing.DISABLED_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def corpus(tmp_path, env):
    root = tmp_path / f'FAKE-input-{SENTINEL}'
    root.mkdir()
    source = text_pdf(tmp_path / 'source.pdf')
    rows = []
    keys = {}
    for number, (decision, form) in enumerate(PLAN):
        relative = f'person-{SENTINEL}-{number:02d}/secret-{number:02d}.pdf'
        (root / relative).parent.mkdir()
        shutil.copyfile(source, root / relative)
        key = timing.document_key(relative)
        keys[key] = (decision, form)
        rows.append(row(key, decision, form, reasons=[] if decision == 'NOT_ASSESSED' else None))
        rows.append(row(key, decision, form, reasons=[] if decision == 'NOT_ASSESSED' else None, repeat=2))
    rows.append(row(next(iter(keys)), phase='warmup', repeat=0))
    write_rows(tmp_path / 'rows.jsonl', rows)
    return dict(root=root, rows=tmp_path / 'rows.jsonl', out=tmp_path / 'labels-out', keys=keys, tmp=tmp_path)


def fake_compute(path, form):
    return dict(items=[dict(name='서류종류', value='건강보험료납부확인서'), dict(name='성명', value=SENTINEL),
                       dict(name='발급일', value='2026-03-04')], unread=['납부총액'], decision='PASS', form=form,
                tier='localocr')


def session(corpus, **kwargs):
    kwargs.setdefault('compute', fake_compute)
    return tool.prepare(corpus['rows'], corpus['root'], corpus['out'], port=PORT, **kwargs)


def client(sess):
    from fastapi.testclient import TestClient
    return TestClient(tool.create_app(sess), base_url=BASE)


def post(http, sess, url, body, **headers):
    return http.post(url, json=body, headers={'X-Label-Token': sess.token, 'Origin': BASE, **headers})


def label_everything(http, sess, status='FAIL'):
    for key in sess.queue:
        reasons = ['R3'] if status == 'FAIL' else []
        assert post(http, sess, f'/api/doc/{key}/blind', {'status': status, 'reasons': reasons}).status_code == 200
        if key in sess.c_keys:
            items = http.get(f'/api/doc/{key}/values').json()['items']
            marks = {item['name']: 'O' for item in items}
            assert post(http, sess, f'/api/doc/{key}/values', {'fields': marks}).status_code == 200


def summary_lines(text):
    return [line.split() for line in text.splitlines()]


def pick(lines, *head):
    return next(line for line in lines if line[:len(head)] == list(head))


# ---------------------------------------------------------------- samples


def test_sample_is_reproducible_stratified_and_saved(corpus):
    digest, docs = tool.load_rows(corpus['rows'])
    first = tool.draw(docs, 12, 7)
    assert first == tool.draw(docs, 12, 7)
    assert first['b'] == sorted(k for k, (d, _) in corpus['keys'].items() if d == 'FAIL')
    assert first['c_alloc'] == {'INSURANCE_4': 4, 'NHIS_PAYMENT': 8}
    assert all(docs[k]['decision'] == 'PASS' for k in first['c']) and len(first['c']) == 12
    assert tool.draw(docs, 12, 8)['c'] != first['c']

    s1 = session(corpus, sample=12, seed=7)
    plan_bytes = (corpus['out'] / 'plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    assert plan['seed'] == 7 and plan['sample'] == 12 and len(plan['rounds']) == 1
    assert plan['rounds'][0]['c'] == first['c'] and plan['rounds'][0]['b'] == first['b']
    assert plan['rounds'][0]['rows_sha256'] == digest
    s2 = session(corpus)  # seed and size come from plan.json
    assert s2.queue == s1.queue and s2.current['c'] == first['c']
    assert len(json.loads((corpus['out'] / 'plan.json').read_bytes())['rounds']) == 1

    with pytest.raises(tool.ToolError, match='PLAN_MISMATCH'):
        session(corpus, seed=8)
    plan['rounds'][0]['c_alloc'] = {'INSURANCE_4': 5, 'NHIS_PAYMENT': 7}
    (corpus['out'] / 'plan.json').write_text(json.dumps(plan))
    with pytest.raises(tool.ToolError, match='PLAN_MISMATCH'):
        session(corpus)
    plan['rounds'][0]['c'] = plan['rounds'][0]['c'][1:]  # sample and kept documents disagree
    (corpus['out'] / 'plan.json').write_text(json.dumps(plan))
    with pytest.raises(tool.ToolError, match='PLAN_INVALID'):
        session(corpus)


def test_default_sample_takes_every_pass_when_fewer_than_150(corpus):
    sess = session(corpus)
    assert len(sess.current['c']) == 24 and len(sess.current['b']) == 8
    assert sess.plan['seed'] == tool.DEFAULT_SEED and sess.plan['sample'] == tool.DEFAULT_SAMPLE
    assert len(sess.queue) == 32


def test_rows_must_be_format_two_or_later(corpus, tmp_path):
    old = write_rows(tmp_path / 'old.jsonl', [row('0' * 16, version=1)])
    with pytest.raises(tool.ToolError, match='ROWS_INVALID'):
        tool.load_rows(old)
    bad = write_rows(tmp_path / 'bad.jsonl', [dict(row('0' * 16), path='/x/secret.pdf')])
    with pytest.raises(tool.ToolError, match='ROWS_INVALID'):
        tool.load_rows(bad)


# ---------------------------------------------------------------- blind order


def test_engine_verdict_stays_hidden_until_stage_one_is_saved(corpus):
    sess = session(corpus)
    http = client(sess)
    over = http.get('/api/session').json()
    assert {entry['state'] for entry in over['queue']} == {'todo'}
    assert all(set(entry) == {'n', 'key', 'state'} for entry in over['queue'])
    # Queue order is a seeded rank over B ∪ C, never "all FAIL first".
    assert sess.queue == sorted(sess.queue, key=lambda k: tool.rank(sess.plan['seed'], 'order', k))
    positions = [i for i, k in enumerate(sess.queue) if k in set(sess.current['b'])]
    assert positions != list(range(len(sess.current['b'])))

    b_key = sess.current['b'][0]
    c_key = sess.current['c'][0]
    for key in (b_key, c_key):
        doc = http.get(f'/api/doc/{key}').json()
        assert set(doc) == {'key', 'n', 'total', 'pages', 'form', 'form_label', 'cutoff', 'label'}
        assert doc['label'] is None and doc['cutoff'] == {'basis': 'issue_date', 'min': '2026-03-03', 'max': None}
        assert 'FAIL' not in json.dumps(doc) and 'DOCUMENT_ISSUED' not in json.dumps(doc)
        assert http.get(f'/api/doc/{key}/engine').json() == {'error': 'BLIND_FIRST'}
        assert http.get(f'/api/doc/{key}/values').status_code == 409
        assert post(http, sess, f'/api/doc/{key}/values', {'fields': {'성명': 'O'}}).status_code == 409

    assert post(http, sess, f'/api/doc/{b_key}/blind', {'status': 'FAIL', 'reasons': ['R3']}).status_code == 200
    assert http.get(f'/api/doc/{b_key}/engine').json() == {
        'decision': 'FAIL', 'reasons': FAIL_REASON, 'needs_values': False, 'values_done': False}
    assert http.get(f'/api/doc/{b_key}/values').json() == {'error': 'NOT_IN_C'}
    assert post(http, sess, f'/api/doc/{c_key}/blind', {'status': 'PASS', 'reasons': []}).status_code == 200
    assert http.get(f'/api/doc/{c_key}/engine').json()['needs_values'] is True
    states = {entry['key']: entry['state'] for entry in http.get('/api/session').json()['queue']}
    assert states[b_key] == 'complete' and states[c_key] == 'blind_done'


def test_stage_one_body_rules(corpus):
    sess = session(corpus)
    http = client(sess)
    key = sess.queue[0]
    for body, code in [({'status': 'FAIL', 'reasons': []}, 'REASONS_REQUIRED'),
                       ({'status': 'PASS', 'reasons': ['R1']}, 'REASONS_NOT_ALLOWED'),
                       ({'status': 'MAYBE', 'reasons': []}, 'BAD_BODY'),
                       ({'status': 'FAIL', 'reasons': ['R7']}, 'BAD_BODY'),
                       ({'status': 'PASS', 'reasons': [], 'memo': SENTINEL}, 'BAD_BODY')]:
        response = post(http, sess, f'/api/doc/{key}/blind', body)
        assert response.status_code == 422 and response.json() == {'error': code}
    assert not (corpus['out'] / 'labels.jsonl').exists()


# ---------------------------------------------------------------- storage


def test_label_files_hold_codes_only(corpus, caplog, capfd):
    caplog.set_level(logging.DEBUG)
    sess = session(corpus)
    http = client(sess)
    key = sess.current['c'][0]
    assert post(http, sess, f'/api/doc/{key}/blind', {'status': 'PASS', 'reasons': []}).status_code == 200
    shown = http.get(f'/api/doc/{key}/values').json()
    assert [i['name'] for i in shown['items']] == ['서류종류', '성명', '발급일']
    assert shown['items'][1]['value'] == SENTINEL  # on screen only
    assert shown['recomputed'] == {'decision': 'PASS', 'form': 'NHIS_PAYMENT', 'tier': 'localocr', 'same': 'O'}
    for marks in ({'성명': 'O'}, {'서류종류': 'O', '성명': 'O', '발급일': 'O', SENTINEL: 'O'},
                  {'서류종류': 'O', '성명': SENTINEL, '발급일': 'O'}):
        assert post(http, sess, f'/api/doc/{key}/values', {'fields': marks}).json() == {'error': 'MARKS_INCOMPLETE'}
    assert post(http, sess, f'/api/doc/{key}/values', {'fields': {'서류종류': 'O', '성명': 'X', '발급일': 'O'},
                                                       'memo': SENTINEL}).status_code == 422
    assert post(http, sess, f'/api/doc/{key}/values',
                {'fields': {'서류종류': 'O', '성명': 'X', '발급일': 'O'}}).status_code == 200
    http.get('/api/doc/' + '../' * 3 + 'etc/passwd')
    http.get(f'/api/doc/{key}/page/99')

    records = [json.loads(line) for line in (corpus['out'] / 'labels.jsonl').read_text().splitlines()]
    assert [r['stage'] for r in records] == ['blind', 'values']
    assert set(records[0]) == {'v', 'key', 'stage', 'status', 'reasons', 'fields', 'round', 'revised', 'at',
                               'criteria'}
    assert records[1]['fields'] == [['서류종류', 'O'], ['성명', 'X'], ['발급일', 'O']]
    assert records[1]['round'] == 1 and records[0]['criteria'] == 'v0.2'
    captured = capfd.readouterr()
    texts = [(corpus['out'] / name).read_text(encoding='utf-8') for name in ('labels.jsonl', 'plan.json')]
    texts += [captured.out, captured.err, caplog.text]
    for text in texts:
        for secret in (SENTINEL, 'secret-', 'person-', str(corpus['root']), str(corpus['tmp']), '2026-03-04'):
            assert secret not in text
    with pytest.raises(ValueError):
        tool.validate_label(dict(records[1], fields=[[SENTINEL, 'O']]))
    with pytest.raises(ValueError):
        tool.validate_label(dict(records[0], memo='x'))


def test_out_must_be_outside_the_repository_and_input(corpus):
    inside = tool.REPO / '.trellis' / 'label-review-test-out'
    with pytest.raises(tool.ToolError, match='LOCATION_REJECTED'):
        tool.prepare(corpus['rows'], corpus['root'], inside, compute=fake_compute)
    assert not inside.exists()
    with pytest.raises(tool.ToolError, match='INPUT_OUTPUT_OVERLAP'):
        tool.prepare(corpus['rows'], corpus['root'], corpus['root'] / 'labels', compute=fake_compute)
    with pytest.raises(tool.ToolError, match='INPUT_OUTPUT_OVERLAP'):
        tool.prepare(corpus['rows'], corpus['root'], corpus['root'].parent, compute=fake_compute)


def test_incomplete_tail_is_ignored_by_summary_and_repaired_on_serve(corpus):
    sess = session(corpus)
    http = client(sess)
    key = sess.current['b'][0]
    post(http, sess, f'/api/doc/{key}/blind', {'status': 'FAIL', 'reasons': ['R1']})
    path = corpus['out'] / 'labels.jsonl'
    complete = path.read_bytes()
    path.write_bytes(complete + b'{"v": 1, "key": "')
    assert tool.main(['summary', '--out', str(corpus['out'])]) == 0
    assert path.read_bytes() == complete + b'{"v": 1, "key": "'
    session(corpus)
    assert path.read_bytes() == complete
    path.write_bytes(complete + b'{"broken": 1}\n')
    with pytest.raises(tool.ToolError, match='LABELS_INVALID'):
        session(corpus)


# ---------------------------------------------------------------- traversal and host


def test_keys_come_only_from_rows_and_never_leave_root(corpus, tmp_path):
    outside = text_pdf(tmp_path / 'outside.pdf')
    link_relative = 'person-link/secret-link.pdf'
    (corpus['root'] / 'person-link').mkdir()
    os.symlink(outside, corpus['root'] / link_relative)
    link_key = timing.document_key(link_relative)
    rows = [json.loads(line) for line in corpus['rows'].read_text().splitlines()]
    write_rows(corpus['rows'], rows + [row(link_key, 'FAIL')])
    sess = session(corpus)
    http = client(sess)
    assert link_key in sess.current['b'] and link_key not in sess.queue and sess.missing == 1
    assert http.get(f'/api/doc/{link_key}').json() == {'error': 'NOT_FOUND'}
    assert http.get(f'/api/doc/{link_key}/page/0').status_code == 404
    for bad in ('..%2F..%2Fetc%2Fpasswd', '..', 'ABCDEF0123456789', '0123456789abcdef0'):
        assert http.get(f'/api/doc/{bad}').status_code in (400, 404)
    assert http.get('/api/doc/0123456789abcdef').json() == {'error': 'NOT_FOUND'}  # well-formed, not in rows
    assert http.get('/static/..%2Flabel_review.py').status_code == 404
    assert http.get('/static/index.html').status_code == 404

    # A mapped file swapped for a symlink after start is refused at use time.
    key = sess.queue[0]
    path = sess.keymap[key]
    path.unlink()
    os.symlink(outside, path)
    assert http.get(f'/api/doc/{key}').json() == {'error': 'SOURCE_REJECTED'}
    assert http.get(f'/api/doc/{key}/page/0').status_code == 403


def test_pages_render_as_png(corpus):
    sess = session(corpus)
    http = client(sess)
    key = sess.queue[0]
    response = http.get(f'/api/doc/{key}/page/0?s=2')
    assert response.status_code == 200 and response.content[:8] == b'\x89PNG\r\n\x1a\n'
    assert response.headers['cache-control'] == 'no-store'
    assert "default-src 'none'" in response.headers['content-security-policy']
    assert http.get(f'/api/doc/{key}/page/1').json() == {'error': 'PAGE_RANGE'}
    assert http.get(f'/api/doc/{key}/page/0?s=9').json() == {'error': 'BAD_SCALE'}


def test_bind_address_is_fixed_and_requests_are_checked(corpus, monkeypatch):
    assert tool.HOST == '127.0.0.1'
    args = ['serve', '--rows', str(corpus['rows']), '--root', str(corpus['root']), '--out', str(corpus['out'])]
    assert tool.main(args + ['--host', '0.0.0.0']) == 2
    assert not corpus['out'].exists()
    calls = []
    import uvicorn
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(timing, 'own_available', lambda: True)
    assert tool.main(args + ['--port', '8799']) == 0
    assert calls[0]['host'] == '127.0.0.1' and calls[0]['port'] == 8799 and calls[0]['access_log'] is False

    sess = session(corpus)
    http = client(sess)
    key = sess.queue[0]
    assert http.get('/api/session', headers={'Host': 'evil.example:8765'}).json() == {'error': 'HOST_REJECTED'}
    assert http.get('/api/session', headers={'Host': f'127.0.0.1:{PORT}'}).status_code == 200
    assert http.get('/api/session', headers={'Host': f'localhost:{PORT}'}).status_code == 200
    body = {'status': 'PASS', 'reasons': []}
    assert http.post(f'/api/doc/{key}/blind', json=body).json() == {'error': 'TOKEN_REJECTED'}
    assert post(http, sess, f'/api/doc/{key}/blind', body, Origin='http://evil.example').status_code == 403
    assert http.post(f'/api/doc/{key}/blind', content=json.dumps(body),
                     headers={'X-Label-Token': sess.token, 'Content-Type': 'text/plain'}).status_code == 403
    assert http.delete(f'/api/doc/{key}/blind').status_code == 405
    assert not (corpus['out'] / 'labels.jsonl').exists()


def test_screen_uses_no_external_resources():
    for name in ('index.html', 'app.js', 'app.css'):
        text = (tool.STATIC / name).read_text(encoding='utf-8')
        for marker in ('http://', 'https://', '//cdn', '@import', 'url('):
            assert marker not in text, (name, marker)


# ---------------------------------------------------------------- statistics


def test_clopper_pearson_bounds():
    assert tool.cp_lower(0, 0) is None and tool.cp_upper(0, 0) is None
    # Zero errors: closed forms from the measurement definitions.
    assert tool.cp_lower(10, 10) == pytest.approx(0.05 ** (1 / 10))
    assert tool.cp_upper(0, 150) == pytest.approx(1 - 0.05 ** (1 / 150))
    assert tool.cp_lower(10, 10) == pytest.approx(tool._solve(10, 10, 0.05), abs=1e-12)
    assert tool.cp_upper(0, 150) == pytest.approx(tool._solve(150, 1, 0.95), abs=1e-12)
    # One error, many errors (reference values: scipy.stats.beta.ppf).
    assert tool.cp_lower(9, 10) == pytest.approx(0.6058366975634952, abs=1e-9)
    assert tool.cp_lower(1, 10) == pytest.approx(0.005116196891823701, abs=1e-9)
    assert tool.cp_upper(1, 150) == pytest.approx(0.03123381692094287, abs=1e-9)
    assert tool.cp_lower(45, 50) == pytest.approx(0.8011669974835816, abs=1e-9)
    assert tool.cp_upper(3, 150) == pytest.approx(0.050877067978523934, abs=1e-9)
    assert tool.cp_lower(0, 5) == 0.0 and tool.cp_upper(5, 5) == 1.0


def test_clopper_pearson_matches_scipy_when_available():
    stats = pytest.importorskip('scipy.stats')
    for k, n in [(1, 2), (7, 9), (100, 130), (149, 150)]:
        assert tool.cp_lower(k, n) == pytest.approx(stats.beta.ppf(0.05, k, n - k + 1), abs=1e-9)
    for k, n in [(1, 2), (2, 9), (5, 150), (1, 3)]:
        assert tool.cp_upper(k, n) == pytest.approx(stats.beta.ppf(0.95, k + 1, n - k), abs=1e-9)


def _plan_and_records():
    keys = [f'{i:016x}' for i in range(1, 10)]
    b, c = keys[:5], keys[5:]
    docs = {k: dict(form='NHIS_PAYMENT', decision='FAIL', reasons=FAIL_REASON) for k in b}
    docs.update({k: dict(form='INSURANCE_4', decision='PASS', reasons=[]) for k in c})
    plan = dict(schema_version=1, criteria='v0.1', seed=1, sample=150, cross_size=20, cross=None, rounds=[dict(
        round=1, rows_sha256='0' * 64, created='2026-11-17T00:00:00+09:00',
        counts=dict(documents=9, PASS=4, FAIL=5, NEEDS_REVIEW=0, NOT_ASSESSED=0, ERROR=0),
        b=b, c=c, c_alloc={'INSURANCE_4': 4}, docs=docs)])
    blind = ['FAIL', 'FAIL', 'FAIL', 'PASS', 'HOLD', 'PASS', 'PASS', 'NEEDS_REVIEW', 'HOLD']
    records = [tool.label(k, 'blind', status=s, reasons=['R3'] if s == 'FAIL' else []) for k, s in zip(keys, blind)]
    marks = [['O', 'O'], ['O', 'X'], ['O', 'O'], ['O', 'O']]
    records += [tool.label(k, 'values', fields=[('성명', m[0]), ('발급일', m[1])], round_number=1)
                for k, m in zip(c, marks)]
    return tool.validate_plan(plan), records


def test_summary_reports_hold_both_ways():
    plan, records = _plan_and_records()
    lines = summary_lines(tool.summarize(plan, records))
    b_excl, b_hold = pick(lines, 'B', 'EXCL_HOLD'), pick(lines, 'B', 'HOLD_AS_WRONG')
    assert b_excl[2:4] == ['3', '4'] and float(b_excl[4]) == pytest.approx(tool.cp_lower(3, 4), abs=1e-4)
    assert b_hold[2:4] == ['3', '5'] and float(b_hold[4]) == pytest.approx(tool.cp_lower(3, 5), abs=1e-4)
    c_excl, c_hold = pick(lines, 'C', 'EXCL_HOLD'), pick(lines, 'C', 'HOLD_AS_WRONG')
    assert c_excl[2:4] == ['1', '3'] and float(c_excl[4]) == pytest.approx(tool.cp_upper(1, 3), abs=1e-4)
    assert c_hold[2:4] == ['2', '4'] and float(c_hold[4]) == pytest.approx(tool.cp_upper(2, 4), abs=1e-4)
    assert pick(lines, 'C_DETAIL', 'TRUTH_NEEDS_REVIEW')[2] == '1'
    assert pick(lines, 'C_DETAIL', 'VALUE_X')[2] == '1'
    assert pick(lines, 'R_CODE', 'B', 'R3')[3] == '3'
    assert pick(lines, 'ENGINE_FAIL_REASON', 'DOCUMENT_ISSUED_TOO_EARLY')[2:] == ['5', '3', '1']
    assert pick(lines, 'BY_FORM', 'C', 'INSURANCE_4')[3:] == ['4', '2', '1', '0', '1', '1']
    assert pick(lines, 'VALUE_ITEM', 'INSURANCE_4', '발급일')[3:] == ['3', '1']

    # All B right, no C wrong: the zero-error closed forms.
    clean = [r for r in records if r['stage'] == 'blind' and r['key'] in plan['rounds'][0]['b']]
    clean = [dict(r, status='FAIL', reasons=['R3']) for r in clean]
    lines = summary_lines(tool.summarize(plan, records + clean))
    assert float(pick(lines, 'B', 'EXCL_HOLD')[4]) == pytest.approx(0.05 ** (1 / 5), abs=1e-4)


def test_summary_text_has_codes_and_numbers_only():
    plan, records = _plan_and_records()
    text = tool.summarize(plan, records)
    allowed = set(tool.STATES) | set(tool.REASONS) | tool.ALL_ITEMS | set(timing.DECISIONS) | set(tool.timing.batch.KINDS)
    for line in summary_lines(text):
        for token in line:
            assert (token.replace('.', '').replace('_', '').isalnum() and token.isascii()) or token in allowed, token


# ---------------------------------------------------------------- additional rounds


def test_new_rows_reuse_labels_and_add_only_new_documents(corpus):
    sess = session(corpus)
    http = client(sess)
    label_everything(http, sess, status='FAIL')
    before = (corpus['out'] / 'labels.jsonl').read_bytes()
    first = summary_lines(tool.summarize(sess.plan, sess.records))

    # Final run: one old PASS became FAIL, one new FAIL and one new PASS document appear.
    rows = [json.loads(line) for line in corpus['rows'].read_text().splitlines()]
    flipped = sess.current['c'][0]
    for item in rows:
        if item['key'] == flipped:
            item.update(decision='FAIL', reasons=FAIL_REASON)
    source = next(iter(sess.keymap.values()))
    added = {}
    for name, decision in (('new-fail', 'FAIL'), ('new-pass', 'PASS')):
        relative = f'person-{name}/secret-{name}.pdf'
        (corpus['root'] / relative).parent.mkdir()
        shutil.copyfile(source, corpus['root'] / relative)
        added[decision] = timing.document_key(relative)
        rows.append(row(added[decision], decision, 'NHIS_PAYMENT'))
    write_rows(corpus['tmp'] / 'rows-final.jsonl', rows)

    second = tool.prepare(corpus['tmp'] / 'rows-final.jsonl', corpus['root'], corpus['out'], port=PORT,
                          compute=fake_compute)
    assert (corpus['out'] / 'labels.jsonl').read_bytes() == before
    assert [r['round'] for r in second.plan['rounds']] == [1, 2] and second.current['round'] == 2
    assert flipped in second.current['b'] and added['FAIL'] in second.current['b']
    assert added['PASS'] in second.current['n']
    over = client(second).get('/api/session').json()
    states = {entry['key']: entry['state'] for entry in over['queue']}
    todo = {k for k, s in states.items() if s == 'todo'}
    assert todo == {added['FAIL'], added['PASS']}
    # Truth labels are reused; only the per-run key-value O/X is redone for C members.
    assert {k for k, s in states.items() if s == 'blind_done'} == set(second.current['c']) - {added['PASS']}
    assert states[flipped] == 'complete'
    # The earlier round's numbers do not change.
    assert summary_lines(tool.summarize(second.plan, second.records, 1))[3:] == first[3:]  # after the RUN line
    lines = summary_lines(tool.summarize(second.plan, second.records))
    assert pick(lines, 'SAMPLE', 'B')[2:4] == ['10', '9']
    assert pick(lines, 'C_DETAIL', 'VALUES_PENDING')[2] == '23'


# ---------------------------------------------------------------- cross-check


def test_cross_check_is_blind_and_reports_agreement(corpus):
    sess = session(corpus)
    http = client(sess)
    assert post(http, sess, '/api/cross/start', {}).json() == {'error': 'MAIN_INCOMPLETE'}
    label_everything(http, sess, status='PASS')
    assert post(http, sess, '/api/cross/start', {}).json() == {'started': 'O'}
    cross = sess.plan['cross']['keys']
    assert len(cross) == 20 and set(cross) <= set(sess.queue)
    expected = sorted(sess.queue, key=lambda k: tool.rank(sess.plan['seed'], 'cross', k))[:20]
    assert cross == sorted(expected)
    assert json.loads((corpus['out'] / 'plan.json').read_text())['cross']['keys'] == cross
    post(http, sess, '/api/cross/start', {})
    assert sess.plan['cross']['keys'] == cross  # frozen

    over = http.get('/api/session').json()
    assert [entry['key'] for entry in over['cross']] == sess.cross_queue()
    first = over['cross'][0]['key']
    doc = http.get(f'/api/cross/{first}').json()
    assert doc['label'] is None and 'decision' not in doc  # neither the earlier label nor the verdict
    outsider = next(k for k in sess.queue if k not in cross)
    assert http.get(f'/api/cross/{outsider}').json() == {'error': 'NOT_FOUND'}

    for number, key in enumerate(sess.cross_queue()):
        body = {'status': 'PASS', 'reasons': []} if number < 15 else {'status': 'FAIL', 'reasons': ['R4']}
        assert post(http, sess, f'/api/cross/{key}', body).status_code == 200
    lines = summary_lines(tool.summarize(sess.plan, sess.records))
    assert [line for line in lines if line[0] == 'CROSS'][1][1:] == ['20', '20', '15', '0.7500', '15', '0.7500']
    blind = {(r['key']) for r in sess.records if r['stage'] == 'blind'}
    assert len(blind) == len(sess.queue)  # cross labels never overwrite the main labels


def test_cross_keys_stay_usable_after_a_new_round(corpus):
    sess = session(corpus)
    http = client(sess)
    label_everything(http, sess, status='PASS')
    post(http, sess, '/api/cross/start', {})
    dropped = sess.plan['cross']['keys'][0]
    rows = [json.loads(line) for line in corpus['rows'].read_text().splitlines()]
    for item in rows:
        if item['key'] == dropped:
            item.update(decision='NEEDS_REVIEW', reasons=[['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']])
    write_rows(corpus['tmp'] / 'rows-final.jsonl', rows)
    second = tool.prepare(corpus['tmp'] / 'rows-final.jsonl', corpus['root'], corpus['out'], port=PORT,
                          compute=fake_compute)
    assert dropped not in second.queue and dropped in second.cross_queue()
    http = client(second)
    assert http.get(f'/api/cross/{dropped}').json()['form'] == sess.current['docs'][dropped]['form']
    assert post(http, second, f'/api/cross/{dropped}', {'status': 'PASS', 'reasons': []}).status_code == 200


# ---------------------------------------------------------------- service path


def test_values_come_from_the_service_path_and_stay_on_screen(env, tmp_path):
    path = text_pdf(tmp_path / 'acquisition.pdf')
    result = tool.compute_values(path, 'NHIS_ACQUISITION_LOSS')
    assert result['form'] == 'NHIS_ACQUISITION_LOSS' and result['decision'] in timing.DECISIONS
    assert result['tier'] in timing.TIERS
    values = {item['name']: item['value'] for item in result['items']}
    assert values['성명'] == SENTINEL and values['서류종류'] == '건강보험자격득실확인서'
    assert set(values) | set(result['unread']) == set(tool.item_names('NHIS_ACQUISITION_LOSS'))
    assert os.environ.get('JBAI_API_KEY') is None and os.environ.get('UPSTAGE_API_KEY') is None


def test_cli_errors_print_codes_only(corpus, capsys):
    assert tool.main(['summary', '--out', str(corpus['out'])]) == 2
    assert capsys.readouterr().out == 'ERROR INPUT_UNAVAILABLE\n'
    assert tool.main(['serve', '--rows', str(corpus['tmp'] / 'missing.jsonl'), '--root', str(corpus['root']),
                      '--out', str(corpus['out'])]) == 2
    out = capsys.readouterr().out
    assert out == 'ERROR INPUT_UNAVAILABLE\n' and SENTINEL not in out
    assert tool.main(['serve', '--rows', str(corpus['rows']), '--root', str(corpus['root']), '--out',
                      str(corpus['out']), '--port', '80']) == 2


# ---------------------------------------------------------------- per-form checks and criteria v0.2


def test_checks_read_values_from_the_measurement_criteria(env, monkeypatch):
    from engine import config as engine_config
    from demo.backend.ocr import file_evidence
    from demo.backend.rules.criteria import default_criteria
    criteria = default_criteria('double_savings')
    payment = tool.checks('NHIS_PAYMENT')
    text = ' '.join(item['text'] for item in payment)
    assert all(month in text for month in criteria['nhis_payment_months'])
    assert '2026-03-03 이후' in text and timing.requirement('NHIS_PAYMENT').label in text
    assert str(engine_config.IMAGE_QUALITY_THRESHOLD) in text and f'{file_evidence.MIN_SHORT_EDGE}px' in text
    assert {code for item in payment for code in item['codes']} == {'R1', 'R2', 'R3', 'R4', 'R5'}
    assert all(item['source'] for item in payment)
    years = ' '.join(item['text'] for item in tool.checks('NHIS_ACQUISITION_LOSS'))
    assert f"최근 {criteria['nhis_acquisition_loss_years']}년" in years
    consent = tool.checks('ADMIN_INFO_CONSENT')
    assert [item['codes'] for item in consent if 'R6' in item['codes']] == [['R6'], ['R6']]
    assert '발급일 기준 없음' in [item['text'] for item in consent]
    resident = [item for item in tool.checks('RESIDENT_ABSTRACT') if item['codes'] in (['R2'], ['R5'])]
    assert len(resident) == 3
    assert tool.checks('X') == [] and tool.checks('DAILY_WORK_RECORD') == []

    # Values follow the slot, not text baked into the tool.
    from copy import deepcopy
    changed = deepcopy(timing.requirement('NHIS_PAYMENT'))
    changed.premium_months = ['2024-01']
    monkeypatch.setattr(timing, 'requirement', lambda form: changed)
    assert '2024-01' in ' '.join(item['text'] for item in tool.checks('NHIS_PAYMENT'))


def test_checks_endpoint_is_per_form_and_verdict_free(corpus):
    sess = session(corpus)
    http = client(sess)
    data = http.get('/api/checks').json()
    assert set(data) == {'NHIS_PAYMENT', 'INSURANCE_4'}
    assert set(data['NHIS_PAYMENT']) == {'label', 'items'} and data['NHIS_PAYMENT']['items'] == tool.checks('NHIS_PAYMENT')
    text = json.dumps(data, ensure_ascii=False)
    for secret in ('FAIL', 'PASS', 'DOCUMENT_ISSUED', SENTINEL, *sess.queue):
        assert secret not in text
    key = sess.queue[0]
    assert http.get(f'/api/doc/{key}/engine').json() == {'error': 'BLIND_FIRST'}


def test_fail_is_not_saved_without_a_reason_code(corpus):
    sess = session(corpus)
    http = client(sess)
    key = sess.queue[0]
    response = post(http, sess, f'/api/doc/{key}/blind', {'status': 'FAIL', 'reasons': []})
    assert response.status_code == 422 and response.json() == {'error': 'REASONS_REQUIRED'}
    assert not (corpus['out'] / 'labels.jsonl').exists() and sess.blind(key) is None
    assert post(http, sess, f'/api/doc/{key}/blind', {'status': 'FAIL', 'reasons': ['R5', 'R2']}).status_code == 200
    assert sess.blind(key)['reasons'] == ['R2', 'R5']
    app_js = (tool.STATIC / 'app.js').read_text(encoding='utf-8')
    assert "app.status === 'FAIL' && !app.reasons.size" in app_js  # the screen refuses before sending


def test_v01_labels_stay_and_summary_counts_versions(corpus):
    sess = session(corpus)
    plan_path = corpus['out'] / 'plan.json'
    plan = json.loads(plan_path.read_text())
    plan['criteria'] = 'v0.1'  # an out folder started with the v0.1 tool
    plan_path.write_text(json.dumps(plan))
    old_key, new_key = sess.current['b'][:2]
    old = dict(tool.label(old_key, 'blind', status='FAIL', reasons=['R3']), criteria='v0.1')
    tool.append_label(corpus['out'], old)
    before = (corpus['out'] / 'labels.jsonl').read_bytes()

    sess = session(corpus)
    assert sess.plan['criteria'] == 'v0.1' and sess.blind(old_key)['criteria'] == 'v0.1'
    http = client(sess)
    assert post(http, sess, f'/api/doc/{new_key}/blind', {'status': 'PASS', 'reasons': []}).status_code == 200
    data = (corpus['out'] / 'labels.jsonl').read_bytes()
    assert data.startswith(before)
    assert json.loads(data.splitlines()[-1])['criteria'] == tool.CRITERIA == 'v0.2'
    lines = summary_lines(tool.summarize(sess.plan, sess.records))
    assert pick(lines, 'LABEL_VERSION', 'blind', 'v0.1')[3] == '1'
    assert pick(lines, 'LABEL_VERSION', 'blind', 'v0.2')[3] == '1'
    with pytest.raises(ValueError):
        tool.validate_label(dict(old, criteria='v9.9'))


# ---------------------------------------------------------------- mismatch listing


def test_mismatch_lists_ordinals_and_codes_only(corpus, capsys):
    import re
    sess = session(corpus)
    http = client(sess)
    b, c = sess.current['b'], sess.current['c']

    def blind(key, status, reasons=()):
        assert post(http, sess, f'/api/doc/{key}/blind', {'status': status, 'reasons': list(reasons)}).status_code == 200

    def marks(key, x=()):
        names = [item['name'] for item in http.get(f'/api/doc/{key}/values').json()['items']]
        body = {'fields': {name: 'X' if name in x else 'O' for name in names}}
        assert post(http, sess, f'/api/doc/{key}/values', body).status_code == 200

    blind(b[0], 'FAIL', ['R3'])                       # agrees: not listed
    blind(b[1], 'NEEDS_REVIEW')                       # listed
    blind(b[2], 'HOLD')                               # listed
    blind(c[0], 'PASS'); marks(c[0])                  # agrees: not listed
    blind(c[1], 'PASS'); marks(c[1], x=('성명', '발급일'))  # listed with X items
    blind(c[2], 'FAIL', ['R5', 'R2']); marks(c[2])    # listed
    blind(c[3], 'PASS')                               # values pending, nothing known yet: not listed
    blind(c[4], 'NEEDS_REVIEW')                       # listed, values pending

    capsys.readouterr()
    assert tool.main(['mismatch', '--out', str(corpus['out'])]) == 0
    out = capsys.readouterr().out
    lines = [line.split() for line in out.splitlines()]
    assert lines[0][0] == 'MISMATCH' and lines[-1] == ['MISMATCH_COUNT', '5']
    rows = {int(line[2]): line for line in lines[1:-1]}
    number = {key: sess.queue.index(key) + 1 for key in sess.queue}
    assert set(rows) == {number[k] for k in (b[1], b[2], c[1], c[2], c[4])}
    assert rows[number[b[1]]][3:] == ['B', 'NHIS_PAYMENT', 'FAIL', 'DOCUMENT_ISSUED_TOO_EARLY', 'NEEDS_REVIEW', '-', '-']
    assert rows[number[b[2]]][7] == 'HOLD'
    assert rows[number[c[1]]][3:] == ['C', sess.current['docs'][c[1]]['form'], 'PASS', '-', 'PASS', '-', '성명,발급일']
    assert rows[number[c[2]]][7:] == ['FAIL', 'R2,R5', '-']
    assert rows[number[c[4]]][7:] == ['NEEDS_REVIEW', '-', 'VALUES_PENDING']

    # Never a path, file name, read value or document content: ordinals and codes only.
    for marker in ('/', '\\', '.pdf', '.PDF', SENTINEL, 'secret', 'person', corpus['root'].name, corpus['out'].name):
        assert marker not in out, marker
    assert not re.search(r'\d{4}\s*[-./년]\s*\d{1,2}', out)
    assert not re.search(r'\d{1,2}\s*[./]\s*\d{1,2}\s*[./]\s*\d{2,4}', out)
    assert not any(key in out for key in sess.queue)
    assert tool.main(['mismatch', '--out', str(corpus['tmp'] / 'missing')]) == 2
    assert capsys.readouterr().out == 'ERROR INPUT_UNAVAILABLE\n'


# ---------------------------------------------------------------- round two carry-over


def test_round_two_labels_only_new_and_revalued_documents(tmp_path, env, capsys):
    """Three round-one labels; round two flips one decision, adds a PASS and a FAIL, revalues one form."""
    import re
    root = tmp_path / f'FAKE-input-{SENTINEL}'
    root.mkdir()
    source = text_pdf(tmp_path / 'source.pdf')
    keys = {}
    for name in ('revalued', 'kept', 'flipped', 'new-pass', 'new-fail'):
        relative = f'person-{SENTINEL}-{name}/secret-{name}.pdf'
        (root / relative).parent.mkdir()
        shutil.copyfile(source, root / relative)
        keys[name] = timing.document_key(relative)
    k = keys
    first_rows = [row(k['revalued'], 'PASS', 'NHIS_PAYMENT'), row(k['kept'], 'PASS', 'INSURANCE_4'),
                  row(k['flipped'], 'PASS', 'INSURANCE_4')]
    out = tmp_path / 'labels-out'
    first = tool.prepare(write_rows(tmp_path / 'rows-1.jsonl', first_rows), root, out, port=PORT,
                         compute=fake_compute)
    assert set(first.queue) == {k['revalued'], k['kept'], k['flipped']}
    http = client(first)
    for name, status, x in (('revalued', 'PASS', ()), ('kept', 'PASS', ('성명',)), ('flipped', 'PASS', ())):
        key = k[name]
        assert post(http, first, f'/api/doc/{key}/blind', {'status': status, 'reasons': []}).status_code == 200
        names = [item['name'] for item in http.get(f'/api/doc/{key}/values').json()['items']]
        marks = {item: 'X' if item in x else 'O' for item in names}
        assert post(http, first, f'/api/doc/{key}/values', {'fields': marks}).status_code == 200
    assert http.get(f'/api/doc/{k["kept"]}').json()['label']['inherited'] is None  # labeled in this round
    before = (out / 'labels.jsonl').read_bytes()

    # Round two: one decision flips (PASS → NEEDS_REVIEW), a new PASS and a new FAIL appear, and the
    # NHIS_PAYMENT extraction changed, so only that form's key values are checked again.
    second_rows = [row(k['revalued'], 'PASS', 'NHIS_PAYMENT'), row(k['kept'], 'PASS', 'INSURANCE_4'),
                   row(k['flipped'], 'NEEDS_REVIEW', 'INSURANCE_4',
                       reasons=[['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']]),
                   row(k['new-pass'], 'PASS', 'INSURANCE_4'), row(k['new-fail'], 'FAIL', 'NHIS_PAYMENT')]
    rows_two = write_rows(tmp_path / 'rows-2.jsonl', second_rows)
    capsys.readouterr()
    second = tool.prepare(rows_two, root, out, port=PORT, compute=fake_compute,
                          revalue=tool.parse_forms('NHIS_PAYMENT'))
    console = capsys.readouterr().out
    assert (out / 'labels.jsonl').read_bytes() == before
    assert second.current['round'] == 2 and second.current['revalue'] == ['NHIS_PAYMENT']
    assert set(second.current['b']) == {k['new-fail']}
    assert set(second.current['c']) == {k['revalued'], k['kept']}
    assert k['flipped'] not in second.queue

    http = client(second)
    states = {entry['key']: entry['state'] for entry in http.get('/api/session').json()['queue']}
    # Stage one is needed only for the new PASS and the new FAIL; the revalued form needs O/X again.
    assert {key for key, state in states.items() if state == 'todo'} == {k['new-pass'], k['new-fail']}
    assert states[k['revalued']] == 'blind_done' and states[k['kept']] == 'complete'
    assert http.get(f'/api/doc/{k["kept"]}').json()['label']['inherited'] == 1
    assert http.get(f'/api/doc/{k["revalued"]}').json()['label']['inherited'] == 1
    assert http.get(f'/api/doc/{k["new-pass"]}').json()['label'] is None
    kept = http.get(f'/api/doc/{k["kept"]}/values').json()
    assert kept['inherited'] == 1 and {i['name']: i['mark'] for i in kept['items']}['성명'] == 'X'
    revalued = http.get(f'/api/doc/{k["revalued"]}/values').json()
    assert revalued['inherited'] is None and all(item['mark'] is None for item in revalued['items'])

    # Re-serving the same rows keeps the stored revalue list.
    again = tool.prepare(rows_two, root, out, port=PORT, compute=fake_compute)
    assert again.current['round'] == 2 and again.current['revalue'] == ['NHIS_PAYMENT']

    lines = summary_lines(tool.summarize(second.plan, second.records))
    assert [line for line in lines if line[0] == 'REVALUE'][1] == ['REVALUE', 'NHIS_PAYMENT']
    assert pick(lines, 'INHERITED', 'C')[2:] == ['2', '1'] and pick(lines, 'INHERITED', 'B')[2:] == ['0', '0']
    assert pick(lines, 'SAMPLE', 'C')[2:] == ['2', '2', '1']
    assert pick(lines, 'C_DETAIL', 'VALUES_PENDING')[2] == '1'
    assert pick(lines, 'C_DETAIL', 'VALUES_INHERITED')[2] == '1'
    assert pick(lines, 'C', 'EXCL_HOLD')[2:4] == ['1', '1']  # the carried X on the kept document
    assert pick(lines, 'TRANSITION', 'C', 'PASS', 'PASS', 'C')[5:] == ['2', '2', '0', '0', '0']
    assert pick(lines, 'TRANSITION', 'C', 'PASS', 'NEEDS_REVIEW', 'OUT')[5:] == ['1', '1', '0', '0', '0']
    assert pick(lines, 'TRANSITION_CHANGED') == ['TRANSITION_CHANGED', '1']

    # Finish round two: only the targets are labeled; the carried O/X is never asked again.
    post(http, second, f'/api/doc/{k["new-fail"]}/blind', {'status': 'FAIL', 'reasons': ['R3']})
    post(http, second, f'/api/doc/{k["new-pass"]}/blind', {'status': 'PASS', 'reasons': []})
    for key in (k['new-pass'], k['revalued']):
        names = [item['name'] for item in http.get(f'/api/doc/{key}/values').json()['items']]
        assert post(http, second, f'/api/doc/{key}/values', {'fields': {n: 'O' for n in names}}).status_code == 200
    assert second.main_complete()
    lines = summary_lines(tool.summarize(second.plan, second.records))
    assert pick(lines, 'B', 'EXCL_HOLD')[2:4] == ['1', '1']
    assert pick(lines, 'C', 'EXCL_HOLD')[2:4] == ['1', '2']
    assert [r['round'] for r in second.records if r['stage'] == 'values'] == [1, 1, 1, 2, 2]

    # Without the option every C document of a new round is checked again.
    plan = json.loads((out / 'plan.json').read_text())
    plan['rounds'][1]['revalue'] = None
    assert tool.values_record(tool.validate_plan(plan), tool.latest(second.records), 2, k['kept']) is None
    assert tool.parse_forms(None) is None
    with pytest.raises(tool.ToolError):
        tool.parse_forms('NHIS_PAYMENT,BOGUS')

    capsys.readouterr()
    assert tool.main(['summary', '--out', str(out)]) == 0
    assert tool.main(['mismatch', '--out', str(out)]) == 0
    text = console + capsys.readouterr().out
    mismatch = [line.split() for line in text.splitlines() if line.startswith('MISMATCH ')]
    assert [line[3:] for line in mismatch[1:]] == [['C', 'INSURANCE_4', 'PASS', '-', 'PASS', '-', '성명']]

    # Codes and counts only: no path, file name, read value or date anywhere in the output or stored files.
    stored = (out / 'labels.jsonl').read_text() + (out / 'plan.json').read_text()
    for marker in ('/', '\\', '.pdf', SENTINEL, 'secret', 'person', root.name, out.name, '2026-03-04'):
        assert marker not in text, marker
    for marker in ('.pdf', SENTINEL, 'secret', 'person', root.name, '2026-03-04'):
        assert marker not in stored, marker
    assert not re.search(r'\d{4}\s*[-./년]\s*\d{1,2}', text)
    assert not re.search(r'\d{1,2}\s*[./]\s*\d{1,2}\s*[./]\s*\d{2,4}', text)
    assert not any(key in text for key in keys.values())
    assert tool.main(['serve', '--rows', str(rows_two), '--root', str(root), '--out', str(out),
                      '--revalue-forms', 'BOGUS']) == 2
    assert capsys.readouterr().out == 'ERROR ARGUMENT_ERROR\n'


# ---------------------------------------------------------------- new-PASS census set N


def test_round_two_keeps_the_c_sample_and_labels_every_new_pass(tmp_path, env, capsys):
    """Round-1 C = 3 of 5 PASS (one turns NEEDS_REVIEW), two NEEDS_REVIEW turn PASS (→ N), one new FAIL."""
    import re
    root = tmp_path / f'FAKE-input-{SENTINEL}'
    root.mkdir()
    source = text_pdf(tmp_path / 'source.pdf')
    keys = {}
    names = [f'pass-{i}' for i in range(5)] + ['review-0', 'review-1', 'new-fail']
    for name in names:
        relative = f'person-{SENTINEL}-{name}/secret-{name}.pdf'
        (root / relative).parent.mkdir()
        shutil.copyfile(source, root / relative)
        keys[name] = timing.document_key(relative)
    review = [['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']]
    first_rows = [row(keys[f'pass-{i}'], 'PASS', 'INSURANCE_4') for i in range(5)]
    first_rows += [row(keys[name], 'NEEDS_REVIEW', 'NHIS_PAYMENT', reasons=review) for name in ('review-0', 'review-1')]
    out = tmp_path / 'labels-out'
    rows_one = write_rows(tmp_path / 'rows-1.jsonl', first_rows)
    first = tool.prepare(rows_one, root, out, port=PORT, compute=fake_compute, sample=3)
    c_one = list(first.current['c'])
    assert len(c_one) == 3 and first.current['n'] == [] and first.current['b'] == []
    http = client(first)
    for key in c_one:
        assert post(http, first, f'/api/doc/{key}/blind', {'status': 'PASS', 'reasons': []}).status_code == 200
        names_shown = [item['name'] for item in http.get(f'/api/doc/{key}/values').json()['items']]
        assert post(http, first, f'/api/doc/{key}/values', {'fields': {n: 'O' for n in names_shown}}).status_code == 200

    flipped = c_one[0]
    second_rows = []
    for item in first_rows:
        item = dict(item)
        if item['key'] == flipped:
            item.update(decision='NEEDS_REVIEW', reasons=review)
        elif item['decision'] == 'NEEDS_REVIEW':
            item.update(decision='PASS', reasons=[])
        second_rows.append(item)
    second_rows.append(row(keys['new-fail'], 'FAIL', 'NHIS_PAYMENT'))
    rows_two = write_rows(tmp_path / 'rows-2.jsonl', second_rows)

    # A plan written before N has no round-1 PASS keys: round two asks for the round-1 rows once.
    plan = json.loads((out / 'plan.json').read_text())
    del plan['rounds'][0]['pass_keys']
    (out / 'plan.json').write_text(json.dumps(plan))
    with pytest.raises(tool.ToolError) as error:
        tool.prepare(rows_two, root, out, port=PORT, compute=fake_compute)
    assert error.value.args[0] == 'BASE_ROWS_REQUIRED'
    with pytest.raises(tool.ToolError) as error:
        tool.prepare(rows_two, root, out, port=PORT, compute=fake_compute, base_rows=rows_two)
    assert error.value.args[0] == 'PLAN_MISMATCH'  # not the round-1 file
    capsys.readouterr()
    second = tool.prepare(rows_two, root, out, port=PORT, compute=fake_compute, base_rows=rows_one)
    console = capsys.readouterr().out
    assert second.plan['rounds'][0]['pass_keys'] == sorted(keys[f'pass-{i}'] for i in range(5))

    # C is the round-1 sample minus the flipped document (not drawn again); N is exactly the two new PASS.
    assert second.current['c'] == sorted(c_one[1:])
    redrawn = tool.draw({item['key']: dict(form=item['form'], decision=item['decision']) for item in second_rows},
                        3, second.plan['seed'])['c']
    assert len(redrawn) == 3 and len(second.current['c']) == 2
    assert second.current['n'] == sorted([keys['review-0'], keys['review-1']])
    assert second.current['b'] == [keys['new-fail']]
    assert flipped not in second.queue and set(second.queue) == set(second.current['c'] + second.current['n'] +
                                                                    second.current['b'])
    http = client(second)
    states = {entry['key']: entry['state'] for entry in http.get('/api/session').json()['queue']}
    assert {k for k, s in states.items() if s == 'todo'} == {keys['review-0'], keys['review-1'], keys['new-fail']}
    lines = summary_lines(tool.summarize(second.plan, second.records))
    assert pick(lines, 'SAMPLE', 'N')[2:] == ['2', '0', '0']
    assert pick(lines, 'PASS_COMBINED', 'EXCL_HOLD')[-2:] == ['NA', 'NA']  # N not labeled yet

    # Label round two: C values again (no --revalue-forms), N gets stage one and O/X, B stage one.
    c_keep, c_x = second.current['c']
    n_pass, n_review = keys['review-0'], keys['review-1']

    def marks(key, x=()):
        shown = [item['name'] for item in http.get(f'/api/doc/{key}/values').json()['items']]
        body = {'fields': {name: 'X' if name in x else 'O' for name in shown}}
        assert post(http, second, f'/api/doc/{key}/values', body).status_code == 200

    assert http.get(f'/api/doc/{n_pass}/values').json() == {'error': 'BLIND_FIRST'}
    post(http, second, f'/api/doc/{n_pass}/blind', {'status': 'PASS', 'reasons': []})
    post(http, second, f'/api/doc/{n_review}/blind', {'status': 'NEEDS_REVIEW', 'reasons': []})
    post(http, second, f'/api/doc/{keys["new-fail"]}/blind', {'status': 'FAIL', 'reasons': ['R3']})
    assert http.get(f'/api/doc/{n_pass}/engine').json()['needs_values'] is True
    marks(c_keep)
    marks(c_x, x=('성명',))
    marks(n_pass)
    marks(n_review)
    assert second.main_complete()

    lines = summary_lines(tool.summarize(second.plan, second.records))
    assert pick(lines, 'C', 'EXCL_HOLD')[2:4] == ['1', '2']
    assert [line for line in lines if line[0] == 'N_TOTAL'][1] == ['N_TOTAL', '2', '2', '2', '0']
    assert pick(lines, 'N', 'EXCL_HOLD')[2:] == ['1', '2', '0.5000']
    assert pick(lines, 'N_DETAIL', 'TRUTH_PASS')[2] == '1' and pick(lines, 'N_DETAIL', 'FAIL_OR_VALUE_X')[2] == '0'
    assert pick(lines, 'C_DETAIL', 'PASS_NOT_TRUTH_OR_VALUE_X')[2] == '1'
    combined = pick(lines, 'PASS_COMBINED', 'EXCL_HOLD')
    # Strict wrong (truth not PASS or any X) in both strata. Old: 4 PASS in both rounds, C labeled 2 with 1
    # wrong (value X); new: N = 2 with 1 wrong (truth NEEDS_REVIEW, missed because nobody looks at a PASS).
    assert combined[2:8] == ['4', '2', '1', '2', '2', '1']
    assert float(combined[8]) == pytest.approx((4 * 0.5 + 2 * 0.5) / 6, abs=1e-4)
    assert float(combined[9]) == pytest.approx((4 * tool.cp_upper(1, 2) + 2 * 0.5) / 6, abs=1e-4)
    assert pick(lines, 'BY_FORM', 'N', 'NHIS_PAYMENT')[3:] == ['2', '1', '1', '0', '0', '1']
    assert pick(lines, 'VALUE_ITEM_N', 'NHIS_PAYMENT', '성명')[3:] == ['2', '0']
    assert pick(lines, 'R_CODE', 'N', 'R3')[3] == '0'
    assert pick(lines, 'TRANSITION', 'C', 'PASS', 'NEEDS_REVIEW', 'OUT')[5] == '1'
    # Round one alone: no N, and PASS_COMBINED equals the C stratum.
    one = summary_lines(tool.summarize(second.plan, second.records, 1))
    assert pick(one, 'PASS_COMBINED', 'EXCL_HOLD')[2:8] == ['5', '3', '0', '0', '0', '0']

    capsys.readouterr()
    assert tool.main(['summary', '--out', str(out)]) == 0
    assert tool.main(['mismatch', '--out', str(out)]) == 0
    text = console + capsys.readouterr().out
    listed = [line.split() for line in text.splitlines() if line.startswith('MISMATCH ')][1:]
    assert sorted(line[3] for line in listed) == ['C', 'N']
    assert next(line for line in listed if line[3] == 'N')[7:] == ['NEEDS_REVIEW', '-', '-']

    # Codes and counts only: no path, file name, read value, date or key in the output or stored files.
    stored = (out / 'labels.jsonl').read_text() + (out / 'plan.json').read_text()
    for marker in ('/', '\\', '.pdf', SENTINEL, 'secret', 'person', root.name, out.name, '2026-03-04'):
        assert marker not in text, marker
    for marker in ('.pdf', SENTINEL, 'secret', 'person', root.name, '2026-03-04'):
        assert marker not in stored, marker
    assert not re.search(r'\d{4}\s*[-./년]\s*\d{1,2}', text)
    assert not re.search(r'\d{1,2}\s*[./]\s*\d{1,2}\s*[./]\s*\d{2,4}', text)
    assert not any(key in text for key in keys.values())
