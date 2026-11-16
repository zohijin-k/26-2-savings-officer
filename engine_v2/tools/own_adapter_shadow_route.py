"""Shadow evaluation of candidate payment-routing header rules (diagnostic only).

Each rule receives the exact payment inputs the operating dispatch received and
replaces only the header selection of the government predicate. Title,
document-number and information-grid gates, the component-top cut, horizontal
clustering and the three-repetition counts stay identical to the operating
predicate. Nothing here changes routing or extraction; the operating result
remains the one observed by the caller.

Rules (H = median positive box height, C = first-month centre, page percent):
  CURRENT  first_month.y0 - 3 * first-month height <= word.y0 and word.cy < first_month.y0
           (independent restatement of the operating predicate).
  A        C - 3H <= word.cy < C - 0.5H.
  S        the contiguous header-line block directly above the first month. Words
           at least 0.5H above C are grouped into lines nearest first (a word joins
           a line within 0.3H of that line's first centre). Lines are accepted
           upward until a centre gap above 1.5H, a line holding a group label
           (고지금액/납부금액) or a line without header vocabulary.
A path without an observed payment dispatch keeps its actual branch under every
rule, because every rule differs only inside the payment dispatch.

Candidate rules (a separate summary section; CURRENT, A and S above are unchanged):
  A_325, A_350  A with the far bound at C - 3.25H and C - 3.50H (near bound C - 0.5H).
                A_300 would equal A exactly and is reported as an alias of A.
  B             title/metadata gates plus the government table structure itself: the two
                group headers, the nine column headers aligned with them, the eight amount
                column boundaries and the continuous twelve-month rows, as checked by the
                existing government reader. No header-band repetition count.
  L             LEGACY when the legacy-only marker is present, otherwise CURRENT.
                CURRENT+L is the same rule and is reported as an alias of L.
  A_325+L, A_350+L  LEGACY when the marker is present, otherwise the band rule.
Legacy-only marker: a grouped line whose text, with whitespace and the bracket, colon and
middle-dot characters removed, contains 가입구분 (the legacy column/field header). No
character-confusion correction is applied.
Position measures: D3 is the third-nearest centre distance, in H, of 보수외 (or 소득월액)
words above the first-month centre; fewer than three such words give NA.
"""
from __future__ import annotations

import re
from statistics import median

RULES = ('CURRENT', 'A', 'S')
BRANCHES = ('LEGACY', 'GOVERNMENT', 'OTHER', 'ERROR')
FORMS = ('LEGACY', 'GOVERNMENT', 'OTHER')
A_FAR, A_NEAR = 3.0, .5
S_SAME_ROW, S_LINE_TOLERANCE, S_GAP = .5, .3, 1.5


class ShadowRouteError(Exception):
    """Only a fixed diagnostic code may leave the shadow boundary."""


def require(condition):
    if not condition:
        raise ShadowRouteError('OUTPUT_ERROR')


def _gates(pairs):
    from engine_v2.extractors import nhis_payment_gov as gov
    from engine_v2.extractors.format_text import normalize_format_text
    from engine_v2.pipeline.layout import squash

    text = squash(' '.join(result.text for _, result in pairs))
    number = '문서확인번호' in text and bool(gov.DOCUMENT_NUMBER.search(normalize_format_text(text)))
    grid = '납부자번호' in text and '사업장명칭' in text
    return '보험료납부확인서' in text and (number or grid)


def _geometry(pairs):
    from engine_v2.extractors import nhis_common as common, nhis_payment_gov as gov
    from engine_v2.pipeline.layout import squash

    words = [word for page, result in pairs for row in common.page_lines(page, result) for word in row]
    component_top = gov._component_top(words)
    months = [word for word in words if word.y0 > component_top and gov.MONTH.fullmatch(squash(word.text))]
    first = min(months, key=lambda word: word.y0) if months else None
    heights = [word.y1 - word.y0 for word in words if word.y1 > word.y0]
    return words, first, median(heights) if heights else None


def _current(words, first, general):
    return [word for word in words if first is not None
            and first.y0 - 3 * (first.y1 - first.y0) <= word.y0 and word.cy < first.y0]


