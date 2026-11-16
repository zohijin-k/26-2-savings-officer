"""Independent synthetic input, denominator and disclosure tests for diagnostics."""
from copy import deepcopy
import json
import logging
import math
import os
import socket
import sqlite3
from types import SimpleNamespace

import pytest

from engine_v2.tools import own_adapter_diag as tool
from engine_v2.tools import ocr_baseline_runtime as runtime

SENTINEL = 'SYNTHETIC_SECRET_809711'
FIELDS = ['NHIS_ACQUISITION_LOSS:NAME', 'NHIS_ACQUISITION_LOSS:ISSUE_DATE']


@pytest.fixture
def locations(tmp_path):
    root, out = tmp_path/'input', tmp_path/'output'
    root.mkdir()
    return root, out


def pdf(path, *, rotate=0):
    import pymupdf
    from engine_v2.tests.nhis_form_samples import text_pdf
    text_pdf(path)
    if rotate:
        with pymupdf.open(path) as document:
            document[0].set_rotation(rotate)
            document.saveIncr()
    return path


def fake_recognize(monkeypatch, path, *, operation=None):
    import pymupdf
    from engine_v2.pipeline.ocr import OcrResult
    with pymupdf.open(path) as document:
        _, words = runtime.reference_page(document[0], 0)
    original = deepcopy(words)
    seen = []

    def recognize(engine, page):
        seen.append((engine, deepcopy(page), deepcopy(words)))
        if operation:
            return operation(engine, page, deepcopy(words))
        return OcrResult(engine, deepcopy(words)), deepcopy(words), {}

    monkeypatch.setattr(runtime, 'recognize', recognize)
    return words, original, seen


def invoke(root, out, *args):
    return tool.main(['--root', str(root), '--out', str(out), '--fields', *FIELDS, *args])


def read_rows(out):
    return [json.loads(line) for line in (out/'results.jsonl').read_text().splitlines()]


def safe_output(out, capfd):
    captured = capfd.readouterr()
    assert captured.err == ''
    assert SENTINEL not in captured.out
    if out.exists():
        for path in out.iterdir():
            assert SENTINEL.encode() not in path.read_bytes()


def test_complete_same_clean_input_and_original_words(locations, monkeypatch, capfd):
    root, out = locations
    path = pdf(root/f'{SENTINEL}.pdf')
    words, original, seen = fake_recognize(monkeypatch, path)
    assert invoke(root, out) == 0
    rows = read_rows(out)
    assert len(rows) == 4
    assert all(row['document'] == 1 and row['page'] == 1 and row['code'] == 'OK' for row in rows)
    assert all(row['exact_match'] == row['normalized_match'] == row['eligible'] == row['counted'] == 1 for row in rows)
    assert [item[0] for item in seen] == ['own', 'applevision']
    assert seen[0][1].png == seen[1][1].png
    assert seen[0][1].dpi == 300
    assert words == original
    assert all(item[2] == original for item in seen)
    meta = json.loads((out/'run.json').read_text())
    assert {p.name for p in out.iterdir()} == set(tool.FILENAMES)
    assert set(meta) == {'schema_version','engines','fields','clean','limit'}
    assert str(root) not in (out/'run.json').read_text()
    summary = json.loads((out/'summary.json').read_text())
    present = [g for g in summary['groups'] if g['match_opportunities']]
    assert len(present) == 4
    assert all(g['exact_match_rate'] == g['normalized_match_rate'] == 1 for g in present)
    absent = [g for g in summary['groups'] if not g['diagnosed']]
    assert absent and all(all(v is None for v in g['rates'].values()) for g in absent)
    safe_output(out, capfd)


