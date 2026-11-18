"""Localhost-only blind ground-truth labeling for B1-B3 and C1-C3 (label criteria v0.1).

Serve the labeling screen (127.0.0.1 only)::

    python -B -m engine_v2.tools.label_review serve --rows ROWS --root ROOT --out OUT [--revalue-forms F1,F2]

A later rows file opens the next round: B = every FAIL, C = the round-1 sample still PASS (never drawn again),
N = every PASS document that was not PASS in round 1 (labeled in full). Stage-one labels carry over by document key; C key-value O/X carry
over from the previous round for every form not named in ``--revalue-forms`` (without the option every C
document of the new round is checked again).

Print the summary (numbers and codes only)::

    python -B -m engine_v2.tools.label_review summary --out OUT [--round N]

List labeled disagreements (ordinal and codes only)::

    python -B -m engine_v2.tools.label_review mismatch --out OUT [--round N]

Inputs are a doc_timing ``rows.jsonl`` (row format 2 or later) and the PDF folder its 16-hex document keys
were computed from. Samples: B = every FAIL document, C = PASS documents stratified by form (fixed seed).
The label file keeps keys, stage, state/reason codes, item O/X, time and criteria version only. Values the
engine reads are recomputed on the service path for the screen and never written anywhere. The measurement
definitions live in ``.trellis/tasks/11-17-speed-baseline/measurement-definitions.md``.
"""
import sys
sys.dont_write_bytecode = True

import argparse
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading

from . import batch_assess as batch
from . import doc_timing as timing

VERSION = 1
CRITERIA = 'v0.2'
#: Label criteria versions this tool reads. Records keep the version they were saved with.
CRITERIA_VERSIONS = ('v0.1', 'v0.2')
#: Fixed bind address. There is deliberately no option to change it.
HOST = '127.0.0.1'
DEFAULT_PORT = 8765
DEFAULT_SAMPLE = 150
DEFAULT_SEED = 20261117
CROSS_SIZE = 20
ALPHA = 0.05
STATES = ('PASS', 'NEEDS_REVIEW', 'FAIL', 'HOLD')
REASONS = ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R9')
STAGES = ('blind', 'cross', 'values')
MARKS = ('O', 'X')
SCALES = (1, 2, 3)
MAX_PIXELS = 6000
VALUE_CACHE = 4
KEY_RE = re.compile('[0-9a-f]{16}')
SHA_RE = re.compile('[0-9a-f]{64}')
REPO = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / 'label_review_static'
STATIC_FILES = {'app.js': 'text/javascript; charset=utf-8', 'app.css': 'text/css; charset=utf-8'}
DOC_ITEM = '서류종류'
ISSUE_ITEM = '발급일'
_RESIDENT_ITEMS = ('성명', '생년월일', '발급일', '초본신청인성명', '초본신청인생년월일', '주소이력건수',
                   '전입일', '현주소시도', '주소변동내역')
ERROR_CODES = ('ARGUMENT_ERROR', 'INPUT_UNAVAILABLE', 'ROWS_INVALID', 'LOCATION_REJECTED',
               'INPUT_OUTPUT_OVERLAP', 'OUT_LOCKED', 'PLAN_INVALID', 'PLAN_MISMATCH', 'LABELS_INVALID',
               'ENGINE_UNAVAILABLE', 'BASE_ROWS_REQUIRED', 'UNEXPECTED_ERROR')
SECURITY_HEADERS = {
    'Content-Security-Policy': ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
                                "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"),
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'Cache-Control': 'no-store',
    'X-Frame-Options': 'DENY',
}


class ToolError(Exception):
    """Carries one fixed code from ERROR_CODES."""


def _fail(code):
    raise ToolError(code)


def _require(condition, code):
    if not condition:
        _fail(code)


def _now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


# ---------------------------------------------------------------- statistics


def _binomial_tail(n, k, p):
    """P(X >= k) for X ~ Binomial(n, p), summed in log space."""
    if k <= 0 or p >= 1:
        return 1.0
    if k > n or p <= 0:
        return 0.0
    log_p, log_q = math.log(p), math.log1p(-p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * log_p + (n - i) * log_q
             for i in range(k, n + 1)]
    top = max(terms)
    return min(1.0, math.exp(top) * sum(math.exp(t - top) for t in terms))


