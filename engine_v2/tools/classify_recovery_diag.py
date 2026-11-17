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

VERSION = 2
#: Format 1 (commit 2) had no consent/payment/p1/c1 keys.
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
        self.payment = None      # (pages, result) of the last production payment extraction, memory only
        self.page_texts = None   # squeezed per-page reading text, memory only
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


def _wrap_classify_pages(trace, original):
    def classify_pages_with_evidence(pages):
        detected, evidence = original(pages)
        trace.event('classify_pages', _kind(detected))
        if trace.capture:
            trace.page_texts = [re.sub(r'\s+', '', result.text) for _, result in pages]
        return detected, evidence
    return classify_pages_with_evidence


def _wrap_payment_extract(trace, original):
    def extract(pages, *args, **kwargs):
        result = original(pages, *args, **kwargs)
        if trace.capture:
            trace.payment = (pages, result)
        return result
    return extract


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
            _wrap_classify_pages(trace, pdftext.classify_pages_with_evidence))
        from engine_v2.extractors import nhis_payment
        put(nhis_payment, 'extract', _wrap_payment_extract(trace, nhis_payment.extract))
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


# ---------------------------------------------------------------- consent mark and payment table stages


#: P1: header-band slack in percent of page height (synthetic overlap was about 0.05).
P1_MARGINS = (0.1, 0.2, 0.3)
P1_KEYS = tuple(f'm{int(round(m * 10)):02d}' for m in P1_MARGINS)
CONSENT_TITLE = '행정정보공동이용'
MARKS = ('NONE', 'AGREE', 'DISAGREE', 'BOTH')
PAYMENT_STAGES = ('HEADER', 'COLUMN', 'ROW', 'FORMAT', 'ARITH', 'TABLE_OK', 'NOT_EXTRACTED')
PAYMENT_DETAILS = ('HEADER_GROUPS', 'HEADER_BAND_CUT', 'HEADER_LABEL', 'MONTH_HEADER_MISSING',
                   'CHARGE_HEADER_MISSING', 'NONE')
PAGING_STATES = ('COMPLETE', 'INCOMPLETE', 'NOT_REQUIRED', 'UNCERTAIN', 'ABSENT', 'INVALID')
COMPLETENESS_KEYS = ('period_status', 'printed_total_observed', 'arithmetic_complete', 'issue_information_read')
C1_EXCLUDED = frozenset({'ADMIN_CONSENT_MARK_UNREADABLE', 'ADMIN_CONSENT_SIGNATURE_UNREADABLE'})
#: Phase-correlation peak (z-score of the correlation surface) treated as a confident alignment.
PEAK_STRONG = 20.0
#: Inner-box variant of the alignment shadow: the printed checkbox border is excluded (pt per side).
INNER_PT = 2.0


@contextmanager
def p1_patch(margin):
    """Shadow P1: the column-header band starts ``margin`` above the group-header bottom.

    Only the GROUPS call of ``_header_columns`` is wrapped; it returns copies of the
    group words with ``y1 - margin``. x and confidence are unchanged, so only
    ``group_bottom`` (and therefore the header band) moves.
    """
    from dataclasses import replace
    from engine_v2.extractors import nhis_payment_gov as gov
    original = gov._header_columns

    def header_columns(words, expected=gov.HEADERS):
        clusters = original(words, expected=expected)
        if clusters is None or expected != gov.GROUPS:
            return clusters
        return [[replace(word, y1=word.y1 - margin) for word in cluster] for cluster in clusters]
    with patch.object(gov, '_header_columns', header_columns):
        yield


@contextmanager
def c1_patch():
    """Shadow C1: consent mark/signature unreadability alone no longer makes low quality a FAIL."""
    from demo.backend.rules import doc_check
    with patch.object(doc_check, 'ESSENTIAL_FIELD_UNREADABLE_CODES',
                      set(doc_check.ESSENTIAL_FIELD_UNREADABLE_CODES) - C1_EXCLUDED):
        yield


def _validations(result):
    return {check.name: bool(check.passed) for check in getattr(result, 'validations', ()) or ()}


