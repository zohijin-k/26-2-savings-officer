"""Value-free per-document timing of the demo upload path (own engine).

Use ``python -B -m engine_v2.tools.doc_timing --root DIR --out NEW_DIR``.

Each PDF goes through the same functions the service calls for one uploaded file:
``demo.backend.ocr.read_document`` (the full production reader chain) and
``demo.backend.upload_assessment.assess_upload`` (per-document verdict). HTTP,
database, paired NHIS reassessment and application-level judgement are outside
the timed region. Stage times come from delegation-only wrappers; they never
change arguments, results or exceptions.

Screen output and summary_brief.txt contain numbers, O/X and fixed codes only.
rows.jsonl carries a 16-hex document key, never a path, name or value. Row format 2
adds ``reasons``: distinct registered verdict reason codes with their severity,
recorded outside the timed region (unregistered codes become UNKNOWN_CODE).
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import statistics
import subprocess
import time
from unittest.mock import patch

from . import batch_assess as batch

VERSION = 2
#: Row format 1 (fea711b) had no ``reasons``; both remain readable.
READABLE_VERSIONS = (1, 2)
SEVERITIES = ('FAIL', 'NEEDS_REVIEW', 'INFO', 'PASS', 'OTHER')
UNKNOWN_CODE = 'UNKNOWN_CODE'
ENGINES = ('own',)
STAGES = ('open', 'text_layer', 'render', 'ocr', 'classify', 'extract', 'evidence', 'decision', 'other')
TIMED_STAGES = STAGES[:-1]
SKIP_CODES = ('ENCRYPTED', 'OPEN_ERROR', 'EMPTY_DOCUMENT')
ROW_CODES = ('NONE', 'PROCESSING_ERROR', 'GUARD_BLOCKED') + SKIP_CODES
PHASES = ('warmup', 'measure', 'skipped')
TEXT_CLASSES = ('TEXT', 'NONE', 'MIXED')
PAGE_BINS = ('1', '2', '3+')
DECISIONS = ('PASS', 'FAIL', 'NEEDS_REVIEW', 'NOT_ASSESSED', 'ERROR')
TIERS = ('fixture', 'jbai', 'localocr', 'pdftext', 'upstage', 'none', 'OTHER')
ERROR_CODES = ('ARGUMENT_ERROR', 'OUT_EXISTS', 'INPUT_UNAVAILABLE', 'INPUT_OUTPUT_OVERLAP',
               'LOCATION_REJECTED', 'ENGINE_UNAVAILABLE', 'STRATA_INVALID', 'UNEXPECTED_ERROR')
TARGET_MEAN_S = 2.5
TARGET_P95_S = 5.0
DISABLED_ENV = ('JBAI_API_KEY', 'JBAI_ALLOW_REAL_DOCS', 'UPSTAGE_API_KEY')
THREAD_ENV = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS')
KEY_RE = re.compile('[0-9a-f]{16}')
PROGRESS_EVERY = 25
EXTRACTOR_MODULES = ('resident_abstract', 'nhis_payment', 'nhis_payment_gov', 'nhis_acquisition_loss',
                     'nhis_qualification', 'insurance_4', 'business_registration', 'daily_work_record',
                     'receipt', 'exam_docs', 'interview_confirmation')
LOCAL_CONVERSIONS = ('_from_resident', '_from_business_proof', '_from_nhis', '_from_insurance4',
                     '_from_supported_form', '_from_job_doc', '_generic')


class ToolError(Exception):
    """Carries one fixed code from ERROR_CODES."""


def _fail(code):
    raise ToolError(code)


# ---------------------------------------------------------------- statistics


def quantile(values, probability):
    """Linear interpolation on sorted values (same rule as batch_assess)."""
    return batch._quantile(sorted(values), probability)


def describe(values):
    values = sorted(values)
    if not values:
        return dict(n=0, mean=None, median=None, p90=None, p95=None, max=None)
    return dict(n=len(values), mean=statistics.fmean(values), median=statistics.median(values),
                p90=quantile(values, .9), p95=quantile(values, .95), max=values[-1])


def spread(values):
    """Max/min ratio over one document's repeats; None if not computable."""
    values = [v for v in values if v is not None]
    if len(values) < 2 or min(values) <= 0:
        return None
    return max(values) / min(values)