def test_route_output_counts_pages_once_and_retains_missing_reference(locations, monkeypatch, capfd):
    from demo.backend.rules.doc_types import DocType
    from engine_v2.tools import own_adapter_diag_evidence as evidence
    root, out = locations
    path = pdf(root/f'{SENTINEL}.pdf')
    fake_recognize(monkeypatch, path)

    def extract(page, words, engine):
        fields = {'고지월': ['2025-10'], '발급일': '2026-11-10'}
        if engine == 'own':
            fields = {'발급일': '2026-11-10'}
        form = 'LEGACY' if engine == 'own' else 'GOVERNMENT'
        return SimpleNamespace(detected_doc_type=DocType.NHIS_PAYMENT), fields, form

    monkeypatch.setattr(evidence, 'extract_with_form', extract)
    assert tool.main(['--root', str(root), '--out', str(out)]) == 0
    rows = read_rows(out)
    assert len(rows) == 6
    own = {r['field']: r for r in rows if r['engine'] == 'own'}
    assert own['MEMBERSHIP']['code'] == 'REFERENCE_MISSING'
    assert own['BILLING_MONTH']['code'] == 'ROUTE_MISMATCH'
    assert own['BILLING_MONTH']['counted'] == own['BILLING_MONTH']['eligible'] == 1
    assert own['BILLING_MONTH']['exact_match'] == own['BILLING_MONTH']['normalized_match'] == 0
    assert own['ISSUE_DATE']['code'] == 'OK'
    summary = json.loads((out/'summary.json').read_text())
    distributions = {(r['engine'], r['form']): r['pages'] for r in summary['routes']['distributions']}
    assert {k: v for k, v in distributions.items() if v} == {
        ('text_layer', 'GOVERNMENT'): 1, ('own', 'LEGACY'): 1, ('applevision', 'GOVERNMENT'): 1}
    cross = {(r['engine'], r['reference_form'], r['observed_form']): r['pages']
             for r in summary['routes']['cross']}
    assert {k: v for k, v in cross.items() if v} == {
        ('own', 'GOVERNMENT', 'LEGACY'): 1, ('applevision', 'GOVERNMENT', 'GOVERNMENT'): 1}
    text = (out/'summary.txt').read_text()
    assert 'ROUTE own LEGACY 1\n' in text
    assert 'ROUTE_CROSS own GOVERNMENT LEGACY 1\n' in text
    assert 'ROUTE_CROSS applevision GOVERNMENT GOVERNMENT 1\n' in text
    safe_output(out, capfd)


def test_route_summary_excludes_incomplete_paths_and_counts_other_dispatch():
    meta = {'engines': ['own', 'applevision'], 'fields': [{'type': 'NHIS_PAYMENT', 'field': 'MEMBERSHIP'}]}
    rows = [
        tool.row(1, 1, code='REFERENCE_ERROR'),
        tool.row(2, 1, 'NHIS_PAYMENT', 'GOVERNMENT', 'MEMBERSHIP', 'own', 'EMPTY_OCR'),
        tool.row(2, 1, 'NHIS_PAYMENT', 'GOVERNMENT', 'MEMBERSHIP', 'applevision',
                 'REFERENCE_MISSING', observed_form='OTHER'),
        tool.row(3, 1, form='OTHER', code='CLASSIFICATION_FAILED'),
    ]
    summary = tool.build_summary(meta, rows, dict.fromkeys(tool.COUNTERS, 0))
    tool.validate_summary(summary, meta, rows)
    distributions = {(r['engine'], r['form']): r['pages'] for r in summary['routes']['distributions']}
    assert distributions[('text_layer', 'GOVERNMENT')] == distributions[('text_layer', 'OTHER')] == 1
    assert distributions[('applevision', 'OTHER')] == 1
    assert sum(v for (engine, _), v in distributions.items() if engine == 'own') == 0
    assert sum(r['pages'] for r in summary['routes']['cross']) == 1


@pytest.mark.parametrize('reference', (True, False))
def test_route_summary_rejects_inconsistent_page_routes(reference):
    meta = {'engines': ['own']}
    rows = [tool.row(1, 1, form='GOVERNMENT', engine='own', observed_form='LEGACY'),
            tool.row(1, 1, form='LEGACY' if reference else 'GOVERNMENT',
                     engine='own', observed_form='LEGACY' if reference else 'GOVERNMENT')]
    with pytest.raises(tool.DiagnosticError):
        tool.route_summary(meta, rows)


