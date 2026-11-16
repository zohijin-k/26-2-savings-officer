"""Closed, aggregate observations of the existing payment routing predicate."""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
import math
from statistics import median
from unittest.mock import patch

CONDITIONS = (
    'PAYMENT_DISPATCH_CALLED', 'GOV_TITLE', 'DOCUMENT_NUMBER_LABEL',
    'DOCUMENT_NUMBER_PATTERN', 'GOV_NUMBER_GATE', 'PAYER_NUMBER_LABEL',
    'WORKPLACE_LABEL', 'INFO_GRID_GATE', 'COMPONENT_TOP_FOUND',
    'FIRST_MONTH_FOUND', 'HEADER_COMPONENT_TOP_FOUND', 'HEADER_BOSUOE_GE3',
    'HEADER_INCOME_GE3', 'GOV_PREDICATE', 'LEGACY_TITLE',
)
FORMS = ('LEGACY', 'GOVERNMENT', 'OTHER')
STATUSES = (
    'MEASURED', 'PROSPECTIVE', 'CONDITION_ERROR', 'PREDICATE_DIVERGENCE',
    'ENGINE_UNAVAILABLE', 'OCR_ERROR', 'EXTRACTION_ERROR', 'EMPTY_OCR',
    'RENDER_ERROR', 'TYPE_NOT_REQUESTED', 'PROCESSING_ERROR', 'NOT_OBSERVED',
)
ANALYSIS_ERRORS = ('CONDITION_ERROR', 'PREDICATE_DIVERGENCE')
# Each threshold is the exclusive upper bound of the corresponding interval.
METRICS = {
    'HEADER_BOSUOE_COUNT': ((1, 2, 3, 4, 10), ('N0', 'N1', 'N2', 'N3', 'N4_9', 'GE10')),
    'HEADER_INCOME_COUNT': ((1, 2, 3, 4, 10), ('N0', 'N1', 'N2', 'N3', 'N4_9', 'GE10')),
    'HEADER_HEIGHT_RATIO': ((.01, .02, .05, .10, .25),
        ('LT_001', 'R001_002', 'R002_005', 'R005_010', 'R010_025', 'GE_025')),
    'BOX_HEIGHT_MEDIAN_RATIO': ((.005, .01, .02, .05, .10),
        ('LT_0005', 'R0005_001', 'R001_002', 'R002_005', 'R005_010', 'GE_010')),
    'BOX_CHAR_MEDIAN': ((1, 4, 8, 16, 32, 64),
        ('LT1', 'R1_4', 'R4_8', 'R8_16', 'R16_32', 'R32_64', 'GE64')),
    'PAGE_BOX_COUNT': ((1, 50, 100, 200, 400, 800),
        ('ZERO', 'N1_49', 'N50_99', 'N100_199', 'N200_399', 'N400_799', 'GE800')),
}


class RouteDiagnosticError(Exception):
    """Only a fixed diagnostic code may leave the analysis boundary."""


def require(condition):
    if not condition:
        raise RouteDiagnosticError('OUTPUT_ERROR')


def bin_value(metric, value):
    if value is None:
        return 'NA'
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0)
    thresholds, labels = METRICS[metric]
    for boundary, label in zip(thresholds, labels):
        if value < boundary:
            return label
    return labels[-1]