def _band_a(words, first, general):
    if first is None or not general:
        return []
    return [word for word in words
            if first.cy - A_FAR * general <= word.cy < first.cy - A_NEAR * general]


def _vocabulary():
    from engine_v2.extractors import nhis_payment_gov as gov
    return (*gov.HEADERS, *gov.GROUPS, '년월'), gov.GROUPS


def _block_s(words, first, general):
    from engine_v2.pipeline.layout import squash

    if first is None or not general:
        return []
    vocabulary, groups = _vocabulary()

    def header_word(text):
        value = squash(text)
        return bool(value) and (any(value in label for label in vocabulary)
                                or '보수외' in value or '소득월액' in value)

    centre = first.cy
    above = sorted((word for word in words if centre - word.cy >= S_SAME_ROW * general),
                   key=lambda word: -word.cy)
    lines = []
    for word in above:
        if lines and lines[-1][0] - word.cy <= S_LINE_TOLERANCE * general:
            lines[-1][1].append(word)
        else:
            lines.append((word.cy, [word]))
    selected, previous = [], centre
    for line_centre, members in lines:
        if previous - line_centre > S_GAP * general:
            break
        if (any(squash(word.text) in groups for word in members)
                or not any(header_word(word.text) for word in members)):
            break
        selected.extend(members)
        previous = line_centre
    return selected


SELECTIONS = {'CURRENT': _current, 'A': _band_a, 'S': _block_s}


def government(pairs, rule):
    """Return the candidate government decision of one rule on prepared payment inputs."""
    from engine_v2.extractors import nhis_common as common, nhis_payment_gov as gov
    from engine_v2.pipeline.layout import line_text, squash

    words, first, general = _geometry(pairs)
    header = SELECTIONS[rule](words, first, general)
    top = gov._component_top(header)
    header = [word for word in header if word.y0 >= top]
    text = ' '.join(squash(''.join(line_text(row) for row in common.group_lines(cluster, tol=.25)))
                    for cluster in gov._header_clusters(header))
    return bool(_gates(pairs) and text.count('보수외') >= 3 and text.count('소득월액') >= 3)


def branches(pairs, actual):
    """Map every rule to a fixed branch code; pairs is None without a payment dispatch."""
    require(actual in FORMS)
    if pairs is None:
        return dict.fromkeys(RULES, actual)
    output = {}
    for rule in RULES:
        try:
            output[rule] = 'GOVERNMENT' if government(pairs, rule) else 'LEGACY'
        except Exception:
            output[rule] = 'ERROR'
    return output


def record(observations, document, page, engine, form, value):
    if observations is not None and value is not None:
        observations.append(dict(document=document, page=page, engine=engine, form=form, rules=dict(value)))


def validate_observation(item, engines):
    require(set(item) == {'document', 'page', 'engine', 'form', 'rules'})
    require(all(type(item[key]) is int and item[key] > 0 for key in ('document', 'page')))
    require(item['engine'] in engines and item['form'] in FORMS)
    require(set(item['rules']) == set(RULES) and all(item['rules'][rule] in BRANCHES for rule in RULES))


def build_summary(meta, observations):
    engines = ('text_layer', *meta['engines'])
    paths = {}
    for item in observations:
        validate_observation(item, engines)
        key = (item['document'], item['page'], item['engine'])
        require(key not in paths)
        paths[key] = item
    reference = {(document, page): item for (document, page, engine), item in paths.items()
                 if engine == 'text_layer'}
    routes, cross, checks = [], [], []
    for rule in RULES:
        for engine in engines:
            values = [item['rules'][rule] for (_, _, name), item in paths.items() if name == engine]
            routes.extend(dict(rule=rule, engine=engine, form=branch, pages=values.count(branch))
                          for branch in BRANCHES)
        for engine in meta['engines']:
            pairs = [(reference[(document, page)]['rules'][rule], item['rules'][rule])
                     for (document, page, name), item in paths.items()
                     if name == engine and (document, page) in reference]
            cross.extend(dict(rule=rule, engine=engine, reference_form=left, form=right,
                              pages=pairs.count((left, right)))
                         for left in BRANCHES for right in BRANCHES)
    for engine in engines:
        values = [item for (_, _, name), item in paths.items() if name == engine]
        matched = sum(item['rules']['CURRENT'] == item['form'] for item in values)
        checks.append(dict(engine=engine, match=matched, mismatch=len(values) - matched))
    return dict(rules=list(RULES), branches=list(BRANCHES), routes=routes, cross=cross, checks=checks)