@pytest.mark.parametrize('mutation', ('route_value', 'route_key', 'route_count', 'route_bool', 'route_float'))
def test_route_summary_closed_schema_rejects_unreviewed_output(mutation):
    meta = {'engines': ['own'], 'fields': []}
    summary = tool.build_summary(meta, [], dict.fromkeys(tool.COUNTERS, 0))
    if mutation == 'route_value':
        summary['routes']['distributions'][0]['form'] = SENTINEL
    elif mutation == 'route_key':
        summary['routes'][SENTINEL] = 0
    elif mutation == 'route_count':
        summary['routes']['cross'][0]['pages'] = 1
    else:
        summary['routes']['cross'][0]['pages'] = False if mutation == 'route_bool' else 0.0
    with pytest.raises(tool.DiagnosticError):
        tool.validate_summary(summary, meta, [])


def test_route_mismatch_priority_vocabulary_matches_evidence():
    from engine_v2.tools import own_adapter_diag_evidence as evidence
    assert tool.CAUSES == evidence.CODES
    assert tool.CAUSES[:3] == ('OK', 'ROUTE_MISMATCH', 'LABEL_NOT_FOUND')


@pytest.mark.parametrize('form,observed_form,normalized', (
    ('LEGACY', 'LEGACY', 0), ('GOVERNMENT', None, 0), ('GOVERNMENT', 'LEGACY', 1)))
def test_route_mismatch_row_requires_different_completed_routes(form, observed_form, normalized):
    meta = {'engines': ['own'], 'fields': [{'type': 'NHIS_PAYMENT', 'field': 'MEMBERSHIP'}]}
    item = tool.row(1, 1, 'NHIS_PAYMENT', form, 'MEMBERSHIP', 'own', 'ROUTE_MISMATCH',
                    observed_form=observed_form, eligible=1, exact=0, normalized=normalized)
    with pytest.raises(tool.DiagnosticError):
        tool.validate_row(item, meta)


def test_selection_duplicates_limit_and_nonpdf(locations, monkeypatch, capfd):
    root, out = locations
    first = pdf(root/'first.pdf')
    pdf(root/'second.PDF')
    pdf(root/'.hidden.pdf')
    (root/'image.png').write_bytes(b'authored')
    ids = root.parent/f'{SENTINEL}.txt'
    ids.write_text('second.PDF\nfirst.pdf\nfirst.pdf\n../outside.pdf\nmissing.pdf\nimage.png\n./first.pdf\n')
    fake_recognize(monkeypatch, first)
    assert invoke(root, out, '--ids', str(ids), '--limit', '1') == 0
    counters = json.loads((out/'summary.json').read_text())['counters']
    assert counters['inventory_pdf'] == 2
    assert counters['excluded_files'] == 2
    assert counters['selected_documents'] == 2
    assert counters['duplicate_ids'] == counters['outside_root_ids'] == counters['invalid_ids'] == 1
    assert counters['missing_ids'] == 2
    assert counters['attempted_documents'] == counters['limit_remaining'] == 1
    assert {r['document'] for r in read_rows(out)} == {1}
    safe_output(out, capfd)


@pytest.mark.parametrize('arguments', [
    ['--engines','own','own'], ['--engines','remote'], ['--limit','0'], ['--limit','-1'],
    ['--fields','NHIS_PAYMENT:UNREGISTERED'], ['--fields','UNKNOWN:NAME'],
    ['--fields','NHIS_PAYMENT:NAME','NHIS_PAYMENT:NAME'], ['--limit',SENTINEL],
    [f'--{SENTINEL}'],
])
def test_bad_arguments_are_fixed_code_only(locations, arguments, capfd):
    root, out = locations
    assert invoke(root, out, *arguments) == 2
    assert not out.exists()
    safe_output(out, capfd)


@pytest.mark.parametrize('mode', ['existing','input-overlap','output-symlink','ids-symlink','ids-hardlink'])
def test_alias_and_overwrite_rejected_before_mutation(locations, mode, capfd):
    root, out = locations
    source = pdf(root/'source.pdf')
    arguments = []
    if mode == 'existing':
        out.mkdir()
        (out/'run.json').write_text(SENTINEL)
    elif mode == 'input-overlap':
        out = root/'output'
    elif mode == 'output-symlink':
        out.symlink_to(root, target_is_directory=True)
    elif mode == 'ids-symlink':
        original = root.parent/'list.txt'
        original.write_text('source.pdf\n')
        linked = root.parent/'linked.txt'
        linked.symlink_to(original)
        arguments = ['--ids',str(linked)]
    elif mode == 'ids-hardlink':
        linked = root.parent/'linked.txt'
        os.link(source, linked)
        arguments = ['--ids',str(linked)]
    before = source.read_bytes()
    assert invoke(root, out, *arguments) == 2
    assert source.read_bytes() == before
    captured = capfd.readouterr()
    assert captured.err == '' and SENTINEL not in captured.out