def payment_table_stage(pages, result):
    """First failing table stage of the production payment reading; codes only."""
    from engine_v2.extractors import nhis_payment as legacy, nhis_payment_gov as gov
    if pages is None or result is None:
        return 'NOT_EXTRACTED', 'NOT_EXTRACTED', 'NONE'
    checks = _validations(result)
    ok = lambda *names: all(checks.get(name, False) for name in names)  # noqa: E731
    if gov.recognizes(pages):
        route = 'GOV'
        if not ok('payment_group_headers', 'payment_component_headers'):
            detail = 'HEADER_GROUPS' if not ok('payment_group_headers') else 'HEADER_LABEL'
            if detail == 'HEADER_LABEL':
                with p1_patch(max(P1_MARGINS)):
                    relaxed = _validations(gov.extract(pages))
                if relaxed.get('payment_component_headers'):
                    detail = 'HEADER_BAND_CUT'
            return route, 'HEADER', detail
        if not ok('payment_columns'):
            return route, 'COLUMN', 'NONE'
        if not ok('monthly_rows_found', 'months_continuous', 'payment_sum_row'):
            return route, 'ROW', 'NONE'
    else:
        route = 'LEGACY'
        if not legacy._header_x(pages, legacy.MONTH_LABELS):
            return route, 'HEADER', 'MONTH_HEADER_MISSING'
        if not legacy._header_x(pages, ('고지금액', '고지보험료')):
            return route, 'HEADER', 'CHARGE_HEADER_MISSING'
        if not ok('monthly_rows_found', 'months_continuous'):
            return route, 'ROW', 'NONE'
    if not ok('monthly_amounts_numeric'):
        return route, 'FORMAT', 'NONE'
    if not ok('monthly_total_matches', 'paid_total_matches'):
        return route, 'ARITH', 'NONE'
    return route, 'TABLE_OK', 'NONE'


def _json_field(fields, name):
    raw = fields.get(name)
    if raw is None:
        return 'ABSENT'
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return 'INVALID'


def payment_evidence(ocr):
    """Paging, completeness and period evidence states of the stored reading; codes only."""
    from engine_v2.extractors import payment_completeness, payment_paging, payment_period
    paging = _json_field(ocr.fields, payment_paging.FIELD)
    if isinstance(paging, str):
        state, fallback = paging, 'NA'
    else:
        try:
            state = payment_paging.assess(paging)
            state = state if state in PAGING_STATES else 'INVALID'
            fallback = 'O' if payment_paging.fallback_allowed(paging, ocr.page_count) else 'X'
        except Exception:
            state, fallback = 'INVALID', 'NA'
    table = _json_field(ocr.fields, payment_completeness.FIELD)
    complete = {}
    for key in COMPLETENESS_KEYS:
        if not isinstance(table, dict):
            complete[key] = 'NA'
        elif key == 'period_status':
            complete[key] = 'O' if table.get(key) == 'READABLE' else 'X'
        else:
            complete[key] = 'O' if table.get(key) is True else 'X'
    period = _json_field(ocr.fields, payment_period.FIELD)
    if isinstance(period, dict):
        period_state = 'READABLE' if period.get('status') == 'READABLE' else 'OTHER'
        certain = 'O' if period.get('amounts_certain') is True else 'X'
    else:
        period_state, certain = 'ABSENT' if period == 'ABSENT' else 'OTHER', 'NA'
    return dict(paging=state, fallback=fallback, period=period_state, amounts_certain=certain, **complete)


def payment_reason_flags(reasons):
    codes = {code: severity for code, severity in reasons}
    billing = codes.get('MISSING_BILLING_MONTHS')
    return dict(paging_uncertain='O' if 'NHIS_PAYMENT_PAGING_UNCERTAIN' in codes else 'X',
                missing_billing=billing if billing in ('FAIL', 'NEEDS_REVIEW') else 'X',
                pages_incomplete='O' if 'PAGES_INCOMPLETE' in codes else 'X')