def validate_summary(value):
    require(set(value) == {'rules', 'branches', 'routes', 'cross', 'checks'})
    require(value['rules'] == list(RULES) and value['branches'] == list(BRANCHES))
    require(all(set(item) == {'rule', 'engine', 'form', 'pages'} and item['rule'] in RULES
                and item['form'] in BRANCHES for item in value['routes']))
    require(all(set(item) == {'rule', 'engine', 'reference_form', 'form', 'pages'} and item['rule'] in RULES
                and item['reference_form'] in BRANCHES and item['form'] in BRANCHES for item in value['cross']))
    require(all(set(item) == {'engine', 'match', 'mismatch'} for item in value['checks']))
    require(all(item['engine'] in ('text_layer', 'own', 'applevision')
                for family in ('routes', 'cross', 'checks') for item in value[family]))
    numbers = [*(item['pages'] for item in value['routes']), *(item['pages'] for item in value['cross']),
               *(item[key] for item in value['checks'] for key in ('match', 'mismatch'))]
    require(all(type(number) is int and number >= 0 for number in numbers))


def failures(value):
    """CURRENT disagreements with the operating branch and rule errors."""
    return (sum(item['mismatch'] for item in value['checks'])
            + sum(item['pages'] for item in value['routes'] if item['form'] == 'ERROR'))


def text_lines(value, *, brief=False):
    lines = [f"SHADOW_RULES {' '.join(value['rules'])}"]
    lines.extend(f"SHADOW_ROUTE {item['rule']} {item['engine']} {item['form']} {item['pages']}"
                 for item in value['routes'] if item['pages'] or not brief or item['form'] != 'ERROR')
    lines.extend(f"SHADOW_CROSS {item['rule']} {item['engine']} {item['reference_form']} {item['form']} {item['pages']}"
                 for item in value['cross'] if item['pages'] or not brief)
    lines.extend(f"SHADOW_CHECK CURRENT {item['engine']} MATCH {item['match']} MISMATCH {item['mismatch']}"
                 for item in value['checks'])
    return lines


# ---------------------------------------------------------------------------
# Candidate rules, position distribution and legacy-only marker (diagnostic only).

CANDIDATES = ('A_325', 'A_350', 'B', 'L', 'A_325+L', 'A_350+L')
ALIASES = (('A_300', 'A'), ('CURRENT+L', 'L'))
STRUCTURE_CHECKS = ('payment_group_headers', 'payment_component_headers', 'payment_columns',
                    'monthly_rows_found', 'months_continuous')
LEGACY_MARKER = '가입구분'
MARKER_NOISE = re.compile(r'[\s\[\]()（）:：·ㆍ・.]')
MEASURES = ('BOSUOE', 'INCOME')
MEASURE_TEXT = {'BOSUOE': '보수외', 'INCOME': '소득월액'}
MARKERS = ('O', 'X', 'NA')
_FINE = tuple(2 + step * .125 for step in range(17))
_COARSE = (4.5, 5.0, 5.5, 6.0)
BOUNDS = (0.0, *_FINE, *_COARSE)
DISTANCE_BINS = (*(f'{low:.3f}-{high:.3f}' for low, high in zip(BOUNDS, BOUNDS[1:])), '6.000+', 'NA')


def _band(far):
    def select(words, first, general):
        if first is None or not general:
            return []
        return [word for word in words
                if first.cy - far * general <= word.cy < first.cy - A_NEAR * general]
    return select


SELECTIONS.update({'A_325': _band(3.25), 'A_350': _band(3.5)})