def target_flags(stats):
    mean, p95 = stats['mean'], stats['p95']
    return ('NA' if mean is None else 'O' if mean <= TARGET_MEAN_S else 'X',
            'NA' if p95 is None else 'O' if p95 <= TARGET_P95_S else 'X')


def page_bin(count):
    return '1' if count <= 1 else '2' if count == 2 else '3+'


def text_class(flags):
    if all(flags):
        return 'TEXT'
    return 'NONE' if not any(flags) else 'MIXED'


def document_key(relative):
    return hashlib.sha256(relative.encode('utf-8')).hexdigest()[:16]


# ---------------------------------------------------------------- stage timer


class StageTimer:
    """Exclusive stage times: a nested stage's time is removed from its parent."""

    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.active = False
        self.phase = 'NONE'
        self.cold_model_load = None
        self.first_ocr_call = None
        self.cold_phase = 'NONE'
        self.reset()

    def reset(self):
        self.totals = dict.fromkeys(TIMED_STAGES, 0.0)
        self.stack = []
        self.excluded = 0.0
        self.ocr_calls = 0
        self.text_pages = 0

    @contextmanager
    def stage(self, name):
        if not self.active:
            yield
            return
        frame = [name, 0.0]
        self.stack.append(frame)
        start = self.clock()
        try:
            yield
        finally:
            elapsed = self.clock() - start
            # Identity, not equality: nested same-name frames can compare equal.
            del self.stack[next(i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i] is frame)]
            self.totals[name] += max(0.0, elapsed - frame[1])
            if self.stack:
                self.stack[-1][1] += elapsed

    def exclude(self, elapsed):
        """Remove time (model load) from the enclosing stage and the document total."""
        if not self.active:
            return
        if self.stack:
            self.stack[-1][1] += elapsed
        self.excluded += elapsed

    def wrap(self, name, function):
        timer = self

        def timed(*args, **kwargs):
            with timer.stage(name):
                return function(*args, **kwargs)

        timed.__wrapped__ = function
        return timed


def _wrap_sessions(timer, original):
    def sessions():
        before = original.cache_info().misses
        start = timer.clock()
        try:
            return original()
        finally:
            elapsed = timer.clock() - start
            if original.cache_info().misses > before:
                timer.exclude(elapsed)
                if timer.cold_model_load is None:
                    timer.cold_model_load = elapsed
                    timer.cold_phase = timer.phase
    sessions.cache_info = original.cache_info
    sessions.cache_clear = original.cache_clear
    sessions.__wrapped__ = original
    return sessions


def _wrap_ocr(timer, original):
    def recognize(png, size):
        first = timer.first_ocr_call is None
        start = timer.clock()
        try:
            with timer.stage('ocr'):
                return original(png, size)
        finally:
            if timer.active:
                timer.ocr_calls += 1
            if first:
                timer.first_ocr_call = timer.clock() - start
    recognize.__wrapped__ = original
    return recognize


def _wrap_load_pages(timer, original):
    def load_pages(*args, **kwargs):
        pages = original(*args, **kwargs)
        if timer.active and isinstance(pages, list):
            timer.text_pages += sum(getattr(result, 'engine', None) == 'text_layer' for _, result in pages)
        return pages
    load_pages.__wrapped__ = original
    return load_pages


@contextmanager
def instrument(timer):
    """Install delegation-only wrappers around production functions."""
    import importlib
    import pymupdf
    import fitz
    from demo.backend.ocr import admin_consent_scan, file_evidence, localocr, pdftext
    from engine_v2 import engine as v2engine
    from engine_v2.pipeline import ocr as v2ocr, preprocess
    from engine_v2.pipeline.ocr import own

    with ExitStack() as stack:
        def wrap(owner, name, stage):
            stack.enter_context(patch.object(owner, name, timer.wrap(stage, getattr(owner, name))))
        wrap(pymupdf, 'open', 'open')
        if getattr(fitz, 'open', None) is not None:
            stack.enter_context(patch.object(fitz, 'open', timer.wrap('open', fitz.open)))
        wrap(pymupdf.Page, 'get_text', 'text_layer')
        wrap(pymupdf.Page, 'get_pixmap', 'render')
        wrap(preprocess, '_process_pdf_page', 'render')
        for name in ('classify', 'classify_with_evidence', 'classify_pages_with_evidence'):
            wrap(pdftext, name, 'classify')
        wrap(pdftext, 'read_page_text', 'extract')
        for name in LOCAL_CONVERSIONS:
            wrap(localocr, name, 'extract')
        for name in EXTRACTOR_MODULES:
            wrap(importlib.import_module(f'engine_v2.extractors.{name}'), 'extract', 'extract')
        wrap(file_evidence, 'attach_file_evidence', 'evidence')
        wrap(file_evidence, 'normalize_image_quality', 'evidence')
        wrap(admin_consent_scan, 'inspect_admin_consent_scan', 'evidence')
        stack.enter_context(patch.object(own, 'sessions', _wrap_sessions(timer, own.sessions)))
        stack.enter_context(patch.dict(v2ocr.ENGINES, {'own': _wrap_ocr(timer, v2ocr.ENGINES['own'])}))
        stack.enter_context(patch.object(v2engine, '_load_pages', _wrap_load_pages(timer, v2engine._load_pages)))
        yield timer