def _phase_shift(scan, template):
    """Translation (dx, dy) in template pixels that maps the template onto the scan, and peak strength."""
    import numpy as np
    from PIL import Image
    size = (template.width // 2, template.height // 2)
    a = 255.0 - np.asarray(scan.resize(size, Image.Resampling.BILINEAR), dtype=np.float64)
    b = 255.0 - np.asarray(template.resize(size, Image.Resampling.BILINEAR), dtype=np.float64)
    a -= a.mean()
    b -= b.mean()
    cross = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    cross /= np.abs(cross) + 1e-9
    surface = np.real(np.fft.ifft2(cross))
    y, x = np.unravel_index(int(np.argmax(surface)), surface.shape)
    if y > surface.shape[0] // 2:
        y -= surface.shape[0]
    if x > surface.shape[1] // 2:
        x -= surface.shape[1]
    strength = (surface.max() - surface.mean()) / (surface.std() or 1.0)
    return 2 * x, 2 * y, strength


def _translate(image, dx, dy):
    from PIL import Image
    return image.transform(image.size, Image.Transform.AFFINE, (1, 0, dx, 0, 1, dy), fillcolor=255)


def _mark(spec, scan, template, page_width, page_height, inset=0.0):
    from demo.backend.ocr import admin_consent_scan as consent
    ratios = []
    for key in ('agree.동의함', 'agree.동의하지 않음'):
        field = spec.fields.get(key)
        box = [field['box'][0] + inset, field['box'][1] + inset, field['box'][2] - inset,
               field['box'][3] - inset] if field else None
        ratios.append(consent._extra_ink_ratio(scan, template, box, page_width, page_height) if field else 0.0)
    selected = [ratio > .035 for ratio in ratios]
    mark = 'BOTH' if all(selected) else 'AGREE' if selected[0] else 'DISAGREE' if selected[1] else 'NONE'
    signature = spec.fields.get('signature')
    signed = bool(signature and consent._extra_ink_ratio(scan, template, signature['box'], page_width,
                                                          page_height) > .012)
    return mark, ratios, signed


def ratio_bin(value):
    return 'R_LT1' if value < .01 else 'R1_3_5' if value <= .035 else 'R_GE3_5'


def consent_stage(path, page_texts=None):
    """Production mark reading reproduced step by step, plus an alignment shadow; codes only."""
    import pymupdf
    from demo.backend.forms import coords as form_coords
    from demo.backend.ocr import admin_consent_scan as consent
    from engine_v2.pipeline.privacy import mask_rrn
    result = dict(spec='SPEC_OK', load='LOAD_OK', pages='NA', title='TITLE_NONE', aspect='NA', shift='NA',
                  peak='NA', mark='NA', aligned='NA', aligned_inner='NA', inner_strong='NA', agree_ratio='NA', disagree_ratio='NA', sign='NA',
                  aligned_sign='NA')
    spec = form_coords.load('서식5')
    if spec is None or not spec.available:
        result['spec'] = 'SPEC_UNAVAILABLE'
        return result
    with pymupdf.open(spec.template) as template_pdf:
        page = template_pdf[0]
        page_width, page_height = page.rect.width, page.rect.height
        from io import BytesIO
        from PIL import Image
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1200 / page_width, 1200 / page_width), alpha=False)
        template = Image.open(BytesIO(pix.tobytes('png'))).convert('L')
    try:
        with pymupdf.open(path) as document:
            count = document.page_count
            if page_texts is None:
                page_texts = [re.sub(r'\s+', '', mask_rrn(p.get_text())) for p in document]
        raw = consent._page_image(Path(path), 1200)
    except Exception:
        result['load'] = 'LOAD_ERROR'
        return result
    result['pages'] = 'P1' if count == 1 else 'P2P'
    hits = [index for index, text in enumerate(page_texts or []) if CONSENT_TITLE in text]
    result['title'] = 'TITLE_NONE' if not hits else 'TITLE_FIRST' if hits[0] == 0 else 'TITLE_LATER'
    difference = abs((raw.height / raw.width) / (template.height / template.width) - 1) * 100
    result['aspect'] = 'A_LE_2' if difference <= 2 else 'A_2_5' if difference <= 5 else 'A_GT_5'
    scan = raw.resize(template.size)
    mark, ratios, signed = _mark(spec, scan, template, page_width, page_height)
    result.update(mark='MARK_' + mark, agree_ratio=ratio_bin(ratios[0]), disagree_ratio=ratio_bin(ratios[1]),
                  sign='SIGN_O' if signed else 'SIGN_X')
    dx, dy, strength = _phase_shift(scan, template)
    shift_pt = (dx * dx + dy * dy) ** .5 * page_width / 1200
    result['shift'] = 'S_LE_3' if shift_pt <= 3 else 'S_3_10' if shift_pt <= 10 else 'S_GT_10'
    result['peak'] = 'PEAK_STRONG' if strength >= PEAK_STRONG else 'PEAK_WEAK'
    moved = _translate(scan, dx, dy)
    aligned_mark, _, aligned_signed = _mark(spec, moved, template, page_width, page_height)
    inner_mark, _, _ = _mark(spec, moved, template, page_width, page_height, inset=INNER_PT)
    # Production candidate: the inner reading counts only with a strong alignment; otherwise it is held
    # and the document stays NEEDS_REVIEW exactly as today.
    strong = result['peak'] == 'PEAK_STRONG'
    result.update(aligned='ALIGNED_' + aligned_mark, aligned_inner='INNER_' + inner_mark,
                  inner_strong='STRONG_' + inner_mark if strong else 'STRONG_HOLD',
                  aligned_sign='ALIGNED_SIGN_O' if aligned_signed else 'ALIGNED_SIGN_X')
    return result



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