def legacy_marker(pairs):
    """True when any grouped line carries the legacy-only 가입구분 header."""
    from engine_v2.extractors import nhis_common as common
    from engine_v2.pipeline.layout import line_text

    return any(LEGACY_MARKER in MARKER_NOISE.sub('', line_text(row))
               for page, result in pairs for row in common.page_lines(page, result))


def structure(pairs):
    """Gates plus the complete government table structure observed by the existing reader."""
    from engine_v2.extractors import nhis_payment_gov as gov

    if not _gates(pairs):
        return False
    passed = {check.name: check.passed for check in gov.extract(pairs).validations}
    return all(passed.get(name) is True for name in STRUCTURE_CHECKS)


def candidate_government(pairs, rule):
    if rule == 'B':
        return structure(pairs)
    base, _, marker = rule.partition('+')
    if rule == 'L':
        base, marker = 'CURRENT', 'L'
    if marker and legacy_marker(pairs):
        return False
    return government(pairs, base)


def distance_bin(value):
    if value is None:
        return 'NA'
    require(type(value) is float and value == value and value >= 0)
    for low, high, label in zip(BOUNDS, BOUNDS[1:], DISTANCE_BINS):
        if value < high:
            return label
    return '6.000+'


def third_distances(pairs):
    """Third-nearest upward centre distance in H for each component phrase, or None."""
    from engine_v2.pipeline.layout import squash

    words, first, general = _geometry(pairs)
    output = {}
    for measure in MEASURES:
        values = [] if first is None or not general else sorted(
            float((first.cy - word.cy) / general) for word in words
            if word.cy < first.cy and MEASURE_TEXT[measure] in squash(word.text))
        output[measure] = values[2] if len(values) >= 3 else None
    return output


def candidates(pairs, actual):
    """Fixed codes only: candidate branches, D3 bins and the marker state of one path."""
    require(actual in FORMS)
    if pairs is None:
        return dict(rules=dict.fromkeys(CANDIDATES, actual),
                    measures={**dict.fromkeys(MEASURES, 'NA'), 'MARKER': 'NA'})
    rules = {}
    for rule in CANDIDATES:
        try:
            rules[rule] = 'GOVERNMENT' if candidate_government(pairs, rule) else 'LEGACY'
        except Exception:
            rules[rule] = 'ERROR'
    try:
        measures = {measure: distance_bin(value) for measure, value in third_distances(pairs).items()}
    except Exception:
        measures = dict.fromkeys(MEASURES, 'NA')
    try:
        measures['MARKER'] = 'O' if legacy_marker(pairs) else 'X'
    except Exception:
        measures['MARKER'] = 'NA'
    return dict(rules=rules, measures=measures)


def failed_candidates():
    return dict(rules=dict.fromkeys(CANDIDATES, 'ERROR'),
                measures={**dict.fromkeys(MEASURES, 'NA'), 'MARKER': 'NA'})


def record_candidates(observations, document, page, engine, form, value):
    if observations is not None and value is not None:
        observations.append(dict(document=document, page=page, engine=engine, form=form,
                                 rules=dict(value['rules']), measures=dict(value['measures'])))


def validate_candidate_observation(item, engines):
    require(set(item) == {'document', 'page', 'engine', 'form', 'rules', 'measures'})
    require(all(type(item[key]) is int and item[key] > 0 for key in ('document', 'page')))
    require(item['engine'] in engines and item['form'] in FORMS)
    require(set(item['rules']) == set(CANDIDATES) and all(item['rules'][rule] in BRANCHES for rule in CANDIDATES))
    require(set(item['measures']) == {*MEASURES, 'MARKER'} and item['measures']['MARKER'] in MARKERS
            and all(item['measures'][measure] in DISTANCE_BINS for measure in MEASURES))