def analyze(pairs, payment_called, original_result=None):
    """Project exact prepared inputs to flags and bins without retaining text."""
    from engine_v2.extractors import nhis_common as common, nhis_payment_gov as gov
    from engine_v2.extractors.format_text import normalize_format_text
    from engine_v2.pipeline.layout import line_text, squash

    require(len(pairs) == 1)
    page, result = pairs[0]
    require(page.pixel_size and all(type(v) in (int, float) and math.isfinite(v) and v > 0
                                   for v in page.pixel_size))
    require(all(len(w.bbox_px) == 4 and
                all(type(v) in (int, float) and math.isfinite(v) for v in w.bbox_px) and
                w.bbox_px[2] > w.bbox_px[0] and w.bbox_px[3] > w.bbox_px[1]
                for w in result.words))
    text = squash(' '.join(item.text for _, item in pairs))
    title = '보험료납부확인서' in text
    number_label = '문서확인번호' in text
    number_pattern = bool(gov.DOCUMENT_NUMBER.search(normalize_format_text(text)))
    payer = '납부자번호' in text
    workplace = '사업장명칭' in text
    words = [word for source, item in pairs for row in common.page_lines(source, item) for word in row]
    component_top = gov._component_top(words)
    months = [word for word in words if word.y0 > component_top and gov.MONTH.fullmatch(squash(word.text))]
    first_month = min(months, key=lambda word: word.y0) if months else None
    header_words = [word for word in words if first_month is not None
                    and first_month.y0 - 3 * (first_month.y1 - first_month.y0) <= word.y0
                    and word.cy < first_month.y0]
    header_top = gov._component_top(header_words)
    header_words = [word for word in header_words if word.y0 >= header_top]
    header_text = ' '.join(squash(''.join(line_text(row) for row in common.group_lines(cluster, tol=.25)))
                           for cluster in gov._header_clusters(header_words))
    bosuoe = header_text.count('보수외')
    income = header_text.count('소득월액')
    predicate = bool(title and ((number_label and number_pattern) or (payer and workplace))
                     and bosuoe >= 3 and income >= 3)
    actual = gov.recognizes(pairs) if original_result is None else original_result
    if predicate != actual:
        raise RouteDiagnosticError('PREDICATE_DIVERGENCE')
    flags = dict(zip(CONDITIONS, (
        payment_called, title, number_label, number_pattern, number_label and number_pattern,
        payer, workplace, payer and workplace, math.isfinite(component_top), first_month is not None,
        math.isfinite(header_top), bosuoe >= 3, income >= 3, predicate,
        any(label in text for label in ('보험료납부확인', '건강보험료납부확인')),
    )))
    heights = [(word.y1 - word.y0) / 100 for word in words]
    lengths = [len(squash(word.text)) for word in words]
    measurements = {
        'HEADER_BOSUOE_COUNT': bosuoe, 'HEADER_INCOME_COUNT': income,
        'HEADER_HEIGHT_RATIO': 3 * (first_month.y1 - first_month.y0) / 100 if first_month else None,
        'BOX_HEIGHT_MEDIAN_RATIO': median(heights) if heights else None,
        'BOX_CHAR_MEDIAN': median(lengths) if lengths else None,
        'PAGE_BOX_COUNT': len(words),
    }
    return dict(status='MEASURED' if payment_called else 'PROSPECTIVE', flags=flags,
                bins={metric: bin_value(metric, value) for metric, value in measurements.items()})


def inspect_extraction(page, words, engine, extract, shadow=None, candidates=None):
    """Delegate one primary extraction and observe its actual payment inputs.

    When shadow is a list, one branch mapping of the candidate header rules is
    appended for the same observed payment inputs. When candidates is a list, one
    record of the additional candidate rules, position bins and marker state is
    appended for the same inputs.
    """
    from engine_v2.extractors import nhis_payment, nhis_payment_gov
    from .ocr_baseline_fields import prepare_pairs
    from . import own_adapter_shadow_route as shadow_route

    payment_inputs, predicate_results = [], []
    original_payment = nhis_payment.extract
    original_recognizes = nhis_payment_gov.recognizes

    def payment(pairs, *args, **kwargs):
        payment_inputs.append(pairs)
        return original_payment(pairs, *args, **kwargs)

    def recognizes(pairs):
        result = original_recognizes(pairs)
        predicate_results.append(result)
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.object(nhis_payment, 'extract', payment))
        stack.enter_context(patch.object(nhis_payment_gov, 'recognizes', recognizes))
        extracted = extract(page, words, engine)
    if shadow is not None:
        try:
            require(len(payment_inputs) <= 1)
            shadow.append(shadow_route.branches(payment_inputs[0] if payment_inputs else None, extracted[2]))
        except Exception:
            shadow.append(dict.fromkeys(shadow_route.RULES, 'ERROR'))
    if candidates is not None:
        try:
            require(len(payment_inputs) <= 1)
            candidates.append(shadow_route.candidates(payment_inputs[0] if payment_inputs else None, extracted[2]))
        except Exception:
            candidates.append(shadow_route.failed_candidates())
    try:
        if payment_inputs:
            require(len(payment_inputs) == len(predicate_results) == 1)
            observation = analyze(payment_inputs[0], True, predicate_results[0])
            expected_form = 'GOVERNMENT' if predicate_results[0] else 'LEGACY'
            if extracted[2] != expected_form:
                raise RouteDiagnosticError('PREDICATE_DIVERGENCE')
        else:
            observation = analyze(prepare_pairs(page, words, engine), False)
    except Exception as exc:
        code = 'PREDICATE_DIVERGENCE' if isinstance(exc, RouteDiagnosticError) and exc.args == ('PREDICATE_DIVERGENCE',) else 'CONDITION_ERROR'
        observation = dict(status=code, flags={}, bins={})
    return extracted, observation