def _quality(path):
    from demo.backend.ocr.file_evidence import objective_image_quality
    value = round(objective_image_quality(str(path)), 2)
    return {1.0: 'Q10', .9: 'Q09', .7: 'Q07', .5: 'Q05'}.get(value, 'Q_OTHER')


def _severity(reasons, code):
    found = [severity for name, severity in reasons if name == code]
    return found[0] if found and found[0] in ('FAIL', 'NEEDS_REVIEW') else 'X'


def consent_shadow(trace, path, row, ocr):
    stage = consent_stage(path, trace.page_texts)
    field = ocr.fields.get('동의여부')
    expected = 'MARK_AGREE' if field == '동의함' else 'MARK_DISAGREE' if field == '동의하지 않음' else None
    if stage['mark'] == 'NA':
        stage['prod_match'] = 'NA'
    else:
        stage['prod_match'] = 'O' if (stage['mark'] == expected if expected else
                                      stage['mark'] in ('MARK_NONE', 'MARK_BOTH')) else 'X'
    stage['quality'] = _quality(path)
    stage['low_quality'] = _severity(row['reasons'], 'LOW_IMAGE_QUALITY')
    row['consent'] = stage
    with c1_patch():
        row['c1'] = _assess(path, row['form'], deepcopy(ocr))[0]


def payment_shadow(trace, path, row, ocr):
    pages, result = trace.payment if trace.payment is not None else (None, None)
    route, stage, detail = payment_table_stage(pages, result)
    row['payment'] = dict(route=route, stage=stage, detail=detail, **payment_evidence(ocr),
                          **payment_reason_flags(row['reasons']))
    if route != 'GOV':
        # P1 only wraps the government-form GROUPS header call; other routes cannot diverge.
        row['p1'] = {key: dict(paging_uncertain=row['payment']['paging_uncertain'],
                               missing_billing=row['payment']['missing_billing'], decision=row['decision'])
                     for key in P1_KEYS}
        return
    row['p1'] = {}
    for key, margin in zip(P1_KEYS, P1_MARGINS):
        shadow = _shadow_read(trace, path, lambda stack, m=margin: stack.enter_context(p1_patch(m)))
        decision, reasons = _assess(path, _kind(shadow.detected_doc_type), shadow)
        flags = payment_reason_flags(reasons)
        row['p1'][key] = dict(paging_uncertain=flags['paging_uncertain'], missing_billing=flags['missing_billing'],
                              decision=decision)


def blank_row(key, code='NONE'):
    return dict(schema_version=VERSION, key=key, code=code, form='X', tier='none', decision='NOT_ASSESSED',
                reasons=[], exit=None, reclass=None, exceptions={}, ocr_chars='NA', cause=None,
                struct=None, scan=None, scan_code=None, text_all=None,
                g1={name: None for name in CANDIDATES}, g1_decision={name: None for name in CANDIDATES},
                consent=None, c1=None, payment=None, p1=None, shadow_errors=[])


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
    # A failing shadow keeps the baseline row; only the stage name is recorded.
    for name, applies, function in (('G1', True, lambda: g1_shadow(trace, path, row)),
                                    ('CONSENT', row['form'] == 'ADMIN_INFO_CONSENT',
                                     lambda: consent_shadow(trace, path, row, ocr)),
                                    ('PAYMENT', row['form'] == 'NHIS_PAYMENT',
                                     lambda: payment_shadow(trace, path, row, ocr))):
        if not applies:
            continue
        try:
            function()
        except batch.BatchError:
            raise
        except Exception:
            row['shadow_errors'].append(name)
    trace.classified.clear()
    trace.ocr_cache.clear()
    return row


def _code_in(value, allowed, optional=False):
    return (optional and value is None) or value in allowed