# ---------------------------------------------------------------- documents


def inspect(path):
    """Untimed pre-check. Returns only counts and fixed codes."""
    import pymupdf
    from engine_v2.pipeline.preprocess import TEXT_LAYER_MIN_CHARS
    from engine_v2.pipeline.privacy import mask_rrn
    try:
        document = pymupdf.open(path)
    except Exception:
        return dict(code='OPEN_ERROR')
    try:
        with document:
            if document.needs_pass:
                return dict(code='ENCRYPTED')
            if not document.page_count:
                return dict(code='EMPTY_DOCUMENT')
            flags = [len(mask_rrn(page.get_text('text')).strip()) >= TEXT_LAYER_MIN_CHARS for page in document]
    except Exception:
        return dict(code='OPEN_ERROR')
    return dict(code='NONE', pages=len(flags), text_layer=text_class(flags),
                first_image_later_text=int(not flags[0] and any(flags[1:])))


_REQUIREMENTS = {}


def requirement(kind):
    """Upload slot for a detected kind (same rule as batch_assess), cached per kind."""
    if kind in {'X', 'DAILY_WORK_RECORD', 'FARM_BIZ_CERT', 'FISHERY_BIZ_CERT'}:
        return None
    if kind not in _REQUIREMENTS:
        _REQUIREMENTS[kind] = batch._requirement(kind)
    return _REQUIREMENTS[kind]


def _tier(value):
    return value if value in TIERS else 'OTHER'


def _safe_codes():
    from demo.backend.tools.verify_upload import SAFE_CODES
    return SAFE_CODES


def reason_codes(findings):
    """Distinct, sorted ``[code, severity]`` pairs. Message, guidance and detail are never read."""
    safe = _safe_codes()
    pairs = set()
    for finding in findings or ():
        code, severity = getattr(finding, 'code', None), getattr(finding, 'severity', None)
        code = code if isinstance(code, str) and code in safe else UNKNOWN_CODE
        severity = severity if isinstance(severity, str) and severity in SEVERITIES else 'OTHER'
        pairs.add((code, severity))
    return [list(pair) for pair in sorted(pairs)]


def measure(path, timer, *, slot=requirement):
    """Time one document on the production upload path. Caller supplies guards."""
    from demo.backend import ocr as demo_ocr
    from demo.backend.upload_assessment import assess_upload
    timer.reset()
    result = dict(code='NONE', form='X', tier='none', decision='ERROR', reasons=[])
    checked = None
    clock = timer.clock
    read_seconds = decision_seconds = 0.0
    timer.active = True
    started = clock()
    try:
        ocr = demo_ocr.read_document(str(path), None)
        read_seconds = clock() - started
        timer.active = False
        kind = ocr.detected_doc_type.name if ocr.detected_doc_type is not None else 'X'
        result.update(form=kind if kind in batch.KINDS else 'X', tier=_tier(ocr.tier))
        req = slot(kind)  # untimed: the service already knows the slot
        if req is None:
            result['decision'] = 'NOT_ASSESSED'
        else:
            timer.active = True
            decided = clock()
            try:
                with timer.stage('decision'):
                    _, checked = assess_upload(path, req, identity=None,
                                               paper_admin_consent=kind == 'ADMIN_INFO_CONSENT',
                                               reader=lambda file_path, expected: ocr)
            finally:
                decision_seconds = clock() - decided
            result['decision'] = checked.status if checked.status in DECISIONS else 'ERROR'
    except Exception:
        if timer.active and not read_seconds:
            read_seconds = clock() - started
        result['code'] = 'PROCESSING_ERROR'
    finally:
        timer.active = False
    if checked is not None:
        try:  # outside the timed region: only registered codes and severities are kept
            result['reasons'] = reason_codes(checked.findings)
        except Exception:
            result.update(code='PROCESSING_ERROR', reasons=[])
    total = max(0.0, read_seconds + decision_seconds - timer.excluded)
    seconds = {name: timer.totals[name] for name in TIMED_STAGES}
    seconds['other'] = max(0.0, total - sum(seconds.values()))
    seconds['total'] = total
    text_pages = timer.text_pages + (1 if result['tier'] == 'pdftext' else 0)
    result.update(seconds=seconds, ocr_pages=timer.ocr_calls, text_pages=text_pages,
                  cold_start=timer.excluded)
    return result