def record(observations, document, page, engine, reference_form, form, analysis):
    if observations is not None:
        observations.append(dict(document=document, page=page, engine=engine,
                                 reference_form=reference_form, form=form, **analysis))


def validate_observation(item, engines):
    require(set(item) == {'document', 'page', 'engine', 'reference_form', 'form', 'status', 'flags', 'bins'})
    require(all(type(item[key]) is int and item[key] > 0 for key in ('document', 'page')))
    require(item['engine'] in engines and item['reference_form'] in FORMS and item['form'] in FORMS)
    require(item['status'] in ('MEASURED', 'PROSPECTIVE', *ANALYSIS_ERRORS))
    if item['status'] in ANALYSIS_ERRORS:
        require(item['flags'] == item['bins'] == {})
        return
    require(set(item['flags']) == set(CONDITIONS) and all(type(v) is bool for v in item['flags'].values()))
    require(set(item['bins']) == set(METRICS))
    require(all(item['bins'][metric] in (*METRICS[metric][1], 'NA') for metric in METRICS))
    require(item['flags']['PAYMENT_DISPATCH_CALLED'] == (item['status'] == 'MEASURED'))


def bin_definitions():
    definitions = []
    for metric, (thresholds, labels) in METRICS.items():
        intervals = [dict(bin=label, lower=lower, upper=upper)
                     for label, lower, upper in zip(labels, (0, *thresholds), (*thresholds, 'INF'))]
        intervals.append(dict(bin='NA', lower='NA', upper='NA'))
        definitions.append(dict(metric=metric, intervals=intervals))
    return definitions


def build_summary(meta, rows, observations):
    engines = ('text_layer', *meta['engines'])
    references, paths, observed = {}, {}, {}
    for item in rows:
        if item['type'] == 'NHIS_PAYMENT' and item['form'] is not None:
            identity = (item['document'], item['page'])
            require(identity not in references or references[identity] == item['form'])
            references[identity] = item['form']
            paths.setdefault((*identity, item['engine']), []).append(item)
    for item in observations:
        validate_observation(item, engines)
        identity = (item['document'], item['page'])
        require(references.get(identity) == item['reference_form'])
        path = (*identity, item['engine'])
        require(path not in observed)
        observed[path] = item
    groups = []
    for reference_form in FORMS:
        identities = [identity for identity, form in references.items() if form == reference_form]
        for engine in engines:
            statuses = dict.fromkeys(STATUSES, 0)
            conditions = {code: {'O': 0, 'X': 0} for code in CONDITIONS}
            distributions = {metric: dict.fromkeys((*labels, 'NA'), 0)
                             for metric, (_, labels) in METRICS.items()}
            patterns = Counter()
            for identity in identities:
                observation = observed.get((*identity, engine))
                if observation is None:
                    codes = {item['code'] for item in paths.get((*identity, engine), [])}
                    codes.update(item['code'] for item in paths.get((*identity, 'X'), [])
                                 if item['code'] == 'TYPE_NOT_REQUESTED')
                    status = next((code for code in STATUSES if code in codes), 'NOT_OBSERVED')
                    statuses[status] += 1
                    continue
                statuses[observation['status']] += 1
                if observation['status'] in ANALYSIS_ERRORS:
                    continue
                for code, value in observation['flags'].items():
                    conditions[code]['O' if value else 'X'] += 1
                for metric, bucket in observation['bins'].items():
                    distributions[metric][bucket] += 1
                pattern = ''.join('O' if observation['flags'][code] else 'X' for code in CONDITIONS)
                patterns[(pattern, observation['form'])] += 1
            groups.append(dict(reference_form=reference_form, engine=engine, pages=len(identities),
                statuses=statuses, conditions=conditions, distributions=distributions,
                patterns=[dict(pattern=pattern, form=form, pages=number)
                          for (pattern, form), number in sorted(patterns.items())]))
    return dict(condition_order=list(CONDITIONS), bin_definitions=bin_definitions(), groups=groups)


