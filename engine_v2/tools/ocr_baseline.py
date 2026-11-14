"""Resumable, value-free page OCR and extractor agreement measurement.

Use ``python -B -m engine_v2.tools.ocr_baseline``. Document contents, geometry
and dependency exception messages are transient memory only. Summary is read-only
and does not import OCR/model backends. This single-worker CLI owns global guards.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import fcntl
import hashlib
import math
import os
from pathlib import Path
import re
import statistics
import time
import uuid

from . import batch_assess as batch
from .ocr_baseline_settings import SETTINGS

VERSION = 1
ENGINES = ('own', 'applevision')
VARIANTS = ('clean', 'scan', 'phone')
EXCLUSIONS = ('NONE', 'NO_TEXT_LAYER', 'SHORT_TEXT_LAYER', 'BROKEN_TEXT_LAYER',
              'CLASSIFICATION_FAILED', 'REFERENCE_ERROR', 'PAGE_ERROR')
DOCUMENT_CODES = ('NONE', 'ENCRYPTED', 'EMPTY_DOCUMENT', 'OPEN_ERROR', 'PROCESSING_ERROR')
MEASUREMENT_CODES = ('NONE', 'ENGINE_UNAVAILABLE', 'OCR_ERROR', 'EXTRACTION_ERROR', 'RENDER_ERROR')
FILENAMES = ('run.json', 'results.jsonl', 'summary.json', 'summary.txt', '.lock')
QUALITY = dict(characters=0, replacement=0, private_use=0, controls=0)
TIMING = dict(ocr=0.0, detection=None, recognition=None, initialization=None,
              residual=None, observer=0.0, cold=0, intra_threads=None,
              inter_threads=None, workers=1, extraction=0.0, total=0.0)
FIELD = dict(eligible=0, match=0, missing_reference=0, ocr_cause=0,
             structure_cause=0, unattributable=0)


def _require(condition):
    batch._require(condition)


def _numeric(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _count(value):
    return type(value) is int and value >= 0


def _shape(value, template):
    """Reject arbitrary keys/strings recursively before anything reaches disk."""
    if isinstance(template, dict):
        _require(isinstance(value, dict) and value.keys() == template.keys())
        for key in template:
            _shape(value[key], template[key])
    elif template is None:
        _require(value is None or _numeric(value))
    else:
        _require(_numeric(value))


def validate_meta(meta):
    _require(isinstance(meta, dict) and set(meta) == {'schema_version', 'root_digest', 'engines', 'variants', 'settings'})
    _require(type(meta['schema_version']) is int and meta['schema_version'] == VERSION)
    _require(isinstance(meta['root_digest'], str) and re.fullmatch('[0-9a-f]{64}', meta['root_digest']))
    _require(isinstance(meta['engines'], list) and bool(meta['engines']) and
             all(e in ENGINES for e in meta['engines']) and len(set(meta['engines'])) == len(meta['engines']))
    _require(isinstance(meta['variants'], list) and bool(meta['variants']) and
             all(v in VARIANTS for v in meta['variants']) and len(set(meta['variants'])) == len(meta['variants']))
    _require(meta['settings'] == SETTINGS)
    return meta


def validate_row(row, meta):
    from .ocr_baseline_metrics import validate_metrics
    _require(isinstance(row, dict) and set(row) == {'schema_version', 'id', 'page_count', 'code', 'pages'})
    _require(type(row['schema_version']) is int and row['schema_version'] == VERSION)
    _require(batch._relative(row['id']) and '\\' not in row['id'] and Path(row['id']).suffix.lower() == '.pdf')
    _require(row['page_count'] is None or _count(row['page_count']))
    _require(row['code'] in DOCUMENT_CODES and isinstance(row['pages'], list))
    _require(row['code'] != 'NONE' or row['page_count'] == len(row['pages']))
    numbers = set()
    for page in row['pages']:
        _require(isinstance(page, dict) and set(page) == {'page', 'type', 'exclusion', 'quality', 'seed',
                                                         'reference_seconds', 'measurements'})
        _require(_count(page['page']) and page['page'] > 0 and page['page'] not in numbers)
        _require(row['page_count'] is not None and page['page'] <= row['page_count'])
        numbers.add(page['page'])
        _require(page['type'] in batch.KINDS and page['exclusion'] in EXCLUSIONS)
        _shape(page['quality'], QUALITY)
        _require(all(_count(v) for v in page['quality'].values()))
        _require(_count(page['seed']) and page['seed'] < 2 ** 48 and _numeric(page['reference_seconds']))
        _require(isinstance(page['measurements'], list))
        seen = set()
        for item in page['measurements']:
            _require(isinstance(item, dict) and set(item) == {'engine', 'variant', 'state', 'code', 'type_match',
                                                             'metrics', 'fields', 'seconds'})
            pair = (item['engine'], item['variant'])
            _require(item['engine'] in meta['engines'] and item['variant'] in meta['variants'] and pair not in seen)
            seen.add(pair)
            _require(item['state'] in {'OK', 'ERROR', 'SKIPPED'} and item['code'] in MEASUREMENT_CODES)
            _require(item['type_match'] in (0, 1) and type(item['type_match']) is int)
            _require((item['state'] == 'OK') == (item['code'] == 'NONE'))
            _require((item['state'] == 'SKIPPED') == (item['code'] == 'ENGINE_UNAVAILABLE'))
            if item['metrics'] is not None:
                validate_metrics(item['metrics'])
            _require(item['state'] != 'OK' or item['metrics'] is not None)
            _shape(item['seconds'], TIMING)
            _require(math.isclose(item['seconds']['total'], item['seconds']['ocr'] + item['seconds']['extraction'],
                                 rel_tol=1e-9, abs_tol=1e-9))
            fields = item['fields']
            _require(isinstance(fields, dict) and set(fields) <= set(batch.FIELDS.get(page['type'], ())))
            if item['state'] == 'OK':
                _require(set(fields) == set(batch.FIELDS.get(page['type'], ())))
            for field in fields.values():
                _shape(field, FIELD)
                _require(all(type(v) is int and v in {0, 1} for v in field.values()))
                _require(field['eligible'] + field['missing_reference'] == 1)
                _require(field['match'] <= field['eligible'])
                _require(field['ocr_cause'] + field['structure_cause'] + field['unattributable'] ==
                         field['eligible'] - field['match'])
        if page['exclusion'] == 'NONE':
            _require(page['type'] != 'X' and seen == {(e, v) for e in meta['engines'] for v in meta['variants']})
        else:
            _require(not seen)
    return row


def load_rows(path, meta, *, repair=False):
    """Reuse batch's strict parser/tail detection with this tool's closed schema."""
    if not path.exists():
        return []
    rows, ids = [], set()
    fd = batch._open(path, os.O_RDWR if repair else os.O_RDONLY)
    with os.fdopen(fd, 'r+b' if repair else 'rb') as stream:
        while True:
            start = stream.tell()
            line = stream.readline()
            if not line:
                break
            terminated = line.endswith(b'\n')
            try:
                raw = batch._load(line)
            except batch.BatchError:
                if terminated or not repair or not batch._incomplete_tail(line):
                    raise
                stream.seek(start)
                stream.truncate()
                stream.flush()
                os.fsync(stream.fileno())
                break
            row = validate_row(raw, meta)
            _require(row['id'] not in ids)
            ids.add(row['id'])
            rows.append(row)
            if not terminated:
                if repair:
                    stream.seek(0, os.SEEK_END)
                    stream.write(b'\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                break
    return rows


def _blank_document(identifier, code='NONE', page_count=None):
    return dict(schema_version=VERSION, id=identifier, page_count=page_count, code=code, pages=[])


def _blank_measurement(engine, variant):
    return dict(engine=engine, variant=variant, state='ERROR', code='OCR_ERROR', type_match=0,
                metrics=None, fields={}, seconds=deepcopy(TIMING))


def process_file(path, identifier, engines, variants):
    """Caller supplies the quiet/read-only/network boundary; only projections escape."""
    import numpy as np
    import pymupdf
    from demo.backend.ocr import pdftext
    from . import ocr_baseline_runtime as runtime
    from .ocr_baseline_fields import compare_fields, prepare_pairs, table_region
    from .ocr_baseline_metrics import measure

    row = _blank_document(identifier)
    try:
        document = pymupdf.open(path)
    except Exception:
        row['code'] = 'OPEN_ERROR'
        return row
    with document:
        if document.needs_pass:
            row['code'] = 'ENCRYPTED'
            return row
        row['page_count'] = document.page_count
        if not document.page_count:
            row['code'] = 'EMPTY_DOCUMENT'
            return row
        for index, source in enumerate(document):
            seed = runtime.page_seed(identifier, index + 1)
            page_row = dict(page=index + 1, type='X', exclusion='PAGE_ERROR', quality=deepcopy(QUALITY),
                            seed=seed, reference_seconds=0.0, measurements=[])
            row['pages'].append(page_row)
            try:
                page, truth = runtime.reference_page(source, index)
                code, counts = runtime.quality(source.get_text('text'), truth)
                page_row.update(exclusion=code, quality=counts)
                if code != 'NONE':
                    continue
                reference_pairs = prepare_pairs(page, truth, 'text_layer')
                detected, _ = pdftext.classify_pages_with_evidence(reference_pairs)
                kind = detected.name if detected is not None else 'X'
                page_row['type'] = kind if kind in batch.KINDS else 'X'
                if page_row['type'] == 'X':
                    page_row['exclusion'] = 'CLASSIFICATION_FAILED'
                    continue
                started = time.perf_counter()
                try:
                    reference, ref_fields = runtime.extract(page, truth, 'text_layer')
                except Exception:
                    page_row['exclusion'] = 'REFERENCE_ERROR'
                    continue
                finally:
                    page_row['reference_seconds'] = time.perf_counter() - started
                bounds = table_region(kind, *reference_pairs[0])
                reference_text = reference_pairs[0][1].text
                for variant in variants:
                    try:
                        image, forward = runtime.variant_image(source, variant, seed, page.pixel_size)
                        inverse = np.linalg.inv(forward)
                    except Exception:
                        for engine in engines:
                            item = _blank_measurement(engine, variant)
                            item['code'] = 'RENDER_ERROR'
                            page_row['measurements'].append(item)
                        continue
                    for engine in engines:
                        item = _blank_measurement(engine, variant)
                        page_row['measurements'].append(item)
                        started = time.perf_counter()
                        try:
                            recognized, raw_words, timing = runtime.recognize(engine, image)
                            item['seconds'].update(timing)
                        except Exception as exc:
                            item['seconds']['ocr'] = time.perf_counter() - started
                            item['seconds']['total'] = item['seconds']['ocr']
                            unavailable = isinstance(exc, (ImportError, NotImplementedError, FileNotFoundError))
                            item.update(state='SKIPPED' if unavailable else 'ERROR',
                                        code='ENGINE_UNAVAILABLE' if unavailable else 'OCR_ERROR')
                            continue
                        item['metrics'] = measure(truth, runtime.map_words(raw_words, inverse), page.pixel_size,
                                                  height_scale=SETTINGS['variants'][variant]['dpi'] / 300,
                                                  table_bounds=bounds)
                        started = time.perf_counter()
                        try:
                            observed, actual_fields = runtime.extract(image, recognized.words, engine)
                        except Exception:
                            item['code'] = 'EXTRACTION_ERROR'
                            continue
                        finally:
                            item['seconds']['extraction'] = time.perf_counter() - started
                            item['seconds']['total'] = item['seconds']['ocr'] + item['seconds']['extraction']
                        actual_kind = observed.detected_doc_type.name if observed.detected_doc_type else 'X'
                        observed_text = prepare_pairs(image, recognized.words, engine)[0][1].text
                        item['fields'] = compare_fields(kind, ref_fields, actual_fields, actual_kind,
                                                       reference_text, observed_text)
                        item.update(state='OK', code='NONE', type_match=int(actual_kind == kind))
            except Exception:
                # A dependency failure has no message/class/partial values in output.
                page_row.update(exclusion='PAGE_ERROR', measurements=[])
    return row


def _statistics(values):
    values = sorted(v for v in values if v is not None)
    return dict(count=len(values), mean=statistics.mean(values) if values else None,
                median=statistics.median(values) if values else None,
                p90=batch._quantile(values, .9) if values else None)


def build_summary(meta, rows):
    from .ocr_baseline_metrics import aggregate_metrics
    groups = defaultdict(list)
    excluded = Counter({c: 0 for c in EXCLUSIONS if c != 'NONE'})
    documents = Counter({c: 0 for c in DOCUMENT_CODES})
    reference_times = []
    for row in rows:
        documents[row['code']] += 1
        for page in row['pages']:
            if page['exclusion'] != 'NONE':
                excluded[page['exclusion']] += 1
            else:
                reference_times.append(page['reference_seconds'])
            for item in page['measurements']:
                groups[(page['type'], item['engine'], item['variant'])].append(item)
    output = []
    for (kind, engine, variant), items in sorted(groups.items()):
        measured_items = [i for i in items if i['metrics'] is not None]
        measured = [i['metrics'] for i in measured_items]
        successful = [i for i in items if i['state'] == 'OK']
        fields = {key: {**{name: sum(i['fields'][key][name] for i in successful) for name in FIELD},
                        'rate': None} for key in batch.FIELDS.get(kind, ())}
        for field in fields.values():
            field['rate'] = field['match'] / field['eligible'] if field['eligible'] else None
        output.append(dict(type=kind, engine=engine, variant=variant, attempted=len(items),
                           states=dict(Counter(i['state'] for i in items)),
                           codes=dict(Counter(i['code'] for i in items)),
                           type_matches=sum(i['type_match'] for i in successful), successful=len(successful),
                           metrics=aggregate_metrics(measured),
                           empty_ocr_pages=sum(m['words']['observed'] == 0 for m in measured),
                           table_unmeasured=sum(m['table']['measured'] == 0 for m in measured),
                           table_unavailable=len(items) - len(measured),
                           page_cer=_statistics([m['cer']['rate'] for m in measured]),
                           fields=fields,
                           seconds={key: _statistics([i['seconds'][key] for i in measured_items])
                                    for key in ('ocr', 'detection', 'recognition', 'initialization', 'residual',
                                                'observer', 'extraction', 'total')},
                           attempt_seconds=_statistics([i['seconds']['total'] for i in items]),
                           cold_calls=sum(i['seconds']['cold'] for i in items),
                           threads=[dict(intra=intra, inter=inter, workers=1) for intra, inter in sorted(
                               {(i['seconds']['intra_threads'], i['seconds']['inter_threads']) for i in items},
                               key=lambda pair: (-1 if pair[0] is None else pair[0], -1 if pair[1] is None else pair[1]))]))
    return dict(schema_version=VERSION, settings=meta['settings'], documents=len(rows),
                document_codes=dict(documents), pages=sum(len(r['pages']) for r in rows),
                inaccessible_page_count=sum(r['page_count'] is None for r in rows),
                excluded_pages=dict(excluded), reference_seconds=_statistics(reference_times), groups=output)


def _format(value):
    return 'N/A' if value is None else f'{value:.6f}' if isinstance(value, float) else str(value)


def summary_text(summary):
    lines = ['OCR_BASELINE', 'documents pages inaccessible_page_count',
             f"{summary['documents']} {summary['pages']} {summary['inaccessible_page_count']}",
             'document_code count']
    lines.extend(f'{code} {count}' for code, count in summary['document_codes'].items())
    lines.append('page_exclusion count')
    lines.extend(f'{code} {count}' for code, count in summary['excluded_pages'].items())
    lines.append('type engine variant attempted successful CER_mean CER_median CER_p90 '
                 'digit_CER hangul_CER word_F1 OCR_mean_s total_mean_s '
                 'table_measured table_unmeasured table_unavailable empty_ocr_pages')
    for group in summary['groups']:
        values = [group['type'], group['engine'], group['variant'], group['attempted'], group['successful'],
                  group['page_cer']['mean'], group['page_cer']['median'], group['page_cer']['p90'],
                  group['metrics']['digit_cer']['rate'], group['metrics']['hangul_cer']['rate'],
                  group['metrics']['words']['f1'], group['seconds']['ocr']['mean'],
                  group['seconds']['total']['mean'], group['metrics']['table']['measured'],
                  group['table_unmeasured'], group['table_unavailable'], group['empty_ocr_pages']]
        lines.append(' '.join(_format(value) for value in values))
    # Flatten only reviewed aggregate keys, never row IDs or source contents.
    def flatten(value, prefix=''):
        if isinstance(value, dict):
            for key, child in value.items():
                yield from flatten(child, f'{prefix}.{key}' if prefix else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from flatten(child, f'{prefix}.{index}')
        else:
            yield f'{prefix} {_format(value)}'
    lines.append('parameter value')
    lines.extend(flatten(summary['settings']))
    for group in summary['groups']:
        lines.append(f"type engine variant\n{group['type']} {group['engine']} {group['variant']}")
        lines.append('metric value')
        lines.extend(flatten({key: value for key, value in group.items() if key not in {'type', 'engine', 'variant'}}))
    return '\n'.join(lines) + '\n'


def _atomic_text(path, value):
    temporary = batch._target(path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp'))
    try:
        fd = batch._open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(value.encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        batch._target(path)
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _protected_outputs(out, files, ids=None):
    protected = files + ([ids] if ids is not None else [])
    targets = [batch._target(out / name) for name in FILENAMES]
    for source in protected:
        if source is None:
            continue
        for target in targets:
            if target.exists() and os.path.samefile(source, target):
                batch._fail('INPUT_OUTPUT_OVERLAP')
    return targets


def run(root, out, engines=('own',), variants=VARIANTS, *, ids=None, limit=None):
    started = time.perf_counter()
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        batch._fail('INPUT_UNAVAILABLE')
    requested = Path(out).absolute()
    if requested.is_symlink():
        batch._fail('LOCATION_REJECTED')
    out = batch._location(requested)
    if root.is_relative_to(out) or out.is_relative_to(root):
        batch._fail('INPUT_OUTPUT_OVERLAP')
    inventory, excluded = batch.inventory(root)
    files = [p for p in inventory if p.suffix.lower() == '.pdf']
    _protected_outputs(out, files)
    selection = None
    if ids is not None:
        actual_ids = batch._location(ids)
        _protected_outputs(out, files, actual_ids)
        selection, counts = batch._ids_selection(root, ids, out, files)
        batch._selection_progress(counts)
    print(f'inventory_pdf {len(files)} excluded_files {sum(excluded.values()) + len(inventory) - len(files)}', flush=True)
    meta = validate_meta(dict(schema_version=VERSION, root_digest=hashlib.sha256(os.fsencode(root)).hexdigest(),
                              engines=list(engines), variants=list(variants), settings=deepcopy(SETTINGS)))
    # Validate every existing output target before directory/lock/tail mutation.
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    batch._location(out)
    fd = batch._open(out / '.lock', os.O_CREAT | os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            batch._fail('OUTPUT_LOCKED')
        metadata, records = batch._target(out / 'run.json'), batch._target(out / 'results.jsonl')
        if metadata.exists():
            previous = validate_meta(batch._load(metadata.read_bytes()))
            if previous != meta:
                batch._fail('RUN_INCOMPATIBLE')
        elif records.exists() and records.stat().st_size:
            batch._fail('RESUME_INVALID')
        rows = load_rows(records, meta, repair=True)
        if not metadata.exists():
            batch._atomic(metadata, meta)
        completed = {row['id'] for row in rows}
        selected = files if selection is None else selection
        pending = [p for p in selected if p.relative_to(root).as_posix() not in completed]
        unfinished = len(pending)
        skipped = len(selected) - unfinished
        if limit is not None:
            pending = pending[:limit]
        for number, path in enumerate(pending, 1):
            identifier = path.relative_to(root).as_posix()
            try:
                with batch.guarded():
                    row = process_file(path, identifier, engines, variants)
            except Exception:
                row = _blank_document(identifier, 'PROCESSING_ERROR')
            validate_row(row, meta)
            batch._append(records, row)
            rows.append(row)
            print(f'completed {number} skipped {skipped} remaining {unfinished - number} total {len(selected)} '
                  f'pages {sum(len(r["pages"]) for r in rows)} seconds {time.perf_counter() - started:.3f}', flush=True)
        summary = build_summary(meta, rows)
        batch._atomic(batch._target(out / 'summary.json'), summary)
        _atomic_text(batch._target(out / 'summary.txt'), summary_text(summary))
        errors = any(r['code'] in {'OPEN_ERROR', 'PROCESSING_ERROR', 'EMPTY_DOCUMENT'} or
                     any(p['exclusion'] in {'REFERENCE_ERROR', 'PAGE_ERROR'} or
                         any(i['state'] == 'ERROR' for i in p['measurements']) for p in r['pages']) for r in rows)
        return 1 if errors else 0
    finally:
        os.close(fd)


def summarize(out):
    out = batch._location(Path(out).absolute())
    meta = validate_meta(batch._load(batch._target(out / 'run.json').read_bytes()))
    rows = load_rows(batch._target(out / 'results.jsonl'), meta)
    summary = build_summary(meta, rows)
    print(summary_text(summary), end='')
    print(batch._json(summary).decode('utf-8'))
    return 0


def parser():
    result = batch.SafeParser(prog='ocr_baseline', description='Value-free text-layer page OCR baseline')
    result.add_argument('--root')
    result.add_argument('--out', required=True)
    result.add_argument('--ids')
    result.add_argument('--engines', nargs='+', default=None)
    result.add_argument('--variants', nargs='+', default=None)
    result.add_argument('--limit', type=int)
    result.add_argument('--summarize', action='store_true')
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.summarize:
            if args.root is not None or args.ids is not None or args.limit is not None or args.engines or args.variants:
                batch._fail('ARGUMENT_ERROR')
            return summarize(args.out)
        engines, variants = args.engines or ['own'], args.variants or list(VARIANTS)
        if (not args.root or any(e not in ENGINES for e in engines) or len(set(engines)) != len(engines) or
                any(v not in VARIANTS for v in variants) or len(set(variants)) != len(variants) or
                (args.limit is not None and args.limit < 1)):
            batch._fail('ARGUMENT_ERROR')
        return run(args.root, args.out, engines, variants, ids=args.ids, limit=args.limit)
    except KeyboardInterrupt:
        return 130
    except Exception:
        # Never echo arguments, document/dependency messages or tracebacks.
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