# ---------------------------------------------------------------- rows


def _blank_row(doc, engine, phase, repeat, code):
    return dict(schema_version=VERSION, key=doc['key'], engine=engine, phase=phase, repeat=repeat, code=code,
                form='X', text_layer=doc.get('text_layer'), pages=doc.get('pages'),
                page_bin=page_bin(doc['pages']) if doc.get('pages') else None,
                first_image_later_text=doc.get('first_image_later_text', 0), tier='none',
                decision='NOT_ASSESSED', ocr_pages=0, text_pages=0, cold_start=0.0, seconds=None, reasons=[])


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_row(row):
    keys = {'schema_version', 'key', 'engine', 'phase', 'repeat', 'code', 'form', 'text_layer', 'pages',
            'page_bin', 'first_image_later_text', 'tier', 'decision', 'ocr_pages', 'text_pages',
            'cold_start', 'seconds'}
    batch._require(isinstance(row, dict) and row.get('schema_version') in READABLE_VERSIONS)
    if row['schema_version'] >= 2:
        keys = keys | {'reasons'}
    batch._require(set(row) == keys)
    batch._require(isinstance(row['key'], str) and KEY_RE.fullmatch(row['key']) is not None)
    batch._require(row['engine'] in ENGINES and row['phase'] in PHASES and row['code'] in ROW_CODES)
    batch._require(type(row['repeat']) is int and row['repeat'] >= 0)
    batch._require(row['form'] in batch.KINDS and row['tier'] in TIERS and row['decision'] in DECISIONS)
    batch._require(row['text_layer'] in TEXT_CLASSES + (None,) and row['page_bin'] in PAGE_BINS + (None,))
    batch._require(row['pages'] is None or (type(row['pages']) is int and row['pages'] > 0))
    batch._require(row['first_image_later_text'] in (0, 1) and type(row['first_image_later_text']) is int)
    batch._require(all(type(row[k]) is int and row[k] >= 0 for k in ('ocr_pages', 'text_pages')))
    batch._require(_finite(row['cold_start']))
    batch._require((row['phase'] == 'skipped') == (row['code'] in SKIP_CODES))
    if row['seconds'] is None:
        batch._require(row['phase'] == 'skipped')
    else:
        batch._require(isinstance(row['seconds'], dict) and set(row['seconds']) == set(STAGES) | {'total'})
        batch._require(all(_finite(v) for v in row['seconds'].values()))
    if 'reasons' in row:
        reasons = row['reasons']
        safe = _safe_codes()
        batch._require(isinstance(reasons, list) and all(
            isinstance(pair, list) and len(pair) == 2 and (pair[0] in safe or pair[0] == UNKNOWN_CODE)
            and pair[1] in SEVERITIES for pair in reasons))
        batch._require([tuple(pair) for pair in reasons] == sorted({tuple(pair) for pair in reasons}))
        batch._require(row['decision'] not in {'NOT_ASSESSED', 'ERROR'} or not reasons)
    return row


def load_strata(directory):
    """Form code per document key from a previous doc_timing run."""
    try:
        out = batch._location(Path(directory).absolute())
        rows_path, run_path = batch._target(out / 'rows.jsonl'), batch._target(out / 'run.json')
        meta = json.loads(run_path.read_bytes())
        batch._require(isinstance(meta, dict) and meta.get('schema_version') in READABLE_VERSIONS)
        forms = defaultdict(Counter)
        for line in rows_path.read_bytes().splitlines():
            row = validate_row(batch._load(line))
            if row['phase'] == 'measure' and row['code'] == 'NONE':
                forms[row['key']][row['form']] += 1
    except Exception:
        _fail('STRATA_INVALID')
    return {key: sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]
            for key, counter in forms.items()}