def validate_summary(value):
    require(set(value) == {'condition_order', 'bin_definitions', 'groups'})
    require(value['condition_order'] == list(CONDITIONS) and value['bin_definitions'] == bin_definitions())
    require(all(type(interval[key]) in (str, int, float)
                for definition in value['bin_definitions'] for interval in definition['intervals']
                for key in ('lower', 'upper')))
    for group in value['groups']:
        require(set(group) == {'reference_form', 'engine', 'pages', 'statuses', 'conditions', 'distributions', 'patterns'})
        require(group['reference_form'] in FORMS and group['engine'] in ('text_layer', 'own', 'applevision'))
        require(set(group['statuses']) == set(STATUSES) and set(group['conditions']) == set(CONDITIONS))
        require(all(set(outcomes) == {'O', 'X'} for outcomes in group['conditions'].values()))
        require(set(group['distributions']) == set(METRICS))
        require(all(set(group['distributions'][metric]) == {*labels, 'NA'}
                    for metric, (_, labels) in METRICS.items()))
        require(all(set(item) == {'pattern', 'form', 'pages'} and item['form'] in FORMS and
                    type(item['pattern']) is str and len(item['pattern']) == len(CONDITIONS) and
                    set(item['pattern']) <= {'O', 'X'} for item in group['patterns']))
        numbers = [group['pages'], *group['statuses'].values(),
                   *(n for outcomes in group['conditions'].values() for n in outcomes.values()),
                   *(n for buckets in group['distributions'].values() for n in buckets.values()),
                   *(item['pages'] for item in group['patterns'])]
        require(all(type(n) is int and n >= 0 for n in numbers))
        measured = group['statuses']['MEASURED'] + group['statuses']['PROSPECTIVE']
        require(sum(group['statuses'].values()) == group['pages'])
        require(all(sum(outcomes.values()) == measured for outcomes in group['conditions'].values()))
        require(all(sum(buckets.values()) == measured for buckets in group['distributions'].values()))
        require(sum(item['pages'] for item in group['patterns']) == measured)


def text_lines(value, *, brief=False):
    lines = ['CONDITION_ORDER ' + ' '.join(value['condition_order'])]
    for definition in value['bin_definitions']:
        for interval in definition['intervals']:
            lines.append(f"BIN {definition['metric']} {interval['bin']} {interval['lower']} {interval['upper']}")
    for group in value['groups']:
        prefix = f"{group['reference_form']} {group['engine']}"
        if brief and not group['pages']:
            continue
        lines.append(f"CONDITION_POPULATION {prefix} {group['pages']}")
        for code, number in group['statuses'].items():
            if number or not brief:
                lines.append(f'CONDITION_STATUS {prefix} {code} {number}')
        for code, outcomes in group['conditions'].items():
            lines.extend(f'CONDITION {prefix} {code} {outcome} {number}' for outcome, number in outcomes.items())
        for metric, buckets in group['distributions'].items():
            for bucket, number in buckets.items():
                if number or not brief:
                    lines.append(f'DISTRIBUTION {prefix} {metric} {bucket} {number}')
        lines.extend(f"CONDITION_PATTERN {prefix} {item['pattern']} {item['form']} {item['pages']}"
                     for item in group['patterns'])
    return lines