def build_candidate_summary(meta, observations):
    engines = ('text_layer', *meta['engines'])
    paths = {}
    for item in observations:
        validate_candidate_observation(item, engines)
        key = (item['document'], item['page'], item['engine'])
        require(key not in paths)
        paths[key] = item
    reference = {(document, page): item for (document, page, engine), item in paths.items()
                 if engine == 'text_layer'}
    routes, cross, distances, markers = [], [], [], []
    for rule in CANDIDATES:
        for engine in engines:
            values = [item['rules'][rule] for (_, _, name), item in paths.items() if name == engine]
            routes.extend(dict(rule=rule, engine=engine, form=branch, pages=values.count(branch))
                          for branch in BRANCHES)
        for engine in meta['engines']:
            pairs = [(reference[(document, page)]['rules'][rule], item['rules'][rule])
                     for (document, page, name), item in paths.items()
                     if name == engine and (document, page) in reference]
            cross.extend(dict(rule=rule, engine=engine, reference_form=left, form=right,
                              pages=pairs.count((left, right)))
                         for left in BRANCHES for right in BRANCHES)
    for engine in engines:
        values = [item['measures'] for (_, _, name), item in paths.items() if name == engine]
        for measure in MEASURES:
            found = [value[measure] for value in values]
            distances.extend(dict(engine=engine, measure=measure, bin=label, pages=found.count(label))
                             for label in DISTANCE_BINS)
        found = [value['MARKER'] for value in values]
        markers.extend(dict(engine=engine, marker=state, pages=found.count(state)) for state in MARKERS)
    return dict(rules=list(CANDIDATES), aliases=[dict(alias=alias, rule=rule) for alias, rule in ALIASES],
                branches=list(BRANCHES), routes=routes, cross=cross, distances=distances, markers=markers)


def validate_candidate_summary(value):
    require(set(value) == {'rules', 'aliases', 'branches', 'routes', 'cross', 'distances', 'markers'})
    require(value['rules'] == list(CANDIDATES) and value['branches'] == list(BRANCHES))
    require(value['aliases'] == [dict(alias=alias, rule=rule) for alias, rule in ALIASES])
    require(all(set(item) == {'rule', 'engine', 'form', 'pages'} and item['rule'] in CANDIDATES
                and item['form'] in BRANCHES for item in value['routes']))
    require(all(set(item) == {'rule', 'engine', 'reference_form', 'form', 'pages'} and item['rule'] in CANDIDATES
                and item['reference_form'] in BRANCHES and item['form'] in BRANCHES for item in value['cross']))
    require(all(set(item) == {'engine', 'measure', 'bin', 'pages'} and item['measure'] in MEASURES
                and item['bin'] in DISTANCE_BINS for item in value['distances']))
    require(all(set(item) == {'engine', 'marker', 'pages'} and item['marker'] in MARKERS
                for item in value['markers']))
    require(all(item['engine'] in ('text_layer', 'own', 'applevision')
                for family in ('routes', 'cross', 'distances', 'markers') for item in value[family]))
    numbers = [item['pages'] for family in ('routes', 'cross', 'distances', 'markers') for item in value[family]]
    require(all(type(number) is int and number >= 0 for number in numbers))


def candidate_failures(value):
    return sum(item['pages'] for item in value['routes'] if item['form'] == 'ERROR')


def candidate_lines(value, *, brief=False):
    lines = [f"CANDIDATE_RULES {' '.join(value['rules'])}"]
    lines.extend(f"CANDIDATE_ALIAS {item['alias']} {item['rule']}" for item in value['aliases'])
    lines.extend(f"CANDIDATE_ROUTE {item['rule']} {item['engine']} {item['form']} {item['pages']}"
                 for item in value['routes'] if item['pages'] or not brief or item['form'] != 'ERROR')
    lines.extend(f"CANDIDATE_CROSS {item['rule']} {item['engine']} {item['reference_form']} {item['form']} {item['pages']}"
                 for item in value['cross'] if item['pages'] or not brief)
    lines.extend(f"DIST3 {item['engine']} {item['measure']} {item['bin']} {item['pages']}"
                 for item in value['distances'] if item['pages'] or not brief)
    lines.extend(f"MARKER {item['engine']} {item['marker']} {item['pages']}"
                 for item in value['markers'] if item['pages'] or not brief or item['marker'] != 'NA')
    return lines