def test_symlink_input_not_opened(locations, monkeypatch):
    root, out = locations
    external = root.parent/f'{SENTINEL}.pdf'
    external.write_bytes(b'not a PDF')
    (root/'link.pdf').symlink_to(external)
    monkeypatch.setattr(tool, 'process_document', lambda *args: pytest.fail('symlink processed'))
    assert invoke(root, out) == 0
    summary = json.loads((out/'summary.json').read_text())
    assert summary['counters']['attempted_documents'] == 0
    assert summary['counters']['excluded_files'] == 1
    assert read_rows(out) == []


@pytest.mark.parametrize('mode,code,exit_code', [('broken','OPEN_ERROR',1),('empty','EMPTY_DOCUMENT',1),('encrypted','ENCRYPTED',0),
    ('image','NO_TEXT_LAYER',0),('short','SHORT_TEXT_LAYER',0),('unknown','CLASSIFICATION_FAILED',0)])
def test_document_and_page_exclusions(locations, mode, code, exit_code, capfd):
    import pymupdf
    root, out = locations
    path = root/f'{SENTINEL}.pdf'
    if mode == 'broken':
        path.write_bytes(SENTINEL.encode())
    elif mode == 'empty':
        data=b'%PDF-1.4\n'
        offsets=[]
        for value in (b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n',b'2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n'):
            offsets.append(len(data))
            data+=value
        position=len(data)
        data+=b'xref\n0 3\n0000000000 65535 f \n'
        data+=b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets)
        data+=f'trailer<</Size 3/Root 1 0 R>>\nstartxref\n{position}\n%%EOF\n'.encode()
        path.write_bytes(data)
    else:
        with pymupdf.open() as document:
            page = document.new_page()
            if mode in ('short','unknown'):
                page.insert_text((30,40), 'short' if mode == 'short' else 'SYNTHETIC UNCLASSIFIED DOCUMENT '+('FILLER '*30))
            settings = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256,user_pw='authored',owner_pw='owner') if mode == 'encrypted' else {}
            document.save(path, **settings)
    assert invoke(root, out) == exit_code
    rows = read_rows(out)
    assert len(rows) == 1 and rows[0]['code'] == code and rows[0]['counted'] == 0
    summary = json.loads((out/'summary.json').read_text())
    assert summary['counters']['attempted_documents'] == 1
    unit='documents' if mode in ('broken','empty','encrypted') else 'pages'
    assert summary['availability'][unit][code] == 1
    assert all(g['match_opportunities'] == 0 for g in summary['groups'])
    safe_output(out, capfd)


@pytest.mark.parametrize('mode,code,exit_code', [('error','OCR_ERROR',1),('missing','ENGINE_UNAVAILABLE',0),('empty','EMPTY_OCR',0)])
def test_engine_populations_are_separate(locations, monkeypatch, mode, code, exit_code, capfd):
    from engine_v2.pipeline.ocr import OcrResult
    root, out = locations
    path = pdf(root/'source.pdf')

    def operation(engine, page, words):
        if mode == 'error':
            raise RuntimeError(SENTINEL)
        if mode == 'missing':
            raise ImportError(SENTINEL)
        return OcrResult(engine, []), [], {}

    fake_recognize(monkeypatch, path, operation=operation)
    assert invoke(root, out) == exit_code
    rows = read_rows(out)
    assert len(rows) == 4 and all(r['code'] == code and r['counted'] == 0 for r in rows)
    assert all(r['eligible'] == 1 and r['normalized_match'] is None for r in rows)
    summary = json.loads((out/'summary.json').read_text())
    assert summary['counters']['empty_ocr'] == (2 if mode == 'empty' else 0)
    assert summary['counters']['engine_errors'] == (0 if mode == 'empty' else 2)
    assert summary['availability']['engines'][code] == 2
    safe_output(out, capfd)