def validate_row(row):
    req = batch._require
    keys = {'schema_version', 'key', 'code', 'form', 'tier', 'decision', 'reasons', 'exit', 'reclass',
            'exceptions', 'ocr_chars', 'cause', 'struct', 'scan', 'scan_code', 'text_all', 'g1', 'g1_decision',
            'consent', 'c1', 'payment', 'p1', 'shadow_errors'}
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
    req(isinstance(row['shadow_errors'], list) and set(row['shadow_errors']) <= {'G1', 'CONSENT', 'PAYMENT'})
    if row['consent'] is not None:
        c = row['consent']
        allowed = dict(spec=('SPEC_OK', 'SPEC_UNAVAILABLE'), load=('LOAD_OK', 'LOAD_ERROR'), pages=('P1', 'P2P', 'NA'),
                       title=('TITLE_FIRST', 'TITLE_LATER', 'TITLE_NONE'), aspect=('A_LE_2', 'A_2_5', 'A_GT_5', 'NA'),
                       shift=('S_LE_3', 'S_3_10', 'S_GT_10', 'NA'), peak=('PEAK_STRONG', 'PEAK_WEAK', 'NA'),
                       mark=tuple('MARK_' + m for m in MARKS) + ('NA',),
                       aligned=tuple('ALIGNED_' + m for m in MARKS) + ('NA',),
                       aligned_inner=tuple('INNER_' + m for m in MARKS) + ('NA',),
                       inner_strong=tuple('STRONG_' + m for m in MARKS) + ('STRONG_HOLD', 'NA'),
                       agree_ratio=('R_LT1', 'R1_3_5', 'R_GE3_5', 'NA'),
                       disagree_ratio=('R_LT1', 'R1_3_5', 'R_GE3_5', 'NA'), sign=('SIGN_O', 'SIGN_X', 'NA'),
                       aligned_sign=('ALIGNED_SIGN_O', 'ALIGNED_SIGN_X', 'NA'), prod_match=('O', 'X', 'NA'),
                       quality=('Q10', 'Q09', 'Q07', 'Q05', 'Q_OTHER'), low_quality=('FAIL', 'NEEDS_REVIEW', 'X'))
        req(isinstance(c, dict) and set(c) == set(allowed) and all(c[k] in v for k, v in allowed.items()))
    req(_code_in(row['c1'], DECISIONS, True))
    if row['payment'] is not None:
        p = row['payment']
        allowed = dict(route=('GOV', 'LEGACY', 'NOT_EXTRACTED'), stage=PAYMENT_STAGES, detail=PAYMENT_DETAILS,
                       paging=PAGING_STATES, fallback=('O', 'X', 'NA'), period=('READABLE', 'OTHER', 'ABSENT'),
                       amounts_certain=('O', 'X', 'NA'), paging_uncertain=('O', 'X'),
                       missing_billing=('FAIL', 'NEEDS_REVIEW', 'X'), pages_incomplete=('O', 'X'),
                       **{key: ('O', 'X', 'NA') for key in COMPLETENESS_KEYS})
        req(isinstance(p, dict) and set(p) == set(allowed) and all(p[k] in v for k, v in allowed.items()))
    if row['p1'] is not None:
        req(isinstance(row['p1'], dict) and set(row['p1']) == set(P1_KEYS) and all(
            isinstance(v, dict) and set(v) == {'paging_uncertain', 'missing_billing', 'decision'}
            and v['paging_uncertain'] in ('O', 'X') and v['missing_billing'] in ('FAIL', 'NEEDS_REVIEW', 'X')
            and v['decision'] in DECISIONS for v in row['p1'].values()))
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
    five = ('HIDDEN_TEXT_LAYER', 'FEW_CHARS_DISCARD', 'FIRST_IMAGE_LATER_TEXT', 'PREPROCESS_ERROR', 'BACKGROUND_ONLY')
    lines.append('XCAUSE5 ' + ' '.join(five) + ' OTHER_CAUSES')
    causes = Counter(r['cause'] for r in x)
    lines.append(_line('XCAUSE5', *(causes[c] for c in five), len(x) - sum(causes[c] for c in five)))
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
    lines.extend(_stage_summary(done))
    return '\n'.join(lines) + '\n'


def _counted(lines, header, items):
    title = header.split()[0]
    lines.append(header)
    for values, n in sorted(Counter(items).items(), key=lambda item: tuple(map(str, item[0]))):
        lines.append(_line(title, *values, n))