def allocate(sizes, n):
    """Proportional allocation, at least one per stratum, largest remainder, capped by size."""
    total = sum(sizes.values())
    strata = sorted(sizes)
    if n >= total:
        return dict(sizes)
    if n < len(strata):
        chosen = sorted(strata, key=lambda s: (-sizes[s], s))[:n]
        return {s: int(s in chosen) for s in strata}
    exact = {s: n * sizes[s] / total for s in strata}
    alloc = {s: min(sizes[s], max(1, math.floor(exact[s]))) for s in strata}
    while sum(alloc.values()) > n:  # minimum-one bumps: take back from the most over-allocated
        s = min((s for s in strata if alloc[s] > 1), key=lambda s: (exact[s] - alloc[s], s))
        alloc[s] -= 1
    while sum(alloc.values()) < n:  # largest remainder, capped by stratum size
        s = max((s for s in strata if alloc[s] < sizes[s]), key=lambda s: (exact[s] - alloc[s], sizes[s], s))
        alloc[s] += 1
    return alloc


def stratified_sample(strata, n, seed):
    """strata: {stratum: [keys]} → sorted selected keys, deterministic for a seed."""
    alloc = allocate({s: len(keys) for s, keys in strata.items()}, n)
    rng = random.Random(seed)
    selected = []
    for s in sorted(strata):
        selected.extend(rng.sample(sorted(strata[s]), alloc[s]))
    return sorted(selected)


# ---------------------------------------------------------------- summary


def _fmt(value):
    if value is None:
        return 'NA'
    if isinstance(value, float):
        return f'{value:.3f}'
    return str(value)


def _line(*values):
    return ' '.join(_fmt(v) for v in values)


def _stats_line(head, stats):
    return _line(*head, stats['n'], stats['mean'], stats['median'], stats['p90'], stats['p95'], stats['max'])