@pytest.mark.parametrize('operation', ['python','native','logging','write','database','network'])
def test_dependency_disclosure_and_side_effects_are_guarded(locations, monkeypatch, operation, capfd):
    root, out = locations
    path = pdf(root/f'{SENTINEL}.pdf')
    side_effect = root.parent/'side-effect'
    from engine_v2.pipeline.ocr import OcrResult

    def injected(engine, page, words):
        if operation == 'python':
            print(SENTINEL)
        elif operation == 'native':
            os.write(1, SENTINEL.encode())
            os.write(2, SENTINEL.encode())
        elif operation == 'logging':
            logging.getLogger(__name__).warning(SENTINEL)
        else:
            try:
                if operation == 'write':
                    side_effect.write_text(SENTINEL)
                elif operation == 'database':
                    sqlite3.connect(side_effect)
                elif operation == 'network':
                    socket.create_connection(('127.0.0.1',9))
            except Exception:
                pass
        return OcrResult(engine, words), words, {}

    fake_recognize(monkeypatch, path, operation=injected)
    assert invoke(root, out) == (1 if operation in ('write','database','network') else 0)
    assert not side_effect.exists()
    safe_output(out, capfd)


@pytest.mark.parametrize('rotation',[90,180,270])
def test_rotated_reference_and_render_share_geometry(locations, monkeypatch, rotation):
    root, out = locations
    path = pdf(root/'source.pdf',rotate=rotation)
    _,_,seen = fake_recognize(monkeypatch,path)
    assert invoke(root,out) == 0
    # The existing upright form extractor has no reference values in this rotated
    # layout. Keep that absence explicit even though the word/raster frames agree.
    assert all(r['code']=='REFERENCE_MISSING' and r['eligible']==0 and
               r['exact_match'] is None and r['normalized_match'] is None for r in read_rows(out))
    assert len(seen) == 2
    assert seen[0][1].pixel_size == seen[1][1].pixel_size
    assert seen[0][1].png == seen[1][1].png


def test_reference_missing_and_unattributable_have_distinct_denominators():
    meta = tool.validate_meta(dict(schema_version=1,engines=['own'],
        fields=[dict(type='NHIS_PAYMENT',field='MEMBERSHIP')],clean=deepcopy(tool.SETTINGS['variants']['clean']),limit=None))
    rows = [tool.row(1,1,'NHIS_PAYMENT','LEGACY','MEMBERSHIP','own','OK',eligible=1,exact=1,normalized=1),
            tool.row(2,1,'NHIS_PAYMENT','LEGACY','MEMBERSHIP','own','REFERENCE_UNATTRIBUTABLE',eligible=1,exact=0,normalized=0),
            tool.row(3,1,'NHIS_PAYMENT','LEGACY','MEMBERSHIP','own','REFERENCE_MISSING')]
    summary=tool.build_summary(meta,rows,dict.fromkeys(tool.COUNTERS,0))
    group=next(g for g in summary['groups'] if g['form']=='LEGACY')
    assert group['eligible']==2 and group['diagnosed']==1 and group['match_opportunities']==2
    assert group['missing_reference']==group['unsupported_evidence']==1
    assert group['rates']['OK']==1 and group['normalized_match_rate']==.5
    tool.validate_summary(summary,meta,rows)


@pytest.mark.parametrize('injection', ['path','hash','coordinate','unknown-key','unknown-code','nan','bool'])
def test_closed_serializer_rejects_unreviewed_material(injection):
    meta=tool.validate_meta(dict(schema_version=1,engines=['own'],fields=[dict(type='NHIS_PAYMENT',field='MEMBERSHIP')],
        clean=deepcopy(tool.SETTINGS['variants']['clean']),limit=None))
    record=tool.row(1,1,'NHIS_PAYMENT','LEGACY','MEMBERSHIP','own','OTHER',eligible=1,exact=0,normalized=0)
    if injection in ('path','hash','coordinate','unknown-key'):
        record[injection]=SENTINEL
    elif injection=='unknown-code':
        record['code']=SENTINEL
    elif injection=='nan':
        record['document']=math.nan
    else:
        record['document']=True
    with pytest.raises(tool.DiagnosticError):
        tool.validate_row(record,meta)


