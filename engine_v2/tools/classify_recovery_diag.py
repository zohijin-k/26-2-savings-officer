"""Value-free classification recovery diagnostics for the production upload reader.

Run with ``python -B -m engine_v2.tools.classify_recovery_diag``.

* ``crosstab`` joins an existing doc_timing ``rows.jsonl`` with an existing
  batch_assess ``results.jsonl`` by document key; nothing is re-read.
* ``run`` re-reads every PDF once through the unmodified ``read_document`` chain
  with delegation-only wrappers, records where LocalOcr gave up (exit and cause
  codes, swallowed exception class names), compares unclassified documents with
  the batch_assess 300 dpi reading, and evaluates candidate rules in the shadow.

Production behaviour never changes: candidate rules are installed only inside a
second, separate read of the same document. Screen output, ``summary.txt`` and
``run.json`` contain numbers, O/X and fixed codes only; ``rows.jsonl`` adds the
16-hex document key. Values, names, paths and exception messages are never kept.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import time
from unittest.mock import patch

from . import batch_assess as batch
from . import doc_timing as timing

VERSION = 1
KINDS = batch.KINDS
TIERS = timing.TIERS
DECISIONS = timing.DECISIONS
ROW_CODES = ('NONE', 'PROCESSING_ERROR', 'GUARD_BLOCKED') + timing.SKIP_CODES
ERROR_CODES = ('ARGUMENT_ERROR', 'OUT_EXISTS', 'INPUT_UNAVAILABLE', 'INPUT_INVALID', 'INPUT_OUTPUT_OVERLAP',
               'LOCATION_REJECTED', 'ENGINE_UNAVAILABLE', 'UNEXPECTED_ERROR')
EXITS = ('L_RESULT', 'L_EXCEPTION', 'L_SKIPPED', 'T_READ_NONE', 'T_TIER2_FORM', 'T_QUAL_NOT_NOTICE',
         'T_LOAD_ERROR', 'T_RECLASS_NONE', 'T_RECLASS_DISCARD', 'I_PREPROCESS_ERROR', 'I_TEXT_PAGE',
         'I_OCR_ERROR', 'I_UNCLASSIFIED', 'I_UNCLASSIFIED_MARKERS', 'I_GENERIC_NONE', 'OTHER')
CAUSES = ('EXCEPTION', 'PREPROCESS_ERROR', 'FIRST_IMAGE_LATER_TEXT', 'FEW_CHARS_DISCARD',
          'TEXT_RECLASS_DISCARD', 'HIDDEN_TEXT_LAYER', 'BACKGROUND_ONLY', 'OCR_ERROR', 'OCR_EMPTY',
          'OCR_NO_KEYWORD', 'TEXT_NO_KEYWORD', 'OTHER')
CHAR_BINS = ('C0', 'C1_99', 'C100_499', 'C500P', 'NA')
FIRST_BINS = ('C0', 'C1_49', 'C50P', 'NA')
MAIN_KINDS = ('MAIN_NONE', 'RGB', 'GRAY', 'CMYK', 'STENCIL', 'SMASK', 'OTHER')
LAYERS = ('L0', 'L1', 'L2P')
DPI_BINS = ('D_LT150', 'D150_199', 'D200_299', 'D300P', 'NA')
ROTATIONS = ('R0', 'R90', 'R180', 'R270', 'R_OTHER')
CANDIDATES = ('N', 'W', 'E')
CLASS_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')
PROGRESS_EVERY = 25

# ---------------------------------------------------------------- G1 candidates

#: N: the one usage mark observed between the two title lines of the synthetic form.
INS4_N = '4대사회보험확인용가입자가입내역확인서'
#: W: any two- or three-letter usage mark ending in 용 at the same position (comparison only).
INS4_W = re.compile(r'4대사회보험[가-힣]{2,3}용가입자가입내역확인서')
#: E: the insurance_4 extractor's own recognition scope (insurance_4.py ``_looks_like_insurance4``).
INS4_E = ('4대사회보험', '가입자가입내역확인서')
INS4_EVIDENCE = "본문에서 '4대사회보험 가입자 가입내역 확인서' 제목·서식 단서를 확인했습니다."


def candidate_fires(name, text):
    """Whether candidate ``name`` recognizes 4대보험 in an unclassified classify input."""
    flat = re.sub(r'\s+', '', text or '')
    if name == 'N':
        return INS4_N in flat
    if name == 'W':
        return INS4_W.search(flat) is not None
    if name == 'E':
        return all(part in flat for part in INS4_E)
    raise ValueError('UNKNOWN_CANDIDATE')


def candidate_classifier(name, original):
    """Wrap ``classify_with_evidence``: only an unclassified result may become INSURANCE_4."""
    from demo.backend.rules.doc_types import DocType

    def classify_with_evidence(text):
        detected, evidence = original(text)
        if detected is None and candidate_fires(name, text):
            return DocType.INSURANCE_4, INS4_EVIDENCE
        return detected, evidence
    return classify_with_evidence


# ---------------------------------------------------------------- small helpers


class ToolError(Exception):
    """Carries one fixed code from ERROR_CODES."""


def _fail(code):
    raise ToolError(code)


def class_name(exc):
    name = type(exc).__name__
    return name if CLASS_RE.fullmatch(name) else 'OTHER'


def _kind(doc_type):
    name = getattr(doc_type, 'name', None)
    return name if name in KINDS and name != 'X' else 'X'


def char_bin(count):
    if count is None:
        return 'NA'
    return 'C0' if count == 0 else 'C1_99' if count < 100 else 'C100_499' if count < 500 else 'C500P'


def first_bin(count):
    if count is None:
        return 'NA'
    return 'C0' if count == 0 else 'C1_49' if count < 50 else 'C50P'


def dpi_bin(dpi):
    if dpi is None:
        return 'NA'
    return 'D_LT150' if dpi < 150 else 'D150_199' if dpi < 200 else 'D200_299' if dpi < 300 else 'D300P'


def _print(text):
    print(text, flush=True)


def _line(*values):
    return ' '.join(str(value) for value in values)


# ---------------------------------------------------------------- crosstab (no re-reading)


def _timing_rows(path):
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        _fail('INPUT_UNAVAILABLE')
    chosen, skipped = {}, 0
    try:
        for text in lines:
            if not text.strip():
                continue
            row = timing.validate_row(json.loads(text))
            if row['phase'] == 'skipped':
                skipped += 1
            elif row['phase'] == 'measure':
                if row['key'] not in chosen or row['repeat'] < chosen[row['key']]['repeat']:
                    chosen[row['key']] = row
    except (ValueError, KeyError, TypeError, batch.BatchError):
        _fail('INPUT_INVALID')
    return chosen, skipped


def _scan_rows(path):
    try:
        rows = batch.load_rows(Path(path))
    except batch.BatchError:
        _fail('INPUT_INVALID')
    except (OSError, UnicodeError):
        _fail('INPUT_UNAVAILABLE')
    return rows


def crosstab(timing_path, scan_path):
    """Join existing A (doc_timing) and A-scan (batch_assess) rows by document key."""
    measured, skipped = _timing_rows(timing_path)
    scan = {}
    for row in _scan_rows(scan_path):
        # doc_timing measures PDFs only; the extension selects the format, never the name.
        if row['id'].lower().endswith('.pdf'):
            scan[timing.document_key(row['id'])] = row
    matched = sorted(measured.keys() & scan.keys())
    lines = [_line('MATCH timing_docs scan_pdf_docs matched timing_only scan_only'),
             _line('MATCH', len(measured), len(scan), len(matched), len(measured.keys() - scan.keys()),
                   len(scan.keys() - measured.keys())),
             _line('SKIPPED timing', skipped)]
    if not matched:
        lines.append('WARNING ROOT_MISMATCH')
    lines.append('CROSS a_form scan_type n')
    cross = Counter((measured[key]['form'], scan[key]['detected_type']) for key in matched)
    for (a, s), n in sorted(cross.items()):
        lines.append(_line('CROSS', a, s, n))
    lines.append(_line('CROSS_TOTAL', len(matched)))
    lines.append('TIER tier n')
    for tier, n in sorted(Counter(row['tier'] for row in measured.values()).items()):
        lines.append(_line('TIER', tier, n))
    x_rows = [row for row in measured.values() if row['form'] == 'X']
    lines.append('XTIER tier text_layer later_text page_bin n')
    profile = Counter((r['tier'], r['text_layer'], r['first_image_later_text'], r['page_bin']) for r in x_rows)
    for values, n in sorted(profile.items(), key=lambda item: tuple(map(str, item[0]))):
        lines.append(_line('XTIER', *values, n))
    x_matched = [key for key in matched if measured[key]['form'] == 'X']
    lines.append(_line('XMATCH a_form_x matched', len(x_rows), len(x_matched)))
    for title, value in (('XSCAN', lambda row: row['detected_type']),
                         ('XSCAN_CODE', lambda row: row['engines']['own']['code']),
                         ('XTEXTREF', lambda row: (row['text_reference']['detected_type']
                                                  if row['text_reference']['state'] == 'OK' else 'NA'))):
        lines.append(_line(title, 'value n'))
        for code, n in sorted(Counter(value(scan[key]) for key in x_matched).items()):
            lines.append(_line(title, code, n))
    lines.append('FALLBACK NOT_RECORDED')
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- run: trace wrappers


class Trace:
    """Per-document event recorder. Holds classify inputs in memory for one document only."""

    def __init__(self):
        self.ocr_cache = {}
        self.reset()

    def reset(self):
        self.active = False      # record exit events
        self.capture = False     # keep classify inputs for G1
        self.in_local = False
        self.events = []
        self.classified = []     # (text, detected) for G1, memory only
        self.ocr_chars = None
        self.exceptions = {}
        self.ocr_cache.clear()

    def event(self, name, value=None):
        if self.active and self.in_local:
            self.events.append((name, value))

    def find(self, name):
        return [value for event, value in self.events if event == name]


def _wrap_local_read(trace, original):
    def read(self, file_path, expected):
        outer = trace.in_local
        trace.in_local = True
        try:
            result = original(self, file_path, expected)
        except Exception as exc:
            if trace.active:
                trace.exceptions.setdefault('local', class_name(exc))
            raise
        finally:
            trace.in_local = outer
        if trace.active:
            trace.events.append(('local_result', None if result is None else _kind(result.detected_doc_type)))
        return result
    return read


def _wrap_pdftext_read(trace, original):
    def read(self, file_path, expected):
        try:
            return original(self, file_path, expected)
        except Exception as exc:
            if trace.active:
                trace.exceptions.setdefault('pdftext', class_name(exc))
            raise
    return read


def _wrap_value(trace, original, name, project):
    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        trace.event(name, project(result))
        return result
    return wrapped


def _wrap_preprocess(trace, original):
    from engine_v2.pipeline.preprocess import PageSource

    def preprocess(*args, **kwargs):
        try:
            pages = original(*args, **kwargs)
        except Exception as exc:
            if trace.active and trace.in_local:
                trace.exceptions.setdefault('preprocess', class_name(exc))
            trace.event('preprocess', 'ERROR')
            raise
        trace.event('preprocess', 'TEXT_PAGE' if any(p.source == PageSource.TEXT_LAYER for p in pages) else 'OK')
        return pages
    return preprocess


def _wrap_ocr(trace, original):
    """Delegating own recognizer with a per-document memo (identical image bytes → identical words)."""
    def recognize(png, size):
        key = (hashlib.sha256(png).hexdigest(), tuple(size))
        if key in trace.ocr_cache:
            words = deepcopy(trace.ocr_cache[key])
        else:
            try:
                words = original(png, size)
            except Exception as exc:
                if trace.active and trace.in_local:
                    trace.exceptions.setdefault('ocr', class_name(exc))
                    trace.events.append(('ocr_error', class_name(exc)))
                raise
            trace.ocr_cache[key] = deepcopy(words)
        if trace.active and trace.in_local:
            trace.ocr_chars = (trace.ocr_chars or 0) + sum(len(re.sub(r'\s+', '', w.text)) for w in words)
        return words
    return recognize


def _wrap_classify(trace, original):
    def classify_with_evidence(text):
        detected, evidence = original(text)
        if trace.capture:
            trace.classified.append((text, detected))
        return detected, evidence
    return classify_with_evidence


@contextmanager
def instrument(trace):
    """Install delegation-only wrappers; arguments, results and exceptions pass through unchanged."""
    from demo.backend.ocr import file_evidence, localocr, pdftext
    from engine_v2 import engine as v2engine
    from engine_v2.pipeline import ocr as v2ocr, preprocess as v2pre

    with ExitStack() as stack:
        def put(owner, name, value):
            stack.enter_context(patch.object(owner, name, value))
        put(localocr.LocalOcr, 'read', _wrap_local_read(trace, localocr.LocalOcr.read))
        put(pdftext.PdfTextOcr, 'read', _wrap_pdftext_read(trace, pdftext.PdfTextOcr.read))
        put(localocr, '_tier2_can_read', _wrap_value(trace, localocr._tier2_can_read, 'route',
                                                      lambda r: 'TEXT' if r else 'IMAGE'))
        put(pdftext, '_read_pdf', _wrap_value(trace, pdftext._read_pdf, 'read_pdf',
                                              lambda r: 'NONE' if r is None else _kind(r.detected_doc_type)))
        put(v2engine, '_load_pages', _wrap_value(trace, v2engine._load_pages, 'load_pages',
                                                 lambda r: 'ERROR' if isinstance(r, str) else 'OK'))
        put(v2pre, 'preprocess', _wrap_preprocess(trace, v2pre.preprocess))
        stack.enter_context(patch.dict(v2ocr.ENGINES, {'own': _wrap_ocr(trace, v2ocr.ENGINES['own'])}))
        put(pdftext, 'classify_with_evidence', _wrap_classify(trace, pdftext.classify_with_evidence))
        put(pdftext, 'classify_pages_with_evidence',
            _wrap_value(trace, pdftext.classify_pages_with_evidence, 'classify_pages', lambda r: _kind(r[0])))
        put(file_evidence, 'independent_page_markers',
            _wrap_value(trace, file_evidence.independent_page_markers, 'markers',
                        lambda r: 'NONE' if r is None else 'FOUND'))
        put(localocr, '_generic', _wrap_value(trace, localocr._generic, 'generic',
                                              lambda r: 'NONE' if r is None else _kind(r.detected_doc_type)))
        yield trace


def exit_code(trace):
    """Where LocalOcr stopped, inferred from the delegated calls it made (localocr.py ``_read``)."""
    if 'local' in trace.exceptions:
        return 'L_EXCEPTION', None
    results = trace.find('local_result')
    routes = trace.find('route')
    route = routes[0] if routes else None
    pages = trace.find('classify_pages')
    if results and results[-1] is not None:
        if route == 'IMAGE' and pages and pages[-1] == 'X' and 'FOUND' in trace.find('markers'):
            return 'I_UNCLASSIFIED_MARKERS', None
        return 'L_RESULT', None
    if route is None:
        return 'L_SKIPPED', None
    if route == 'TEXT':
        first = trace.find('read_pdf')
        if first and first[0] == 'NONE':
            return 'T_READ_NONE', None
        loads = trace.find('load_pages')
        if not loads:
            return ('T_QUAL_NOT_NOTICE' if first and first[0] == 'NHIS_QUALIFICATION' else 'T_TIER2_FORM'), None
        if loads[-1] == 'ERROR':
            return 'T_LOAD_ERROR', None
        if pages:
            return ('T_RECLASS_NONE', None) if pages[-1] == 'X' else ('T_RECLASS_DISCARD', pages[-1])
        return 'OTHER', None
    pre = trace.find('preprocess')
    if pre and pre[-1] == 'ERROR':
        return 'I_PREPROCESS_ERROR', None
    if pre and pre[-1] == 'TEXT_PAGE':
        return 'I_TEXT_PAGE', None
    if trace.find('ocr_error'):
        return 'I_OCR_ERROR', None
    if pages and pages[-1] == 'X':
        return 'I_UNCLASSIFIED', None
    if trace.find('generic') and trace.find('generic')[-1] == 'NONE':
        return 'I_GENERIC_NONE', None
    return 'OTHER', None


# ---------------------------------------------------------------- run: page structure


def structure(path):
    """First-page bitmap structure plus any-page flags; counts and codes only."""
    import pymupdf
    from engine_v2.pipeline.privacy import mask_rrn
    result = dict(first_chars='NA', main='MAIN_NONE', layers='L0', dpi='NA', rotation='R0',
                  any_layers2='X', any_smask='X', any_stencil='X', first_covered='X')
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            area = page.rect.get_area() or 1.0
            covering = []
            for info in page.get_image_info(xrefs=True):
                if info.get('xref') and info.get('bbox') and pymupdf.Rect(info['bbox']).get_area() >= .9 * area:
                    covering.append(info)
            main = max(covering, key=lambda item: item['width'] * item['height']) if covering else None
            kind = 'MAIN_NONE'
            if main is not None:
                if document.xref_get_key(main['xref'], 'ImageMask')[1] == 'true' or main.get('colorspace') == 0:
                    kind = 'STENCIL'
                elif main.get('has-mask'):
                    kind = 'SMASK'
                else:
                    kind = {1: 'GRAY', 3: 'RGB', 4: 'CMYK'}.get(main.get('colorspace'), 'OTHER')
            if len(covering) >= 2:
                result['any_layers2'] = 'O'
            if kind == 'SMASK':
                result['any_smask'] = 'O'
            if kind == 'STENCIL':
                result['any_stencil'] = 'O'
            if index == 0:
                result['first_chars'] = first_bin(len(mask_rrn(page.get_text()).strip()))
                result['main'] = kind
                result['first_covered'] = 'O' if main is not None else 'X'
                result['layers'] = 'L0' if not covering else 'L1' if len(covering) == 1 else 'L2P'
                if main is not None:
                    width_pt = (main['transform'][0] ** 2 + main['transform'][1] ** 2) ** .5
                    result['dpi'] = dpi_bin(main['width'] / (width_pt / 72)) if width_pt > 0 else 'NA'
                rotation = page.rotation % 360
                result['rotation'] = {0: 'R0', 90: 'R90', 180: 'R180', 270: 'R270'}.get(rotation, 'R_OTHER')
    return result


def text_all_type(path):
    """Classify the concatenated text layer of every page (unmodified keyword table)."""
    import pymupdf
    from demo.backend.ocr import pdftext
    from engine_v2.pipeline.privacy import mask_rrn
    with pymupdf.open(path) as document:
        text = '\n'.join(mask_rrn(page.get_text()) for page in document)
    if not text.strip():
        return 'NA'
    return _kind(pdftext.classify_with_evidence(text)[0])


def scan_type(path):
    """batch_assess reading: every page rendered at 300 dpi, own OCR, same classifier."""
    try:
        pages, _, _ = batch._inspect(path)
        record, _, _ = batch._engine(path, pages, 'own')
    except Exception:
        return 'X', 'OPEN_ERROR'
    return record['detected_type'], record['code']


def cause_code(exit, trace, struct, text_all):
    if trace.exceptions.get('local') or trace.exceptions.get('pdftext'):
        return 'EXCEPTION'
    if exit == 'I_PREPROCESS_ERROR':
        return 'PREPROCESS_ERROR'
    if exit == 'I_TEXT_PAGE':
        return 'FIRST_IMAGE_LATER_TEXT'
    if exit == 'T_RECLASS_DISCARD':
        return 'FEW_CHARS_DISCARD' if struct['first_chars'] == 'C1_49' else 'TEXT_RECLASS_DISCARD'
    text_route = exit.startswith('T_')
    if text_route and struct['first_chars'] == 'C50P' and text_all in ('X', 'NA') and struct['first_covered'] == 'O':
        return 'HIDDEN_TEXT_LAYER'
    if exit in ('I_UNCLASSIFIED', 'I_UNCLASSIFIED_MARKERS', 'I_GENERIC_NONE'):
        if struct['any_layers2'] == 'O' or struct['any_smask'] == 'O':
            return 'BACKGROUND_ONLY'
        return 'OCR_EMPTY' if not trace.ocr_chars else 'OCR_NO_KEYWORD'
    if exit == 'I_OCR_ERROR':
        return 'OCR_ERROR'
    if text_route:
        return 'TEXT_NO_KEYWORD'
    return 'OTHER'


# ---------------------------------------------------------------- run: per document


def _assess(path, kind, ocr):
    """Same slot rule and verdict call as doc_timing; returns (decision, reasons)."""
    from demo.backend.upload_assessment import assess_upload
    req = timing.requirement(kind)
    if req is None:
        return 'NOT_ASSESSED', []
    _, checked = assess_upload(path, req, identity=None, paper_admin_consent=kind == 'ADMIN_INFO_CONSENT',
                               reader=lambda file_path, expected: ocr)
    decision = checked.status if checked.status in DECISIONS else 'ERROR'
    return decision, timing.reason_codes(checked.findings)


def _shadow_read(trace, path, patcher):
    """Second read with a candidate installed; exit recording and capture are off."""
    from demo.backend import ocr as demo_ocr
    trace.active = trace.capture = False
    with ExitStack() as stack:
        patcher(stack)
        return demo_ocr.read_document(str(path), None)


def g1_shadow(trace, path, row):
    from demo.backend.ocr import pdftext
    unclassified = [text for text, detected in trace.classified if detected is None]
    for name in CANDIDATES:
        if not any(candidate_fires(name, text) for text in unclassified):
            row['g1'][name] = row['form']
            continue
        current = pdftext.classify_with_evidence
        ocr = _shadow_read(trace, path, lambda stack: stack.enter_context(
            patch.object(pdftext, 'classify_with_evidence', candidate_classifier(name, current))))
        kind = _kind(ocr.detected_doc_type)
        row['g1'][name] = kind
        if kind != row['form']:
            row['g1_decision'][name] = _assess(path, kind, ocr)[0]


def blank_row(key, code='NONE'):
    return dict(schema_version=VERSION, key=key, code=code, form='X', tier='none', decision='NOT_ASSESSED',
                reasons=[], exit=None, reclass=None, exceptions={}, ocr_chars='NA', cause=None,
                struct=None, scan=None, scan_code=None, text_all=None,
                g1={name: None for name in CANDIDATES}, g1_decision={name: None for name in CANDIDATES})


def process(path, key, trace):
    from demo.backend import ocr as demo_ocr
    row = blank_row(key)
    trace.reset()
    trace.active = trace.capture = True
    ocr = demo_ocr.read_document(str(path), None)
    trace.active = trace.capture = False
    row['form'] = _kind(ocr.detected_doc_type)
    row['tier'] = timing._tier(ocr.tier)
    row['decision'], row['reasons'] = _assess(path, row['form'], ocr)
    row['exit'], row['reclass'] = exit_code(trace)
    row['exceptions'] = dict(sorted(trace.exceptions.items()))
    row['ocr_chars'] = char_bin(trace.ocr_chars)
    if row['form'] == 'X':
        row['struct'] = structure(path)
        row['text_all'] = text_all_type(path)
        row['scan'], row['scan_code'] = scan_type(path)
        row['cause'] = cause_code(row['exit'], trace, row['struct'], row['text_all'])
    g1_shadow(trace, path, row)
    trace.classified.clear()
    trace.ocr_cache.clear()
    return row


def _code_in(value, allowed, optional=False):
    return (optional and value is None) or value in allowed


def validate_row(row):
    req = batch._require
    keys = {'schema_version', 'key', 'code', 'form', 'tier', 'decision', 'reasons', 'exit', 'reclass',
            'exceptions', 'ocr_chars', 'cause', 'struct', 'scan', 'scan_code', 'text_all', 'g1', 'g1_decision'}
    req(isinstance(row, dict) and set(row) == keys and row['schema_version'] == VERSION)
    req(isinstance(row['key'], str) and timing.KEY_RE.fullmatch(row['key']) is not None)
    req(row['code'] in ROW_CODES and row['form'] in KINDS and row['tier'] in TIERS and row['decision'] in DECISIONS)
    req(isinstance(row['reasons'], list) and all(isinstance(p, list) and len(p) == 2 and p[1] in timing.SEVERITIES
                                                 and (p[0] in timing._safe_codes() or p[0] == timing.UNKNOWN_CODE)
                                                 for p in row['reasons']))
    req(_code_in(row['exit'], EXITS, True) and _code_in(row['reclass'], KINDS, True))
    req(isinstance(row['exceptions'], dict) and set(row['exceptions']) <= {'local', 'pdftext', 'preprocess', 'ocr'}
        and all(isinstance(v, str) and CLASS_RE.fullmatch(v) for v in row['exceptions'].values()))
    req(row['ocr_chars'] in CHAR_BINS and _code_in(row['cause'], CAUSES, True))
    if row['struct'] is not None:
        s = row['struct']
        req(set(s) == {'first_chars', 'main', 'layers', 'dpi', 'rotation', 'any_layers2', 'any_smask',
                       'any_stencil', 'first_covered'})
        req(s['first_chars'] in FIRST_BINS and s['main'] in MAIN_KINDS and s['layers'] in LAYERS
            and s['dpi'] in DPI_BINS and s['rotation'] in ROTATIONS
            and all(s[k] in ('O', 'X') for k in ('any_layers2', 'any_smask', 'any_stencil', 'first_covered')))
    req(_code_in(row['scan'], KINDS, True) and _code_in(row['scan_code'], batch.CODES, True))
    req(_code_in(row['text_all'], tuple(KINDS) + ('NA',), True))
    req(set(row['g1']) == set(CANDIDATES) and all(_code_in(v, KINDS, True) for v in row['g1'].values()))
    req(set(row['g1_decision']) == set(CANDIDATES)
        and all(_code_in(v, DECISIONS, True) for v in row['g1_decision'].values()))
    return row


# ---------------------------------------------------------------- run: summary


def summarize(rows, meta):
    lines = []
    done = [r for r in rows if r['code'] == 'NONE']
    counts = meta['counts']
    lines.append('COUNTS inventory_pdf selected skipped processed errors')
    lines.append(_line('COUNTS', counts.get('inventory_pdf', 0), counts.get('selected', 0),
                       sum(r['code'] in timing.SKIP_CODES for r in rows), len(done),
                       sum(r['code'] in ('PROCESSING_ERROR', 'GUARD_BLOCKED') for r in rows)))
    for code, n in sorted(Counter(r['code'] for r in rows if r['code'] != 'NONE').items()):
        lines.append(_line('ROWCODE', code, n))
    if meta.get('timing_forms') is not None:
        forms = meta['timing_forms']
        matched = [r for r in done if r['key'] in forms]
        agree = sum(forms[r['key']] == r['form'] for r in matched)
        lines.append('BASELINE_VS_TIMING matched agree disagree')
        lines.append(_line('BASELINE_VS_TIMING', len(matched), agree, len(matched) - agree))
    for title, field in (('FORM', 'form'), ('TIER', 'tier'), ('DECISION', 'decision'), ('EXIT', 'exit')):
        lines.append(_line(title, field, 'n'))
        for value, n in sorted(Counter(str(r[field]) for r in done).items()):
            lines.append(_line(title, value, n))
    x = [r for r in done if r['form'] == 'X']
    lines.append(_line('XCOUNT', len(x)))
    tables = (
        ('XEXIT exit n', lambda r: (r['exit'],)),
        ('XCAUSE cause n', lambda r: (r['cause'],)),
        ('XCAUSE_SCAN cause scan_found n', lambda r: (r['cause'], 'O' if r['scan'] not in (None, 'X') else 'X')),
        ('XRECLASS type n', lambda r: (r['reclass'],) if r['reclass'] else None),
        ('XOCR bin n', lambda r: (r['ocr_chars'],)),
        ('XSTRUCT first_chars main layers dpi rotation n',
         lambda r: (r['struct']['first_chars'], r['struct']['main'], r['struct']['layers'], r['struct']['dpi'],
                    r['struct']['rotation'])),
        ('XSTRUCT_ANY layers2 smask stencil n',
         lambda r: (r['struct']['any_layers2'], r['struct']['any_smask'], r['struct']['any_stencil'])),
        ('XSCAN scan_type n', lambda r: (r['scan'],)),
        ('XSCAN_CODE code n', lambda r: (r['scan_code'],)),
        ('XSCAN_BY_EXIT exit scan_found n', lambda r: (r['exit'], 'O' if r['scan'] not in (None, 'X') else 'X')),
        ('XTEXT text_all_type n', lambda r: (r['text_all'],)),
    )
    for header, key in tables:
        title = header.split()[0]
        lines.append(header)
        counter = Counter(k for k in (key(r) for r in x) if k is not None)
        for values, n in sorted(counter.items(), key=lambda item: tuple(map(str, item[0]))):
            lines.append(_line(title, *values, n))
    lines.append('XEXC where class n')
    for (where, name), n in sorted(Counter(item for r in x for item in r['exceptions'].items()).items()):
        lines.append(_line('XEXC', where, name, n))
    lines.append('EXC where class n')
    for (where, name), n in sorted(Counter(item for r in done for item in r['exceptions'].items()).items()):
        lines.append(_line('EXC', where, name, n))
    lines.append('G1 cand INS4_BASELINE INS4_CHANGED X_TO_INS4 OTHER_TO_INS4 CHANGED_DOCS')
    for name in CANDIDATES:
        base = [r for r in done if r['form'] == 'INSURANCE_4']
        changed = [r for r in done if r['g1'][name] != r['form']]
        lines.append(_line('G1', name, len(base), sum(r['g1'][name] != 'INSURANCE_4' for r in base),
                           sum(r['form'] == 'X' and r['g1'][name] == 'INSURANCE_4' for r in done),
                           sum(r['form'] not in ('X', 'INSURANCE_4') and r['g1'][name] == 'INSURANCE_4' for r in done),
                           len(changed)))
    lines.append('G1_TRANSITION cand before after n')
    for name in CANDIDATES:
        for (a, b), n in sorted(Counter((r['form'], r['g1'][name]) for r in done if r['g1'][name] != r['form']).items()):
            lines.append(_line('G1_TRANSITION', name, a, b, n))
    lines.append('G1_DECISION cand before_decision after_decision n')
    for name in CANDIDATES:
        pairs = Counter((r['decision'], r['g1_decision'][name]) for r in done if r['g1'][name] != r['form'])
        for (a, b), n in sorted(pairs.items(), key=lambda item: tuple(map(str, item[0]))):
            lines.append(_line('G1_DECISION', name, a, b, n))
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- run


def run(root, out, *, timing_path=None, forms=None, limit=None):
    requested = Path(out).absolute()
    if requested.exists() or requested.is_symlink():
        _fail('OUT_EXISTS')
    try:
        root = Path(root).resolve(strict=True)
    except (OSError, RuntimeError):
        _fail('INPUT_UNAVAILABLE')
    if not root.is_dir():
        _fail('INPUT_UNAVAILABLE')
    try:
        out = batch._location(requested)
    except batch.BatchError:
        _fail('LOCATION_REJECTED')
    if out.is_relative_to(root) or root.is_relative_to(out):
        _fail('INPUT_OUTPUT_OVERLAP')
    for name in timing.DISABLED_ENV:
        os.environ.pop(name, None)
    os.environ['ENGINE_V2_OCR'] = 'own'
    if not timing.own_available():
        _fail('ENGINE_UNAVAILABLE')
    timing_forms = None
    if timing_path is not None:
        measured, _ = _timing_rows(timing_path)
        timing_forms = {key: row['form'] for key, row in measured.items()}

    inventory, excluded = batch.inventory(root)
    keyed = {timing.document_key(p.relative_to(root).as_posix()): p for p in inventory if p.suffix.lower() == '.pdf'}
    keys = sorted(keyed)
    if forms:
        keys = [key for key in keys if timing_forms.get(key) in forms]
    if limit is not None:
        keys = keys[:limit]
    meta = dict(schema_version=VERSION, environment=timing.environment(),
                options=dict(forms=sorted(forms) if forms else None, limit=limit,
                             timing_rows='O' if timing_path else 'X', candidates=list(CANDIDATES),
                             external_ocr_disabled='O'),
                counts=dict(inventory_pdf=len(keyed), selected=len(keys)))
    _print(f'inventory_pdf {len(keyed)} selected {len(keys)}')

    out.mkdir(mode=0o700, parents=True)
    batch._location(out)
    batch._atomic(batch._target(out / 'run.json'), meta)
    rows = []
    fd = batch._open(batch._target(out / 'rows.jsonl'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND)
    started = time.perf_counter()
    trace = Trace()
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        with batch.guarded():
            installed = instrument(trace)
            installed.__enter__()
        try:
            for index, key in enumerate(keys, 1):
                path = keyed[key]
                with batch.guarded():
                    pre = timing.inspect(path)
                if pre['code'] != 'NONE':
                    row = blank_row(key, pre['code'])
                else:
                    try:
                        with batch.guarded():
                            row = process(path, key, trace)
                    except batch.BatchError:
                        row = blank_row(key, 'GUARD_BLOCKED')
                    except Exception:
                        row = blank_row(key, 'PROCESSING_ERROR')
                    finally:
                        trace.reset()
                validate_row(row)
                stream.write(json.dumps(row, ensure_ascii=True, sort_keys=True, allow_nan=False) + '\n')
                stream.flush()
                rows.append(row)
                if index % PROGRESS_EVERY == 0 or index == len(keys):
                    _print(f'progress done {index} total {len(keys)} elapsed_s {time.perf_counter() - started:.1f}')
        finally:
            with batch.guarded():
                installed.__exit__(None, None, None)
        os.fsync(stream.fileno())
    meta['environment']['finished'] = timing.datetime.now().astimezone().isoformat(timespec='seconds')
    batch._atomic(batch._target(out / 'run.json'), meta)
    meta['timing_forms'] = timing_forms
    text = summarize(rows, meta)
    batch._target(out / 'summary.txt')
    (out / 'summary.txt').write_text(text, encoding='utf-8')
    _print(text.rstrip('\n'))
    return 1 if any(r['code'] in ('PROCESSING_ERROR', 'GUARD_BLOCKED') for r in rows) else 0


# ---------------------------------------------------------------- CLI


def parser():
    result = batch.SafeParser(prog='classify_recovery_diag', description='Value-free classification diagnostics')
    commands = result.add_subparsers(dest='command', required=True, parser_class=batch.SafeParser)
    cross = commands.add_parser('crosstab')
    cross.add_argument('--timing', required=True)
    cross.add_argument('--scan', required=True)
    rerun = commands.add_parser('run')
    rerun.add_argument('--root', required=True)
    rerun.add_argument('--out', required=True)
    rerun.add_argument('--timing')
    rerun.add_argument('--forms', nargs='+')
    rerun.add_argument('--limit', type=int)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == 'crosstab':
            _print(crosstab(args.timing, args.scan).rstrip('\n'))
            return 0
        forms = set(args.forms) if args.forms else None
        if ((forms and (args.timing is None or not forms <= set(KINDS))) or
                (args.limit is not None and args.limit < 1)):
            _fail('ARGUMENT_ERROR')
        return run(args.root, args.out, timing_path=args.timing, forms=forms, limit=args.limit)
    except KeyboardInterrupt:
        return 130
    except ToolError as error:
        code = error.args[0] if error.args and error.args[0] in ERROR_CODES else 'UNEXPECTED_ERROR'
        _print(f'ERROR {code}')
        return 2
    except batch.BatchError:
        _print('ERROR ARGUMENT_ERROR')
        return 2
    except Exception:
        # Never echo arguments, paths, document contents or exception messages.
        _print('ERROR UNEXPECTED_ERROR')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