def summarize(rows, meta):
    lines = ['DOC_TIMING']
    options = meta['options']
    lines.append('RUN engine repeat warmup sample limit strata_basis documents_selected')
    lines.append(_line('RUN', 'own', options['repeat'], options['warmup'], options['sample'], options['limit'],
                       options['strata_basis'], meta['counts']['selected']))
    skipped = Counter(r['code'] for r in rows if r['phase'] == 'skipped')
    errors = Counter(r['code'] for r in rows if r['phase'] == 'measure' and r['code'] != 'NONE')
    lines.append('SKIP code documents')
    for code in SKIP_CODES:
        lines.append(_line('SKIP', code, skipped[code]))
    lines.append('ERROR code measurements')
    for code in ('PROCESSING_ERROR', 'GUARD_BLOCKED'):
        lines.append(_line('ERROR', code, errors[code]))
    warm = [r['seconds']['total'] for r in rows if r['phase'] == 'warmup' and r['code'] == 'NONE']
    lines.append('WARMUP engine runs mean_s max_s')
    lines.append(_line('WARMUP', 'own', len(warm), statistics.fmean(warm) if warm else None, max(warm, default=None)))
    cold = meta.get('cold_start') or {}
    lines.append('COLD_START engine model_load_s first_ocr_call_s phase')
    lines.append(_line('COLD_START', 'own', cold.get('model_load_s'), cold.get('first_ocr_call_s'),
                       cold.get('phase', 'NONE')))

    measured = [r for r in rows if r['phase'] == 'measure' and r['code'] == 'NONE']
    by_doc = defaultdict(list)
    for row in measured:
        by_doc[row['key']].append(row)
    docs = []
    for key, items in sorted(by_doc.items()):
        items.sort(key=lambda r: r['repeat'])
        first = items[0]
        docs.append(dict(value=statistics.median(r['seconds']['total'] for r in items),
                         spread=spread([r['seconds']['total'] for r in items]),
                         form=Counter(r['form'] for r in items).most_common(1)[0][0],
                         text_layer=first['text_layer'], page_bin=first['page_bin'], pages=first['pages'],
                         decision=first['decision'], tier=first['tier'], later=first['first_image_later_text'],
                         ocr_pages=first['ocr_pages'], text_pages=first['text_pages']))
    overall = describe([d['value'] for d in docs])
    lines.append('OVERALL engine n mean_s median_s p90_s p95_s max_s')
    lines.append(_stats_line(('OVERALL', 'own'), overall))
    mean_flag, p95_flag = target_flags(overall)
    lines.append(_line('TARGET', 'own', 'MEAN_LE_2_5S', mean_flag))
    lines.append(_line('TARGET', 'own', 'P95_LE_5S', p95_flag))

    def grouped(title, field, order):
        lines.append(f'{title} engine group n mean_s median_s p90_s p95_s max_s')
        groups = defaultdict(list)
        for d in docs:
            groups[d[field]].append(d['value'])
        for name in order or sorted(groups):
            lines.append(_stats_line((title, 'own', name), describe(groups.get(name, []))))
    grouped('BY_FORM', 'form', None)
    grouped('BY_TEXT_LAYER', 'text_layer', TEXT_CLASSES)
    grouped('BY_PAGES', 'page_bin', PAGE_BINS)

    stage_sums = {name: sum(r['seconds'][name] for r in measured) for name in STAGES}
    grand = sum(r['seconds']['total'] for r in measured)
    lines.append('STAGE engine stage sum_s share_pct')
    for name in STAGES:
        lines.append(_line('STAGE', 'own', name.upper(), stage_sums[name],
                           100 * stage_sums[name] / grand if grand else None))
    lines.append(_line('STAGE', 'own', 'TOTAL', grand, 100.0 if grand else None))

    spreads = sorted(d['spread'] for d in docs if d['spread'] is not None)
    lines.append('REPEAT engine repeat docs_with_spread spread_median spread_p90')
    lines.append(_line('REPEAT', 'own', options['repeat'], len(spreads),
                       statistics.median(spreads) if spreads else None,
                       quantile(spreads, .9) if spreads else None))

    form_values = defaultdict(list)
    for d in docs:
        form_values[d['form']].append(d['value'])
    total_value = sum(d['value'] for d in docs)
    ranked = sorted(form_values.items(), key=lambda item: (-statistics.fmean(item[1]), item[0]))[:5]
    lines.append('SLOW_FORM engine rank form n mean_s p95_s share_pct')
    for rank, (form, values) in enumerate(ranked, 1):
        lines.append(_line('SLOW_FORM', 'own', rank, form, len(values), statistics.fmean(values),
                           quantile(values, .95), 100 * sum(values) / total_value if total_value else None))

    later = [d for d in docs if d['later']]
    lines.append('FIRST_PAGE_IMAGE_LATER_TEXT engine docs')
    lines.append(_line('FIRST_PAGE_IMAGE_LATER_TEXT', 'own', 'docs', len(later)))
    later_status = Counter(d['decision'] for d in later)
    for status in DECISIONS:
        lines.append(_line('FIRST_PAGE_IMAGE_LATER_TEXT', 'own', 'status', status, later_status[status]))
    later_tier = Counter(d['tier'] for d in later)
    for tier in TIERS:
        if later_tier[tier]:
            lines.append(_line('FIRST_PAGE_IMAGE_LATER_TEXT', 'own', 'tier', tier, later_tier[tier]))
    lines.append('PAGES engine TEXT_PAGES OCR_PAGES TOTAL_PAGES')
    lines.append(_line('PAGES', 'own', sum(d['text_pages'] for d in docs), sum(d['ocr_pages'] for d in docs),
                       sum(d['pages'] for d in docs)))
    decision = Counter(d['decision'] for d in docs)
    lines.append('DECISION engine status docs')
    for status in DECISIONS:
        lines.append(_line('DECISION', 'own', status, decision[status]))
    tiers = Counter(d['tier'] for d in docs)
    lines.append('TIER engine tier docs')
    for tier in TIERS:
        lines.append(_line('TIER', 'own', tier, tiers[tier]))
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- environment


def _command(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10, check=False).stdout.strip()
    except Exception:
        return ''


def _safe(value, pattern=r'[A-Za-z0-9 ,._()+-]{1,64}'):
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else 'UNKNOWN'


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _power():
    text = _command(['pmset', '-g', 'batt'])
    return 'AC' if 'AC Power' in text else 'BATTERY' if 'Battery Power' in text else 'UNKNOWN'