def test_registry_covers_every_existing_field():
    assert set(tool.FIELD_CODES)=={key for values in tool.batch.FIELDS.values() for key in values}
    assert all(len(tool.REGISTRY[kind])==len(values) for kind,values in tool.batch.FIELDS.items())
    for kind,mapping in tool.REGISTRY.items():
        assert tool.parse_fields([f'{kind}:{code}' for code in mapping])


def test_limit_counts_failed_document_attempts(locations,monkeypatch):
    root,out=locations
    (root/'a-broken.pdf').write_bytes(b'authored broken input')
    pdf(root/'b-valid.pdf')
    monkeypatch.setattr(runtime,'recognize',lambda *args: pytest.fail('limit exceeded'))
    assert invoke(root,out,'--limit','1')==1
    assert [r['code'] for r in read_rows(out)]==['OPEN_ERROR']
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['attempted_documents']==counters['limit_remaining']==1


def test_multpage_mixed_document_and_rename_invariance(locations, monkeypatch):
    import pymupdf
    root,out=locations
    path=pdf(root/'first.pdf')
    with pymupdf.open(path) as original, pymupdf.open() as document:
        document.insert_pdf(original)
        document.new_page()
        document.save(root/'mixed.pdf')
    path.unlink()
    mixed=root/'mixed.pdf'
    fake_recognize(monkeypatch,mixed)
    assert invoke(root,out)==0
    rows=read_rows(out)
    assert sum(r['code']=='OK' for r in rows)==4
    assert sum(r['code']=='NO_TEXT_LAYER' for r in rows)==1
    mixed.rename(root/f'{SENTINEL}.pdf')
    second=root.parent/'second-output'
    assert invoke(root,second)==0
    assert read_rows(second)==rows
    summary=json.loads((second/'summary.json').read_text())
    assert summary['counters']['processed_pages']==2 and summary['counters']['excluded_pages']==1


def test_values_and_unreviewed_extractor_keys_stay_in_memory(locations, monkeypatch, capfd):
    from demo.backend.rules.doc_types import DocType
    from engine_v2.tools import own_adapter_diag_evidence as evidence
    root,out=locations
    path=pdf(root/f'{SENTINEL}.pdf')
    fake_recognize(monkeypatch,path)
    def extract(page,words,engine):
        return SimpleNamespace(detected_doc_type=DocType.NHIS_ACQUISITION_LOSS), {
            '성명':SENTINEL,'발급일':'2026-03-03',SENTINEL:{SENTINEL:SENTINEL}},'OTHER'
    monkeypatch.setattr(evidence,'extract_with_form',extract)
    assert invoke(root,out)==0
    assert len(read_rows(out))==4 and all(r['code']=='OK' for r in read_rows(out))
    safe_output(out,capfd)


def test_diagnostic_failure_preserves_other_fields_and_opportunities(locations,monkeypatch,capfd):
    from demo.backend.rules.doc_types import DocType
    from engine_v2.tools import own_adapter_diag_evidence as evidence
    root,out=locations
    path=pdf(root/'source.pdf')
    fake_recognize(monkeypatch,path)
    def extract(page,words,engine):
        values={'성명':'가짜이름','발급일':'2026-03-03'}
        if engine!='text_layer':
            values['성명']='다른가짜'
        return SimpleNamespace(detected_doc_type=DocType.NHIS_ACQUISITION_LOSS),values,'OTHER'
    def fail(*args):
        raise RuntimeError(SENTINEL)
    monkeypatch.setattr(evidence,'extract_with_form',extract)
    monkeypatch.setattr(evidence,'diagnose',fail)
    assert invoke(root,out)==1
    rows=read_rows(out)
    assert len(rows)==4
    assert sum(r['code']=='PROCESSING_ERROR' and r['field']=='NAME' and
        r['eligible']==1 and r['normalized_match']==0 for r in rows)==2
    assert sum(r['code']=='OK' and r['field']=='ISSUE_DATE' for r in rows)==2
    summary=json.loads((out/'summary.json').read_text())
    assert sum(g['match_opportunities'] for g in summary['groups'])==4
    safe_output(out,capfd)