def _stage_summary(done):
    lines = []
    for name, n in sorted(Counter(e for r in done for e in r['shadow_errors']).items()):
        lines.append(_line('SHADOW_ERROR', name, n))
    consent = [r for r in done if r['consent'] is not None]
    lines.append(_line('CONSENT_COUNT', len(consent)))
    for field in ('spec', 'load', 'pages', 'title', 'aspect', 'shift', 'peak', 'mark', 'aligned', 'aligned_inner',
                  'inner_strong', 'agree_ratio',
                  'disagree_ratio', 'sign', 'aligned_sign', 'prod_match', 'quality', 'low_quality'):
        _counted(lines, f'CONSENT_{field.upper()} code n', ((r['consent'][field],) for r in consent))
    lines.append('CONSENT_VARIANT variant READ_OK READ_AGREE READ_DISAGREE DIFF_FROM_PROD HELD_WEAK')
    for variant, field in (('ALIGNED', 'aligned'), ('INNER', 'aligned_inner'), ('INNER_STRONG', 'inner_strong')):
        values = [(r['consent']['mark'].split('_', 1)[-1], r['consent'][field].split('_', 1)[-1])
                  for r in consent if r['consent'][field] != 'NA']
        lines.append(_line('CONSENT_VARIANT', variant,
                           sum(v in ('AGREE', 'DISAGREE') for _, v in values),
                           sum(v == 'AGREE' for _, v in values), sum(v == 'DISAGREE' for _, v in values),
                           sum(v != 'HOLD' and v != p for p, v in values), sum(v == 'HOLD' for _, v in values)))
    _counted(lines, 'CONSENT_MARK prod aligned inner peak n',
             ((r['consent']['mark'], r['consent']['aligned'], r['consent']['aligned_inner'], r['consent']['peak'])
              for r in consent))
    _counted(lines, 'CONSENT_FAILSTAGE title aspect shift mark n',
             ((r['consent']['title'], r['consent']['aspect'], r['consent']['shift'], r['consent']['mark'])
              for r in consent if r['consent']['mark'] not in ('MARK_AGREE', 'MARK_DISAGREE')))
    _counted(lines, 'CONSENT_DECISION mark quality low_quality decision n',
             ((r['consent']['mark'], r['consent']['quality'], r['consent']['low_quality'], r['decision'])
              for r in consent))
    _counted(lines, 'C1 before after n', ((r['decision'], r['c1']) for r in consent))
    lines.append(_line('C1_FAIL_TO_REVIEW', sum(r['decision'] == 'FAIL' and r['c1'] == 'NEEDS_REVIEW'
                                                for r in consent)))
    payment = [r for r in done if r['payment'] is not None]
    lines.append(_line('PAYMENT_COUNT', len(payment)))
    _counted(lines, 'PAYMENT route stage detail n',
             ((r['payment']['route'], r['payment']['stage'], r['payment']['detail']) for r in payment))
    _counted(lines, 'PAYMENT_REASON paging_uncertain missing_billing stage detail n',
             ((r['payment']['paging_uncertain'], r['payment']['missing_billing'], r['payment']['stage'],
               r['payment']['detail']) for r in payment))
    _counted(lines, 'PAYMENT_PAGING state fallback paging_uncertain n',
             ((r['payment']['paging'], r['payment']['fallback'], r['payment']['paging_uncertain']) for r in payment))
    _counted(lines, 'PAYMENT_COMPLETE key value paging_uncertain n',
             ((key, r['payment'][key], r['payment']['paging_uncertain']) for r in payment for key in COMPLETENESS_KEYS))
    _counted(lines, 'PAYMENT_PERIOD state amounts_certain missing_billing n',
             ((r['payment']['period'], r['payment']['amounts_certain'], r['payment']['missing_billing'])
              for r in payment))
    lines.append('P1 margin PAGING_GONE PAGING_NEW BILLING_GONE BILLING_NEW DECISION_CHANGED')
    for key in P1_KEYS:
        after = [(r, r['p1'][key]) for r in payment if r['p1'] is not None]
        lines.append(_line('P1', key,
                           sum(r['payment']['paging_uncertain'] == 'O' and a['paging_uncertain'] == 'X' for r, a in after),
                           sum(r['payment']['paging_uncertain'] == 'X' and a['paging_uncertain'] == 'O' for r, a in after),
                           sum(r['payment']['missing_billing'] != 'X' and a['missing_billing'] == 'X' for r, a in after),
                           sum(r['payment']['missing_billing'] == 'X' and a['missing_billing'] != 'X' for r, a in after),
                           sum(r['decision'] != a['decision'] for r, a in after)))
    _counted(lines, 'P1_DECISION margin before after n',
             ((key, r['decision'], r['p1'][key]['decision']) for r in payment for key in P1_KEYS
              if r['p1'] is not None and r['p1'][key]['decision'] != r['decision']))
    return lines


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