def _version(*names):
    import importlib.metadata
    for name in names:
        try:
            return _safe(importlib.metadata.version(name))
        except Exception:
            continue
    return None


def environment():
    repo = Path(__file__).resolve().parents[2]
    commit = _command(['git', '-C', str(repo), 'rev-parse', 'HEAD'])
    dirty = _command(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=no'])
    load = os.getloadavg()
    return dict(
        machine_model=_safe(_command(['sysctl', '-n', 'hw.model'])),
        cpu=_safe(_command(['sysctl', '-n', 'machdep.cpu.brand_string'])),
        cores=dict(logical=os.cpu_count(), performance=_int(_command(['sysctl', '-n', 'hw.perflevel0.physicalcpu'])),
                   efficiency=_int(_command(['sysctl', '-n', 'hw.perflevel1.physicalcpu']))),
        power=_power(), load_start=[round(v, 2) for v in load], load_end=None,
        os=_safe(platform.platform(terse=True)), python=_safe(platform.python_version()),
        libraries=dict(pymupdf=_version('pymupdf', 'PyMuPDF'), onnxruntime=_version('onnxruntime'),
                       numpy=_version('numpy'),
                       opencv=_version('opencv-python-headless', 'opencv-python', 'opencv-contrib-python'),
                       pillow=_version('pillow', 'Pillow')),
        thread_env={name: (os.environ[name] if re.fullmatch('[0-9]{1,3}', os.environ.get(name, '')) else
                           'SET' if name in os.environ else None) for name in THREAD_ENV},
        git_commit=commit if re.fullmatch('[0-9a-f]{40}', commit) else 'UNKNOWN',
        git_dirty='O' if dirty else 'X',
        started=datetime.now().astimezone().isoformat(timespec='seconds'), finished=None)


def own_threads():
    """Actual ONNX session settings, only if the run already loaded the model."""
    from engine_v2.pipeline.ocr import own
    # The lru_cache object itself (it also has __wrapped__, pointing at the uncached function).
    original = own.sessions if hasattr(own.sessions, 'cache_info') else own.sessions.__wrapped__
    try:
        if not original.cache_info().currsize:
            return dict(intra=None, inter=None, loaded='X')
        det, _, _ = original()
        options = det.get_session_options()
        return dict(intra=options.intra_op_num_threads, inter=options.inter_op_num_threads, loaded='O')
    except Exception:
        return dict(intra=None, inter=None, loaded='X')


def own_available():
    from engine_v2.pipeline.ocr import own
    from engine_v2.tools.fetch_own_models import ASSETS
    return all((own.MODEL_DIR / name).is_file() for name in ASSETS)


# ---------------------------------------------------------------- run


def _print(text):
    print(text, flush=True)


def run(root, out, *, engines=('own',), repeat=1, warmup=3, sample=None, seed=20261117, strata_from=None,
        limit=None):
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
    for name in DISABLED_ENV:
        os.environ.pop(name, None)
    os.environ['ENGINE_V2_OCR'] = 'own'
    if not own_available():
        _fail('ENGINE_UNAVAILABLE')
    strata_forms = load_strata(strata_from) if strata_from is not None else None

    meta = dict(schema_version=VERSION, environment=environment(),
                options=dict(engines=list(engines), repeat=repeat, warmup=warmup, sample=sample, seed=seed,
                             limit=limit, strata_basis='NONE' if sample is None else
                             'FORM' if strata_forms is not None else 'PAGES_TEXT',
                             external_ocr_disabled='O'),
                counts={}, cold_start=None, own_threads=None)
    env = meta['environment']
    if env['load_start'][0] > (env['cores']['logical'] or 1) / 2:
        _print('WARNING LOAD_HIGH')
    if env['power'] == 'BATTERY':
        _print('WARNING ON_BATTERY')

    inventory, excluded = batch.inventory(root)
    files = [p for p in inventory if p.suffix.lower() == '.pdf']
    keyed = {}
    for path in files:
        keyed[document_key(path.relative_to(root).as_posix())] = path
    _print(f'inventory_pdf {len(keyed)} excluded_files {sum(excluded.values()) + len(inventory) - len(files)}')

    docs = {}
    with batch.guarded():
        for key in sorted(keyed):
            docs[key] = dict(key=key, path=keyed[key], **inspect(keyed[key]))
    keys = sorted(docs)
    if sample is not None:
        strata = defaultdict(list)
        for key in keys:
            doc = docs[key]
            if strata_forms is not None:
                stratum = strata_forms.get(key, 'UNSEEN')
            else:
                stratum = doc['code'] if doc['code'] != 'NONE' else f"{doc['text_layer']}_{page_bin(doc['pages'])}"
            strata[stratum].append(key)
        keys = stratified_sample(strata, sample, seed)
    if limit is not None:
        keys = keys[:limit]
    selected = [docs[key] for key in keys]
    meta['counts'] = dict(inventory_pdf=len(keyed), selected=len(selected),
                          skipped=sum(d['code'] != 'NONE' for d in selected))

    out.mkdir(mode=0o700, parents=True)
    batch._location(out)
    rows_path = batch._target(out / 'rows.jsonl')
    batch._atomic(batch._target(out / 'run.json'), meta)
    rows = []
    fd = batch._open(rows_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        def emit(row):
            validate_row(row)
            stream.write(json.dumps(row, ensure_ascii=True, sort_keys=True, allow_nan=False) + '\n')
            stream.flush()
            rows.append(row)

        for doc in selected:
            if doc['code'] != 'NONE':
                emit(_blank_row(doc, 'own', 'skipped', 0, doc['code']))
        processable = [doc for doc in selected if doc['code'] == 'NONE']
        timer = StageTimer()
        started = time.perf_counter()
        with batch.guarded():
            installed = instrument(timer)
            installed.__enter__()
        try:
            plan = [('warmup', 0, processable[:warmup])]
            plan += [('measure', number, processable) for number in range(1, repeat + 1)]
            for phase, number, batch_docs in plan:
                timer.phase = phase
                for index, doc in enumerate(batch_docs, 1):
                    row = _blank_row(doc, 'own', phase, number, 'NONE')
                    try:
                        with batch.guarded():
                            row.update(measure(doc['path'], timer))
                    except batch.BatchError:
                        row['code'] = 'GUARD_BLOCKED'
                        row['seconds'] = row['seconds'] or {name: 0.0 for name in (*STAGES, 'total')}
                    emit(row)
                    if index % PROGRESS_EVERY == 0 or index == len(batch_docs):
                        _print(f'progress own {phase} {number} done {index} total {len(batch_docs)} '
                               f'elapsed_s {time.perf_counter() - started:.1f}')
        finally:
            with batch.guarded():
                installed.__exit__(None, None, None)
        os.fsync(stream.fileno())

    meta['cold_start'] = dict(model_load_s=timer.cold_model_load, first_ocr_call_s=timer.first_ocr_call,
                              phase=timer.cold_phase)
    meta['own_threads'] = own_threads()
    env['load_end'] = [round(v, 2) for v in os.getloadavg()]
    env['finished'] = datetime.now().astimezone().isoformat(timespec='seconds')
    batch._atomic(batch._target(out / 'run.json'), meta)
    text = summarize(rows, meta)
    batch._target(out / 'summary_brief.txt')
    (out / 'summary_brief.txt').write_text(text, encoding='utf-8')
    _print(text.rstrip('\n'))
    return 1 if any(r['code'] in {'PROCESSING_ERROR', 'GUARD_BLOCKED'} for r in rows) else 0


def parser():
    result = batch.SafeParser(prog='doc_timing', description='Value-free per-document upload-path timing')
    result.add_argument('--root', required=True)
    result.add_argument('--out', required=True)
    result.add_argument('--engines', nargs='+', default=['own'])
    result.add_argument('--repeat', type=int, default=1)
    result.add_argument('--warmup', type=int, default=3)
    result.add_argument('--sample', type=int)
    result.add_argument('--seed', type=int, default=20261117)
    result.add_argument('--strata-from')
    result.add_argument('--limit', type=int)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if (args.engines != ['own'] or not 1 <= args.repeat <= 50 or not 0 <= args.warmup <= 100 or
                (args.sample is not None and args.sample < 1) or (args.limit is not None and args.limit < 1) or
                args.seed < 0 or (args.strata_from is not None and args.sample is None)):
            _fail('ARGUMENT_ERROR')
        return run(args.root, args.out, engines=tuple(args.engines), repeat=args.repeat, warmup=args.warmup,
                   sample=args.sample, seed=args.seed, strata_from=args.strata_from, limit=args.limit)
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