@pytest.mark.parametrize('stage,expected', [('reference','REFERENCE_ERROR'),('render','RENDER_ERROR'),('observed','EXTRACTION_ERROR')])
def test_extraction_and_render_failures_are_explicit(locations,monkeypatch,capfd,stage,expected):
    from engine_v2.tools import own_adapter_diag_evidence as evidence
    root,out=locations
    path=pdf(root/'source.pdf')
    fake_recognize(monkeypatch,path)
    original=evidence.extract_with_form
    def extract(page,words,engine):
        if (stage=='reference' and engine=='text_layer') or (stage=='observed' and engine!='text_layer'):
            raise RuntimeError(SENTINEL)
        return original(page,words,engine)
    monkeypatch.setattr(evidence,'extract_with_form',extract)
    if stage=='render':
        def render(*args):
            raise RuntimeError(SENTINEL)
        monkeypatch.setattr(runtime,'variant_image',render)
    assert invoke(root,out)==1
    rows=read_rows(out)
    assert rows and all(r['code']==expected and r['counted']==0 and r['normalized_match'] is None for r in rows)
    safe_output(out,capfd)


def test_actual_runtime_apple_callable_receives_original_clean_input(locations,monkeypatch):
    import pymupdf
    from engine_v2.pipeline import ocr
    root,out=locations
    path=pdf(root/'source.pdf')
    with pymupdf.open(path) as document:
        page,truth=runtime.reference_page(document[0],0)
        image,_=runtime.variant_image(document[0],'clean',0,page.pixel_size)
    original=deepcopy(truth)
    calls=[]
    def apple(png,size):
        calls.append((png,size))
        return deepcopy(truth)
    monkeypatch.setitem(ocr.ENGINES,'applevision',apple)
    with tool.batch.guarded():
        recognized,raw,timing=runtime.recognize('applevision',image)
    assert calls==[(image.png,image.pixel_size)]
    assert recognized.words==raw==truth==original
    assert timing['ocr']>=0


def test_folder_and_file_ids_expand_deduplicate_and_ignore_comments(locations,monkeypatch,capfd):
    root,out=locations
    person=root/'p001'
    nested=person/'nested'
    other=root/'p002'
    nested.mkdir(parents=True)
    other.mkdir()
    first=pdf(person/'a.pdf')
    pdf(person/'b.PDF')
    pdf(nested/'c.pdf')
    pdf(other/'d.pdf')
    pdf(root/'root.pdf')
    (person/'image.png').write_bytes(b'authored image')
    (person/'notes.txt').write_text('authored text')
    ids=root.parent/f'{SENTINEL}.ids'
    ids.write_text('\ufeff# comment\n\n   \n  # another comment\np001/a.pdf\np001\np001/nested/c.pdf\np001\np002/d.pdf\n')
    fake_recognize(monkeypatch,first)
    assert invoke(root,out,'--ids',str(ids))==0
    rows=read_rows(out)
    assert {item['document'] for item in rows}=={1,2,3,4}
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['inventory_pdf']==5 and counters['selected_documents']==4 and counters['not_listed']==1
    assert counters['folder_id_lines']==2 and counters['file_id_lines']==3
    assert counters['duplicate_ids']==2 and counters['overlapping_pdf_ids']==5
    assert counters['invalid_ids']==counters['missing_ids']==counters['outside_root_ids']==0
    assert counters['excluded_files']==2
    safe_output(out,capfd)


def test_folder_selection_excludes_hidden_symlink_and_unsupported_files(locations,monkeypatch,capfd):
    root,out=locations
    person=root/'p001'
    person.mkdir()
    first=pdf(person/'valid.pdf')
    pdf(person/'.hidden.pdf')
    hidden=person/'.hidden'
    hidden.mkdir()
    pdf(hidden/'inside.pdf')
    external=root.parent/f'{SENTINEL}.pdf'
    external.write_bytes(b'authored target that must not be opened')
    (person/'linked.pdf').symlink_to(external)
    (root/'linked-person').symlink_to(person,target_is_directory=True)
    (person/'notes.txt').write_text('authored')
    ids=root.parent/'selection.ids'
    ids.write_text('p001\nlinked-person\np001/.hidden.pdf\np001/linked.pdf\n')
    fake_recognize(monkeypatch,first)
    assert invoke(root,out,'--ids',str(ids))==0
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['selected_documents']==1 and counters['attempted_documents']==1
    assert counters['missing_ids']==2 and counters['invalid_ids']==1
    assert counters['excluded_files']==5
    safe_output(out,capfd)


