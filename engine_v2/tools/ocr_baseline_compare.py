"""Read-only, value-free comparison of two ocr_baseline result directories.

Use ``python -B -m engine_v2.tools.ocr_baseline_compare --before DIR --after DIR``.
Only run.json and results.jsonl are read, through the original closed validators.
Documents are never opened. Output contains fixed codes, registered ASCII type/field
codes, integers, finite numbers and NA only: no IDs, paths, values, hashes or
exception messages.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

from pathlib import Path

from . import batch_assess as batch
from . import ocr_baseline as baseline

ERROR_CODES = ('ARGUMENT_ERROR', 'LOCATION_REJECTED', 'RESULT_UNAVAILABLE', 'RESULT_INVALID')
FIELD_HEADER = ('FIELD type field engine variant before_match before_eligible before_rate_pct '
                'after_match after_eligible after_rate_pct delta_pp')
RECOGNITION_HEADER = ('RECOGNITION type engine variant metric before_pct after_pct delta_pp '
                      'before_measured after_measured')
TIME_HEADER = ('TIME type engine variant metric before_s after_s delta_s '
               'before_measured after_measured before_attempted after_attempted')


class CompareError(Exception):
    """Carries one fixed code from ERROR_CODES."""


def _fail(code):
    raise CompareError(code)


def load(directory):
    """Validate one result directory with the original ocr_baseline schema."""
    try:
        out = batch._location(Path(directory).absolute())
        run_json, results = batch._target(out / 'run.json'), batch._target(out / 'results.jsonl')
    except batch.BatchError:
        _fail('LOCATION_REJECTED')
    if not run_json.is_file() or not results.is_file():
        _fail('RESULT_UNAVAILABLE')
    try:
        meta = baseline.validate_meta(batch._load(run_json.read_bytes()))
        rows = baseline.load_rows(results, meta)
    except (batch.BatchError, OSError, ValueError, TypeError, KeyError):
        _fail('RESULT_INVALID')
    return meta, rows


def _field_codes():
    from .own_adapter_diag import FIELD_CODES
    return FIELD_CODES


def _pct(value):
    return None if value is None else 100 * value


def _delta(before, after):
    return None if before is None or after is None else after - before


def _format(value):
    if value is None:
        return 'NA'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)


def _line(*values):
    return ' '.join(_format(value) for value in values)


def cohort(before_rows, after_rows):
    """Count-only comparability of document/page/type/measurement populations."""
    def keys(rows):
        documents = {row['id'] for row in rows}
        pages = {(row['id'], page['page']): page['type'] for row in rows for page in row['pages']}
        measurements = {(row['id'], page['page'], page['type'], item['engine'], item['variant'])
                        for row in rows for page in row['pages'] for item in page['measurements']}
        return documents, pages, measurements
    (bd, bp, bm), (ad, ap, am) = keys(before_rows), keys(after_rows)
    common_pages = bp.keys() & ap.keys()
    return dict(
        documents=(len(bd), len(ad), len(bd & ad), len(bd - ad), len(ad - bd)),
        pages=(len(bp), len(ap), len(common_pages), len(bp.keys() - ap.keys()), len(ap.keys() - bp.keys())),
        measurements=(len(bm), len(am), len(bm & am), len(bm - am), len(am - bm)),
        type_changed=sum(bp[key] != ap[key] for key in common_pages),
    )


def compare(before, after):
    (before_meta, before_rows), (after_meta, after_rows) = before, after
    lines = ['OCR_BASELINE_COMPARE', 'STATUS key value']
    lines.append(_line('ROOT_DIGEST', 'SAME' if before_meta['root_digest'] == after_meta['root_digest'] else 'DIFFERENT'))
    lines.append(_line('ENGINES', 'SAME' if before_meta['engines'] == after_meta['engines'] else 'DIFFERENT'))
    lines.append(_line('VARIANTS', 'SAME' if before_meta['variants'] == after_meta['variants'] else 'DIFFERENT'))
    counts = cohort(before_rows, after_rows)
    lines.append('COHORT unit before after common before_only after_only')
    for unit in ('documents', 'pages', 'measurements'):
        lines.append(_line('COHORT', unit.upper(), *counts[unit]))
    lines.append(_line('COHORT', 'TYPE_CHANGED_PAGES', counts['type_changed']))
    summaries = [baseline.build_summary(before_meta, before_rows), baseline.build_summary(after_meta, after_rows)]
    lines.append('EXCLUSION code before after')
    for code in baseline.EXCLUSIONS[1:]:
        lines.append(_line('EXCLUSION', code, summaries[0]['excluded_pages'][code], summaries[1]['excluded_pages'][code]))
    groups = [{(g['type'], g['engine'], g['variant']): g for g in summary['groups']} for summary in summaries]
    engines = [e for e in baseline.ENGINES if e in before_meta['engines'] or e in after_meta['engines']]
    variants = [v for v in baseline.VARIANTS if v in before_meta['variants'] or v in after_meta['variants']]
    kinds = sorted(batch.FIELDS)
    codes = _field_codes()
    cells = dict(field=0, field_measured=0, group=0, group_measured=0)

    lines.append(FIELD_HEADER)
    for kind in kinds:
        for key in batch.FIELDS[kind]:
            for engine in engines:
                for variant in variants:
                    values = []
                    for side in groups:
                        field = side.get((kind, engine, variant), {}).get('fields', {}).get(key)
                        match, eligible = (field['match'], field['eligible']) if field else (0, 0)
                        values.append((match, eligible, _pct(match / eligible) if eligible else None))
                    cells['field'] += 1
                    cells['field_measured'] += int(values[0][1] > 0 or values[1][1] > 0)
                    lines.append(_line('FIELD', kind, codes[key], engine, variant, *values[0], *values[1],
                                       _delta(values[0][2], values[1][2])))

    recognition, timing = [RECOGNITION_HEADER], [TIME_HEADER]
    for kind in kinds:
        for engine in engines:
            for variant in variants:
                pair = [side.get((kind, engine, variant)) for side in groups]
                cells['group'] += 1
                cells['group_measured'] += int(any(pair))
                def metric(group, name):
                    if group is None:
                        return None, 0
                    measured = group['attempted'] - group['table_unavailable']
                    if name == 'PAGE_CER_MEAN':
                        return _pct(group['page_cer']['mean']), group['page_cer']['count']
                    if name == 'POOLED_CER':
                        return _pct(group['metrics']['cer']['rate']), measured
                    return _pct(group['metrics']['words']['f1']), measured
                for name in ('PAGE_CER_MEAN', 'POOLED_CER', 'WORD_F1'):
                    (b, bn), (a, an) = metric(pair[0], name), metric(pair[1], name)
                    recognition.append(_line('RECOGNITION', kind, engine, variant, name, b, a, _delta(b, a), bn, an))
                for name, key in (('OCR_TIME_PER_PAGE_S', 'ocr'), ('TOTAL_TIME_PER_PAGE_S', 'total')):
                    stats = [group['seconds'][key] if group else None for group in pair]
                    b, a = (s['mean'] if s else None for s in stats)
                    bn, an = (s['count'] if s else 0 for s in stats)
                    ba, aa = (group['attempted'] if group else 0 for group in pair)
                    timing.append(_line('TIME', kind, engine, variant, name, b, a, _delta(b, a), bn, an, ba, aa))
    lines.extend(recognition)
    lines.extend(timing)
    lines.append('GRID cells measured_cells')
    lines.append(_line('GRID', 'FIELD', cells['field'], cells['field_measured']))
    lines.append(_line('GRID', 'GROUP', cells['group'], cells['group_measured']))
    return '\n'.join(lines) + '\n'


def parser():
    result = batch.SafeParser(prog='ocr_baseline_compare',
                              description='Value-free before/after comparison of two ocr_baseline result folders')
    result.add_argument('--before', required=True)
    result.add_argument('--after', required=True)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        text = compare(load(args.before), load(args.after))
    except KeyboardInterrupt:
        return 130
    except CompareError as error:
        code = error.args[0] if error.args and error.args[0] in ERROR_CODES else 'RESULT_INVALID'
        print(f'ERROR {code}')
        return 2
    except batch.BatchError:
        print('ERROR ARGUMENT_ERROR')
        return 2
    except Exception:
        # Never echo arguments, contents or exception messages.
        print('ERROR RESULT_INVALID')
        return 2
    print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