def _solve(n, k, target):
    """p such that P(Binomial(n, p) >= k) = target (the tail increases with p)."""
    low, high = 0.0, 1.0
    for _ in range(200):
        middle = (low + high) / 2
        if _binomial_tail(n, k, middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def cp_lower(k, n, alpha=ALPHA):
    """One-sided Clopper-Pearson lower bound: Beta(alpha; k, n - k + 1); k = n gives alpha^(1/n)."""
    if n == 0:
        return None
    if k == 0:
        return 0.0
    if k == n:
        return alpha ** (1 / n)
    return _solve(n, k, alpha)


def cp_upper(k, n, alpha=ALPHA):
    """One-sided Clopper-Pearson upper bound: Beta(1 - alpha; k + 1, n - k); k = 0 gives 1 - alpha^(1/n)."""
    if n == 0:
        return None
    if k == n:
        return 1.0
    if k == 0:
        return 1 - alpha ** (1 / n)
    return _solve(n, k + 1, 1 - alpha)


# ---------------------------------------------------------------- items


def item_names(form):
    """Fixed per-form vocabulary of key values compared against the original (never values)."""
    base = _RESIDENT_ITEMS if form in {'RESIDENT_ABSTRACT', 'RESIDENT_CERTIFICATE'} else batch.FIELDS.get(form, ())
    return tuple(dict.fromkeys((DOC_ITEM, *base, ISSUE_ITEM)))


ALL_ITEMS = frozenset(name for form in batch.KINDS for name in item_names(form))


def form_label(form):
    from demo.backend.rules.doc_types import DocType
    member = getattr(DocType, form, None) if form != 'X' else None
    return member.value if member is not None else '미판별'


def cutoff(form):
    """Issue-date bounds the engine rules use for this form's double-savings slot."""
    req = timing.requirement(form)
    if req is None:
        return dict(basis='none', min=None, max=None)
    return dict(basis=req.date_basis if isinstance(req.date_basis, str) else 'none',
                min=req.min_issue_date.isoformat() if req.min_issue_date else None,
                max=req.max_issue_date.isoformat() if req.max_issue_date else None)


def checks(form):
    """What to check for a form, with values read from the slot doc_timing assesses against.

    The slot comes from ``doc_timing.requirement`` (double-savings default criteria, the same code path as the
    measurement); thresholds come from the engine constants. Never depends on a document or its verdict.
    """
    from engine import config as engine_config
    from demo.backend.ocr import file_evidence
    req = timing.requirement(form)
    if req is None:
        return []
    items = []

    def add(text, codes, source):
        items.append(dict(text=text, codes=list(codes), source=source))

    add(f'요구 서류: {req.label}', ['R1'], 'required_docs.py')
    basis = {'issue_date': '발급일', 'payment_date': '결제일', 'interview_date': '면접일',
             'exam_date': '응시일'}.get(req.date_basis, '발급일')
    if req.date_basis == 'none' or (req.min_issue_date is None and req.max_issue_date is None):
        add('발급일 기준 없음', [], 'criteria.py')
    else:
        bounds = [f'{req.min_issue_date.isoformat()} 이후'] if req.min_issue_date else []
        bounds += [f'{req.max_issue_date.isoformat()} 이전'] if req.max_issue_date else []
        add(f'{basis}이 {" · ".join(bounds)}', ['R3'], 'criteria.py · programs.py')
    if req.premium_months:
        add(f'조회기간에 심사 대상 고지월 {", ".join(req.premium_months)}이 모두 들어 있고 그 달의 고지금액이 있음',
            ['R5'], 'criteria.py')
        add('서류에 표시된 전체 쪽수만큼 쪽이 모두 있음', ['R2'], 'doc_check.py')
    if req.recent_years:
        add(f'최근 {req.recent_years}년 자격 변동내역이 포함됨(조회기간 또는 이력)', ['R5'], 'criteria.py')
    if form == 'RESIDENT_ABSTRACT':
        add('쪽 표기(예: 1/3)의 모든 쪽이 있고 중복 쪽이 없음', ['R2'], 'doc_check.py')
        add('과거 주소 변동사항(최근 5년)이 포함됨', ['R5'], 'doc_check.py')
        add('주소 이력에 발생일·신고일 날짜가 있음', ['R5'], 'doc_check.py')
    if form == 'ADMIN_INFO_CONSENT':
        add("동의 표시가 '동의함'", ['R6'], 'upload_assessment.py')
        if req.requires_signature:
            add('자필 서명이 있음', ['R6'], 'required_docs.py')
    add(f'사람이 핵심 항목(성명·생년월일·발급일 등)을 읽을 수 있음. 엔진은 화질 점수 '
        f'{engine_config.IMAGE_QUALITY_THRESHOLD} 미만이거나 원본 이미지가 짧은 변 {file_evidence.MIN_SHORT_EDGE}px·'
        f'긴 변 {file_evidence.MIN_LONG_EDGE}px 미만이면서 핵심 항목을 못 읽을 때만 재업로드로 봄',
        ['R4'], 'config.py · file_evidence.py')
    return items


# ---------------------------------------------------------------- rows and samples


def load_rows(path):
    """Return (sha256, {key: {form, decision, reasons}}) from the first measured repeat of each document."""
    try:
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            _fail('INPUT_UNAVAILABLE')
        data = path.read_bytes()
    except OSError:
        _fail('INPUT_UNAVAILABLE')
    docs = {}
    try:
        for line in data.splitlines():
            if not line.strip():
                continue
            row = timing.validate_row(batch._load(line))
            batch._require(row['schema_version'] >= 2)
            if row['phase'] == 'measure' and row['repeat'] == 1 and row['code'] == 'NONE':
                batch._require(row['key'] not in docs)
                docs[row['key']] = dict(form=row['form'], decision=row['decision'],
                                        reasons=[list(pair) for pair in row['reasons']])
    except ToolError:
        raise
    except Exception:
        _fail('ROWS_INVALID')
    _require(docs, 'ROWS_INVALID')
    return hashlib.sha256(data).hexdigest(), docs


def rank(seed, salt, key):
    """Permanent random number of a key: independent of labels and of other keys."""
    return hashlib.sha256(f'{seed}:{salt}:{key}'.encode('ascii')).hexdigest()


def draw(docs, size, seed):
    """B = every FAIL key; C = PASS keys allocated by form, smallest permanent rank inside each form."""
    b = sorted(key for key, doc in docs.items() if doc['decision'] == 'FAIL')
    strata = defaultdict(list)
    for key, doc in docs.items():
        if doc['decision'] == 'PASS':
            strata[doc['form']].append(key)
    alloc = timing.allocate({form: len(keys) for form, keys in strata.items()}, size) if strata else {}
    c = []
    for form in sorted(strata):
        c.extend(sorted(strata[form], key=lambda key: rank(seed, 'c', key))[:alloc[form]])
    return dict(b=b, c=sorted(c), c_alloc={form: alloc[form] for form in sorted(strata)})


#: Decision code for an earlier sampled key that has no measured row in the new rows file.
ABSENT = 'ABSENT'
#: Round fields added for later rounds; plans written before them stay valid.
ROUND_FIELDS = {'round', 'rows_sha256', 'created', 'counts', 'b', 'c', 'c_alloc', 'docs'}
ROUND_EXTRA = {'revalue', 'label_base', 'carried', 'n', 'pass_keys'}


def members(item):
    """Keys of a round's sets B, C and N (N is empty in round 1 and in plans written before it)."""
    return item['b'] + item['c'] + item.get('n', [])


def valued(item):
    """Keys of a round that need key-value O/X: C and N."""
    return set(item['c']) | set(item.get('n', []))


def _carried(previous, docs):
    """New decision (or ABSENT) of every key sampled in an earlier round: the before → after table."""
    keys = sorted({key for item in previous for key in members(item)})
    return {key: docs[key]['decision'] if key in docs else ABSENT for key in keys}


def sets(docs, size, seed, previous=()):
    """B, C, N of a round.

    Round 1: B = every FAIL, C = the stratified PASS sample (``draw``), N empty. Later rounds keep the round-1
    sample: C = round-1 C keys that are PASS again, N = every PASS key that was not PASS in round-1 rows (the
    new-PASS stratum, labeled in full), B = every FAIL. Needs the round-1 PASS keys (``pass_keys``).
    """
    if not previous:
        return dict(draw(docs, size, seed), n=[])
    base = previous[0]
    _require('pass_keys' in base, 'BASE_ROWS_REQUIRED')
    now = {key for key, doc in docs.items() if doc['decision'] == 'PASS'}
    c = sorted(key for key in base['c'] if key in now)
    forms = Counter(docs[key]['form'] for key in c)
    return dict(b=sorted(key for key, doc in docs.items() if doc['decision'] == 'FAIL'), c=c,
                c_alloc={form: forms[form] for form in sorted(forms)}, n=sorted(now - set(base['pass_keys'])))


def _round(number, digest, docs, size, seed, previous=(), revalue=None, label_base=0):
    sample = sets(docs, size, seed, previous)
    counts = Counter(doc['decision'] for doc in docs.values())
    chosen = sample['b'] + sample['c'] + sample['n']
    return dict(round=number, rows_sha256=digest, created=_now(),
                counts=dict(documents=len(docs), **{d: counts[d] for d in timing.DECISIONS}),
                b=sample['b'], c=sample['c'], c_alloc=sample['c_alloc'], n=sample['n'],
                pass_keys=sorted(key for key, doc in docs.items() if doc['decision'] == 'PASS'),
                docs={key: docs[key] for key in sorted(chosen)},
                revalue=revalue, label_base=label_base, carried=_carried(previous, docs))


def _keys(value):
    return isinstance(value, list) and all(isinstance(k, str) and KEY_RE.fullmatch(k) for k in value) and \
        len(set(value)) == len(value)


def validate_plan(plan):
    try:
        batch._require(isinstance(plan, dict) and set(plan) == {'schema_version', 'criteria', 'seed', 'sample',
                                                                 'cross_size', 'rounds', 'cross'})
        batch._require(plan['schema_version'] == VERSION and plan['criteria'] in CRITERIA_VERSIONS)
        batch._require(all(type(plan[k]) is int and plan[k] >= 0 for k in ('seed', 'sample', 'cross_size')))
        batch._require(isinstance(plan['rounds'], list) and plan['rounds'])
        base = 0
        for number, item in enumerate(plan['rounds'], 1):
            batch._require(isinstance(item, dict) and ROUND_FIELDS <= set(item) <= ROUND_FIELDS | ROUND_EXTRA)
            batch._require(item['round'] == number and SHA_RE.fullmatch(item['rows_sha256']))
            n = item.get('n', [])
            batch._require(_keys(item['b']) and _keys(item['c']) and _keys(n) and _keys(item.get('pass_keys', [])))
            batch._require(len(set(members(item))) == len(members(item)))
            batch._require(set(item['docs']) == set(members(item)))
            for doc in item['docs'].values():
                batch._require(set(doc) == {'form', 'decision', 'reasons'} and doc['form'] in batch.KINDS)
                batch._require(doc['decision'] in timing.DECISIONS and isinstance(doc['reasons'], list))
            revalue = item.get('revalue')
            batch._require(revalue is None or (isinstance(revalue, list) and all(
                isinstance(form, str) and form in batch.KINDS for form in revalue) and revalue == sorted(set(revalue))))
            label_base = item.get('label_base', 0)
            batch._require(type(label_base) is int and label_base >= base)
            base = label_base
            carried = item.get('carried', {})
            batch._require(isinstance(carried, dict) and _keys(list(carried)) and
                           all(value in timing.DECISIONS + (ABSENT,) for value in carried.values()))
        cross = plan['cross']
        batch._require(cross is None or (isinstance(cross, dict) and set(cross) == {'round', 'keys', 'created'}
                                         and _keys(cross['keys'])))
    except batch.BatchError:
        _fail('PLAN_INVALID')
    return plan


def read_plan(out):
    path = Path(out) / 'plan.json'
    if path.is_symlink():
        _fail('PLAN_INVALID')
    if not path.exists():
        return None
    try:
        return validate_plan(batch._load(path.read_bytes()))
    except ToolError:
        raise
    except Exception:
        _fail('PLAN_INVALID')


def write_plan(out, plan):
    validate_plan(plan)
    batch._atomic(batch._target(Path(out) / 'plan.json'), plan)


def update_plan(plan, digest, docs, size, seed, revalue=None, label_base=0):
    """Same rows → same round (re-derived and compared); new rows → a new round. Returns (plan, round).

    ``revalue`` (sorted form codes, or None for every form) is stored on the round; given again for an existing
    round it replaces the stored list, omitted it keeps it. ``label_base`` is the number of label records that
    existed when the round was opened: records before it are carried over from earlier rounds.
    """
    if plan is None:
        plan = dict(schema_version=VERSION, criteria=CRITERIA, seed=seed, sample=size, cross_size=CROSS_SIZE,
                    rounds=[], cross=None)
    _require(plan['seed'] == seed and plan['sample'] == size, 'PLAN_MISMATCH')
    for item in plan['rounds']:
        if item['rows_sha256'] == digest:
            fresh = _round(item['round'], digest, docs, size, seed, plan['rounds'][:item['round'] - 1])
            _require(all(fresh[k] == item[k] for k in ('b', 'c', 'c_alloc', 'docs', 'carried', 'n', 'pass_keys')
                         if k in item), 'PLAN_MISMATCH')
            item.setdefault('pass_keys', fresh['pass_keys'])  # plans written before N: filled from the same rows
            if revalue is not None:
                item['revalue'] = revalue
            return plan, item
    item = _round(len(plan['rounds']) + 1, digest, docs, size, seed, plan['rounds'], revalue, label_base)
    plan['rounds'].append(item)
    return plan, item


# ---------------------------------------------------------------- labels


def validate_label(record):
    try:
        batch._require(isinstance(record, dict) and set(record) == {'v', 'key', 'stage', 'status', 'reasons',
                                                                     'fields', 'round', 'revised', 'at',
                                                                     'criteria'})
        batch._require(record['v'] == VERSION and record['criteria'] in CRITERIA_VERSIONS)
        batch._require(isinstance(record['key'], str) and KEY_RE.fullmatch(record['key']))
        batch._require(record['stage'] in STAGES and record['revised'] in MARKS)
        batch._require(isinstance(record['at'], str) and len(record['at']) <= 40)
        datetime.fromisoformat(record['at'])
        reasons, fields = record['reasons'], record['fields']
        batch._require(isinstance(reasons, list) and isinstance(fields, list))
        if record['stage'] == 'values':
            batch._require(record['status'] is None and not reasons and record['round'] is not None)
            batch._require(type(record['round']) is int and record['round'] >= 1 and fields)
            names = [pair[0] for pair in fields if isinstance(pair, list) and len(pair) == 2]
            batch._require(len(names) == len(fields) and len(set(names)) == len(names))
            batch._require(all(pair[0] in ALL_ITEMS and pair[1] in MARKS for pair in fields))
        else:
            batch._require(record['status'] in STATES and record['round'] is None and not fields)
            batch._require(all(code in REASONS for code in reasons) and reasons == sorted(set(reasons)))
            batch._require(bool(reasons) == (record['status'] == 'FAIL'))
    except (batch.BatchError, TypeError, ValueError):
        raise ValueError('LABEL_INVALID') from None
    return record


def label(key, stage, *, status=None, reasons=(), fields=(), round_number=None, revised='X'):
    return validate_label(dict(v=VERSION, key=key, stage=stage, status=status, reasons=sorted(set(reasons)),
                               fields=[list(pair) for pair in fields], round=round_number, revised=revised,
                               at=_now(), criteria=CRITERIA))


def read_labels(out, *, repair=False):
    """Records in file order. An incomplete final line is ignored (or truncated with repair=True)."""
    path = Path(out) / 'labels.jsonl'
    if path.is_symlink():
        _fail('LABELS_INVALID')
    if not path.exists():
        return []
    data = path.read_bytes()
    lines = data.split(b'\n')
    tail = lines.pop()  # bytes after the last newline: empty for a complete file
    records = []
    try:
        for line in lines:
            records.append(validate_label(batch._load(line)))
    except Exception:
        _fail('LABELS_INVALID')
    if tail and repair:
        fd = batch._open(path, os.O_WRONLY)
        try:
            os.ftruncate(fd, len(data) - len(tail))
            os.fsync(fd)
        finally:
            os.close(fd)
    return records


def append_label(out, record):
    validate_label(record)
    fd = batch._open(Path(out) / 'labels.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    with os.fdopen(fd, 'ab') as stream:
        stream.write(json.dumps(record, ensure_ascii=True, sort_keys=True, allow_nan=False).encode('ascii') + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def latest(records):
    """Latest record per (stage, key) for blind/cross and per (values, key, round)."""
    result = {}
    for record in records:
        if record['stage'] == 'values':
            result[('values', record['key'], record['round'])] = record
        else:
            result[(record['stage'], record['key'])] = record
    return result


def blind_rounds(plan, records):
    """Round in which each key's latest blind record was saved (by its position against ``label_base``)."""
    bases = [(item['round'], item.get('label_base', 0)) for item in plan['rounds']]
    result = {}
    for index, record in enumerate(records):
        if record['stage'] == 'blind':
            result[record['key']] = max(number for number, base in bases if base <= index)
    return result


def values_record(plan, best, number, key):
    """O/X of a C key for round ``number``: its own record, else the one carried from the previous round.

    A record carries over only when the round names its revalue forms (``--revalue-forms``), the key's form is
    not among them, and the key was a C or N member of the previous round with the same form.
    """
    rounds = plan['rounds']
    while True:
        record = best.get(('values', key, number))
        if record is not None:
            return record
        item = rounds[number - 1]
        revalue = item.get('revalue')
        if number == 1 or revalue is None or key not in valued(item):
            return None
        form, previous = item['docs'][key]['form'], rounds[number - 2]
        if form in revalue or key not in valued(previous) or previous['docs'][key]['form'] != form:
            return None
        number -= 1


# ---------------------------------------------------------------- locations


def _out_location(out, root):
    requested = Path(out).absolute()
    _require(not requested.is_symlink(), 'LOCATION_REJECTED')
    actual = requested.resolve()
    _require(not actual.is_relative_to(REPO.resolve()), 'LOCATION_REJECTED')
    if root is not None:
        _require(not (actual.is_relative_to(root) or root.is_relative_to(actual)), 'INPUT_OUTPUT_OVERLAP')
    _require(not actual.exists() or actual.is_dir(), 'LOCATION_REJECTED')
    return actual


def key_map(root, wanted):
    """{key: path} for keys in ``wanted``; symlinks and hidden files are never part of the inventory."""
    files, _ = batch.inventory(root)
    found = {}
    for path in files:
        if path.suffix.lower() != '.pdf':
            continue
        key = timing.document_key(path.relative_to(root).as_posix())
        if key in wanted:
            found[key] = path
    return found


# ---------------------------------------------------------------- session


class ApiError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code, self.status = code, status


class Session:
    """State of one serving process. Holds no document values on disk."""

    def __init__(self, root, out, plan, current, keymap, *, port=DEFAULT_PORT, compute=None, render=None):
        self.root, self.out, self.plan, self.current = root, out, plan, current
        self.keymap, self.port = keymap, port
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.compute = compute or compute_values
        self.render = render or render_page
        self.values = OrderedDict()
        self.records = read_labels(out, repair=True)
        self.latest = latest(self.records)
        self.origins = blind_rounds(plan, self.records)
        seed = plan['seed']
        present = [k for k in members(current) if k in keymap]
        self.queue = sorted(present, key=lambda key: rank(seed, 'order', key))
        self.missing = len(members(current)) - len(present)
        self.c_keys = valued(current)  # C and N: both need key-value O/X

    # -- keys and files

    def check_key(self, key, *, cross=False, either=False):
        """Only keys of this session's queues (all from rows.jsonl) are accepted."""
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):
            raise ApiError('BAD_KEY', 400)
        allowed = set(self.cross_queue()) if cross else set(self.queue)
        if either:
            allowed |= set(self.cross_queue())
        if key not in allowed:
            raise ApiError('NOT_FOUND', 404)
        return key

    def source(self, key):
        """Re-check the mapped file right before use: inside root, no symlinks, regular file."""
        path = self.keymap.get(key)
        if path is None:
            raise ApiError('NOT_FOUND', 404)
        try:
            relative = path.relative_to(self.root)
            if path.is_symlink() or path.resolve(strict=True) != self.root / relative:
                raise ApiError('SOURCE_REJECTED', 403)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except ApiError:
            raise
        except (OSError, ValueError, RuntimeError):
            raise ApiError('SOURCE_REJECTED', 403) from None
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ApiError('SOURCE_REJECTED', 403)
            return path, stream.read()

    # -- state

    def doc(self, key):
        """Measured row of the current round, else of the latest round that sampled the key (cross-check)."""
        for item in [self.current, *reversed(self.plan['rounds'])]:
            if key in item['docs']:
                return item['docs'][key]
        raise ApiError('NOT_FOUND', 404)

    def blind(self, key, stage='blind'):
        return self.latest.get((stage, key))

    def values_of(self, key):
        return values_record(self.plan, self.latest, self.current['round'], key)

    def values_done(self, key):
        return self.values_of(key) is not None

    def inherited(self, key):
        """Earlier round whose blind label this key carries, else None."""
        origin = self.origins.get(key)
        return origin if origin is not None and origin < self.current['round'] else None

    def complete(self, key):
        return self.blind(key) is not None and (key not in self.c_keys or self.values_done(key))

    def main_complete(self):
        return all(self.complete(key) for key in self.queue)

    def cross_queue(self):
        cross = self.plan['cross']
        if cross is None:
            return []
        members = [k for k in cross['keys'] if k in self.keymap]
        return sorted(members, key=lambda key: rank(self.plan['seed'], 'cross-order', key))

    def save(self, record):
        with self.lock:
            append_label(self.out, record)
            self.records.append(record)
            self.latest = latest(self.records)
            self.origins = blind_rounds(self.plan, self.records)

    # -- views

    def checklists(self):
        forms = sorted({self.doc(key)['form'] for key in self.queue + self.cross_queue()})
        return {form: dict(label=form_label(form), items=checks(form)) for form in forms}

    def overview(self):
        queue = []
        for number, key in enumerate(self.queue, 1):
            # 'blind_done' vs 'complete' only differs after stage 1, so it never reveals the sample before it.
            state = 'todo' if self.blind(key) is None else 'complete' if self.complete(key) else 'blind_done'
            queue.append(dict(n=number, key=key, state=state))
        cross = [dict(n=number, key=key, state='complete' if self.blind(key, 'cross') else 'todo')
                 for number, key in enumerate(self.cross_queue(), 1)]
        return dict(token=self.token, criteria=CRITERIA, round=self.current['round'], queue=queue,
                    missing=self.missing, main_complete=self.main_complete(),
                    cross_started=self.plan['cross'] is not None, cross=cross)

    def stage_one(self, key, stage):
        """Everything shown before the blind label: never the engine decision or reasons."""
        _, data = self.source(key)
        form = self.doc(key)['form']
        with self.lock:
            pages = page_count(data)
        record = self.blind(key, stage)
        queue = self.cross_queue() if stage == 'cross' else self.queue
        return dict(key=key, n=queue.index(key) + 1, total=len(queue), pages=pages, form=form,
                    form_label=form_label(form), cutoff=cutoff(form),
                    label=None if record is None else dict(
                        status=record['status'], reasons=record['reasons'],
                        inherited=self.inherited(key) if stage == 'blind' else None))

    def engine(self, key):
        if self.blind(key) is None:
            raise ApiError('BLIND_FIRST', 409)
        doc = self.doc(key)
        return dict(decision=doc['decision'], reasons=doc['reasons'], needs_values=key in self.c_keys,
                    values_done=self.values_done(key))

    def value_view(self, key):
        if self.blind(key) is None:
            raise ApiError('BLIND_FIRST', 409)
        if key not in self.c_keys:
            raise ApiError('NOT_IN_C', 409)
        with self.lock:
            if key not in self.values:
                path, _ = self.source(key)
                try:
                    self.values[key] = self.compute(path, self.doc(key)['form'])
                except ApiError:
                    raise
                except Exception:
                    raise ApiError('COMPUTE_FAILED', 500) from None
                while len(self.values) > VALUE_CACHE:
                    self.values.popitem(last=False)
            result = self.values[key]
        record = self.values_of(key)
        marks = dict(record['fields']) if record else {}
        doc = self.doc(key)
        carried = record is not None and record['round'] != self.current['round']
        return dict(items=[dict(name=item['name'], value=item['value'], mark=marks.get(item['name']))
                           for item in result['items']],
                    unread=result['unread'], inherited=record['round'] if carried else None,
                    recomputed=dict(decision=result['decision'], form=result['form'], tier=result['tier'],
                                    same='O' if (result['decision'], result['form']) ==
                                    (doc['decision'], doc['form']) else 'X'))


# ---------------------------------------------------------------- document work (in memory only)


def page_count(data):
    import pymupdf
    try:
        with pymupdf.open(stream=data, filetype='pdf') as document:
            return document.page_count
    except Exception:
        raise ApiError('OPEN_FAILED', 422) from None


def render_page(data, index, scale):
    import pymupdf
    try:
        with pymupdf.open(stream=data, filetype='pdf') as document:
            if not 0 <= index < document.page_count:
                raise ApiError('PAGE_RANGE', 404)
            page = document[index]
            largest = max(page.rect.width, page.rect.height) or 1
            zoom = min(float(scale), MAX_PIXELS / largest)
            return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes('png')
    except ApiError:
        raise
    except Exception:
        raise ApiError('RENDER_FAILED', 422) from None


def _display(value):
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in '[{':
            try:
                return json.dumps(json.loads(text), ensure_ascii=False, indent=1)
            except ValueError:
                pass
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def compute_values(path, form):
    """Service upload path (read_document + assess_upload, own; JBAI/Upstage removed at start)."""
    from demo.backend import ocr as demo_ocr
    from demo.backend.upload_assessment import assess_upload
    with batch.guarded():
        ocr = demo_ocr.read_document(str(path), None)
        kind = ocr.detected_doc_type.name if ocr.detected_doc_type is not None else 'X'
        kind = kind if kind in batch.KINDS else 'X'
        req = timing.requirement(kind)
        decision = 'NOT_ASSESSED'
        if req is not None:
            _, checked = assess_upload(path, req, identity=None, paper_admin_consent=kind == 'ADMIN_INFO_CONSENT',
                                       reader=lambda file_path, expected: ocr)
            decision = checked.status if checked.status in timing.DECISIONS else 'ERROR'
    items, unread = [], []
    for name in item_names(form):
        if name == DOC_ITEM:
            value = ocr.detected_doc_type.value if ocr.detected_doc_type is not None else None
        elif name in ocr.fields:
            value = ocr.fields[name]
        elif name == ISSUE_ITEM and ocr.issue_date is not None:
            value = ocr.issue_date.isoformat()
        else:
            value = None
        if value is None or value == '':
            unread.append(name)
        else:
            items.append(dict(name=name, value=_display(value)))
    return dict(items=items, unread=unread, decision=decision, form=kind, tier=timing._tier(ocr.tier))


# ---------------------------------------------------------------- web app


def _status_reasons(body):
    if not isinstance(body, dict) or set(body) != {'status', 'reasons'}:
        raise ApiError('BAD_BODY', 422)
    status, reasons = body['status'], body['reasons']
    if status not in STATES or not isinstance(reasons, list) or not all(r in REASONS for r in reasons):
        raise ApiError('BAD_BODY', 422)
    if bool(reasons) != (status == 'FAIL'):
        raise ApiError('REASONS_REQUIRED' if status == 'FAIL' else 'REASONS_NOT_ALLOWED', 422)
    return status, sorted(set(reasons))


def create_app(session):
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, JSONResponse, Response

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    hosts = {f'{HOST}:{session.port}', f'localhost:{session.port}'}
    origins = {f'http://{host}' for host in hosts}

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if request.headers.get('host') not in hosts:
            response = JSONResponse({'error': 'HOST_REJECTED'}, status_code=403)
        elif request.method not in ('GET', 'POST'):
            response = JSONResponse({'error': 'METHOD_REJECTED'}, status_code=405)
        elif request.method == 'POST' and (
                request.headers.get('x-label-token') != session.token
                or request.headers.get('origin', next(iter(origins))) not in origins
                or not request.headers.get('content-type', '').startswith('application/json')):
            response = JSONResponse({'error': 'TOKEN_REJECTED'}, status_code=403)
        else:
            try:
                response = await call_next(request)
            except Exception:  # never let a traceback (paths) reach a log
                response = JSONResponse({'error': 'INTERNAL'}, status_code=500)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    @app.exception_handler(ApiError)
    async def api_error(request, error):
        return JSONResponse({'error': error.code}, status_code=error.status)

    @app.exception_handler(Exception)
    async def any_error(request, error):
        return JSONResponse({'error': 'INTERNAL'}, status_code=500)

    async def body(request):
        try:
            return json.loads(await request.body())
        except ValueError:
            raise ApiError('BAD_BODY', 422) from None

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html', media_type='text/html; charset=utf-8')

    @app.get('/static/{name}')
    def static(name: str):
        if name not in STATIC_FILES:
            raise ApiError('NOT_FOUND', 404)
        return FileResponse(STATIC / name, media_type=STATIC_FILES[name])

    @app.get('/api/session')
    def overview():
        return session.overview()

    @app.get('/api/checks')
    def form_checks():
        """Per-form checklist for every form in this session; no key, decision or reason."""
        return session.checklists()

    @app.get('/api/doc/{key}')
    def doc(key: str):
        return session.stage_one(session.check_key(key), 'blind')

    @app.get('/api/doc/{key}/page/{index}')
    def page(key: str, index: int, s: int = 2):
        key = session.check_key(key, either=True)
        if s not in SCALES:
            raise ApiError('BAD_SCALE', 400)
        _, data = session.source(key)
        with session.lock:
            png = session.render(data, index, s)
        return Response(png, media_type='image/png')

    @app.post('/api/doc/{key}/blind')
    async def save_blind(key: str, request: Request):
        key = session.check_key(key)
        status, reasons = _status_reasons(await body(request))
        revised = 'O' if session.blind(key) is not None else 'X'
        session.save(label(key, 'blind', status=status, reasons=reasons, revised=revised))
        return {'saved': 'O'}

    @app.get('/api/doc/{key}/engine')
    def engine(key: str):
        return session.engine(session.check_key(key))

    @app.get('/api/doc/{key}/values')
    def values(key: str):
        return session.value_view(session.check_key(key))

    @app.post('/api/doc/{key}/values')
    async def save_values(key: str, request: Request):
        key = session.check_key(key)
        payload = await body(request)
        shown = [item['name'] for item in session.value_view(key)['items']]
        marks = payload.get('fields') if isinstance(payload, dict) and set(payload) == {'fields'} else None
        if not isinstance(marks, dict) or set(marks) != set(shown) or not all(m in MARKS for m in marks.values()):
            raise ApiError('MARKS_INCOMPLETE', 422)
        if not shown:
            raise ApiError('NO_ITEMS', 409)
        round_number = session.current['round']
        revised = 'O' if ('values', key, round_number) in session.latest else 'X'
        session.save(label(key, 'values', fields=[(name, marks[name]) for name in shown],
                           round_number=round_number, revised=revised))
        return {'saved': 'O'}

    @app.post('/api/cross/start')
    def cross_start():
        with session.lock:
            if session.plan['cross'] is None:
                if not session.main_complete():
                    raise ApiError('MAIN_INCOMPLETE', 409)
                labeled = [key for key in session.queue if session.blind(key) is not None]
                seed = session.plan['seed']
                keys = sorted(sorted(labeled, key=lambda key: rank(seed, 'cross', key))[:session.plan['cross_size']])
                session.plan['cross'] = dict(round=session.current['round'], keys=keys, created=_now())
                write_plan(session.out, session.plan)
        return {'started': 'O'}

    @app.get('/api/cross/{key}')
    def cross_doc(key: str):
        return session.stage_one(session.check_key(key, cross=True), 'cross')

    @app.post('/api/cross/{key}')
    async def cross_save(key: str, request: Request):
        key = session.check_key(key, cross=True)
        status, reasons = _status_reasons(await body(request))
        revised = 'O' if session.blind(key, 'cross') is not None else 'X'
        session.save(label(key, 'cross', status=status, reasons=reasons, revised=revised))
        return {'saved': 'O'}

    return app



# ---------------------------------------------------------------- serve


def prepare(rows, root, out, *, sample=None, seed=None, revalue=None, base_rows=None, port=DEFAULT_PORT,
            compute=None, render=None):
    """Validate inputs, fix the sample in plan.json and return a Session (prints counts only)."""
    for name in timing.DISABLED_ENV:
        os.environ.pop(name, None)
    os.environ['ENGINE_V2_OCR'] = 'own'
    try:
        root = Path(root).resolve(strict=True)
    except (OSError, RuntimeError):
        _fail('INPUT_UNAVAILABLE')
    _require(root.is_dir(), 'INPUT_UNAVAILABLE')
    out = _out_location(out, root)
    digest, docs = load_rows(rows)
    if compute is None and not timing.own_available():
        _fail('ENGINE_UNAVAILABLE')
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    plan = read_plan(out)
    seed = (plan['seed'] if plan else DEFAULT_SEED) if seed is None else seed
    sample = (plan['sample'] if plan else DEFAULT_SAMPLE) if sample is None else sample
    if base_rows is not None:
        # Round-1 rows for a plan written before N: verified by sha256, fills that round's PASS keys only.
        base_digest, base_docs = load_rows(base_rows)
        _require(plan is not None and any(item['rows_sha256'] == base_digest for item in plan['rounds']),
                 'PLAN_MISMATCH')
        update_plan(plan, base_digest, base_docs, sample, seed)
    plan, current = update_plan(plan, digest, docs, sample, seed, revalue, len(read_labels(out)))
    write_plan(out, plan)
    wanted = set(members(current))
    if plan['cross'] is not None:
        wanted |= set(plan['cross']['keys'])
    keymap = key_map(root, wanted)
    session = Session(root, out, plan, current, keymap, port=port, compute=compute, render=render)
    labeled = sum(session.blind(key) is not None for key in session.queue)
    carried = sum(session.inherited(key) is not None for key in session.queue)
    carried_values = sum(session.values_done(key) and session.values_of(key)['round'] != current['round']
                         for key in session.queue if key in session.c_keys)
    print(f'round {current["round"]} rounds {len(plan["rounds"])} b {len(current["b"])} c {len(current["c"])} '
          f'n {len(current.get("n", []))} '
          f'queue {len(session.queue)} labeled {labeled} inherited {carried} values_inherited {carried_values} '
          f'revalue {_revalue_text(current)} missing {session.missing}', flush=True)
    if session.missing:
        print('WARNING KEYS_MISSING', flush=True)
    return session


def _lock(out):
    fd = batch._open(Path(out) / 'serve.lock', os.O_WRONLY | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        _fail('OUT_LOCKED')
    return fd


def serve(rows, root, out, *, sample=None, seed=None, revalue=None, base_rows=None, port=DEFAULT_PORT):
    import logging
    import uvicorn
    session = prepare(rows, root, out, sample=sample, seed=seed, revalue=revalue, base_rows=base_rows, port=port)
    fd = _lock(session.out)
    try:
        app = create_app(session)
        print(f'open http://{HOST}:{port}/', flush=True)
        logging.getLogger('uvicorn.error').disabled = True
        uvicorn.run(app, host=HOST, port=port, access_log=False, log_level='critical', log_config=None,
                    server_header=False, date_header=False)
    finally:
        os.close(fd)
    return 0


# ---------------------------------------------------------------- summary


def _fmt(value):
    if value is None:
        return 'NA'
    if isinstance(value, float):
        return f'{value:.4f}'
    return str(value)


def _line(*values):
    return ' '.join(_fmt(v) for v in values)


def _revalue_text(item):
    """ALL (no option: every C document again), NONE (empty list) or the form codes."""
    revalue = item.get('revalue')
    return 'ALL' if revalue is None else ' '.join(revalue) or 'NONE'


def _set_name(item, key):
    return ('B' if key in item['b'] else 'C' if key in item['c'] else 'N' if key in item.get('n', ())
            else 'OUT')


def summarize(plan, records, round_number=None):
    """Summary lines (numbers and fixed codes only) for one round (default: latest)."""
    rounds = {item['round']: item for item in plan['rounds']}
    round_number = max(rounds) if round_number is None else round_number
    _require(round_number in rounds, 'ARGUMENT_ERROR')
    current = rounds[round_number]
    best = latest(records)
    blind = {key: best[('blind', key)] for key in current['docs'] if ('blind', key) in best}
    n_keys = current.get('n', [])
    values = {key: values_record(plan, best, round_number, key) for key in current['c'] + n_keys}
    values = {key: record for key, record in values.items() if record is not None}
    origins = blind_rounds(plan, records)
    carried = {key for key in blind if origins[key] < round_number}
    lines = ['LABEL_SUMMARY']
    lines.append('RUN criteria round rounds seed sample alpha')
    lines.append(_line('RUN', CRITERIA, round_number, len(rounds), plan['seed'], plan['sample'], ALPHA))
    lines.append('POPULATION decision documents')
    for decision in timing.DECISIONS:
        lines.append(_line('POPULATION', decision, current['counts'][decision]))
    lines.append('SAMPLE set documents blind_labeled values_labeled')
    lines.append(_line('SAMPLE', 'B', len(current['b']), sum(k in blind for k in current['b']), 'NA'))
    lines.append(_line('SAMPLE', 'C', len(current['c']), sum(k in blind for k in current['c']),
                       sum(k in values for k in current['c'])))
    lines.append(_line('SAMPLE', 'N', len(n_keys), sum(k in blind for k in n_keys), sum(k in values for k in n_keys)))
    for form, count in sorted(current['c_alloc'].items()):
        lines.append(_line('C_ALLOC', form, count))
    lines.append('REVALUE forms')
    lines.append(_line('REVALUE', _revalue_text(current)))
    lines.append('INHERITED set blind values')
    for name, keys in (('B', current['b']), ('C', current['c']), ('N', n_keys)):
        lines.append(_line('INHERITED', name, sum(k in carried for k in keys),
                           sum(k in values and values[k]['round'] != round_number for k in keys)))

    # B: engine FAIL documents; correct when the truth is FAIL as well.
    b_docs = [key for key in current['b'] if key in blind]
    b_hold = sum(blind[k]['status'] == 'HOLD' for k in b_docs)
    b_right = sum(blind[k]['status'] == 'FAIL' for k in b_docs)
    lines.append('B treatment B1 B2 B3')
    lines.append(_line('B', 'EXCL_HOLD', b_right, len(b_docs) - b_hold, cp_lower(b_right, len(b_docs) - b_hold)))
    lines.append(_line('B', 'HOLD_AS_WRONG', b_right, len(b_docs), cp_lower(b_right, len(b_docs))))
    lines.append('B_TRUTH state documents')
    for state in STATES:
        lines.append(_line('B_TRUTH', state, sum(blind[k]['status'] == state for k in b_docs)))

    # C: engine PASS sample; wrong when the truth is FAIL or any key value is X (values of this round).
    c_done = [key for key in current['c'] if key in blind and key in values]
    c_pending = sum(key in blind and key not in values for key in current['c'])

    def wrong(key):
        return blind[key]['status'] == 'FAIL' or any(mark == 'X' for _, mark in values[key]['fields'])

    c_hold = [k for k in c_done if blind[k]['status'] == 'HOLD']
    c_wrong = [k for k in c_done if blind[k]['status'] != 'HOLD' and wrong(k)]
    n_excl = len(c_done) - len(c_hold)
    lines.append('C treatment C1 C2 C3')
    lines.append(_line('C', 'EXCL_HOLD', len(c_wrong), n_excl, cp_upper(len(c_wrong), n_excl)))
    lines.append(_line('C', 'HOLD_AS_WRONG', len(c_wrong) + len(c_hold), len(c_done),
                       cp_upper(len(c_wrong) + len(c_hold), len(c_done))))
    lines.append('C_DETAIL item documents')
    lines.append(_line('C_DETAIL', 'TRUTH_NEEDS_REVIEW', sum(blind[k]['status'] == 'NEEDS_REVIEW' for k in c_done)))
    lines.append(_line('C_DETAIL', 'TRUTH_FAIL', sum(blind[k]['status'] == 'FAIL' for k in c_done)))
    lines.append(_line('C_DETAIL', 'VALUE_X', sum(any(m == 'X' for _, m in values[k]['fields']) for k in c_done)))
    lines.append(_line('C_DETAIL', 'HOLD', len(c_hold)))
    lines.append(_line('C_DETAIL', 'VALUES_PENDING', c_pending))
    lines.append(_line('C_DETAIL', 'VALUES_INHERITED', sum(values[k]['round'] != round_number for k in c_done)))

    def strict(key):
        """Missed by a PASS: nobody looks at it, so a truth NEEDS_REVIEW counts as wrong too."""
        return blind[key]['status'] != 'PASS' or any(mark == 'X' for _, mark in values[key]['fields'])

    c_strict = sum(blind[k]['status'] != 'HOLD' and strict(k) for k in c_done)
    lines.append(_line('C_DETAIL', 'PASS_NOT_TRUTH_OR_VALUE_X', c_strict))
    lines.append('C_TRUTH state documents')
    for state in STATES:
        lines.append(_line('C_TRUTH', state, sum(blind[k]['status'] == state for k in c_done)))

    # N: every document that became PASS after round 1 (census, no sampling bound). Wrong when the truth is
    # not PASS or any key value is X (strict); FAIL_OR_VALUE_X uses the C1 definition for comparison.
    n_done = [key for key in n_keys if key in blind and key in values]
    n_hold = [k for k in n_done if blind[k]['status'] == 'HOLD']

    def x_marked(key):
        return any(mark == 'X' for _, mark in values[key]['fields'])

    wrong_new = strict

    n_wrong = [k for k in n_done if blind[k]['status'] != 'HOLD' and wrong_new(k)]
    lines.append('N_TOTAL documents blind_labeled values_labeled values_pending')
    lines.append(_line('N_TOTAL', len(n_keys), sum(k in blind for k in n_keys), sum(k in values for k in n_keys),
                       sum(k in blind and k not in values for k in n_keys)))
    lines.append('N treatment wrong labeled rate')
    for name, k, m in (('EXCL_HOLD', len(n_wrong), len(n_done) - len(n_hold)),
                       ('HOLD_AS_WRONG', len(n_wrong) + len(n_hold), len(n_done))):
        lines.append(_line('N', name, k, m, k / m if m else None))
    lines.append('N_DETAIL item documents')
    for state in STATES:
        lines.append(_line('N_DETAIL', 'TRUTH_' + state, sum(blind[k]['status'] == state for k in n_done)))
    lines.append(_line('N_DETAIL', 'VALUE_X', sum(x_marked(k) for k in n_done)))
    lines.append(_line('N_DETAIL', 'FAIL_OR_VALUE_X', sum(blind[k]['status'] != 'HOLD' and wrong(k) for k in n_done)))
    lines.append(_line('N_DETAIL', 'VALUES_INHERITED', sum(values[k]['round'] != round_number for k in n_done)))

    # PASS_COMBINED: the round's PASS population = old stratum (PASS in round 1 too; C sample) + new stratum
    # (N, census). Wrong = strict in both (truth not PASS, FAIL or NEEDS_REVIEW, or any value X). Weighted by
    # stratum size; the bound adds uncertainty only for the old stratum (the new one is known once N is
    # complete): NA until every N document is labeled.
    base = rounds[1]
    if round_number == 1:
        old_population = current['counts']['PASS']
    elif 'pass_keys' in base and 'pass_keys' in current:
        old_population = len(set(current['pass_keys']) & set(base['pass_keys']))
    else:
        old_population = None
    new_population = len(n_keys)
    lines.append('PASS_COMBINED treatment old_population old_labeled old_wrong new_population new_labeled '
                 'new_wrong estimate upper')
    for name, k_old, m_old, k_new, m_new in (
            ('EXCL_HOLD', c_strict, n_excl, len(n_wrong), len(n_done) - len(n_hold)),
            ('HOLD_AS_WRONG', c_strict + len(c_hold), len(c_done), len(n_wrong) + len(n_hold), len(n_done))):
        estimate = upper = None
        total = (old_population or 0) + new_population
        ready = (old_population is not None and total > 0 and len(n_done) == new_population
                 and (old_population == 0 or m_old > 0) and (new_population == 0 or m_new > 0))
        if ready:
            rate_new = k_new / m_new if new_population else 0.0
            rate_old = k_old / m_old if old_population else 0.0
            upper_old = cp_upper(k_old, m_old) if old_population else 0.0
            estimate = (old_population * rate_old + new_population * rate_new) / total
            upper = (old_population * upper_old + new_population * rate_new) / total
        lines.append(_line('PASS_COMBINED', name, old_population, m_old, k_old, new_population, m_new, k_new,
                           estimate, upper))

    lines.append('BY_FORM set form labeled PASS NEEDS_REVIEW FAIL HOLD wrong')
    for name, keys in (('B', b_docs), ('C', c_done), ('N', n_done)):
        forms = defaultdict(list)
        for key in keys:
            forms[current['docs'][key]['form']].append(key)
        for form in sorted(forms):
            group = forms[form]
            states = Counter(blind[k]['status'] for k in group)
            bad = (sum(states[s] for s in ('PASS', 'NEEDS_REVIEW')) if name == 'B'
                   else sum(blind[k]['status'] != 'HOLD' and (wrong if name == 'C' else wrong_new)(k)
                            for k in group))
            lines.append(_line('BY_FORM', name, form, len(group), *(states[s] for s in STATES), bad))

    lines.append('R_CODE set code documents')
    for name, keys in (('B', b_docs), ('C', c_done), ('N', n_done)):
        codes = Counter(code for key in keys for code in blind[key]['reasons'])
        for code in REASONS:
            lines.append(_line('R_CODE', name, code, codes[code]))

    lines.append('ENGINE_FAIL_REASON code documents truth_FAIL truth_HOLD')
    engine = defaultdict(list)
    for key in b_docs:
        for code in sorted({c for c, severity in current['docs'][key]['reasons'] if severity == 'FAIL'}):
            engine[code].append(key)
    for code in sorted(engine):
        group = engine[code]
        lines.append(_line('ENGINE_FAIL_REASON', code, len(group), sum(blind[k]['status'] == 'FAIL' for k in group),
                           sum(blind[k]['status'] == 'HOLD' for k in group)))

    lines.append('VALUE_ITEM form item O X')
    items = defaultdict(Counter)
    for key in c_done:
        for name, mark in values[key]['fields']:
            items[(current['docs'][key]['form'], name)][mark] += 1
    for (form, name), marks in sorted(items.items()):
        lines.append(_line('VALUE_ITEM', form, name, marks['O'], marks['X']))
    lines.append('VALUE_ITEM_N form item O X')
    items = defaultdict(Counter)
    for key in n_done:
        for name, mark in values[key]['fields']:
            items[(current['docs'][key]['form'], name)][mark] += 1
    for (form, name), marks in sorted(items.items()):
        lines.append(_line('VALUE_ITEM_N', form, name, marks['O'], marks['X']))

    lines.append('LABEL_VERSION stage version documents')
    cross_keys = plan['cross']['keys'] if plan['cross'] else []
    staged = (('blind', list(blind.values())), ('values', list(values.values())),
              ('cross', [best[('cross', k)] for k in cross_keys if ('cross', k) in best]))
    for stage, items in staged:
        versions = Counter(record['criteria'] for record in items)
        for version in CRITERIA_VERSIONS:
            lines.append(_line('LABEL_VERSION', stage, version, versions[version]))

    lines.append('REVISED stage documents')
    lines.append(_line('REVISED', 'blind', sum(blind[k]['revised'] == 'O' for k in blind)))
    lines.append(_line('REVISED', 'values', sum(values[k]['revised'] == 'O' for k in values)))

    # Documents whose truth was labeled in an earlier round: engine decision before → after, by truth.
    lines.append('TRANSITION before_set before after after_set documents ' + ' '.join(STATES))
    table = defaultdict(Counter)
    changed = 0
    for key, after in sorted(current.get('carried', {}).items()):
        if ('blind', key) not in best or origins[key] >= round_number:
            continue
        earlier = next(item for item in reversed(plan['rounds'][:round_number - 1]) if key in item['docs'])
        before = earlier['docs'][key]['decision']
        after_set = _set_name(current, key)
        table[(_set_name(earlier, key), before, after, after_set)][best[('blind', key)]['status']] += 1
        changed += before != after
    for (before_set, before, after, after_set), states in sorted(table.items()):
        lines.append(_line('TRANSITION', before_set, before, after, after_set, sum(states.values()),
                           *(states[s] for s in STATES)))
    lines.append(_line('TRANSITION_CHANGED', changed))

    cross = plan['cross']
    pairs = []
    if cross is not None:
        pairs = [(best[('blind', k)], best[('cross', k)]) for k in cross['keys']
                 if ('blind', k) in best and ('cross', k) in best]
    agree = sum(a['status'] == b['status'] for a, b in pairs)
    exact = sum(a['status'] == b['status'] and a['reasons'] == b['reasons'] for a, b in pairs)
    lines.append('CROSS keys pairs status_agree status_rate exact_agree exact_rate')
    lines.append(_line('CROSS', len(cross['keys']) if cross else 0, len(pairs), agree,
                       agree / len(pairs) if pairs else None, exact, exact / len(pairs) if pairs else None))
    return '\n'.join(lines) + '\n'


def mismatches(plan, records, round_number=None):
    """One line per labeled disagreement: ordinal and fixed codes only (no keys, paths or values).

    B: truth is not FAIL. C and N: truth is not PASS, or an item was marked X in this round's values.
    The ordinal is the screen order (seeded rank over B ∪ C ∪ N of the round); it matches the screen when no
    document of the round is missing from the root.
    """
    rounds = {item['round']: item for item in plan['rounds']}
    round_number = max(rounds) if round_number is None else round_number
    _require(round_number in rounds, 'ARGUMENT_ERROR')
    current = rounds[round_number]
    best = latest(records)
    order = sorted(members(current), key=lambda key: rank(plan['seed'], 'order', key))
    b_keys = set(current['b'])
    lines = ['MISMATCH round n set form engine_decision engine_reasons truth r_codes x_items']
    count = 0
    for number, key in enumerate(order, 1):
        record = best.get(('blind', key))
        if record is None:
            continue
        values = values_record(plan, best, round_number, key) if key not in b_keys else None
        if key in b_keys:
            if record['status'] == 'FAIL':
                continue
            name, x_items = 'B', '-'
        else:
            marked = [item for item, mark in values['fields'] if mark == 'X'] if values else []
            if record['status'] == 'PASS' and not marked:
                continue
            name = _set_name(current, key)
            x_items = ','.join(marked) if marked else ('VALUES_PENDING' if values is None else '-')
        doc = current['docs'][key]
        codes = sorted({code for code, _ in doc['reasons']})
        lines.append(_line('MISMATCH', round_number, number, name, doc['form'], doc['decision'],
                           ','.join(codes) or '-', record['status'], ','.join(record['reasons']) or '-', x_items))
        count += 1
    lines.append(_line('MISMATCH_COUNT', count))
    return '\n'.join(lines) + '\n'


def mismatch(out, round_number=None):
    """Read-only: prints ordinals and codes only."""
    out = Path(out).absolute()
    _require(out.is_dir() and not out.is_symlink(), 'INPUT_UNAVAILABLE')
    plan = read_plan(out)
    _require(plan is not None, 'INPUT_UNAVAILABLE')
    print(mismatches(plan, read_labels(out), round_number).rstrip('\n'), flush=True)
    return 0


def summary(out, round_number=None):
    """Read-only: never repairs or writes."""
    out = Path(out).absolute()
    _require(out.is_dir() and not out.is_symlink(), 'INPUT_UNAVAILABLE')
    plan = read_plan(out)
    _require(plan is not None, 'INPUT_UNAVAILABLE')
    text = summarize(plan, read_labels(out), round_number)
    print(text.rstrip('\n'), flush=True)
    return 0


# ---------------------------------------------------------------- cli


def parser():
    result = batch.SafeParser(prog='label_review', description='Localhost-only blind labeling (criteria v0.1)')
    commands = result.add_subparsers(dest='command', required=True)
    run = commands.add_parser('serve')
    run.add_argument('--rows', required=True)
    run.add_argument('--root', required=True)
    run.add_argument('--out', required=True)
    run.add_argument('--sample', type=int)
    run.add_argument('--seed', type=int)
    run.add_argument('--port', type=int, default=DEFAULT_PORT)
    run.add_argument('--revalue-forms', dest='revalue_forms')
    run.add_argument('--base-rows', dest='base_rows')
    report = commands.add_parser('summary')
    report.add_argument('--out', required=True)
    report.add_argument('--round', type=int)
    listing = commands.add_parser('mismatch')
    listing.add_argument('--out', required=True)
    listing.add_argument('--round', type=int)
    return result


def parse_forms(text):
    """``--revalue-forms`` value: comma-separated form codes (None when the option is absent)."""
    if text is None:
        return None
    forms = [part.strip() for part in text.split(',') if part.strip()]
    _require(all(form in batch.KINDS for form in forms), 'ARGUMENT_ERROR')
    return sorted(set(forms))


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == 'serve':
            if ((args.sample is not None and not 1 <= args.sample <= 100000) or
                    (args.seed is not None and args.seed < 0) or not 1024 <= args.port <= 65535):
                _fail('ARGUMENT_ERROR')
            return serve(args.rows, args.root, args.out, sample=args.sample, seed=args.seed,
                         revalue=parse_forms(args.revalue_forms), base_rows=args.base_rows, port=args.port)
        if args.round is not None and args.round < 1:
            _fail('ARGUMENT_ERROR')
        return (mismatch if args.command == 'mismatch' else summary)(args.out, args.round)
    except KeyboardInterrupt:
        return 130
    except ToolError as error:
        code = error.args[0] if error.args and error.args[0] in ERROR_CODES else 'UNEXPECTED_ERROR'
        print(f'ERROR {code}', flush=True)
        return 2
    except batch.BatchError:
        print('ERROR ARGUMENT_ERROR', flush=True)
        return 2
    except Exception:
        # Never echo arguments, paths, document contents or exception messages.
        print('ERROR UNEXPECTED_ERROR', flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