def test_invalid_and_missing_selector_lines_count_individually(locations,capfd):
    root,out=locations
    (root/'p001').mkdir()
    ids=root.parent/f'{SENTINEL}.ids'
    ids.write_bytes(b'\xef\xbb\xbf# ignored\n\xff\n\xff\n../outside\n../outside\n/absolute\n'
                    b'p001//bad.pdf\np001//bad.pdf\np001/nested-folder\nmissing\nmissing\nmissing/file.pdf\n')
    assert invoke(root,out,'--ids',str(ids))==0
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['invalid_ids']==5 and counters['outside_root_ids']==3 and counters['missing_ids']==3
    assert counters['duplicate_ids']==0 and counters['selected_documents']==0
    assert counters['attempted_documents']==0
    safe_output(out,capfd)


def test_safe_folder_without_pdfs_is_valid_empty_selection(locations,monkeypatch):
    root,out=locations
    person=root/'p001'
    person.mkdir()
    (person/'image.png').write_bytes(b'authored image')
    (person/'notes.txt').write_text('authored text')
    ids=root.parent/'selection.ids'
    ids.write_text('p001\np001\n')
    monkeypatch.setattr(tool,'process_document',lambda *args: pytest.fail('empty selection processed'))
    assert invoke(root,out,'--ids',str(ids))==0
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['folder_id_lines']==counters['empty_folder_id_lines']==2
    assert counters['duplicate_ids']==1
    assert counters['missing_ids']==counters['invalid_ids']==counters['attempted_documents']==0
    assert read_rows(out)==[]


def test_default_payment_fields_skip_other_classified_kind_before_ocr(locations,monkeypatch):
    root,out=locations
    pdf(root/'opaque.pdf')
    monkeypatch.setattr(runtime,'recognize',lambda *args: pytest.fail('unrequested kind reached OCR'))
    assert tool.main(['--root',str(root),'--out',str(out)])==0
    rows=read_rows(out)
    assert len(rows)==1 and rows[0]['type']=='NHIS_ACQUISITION_LOSS'
    assert rows[0]['code']=='TYPE_NOT_REQUESTED' and rows[0]['eligible']==rows[0]['counted']==0
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['skipped_documents']==counters['classified_unrequested_documents']==counters['unrequested_pages']==1
    assert counters['excluded_pages']==counters['engine_errors']==0


def test_unknown_classification_stays_explicit_in_skipped_document_count(locations,monkeypatch):
    import pymupdf
    root,out=locations
    with pymupdf.open() as document:
        page=document.new_page()
        page.insert_text((30,40),'SYNTHETIC UNKNOWN DOCUMENT '+('FILLER '*30))
        document.save(root/'opaque.pdf')
    monkeypatch.setattr(runtime,'recognize',lambda *args: pytest.fail('unknown kind reached OCR'))
    assert tool.main(['--root',str(root),'--out',str(out)])==0
    assert [item['code'] for item in read_rows(out)]==['CLASSIFICATION_FAILED']
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['skipped_documents']==1 and counters['classified_unrequested_documents']==0
    assert counters['unrequested_pages']==0 and counters['excluded_pages']==1


def test_mixed_other_kind_and_unknown_pages_count_one_skipped_document(locations,monkeypatch):
    import pymupdf
    root,out=locations
    first=pdf(root.parent/'source.pdf')
    with pymupdf.open(first) as original,pymupdf.open() as document:
        document.insert_pdf(original)
        page=document.new_page()
        page.insert_text((30,40),'SYNTHETIC UNKNOWN DOCUMENT '+('FILLER '*30))
        document.save(root/'mixed.pdf')
    monkeypatch.setattr(runtime,'recognize',lambda *args: pytest.fail('unrequested pages reached OCR'))
    assert tool.main(['--root',str(root),'--out',str(out)])==0
    assert {item['code'] for item in read_rows(out)}=={'TYPE_NOT_REQUESTED','CLASSIFICATION_FAILED'}
    counters=json.loads((out/'summary.json').read_text())['counters']
    assert counters['skipped_documents']==1 and counters['classified_unrequested_documents']==0
    assert counters['unrequested_pages']==counters['excluded_pages']==1
