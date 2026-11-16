"""Value-free diagnostics through the existing clean OCR baseline boundary."""
from __future__ import annotations

import argparse
import builtins
from collections import defaultdict
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from . import batch_assess as batch
from .ocr_baseline_settings import SETTINGS
from . import own_adapter_route_diag as route_diag
from . import own_adapter_shadow_route as shadow_route

VERSION = 1
ENGINES = ('own', 'applevision')
FORMS = ('LEGACY', 'GOVERNMENT', 'OTHER')
CAUSES = ('OK', 'ROUTE_MISMATCH', 'LABEL_NOT_FOUND', 'LABEL_SPACED', 'LABEL_SPLIT', 'VALUE_NOT_FOUND',
          'VALUE_OTHER_LINE', 'LINE_MERGED', 'ORDER', 'NORMALIZE', 'PATTERN_MISMATCH',
          'OCR_CHAR', 'OTHER')
AVAILABILITY = ('ENCRYPTED', 'OPEN_ERROR', 'EMPTY_DOCUMENT', 'NO_TEXT_LAYER',
    'SHORT_TEXT_LAYER', 'BROKEN_TEXT_LAYER', 'REFERENCE_MISSING',
    'REFERENCE_UNATTRIBUTABLE', 'CLASSIFICATION_FAILED', 'ENGINE_UNAVAILABLE',
    'OCR_ERROR', 'EXTRACTION_ERROR', 'EMPTY_OCR', 'LIMIT_REMAINING',
    'REFERENCE_ERROR', 'RENDER_ERROR', 'PROCESSING_ERROR', 'TYPE_NOT_REQUESTED')
ERRORS = frozenset(('OPEN_ERROR', 'EMPTY_DOCUMENT', 'REFERENCE_ERROR', 'RENDER_ERROR',
                    'OCR_ERROR', 'EXTRACTION_ERROR', 'PROCESSING_ERROR'))
FILENAMES = ('run.json', 'results.jsonl', 'summary.json', 'summary.txt', 'summary_brief.txt')
CLI_ERRORS = ('ARGUMENT_ERROR', 'OUTPUT_ERROR', 'ROOT_NOT_DIR', 'OUT_EXISTS',
    'OUT_INSIDE_ROOT', 'ROOT_INSIDE_OUT', 'IDS_NOT_FOUND', 'IDS_INVALID',
    'SYMLINK_REJECTED', 'LOCATION_REJECTED')
EXCEPTION_TYPES = (FileNotFoundError, PermissionError, FileExistsError, IsADirectoryError,
    NotADirectoryError, UnicodeError, OSError, ValueError, TypeError, RuntimeError,
    ImportError, LookupError, ArithmeticError, AssertionError, Exception)

# Public field names are a fixed vocabulary, never extractor-produced strings.
FIELD_CODES = {
    'address_history': 'ADDRESS_HISTORY', 'address_history_count': 'ADDRESS_HISTORY_COUNT',
    'applicant_birth_date': 'APPLICANT_BIRTH_DATE', 'applicant_name': 'APPLICANT_NAME',
    'birth_date': 'BIRTH_DATE', 'current_address': 'CURRENT_ADDRESS',
    'issue_date': 'ISSUE_DATE', 'issuer': 'ISSUER', 'name': 'NAME',
    '가구원목록': 'HOUSEHOLD_MEMBERS', '가구원수': 'HOUSEHOLD_COUNT',
    '가입구분': 'MEMBERSHIP', '가입내역': 'INSURANCE_RECORDS', '개업일': 'OPENING_DATE',
    '건강보험료': 'HEALTH_PREMIUM', '결제금액': 'PAYMENT_AMOUNT',
    '결제수단': 'PAYMENT_METHOD', '결제일': 'PAYMENT_DATE', '고지월': 'BILLING_MONTH',
    '공급가액': 'SUPPLY_AMOUNT', '공동사업자유무': 'JOINT_BUSINESS', '과세유형': 'TAX_TYPE',
    '근로관련가입여부': 'WORK_INSURED', '근로관련최근취득일': 'WORK_LATEST_ACQUISITION',
    '근로관련최초취득일': 'WORK_FIRST_ACQUISITION', '납부자번호': 'PAYER_NUMBER',
    '납부총액': 'PAYMENT_TOTAL', '동의여부': 'CONSENT', '면접시간': 'INTERVIEW_TIME',
    '면접일': 'INTERVIEW_DATE', '면접장소': 'INTERVIEW_PLACE',
    '문서확인번호': 'DOCUMENT_NUMBER', '받는분': 'RECIPIENT', '발급번호': 'ISSUE_NUMBER',
    '발급번호목록': 'ISSUE_NUMBERS', '발급일': 'ISSUE_DATE', '변동내역': 'CHANGE_HISTORY',
    '보수외소득월액_건강': 'OTHER_INCOME_HEALTH', '보험구분': 'INSURANCE_TYPE',
    '보험별가입여부': 'INSURANCE_MEMBERSHIP', '보험별가입자종별': 'INSURANCE_CATEGORIES',
    '부가세': 'VAT', '사업자등록번호': 'BUSINESS_NUMBER', '사업자등록일': 'BUSINESS_REGISTRATION_DATE',
    '사업장관리번호': 'WORKPLACE_NUMBER', '사업장명칭': 'WORKPLACE',
    '사업장명칭목록': 'WORKPLACES', '사업장소재지': 'WORKPLACE_ADDRESS', '상호': 'BUSINESS_NAME',
    '생년월일': 'BIRTH_DATE', '서명잉크확인': 'SIGNATURE_INK', '성명': 'NAME',
    '시험명': 'EXAM_NAME', '업태': 'BUSINESS_TYPE', '업태업종': 'BUSINESS_CATEGORY',
    '용도구분': 'PURPOSE', '월별고지금액': 'MONTHLY_HEALTH_BILLED',
    '월별납부내역': 'MONTHLY_PAYMENTS', '월별보수외소득월액_건강': 'MONTHLY_OTHER_INCOME_HEALTH',
    '월별장기요양보험료': 'MONTHLY_CARE_PREMIUM', '응시일': 'EXAM_DATE',
    '응시직군': 'JOB_CATEGORY', '일용근로내역자료': 'DAILY_WORK_RECORDS',
    '자격이력자료': 'QUALIFICATION_HISTORY', '자격확인요청일': 'QUALIFICATION_REQUEST_DATE',
    '장기요양보험료': 'CARE_PREMIUM', '전입일': 'MOVE_IN_DATE', '조회기간': 'QUERY_PERIOD',
    '종목': 'BUSINESS_ITEM', '취득일': 'ACQUISITION_DATE', '품목수': 'ITEM_COUNT',
    '확인일': 'CONFIRMATION_DATE', '회사명': 'COMPANY',
}
REGISTRY = {kind: {FIELD_CODES[key]: key for key in keys} for kind, keys in batch.FIELDS.items()}
DEFAULT_FIELDS = ('NHIS_PAYMENT:MEMBERSHIP', 'NHIS_PAYMENT:BILLING_MONTH', 'NHIS_PAYMENT:ISSUE_DATE')
SELECTION_KEYS = ('selected', 'not_listed', 'duplicates', 'outside_root', 'missing', 'invalid',
                  'folder_lines', 'file_lines', 'empty_folder_lines', 'overlapping_pdfs')
COUNTERS = ('inventory_pdf', 'excluded_files', 'selected_documents', 'not_listed',
    'duplicate_ids', 'outside_root_ids', 'missing_ids', 'invalid_ids',
    'folder_id_lines', 'file_id_lines', 'empty_folder_id_lines', 'overlapping_pdf_ids',
    'attempted_documents', 'limit_remaining', 'processed_pages', 'diagnosed_pages',
    'excluded_documents', 'excluded_pages', 'unrequested_pages', 'skipped_documents',
    'classified_unrequested_documents',
    'engine_errors', 'empty_ocr', 'execution_errors')
ROW_KEYS = frozenset(('document', 'page', 'type', 'form', 'observed_form', 'field', 'engine',
                       'code', 'eligible', 'counted', 'exact_match', 'normalized_match'))


class DiagnosticError(Exception):
    """A fixed-code failure whose details never enter output."""


def require(condition):
    if not condition:
        raise DiagnosticError('OUTPUT_ERROR')


def count(value):
    return type(value) is int and value >= 0


def parse_fields(values):
    result = []
    for value in values:
        parts = value.split(':')
        if len(parts) != 2 or parts[0] not in REGISTRY or parts[1] not in REGISTRY[parts[0]]:
            raise DiagnosticError('ARGUMENT_ERROR')
        if tuple(parts) in result:
            raise DiagnosticError('ARGUMENT_ERROR')
        result.append(tuple(parts))
    if not result:
        raise DiagnosticError('ARGUMENT_ERROR')
    return result


def validate_meta(value):
    require(isinstance(value, dict) and set(value) == {'schema_version', 'engines', 'fields', 'clean', 'limit'})
    require(type(value['schema_version']) is int and value['schema_version'] == VERSION)
    require(isinstance(value['engines'], list) and bool(value['engines']) and
            all(engine in ENGINES for engine in value['engines']) and
            len(value['engines']) == len(set(value['engines'])))
    require(isinstance(value['fields'], list) and bool(value['fields']))
    selected = []
    for item in value['fields']:
        require(isinstance(item, dict) and set(item) == {'type', 'field'})
        require(item['type'] in REGISTRY and item['field'] in REGISTRY[item['type']])
        selected.append((item['type'], item['field']))
    require(len(set(selected)) == len(selected))
    require(isinstance(value['clean'], dict) and value['clean'].keys() == SETTINGS['variants']['clean'].keys())
    require(all(type(value['clean'][key]) is type(expected) and value['clean'][key] == expected
                for key, expected in SETTINGS['variants']['clean'].items()))
    require(value['limit'] is None or (count(value['limit']) and value['limit'] > 0))
    return value


def validate_row(value, meta):
    require(isinstance(value, dict) and set(value) == ROW_KEYS)
    require(count(value['document']) and value['document'] > 0 and count(value['page']))
    require(value['type'] in {*REGISTRY, 'X'})
    require(value['form'] in (*FORMS, None) and value['observed_form'] in (*FORMS, None))
    require(value['form'] is None or value['page'] > 0)
    require(value['observed_form'] is None or
            (value['form'] in FORMS and value['engine'] in meta['engines'] and value['page'] > 0))
    require(value['engine'] in {*meta['engines'], 'X'})
    require(value['code'] in CAUSES + AVAILABILITY)
    require(value['field'] == 'X' or (value['type'] in REGISTRY and
            {'type': value['type'], 'field': value['field']} in meta['fields']))
    require(all(type(value[key]) is int and value[key] in (0, 1) for key in ('eligible', 'counted')))
    require(all(value[key] is None or (type(value[key]) is int and value[key] in (0, 1))
                for key in ('exact_match', 'normalized_match')))
    require(value['counted'] == int(value['code'] in CAUSES))
    require(not value['counted'] or (value['eligible'] == 1 and value['field'] != 'X'
                                    and value['engine'] != 'X' and value['page'] > 0))
    require(value['code'] != 'REFERENCE_MISSING' or value['eligible'] == 0)
    require(value['eligible'] or (value['exact_match'] is None and value['normalized_match'] is None))
    require(not value['counted'] or value['normalized_match'] is not None)
    require(value['exact_match'] != 1 or value['normalized_match'] == 1)
    require(value['code'] != 'OK' or value['normalized_match'] == 1)
    require(value['normalized_match'] != 1 or value['code'] == 'OK')
    require(value['code'] != 'ROUTE_MISMATCH' or
            (value['form'] in FORMS and value['observed_form'] in FORMS and
             value['form'] != value['observed_form'] and value['normalized_match'] == 0))
    require(value['code'] != 'TYPE_NOT_REQUESTED' or
            (value['type'] != 'X' and value['field'] == value['engine'] == 'X' and value['eligible'] == 0))
    return value


def row(document, page=0, kind='X', form=None, field='X', engine='X', code='PROCESSING_ERROR',
        *, observed_form=None, eligible=0, exact=None, normalized=None):
    return dict(document=document, page=page, type=kind, form=form, observed_form=observed_form,
                field=field, engine=engine, code=code, eligible=eligible,
                counted=int(code in CAUSES), exact_match=exact, normalized_match=normalized)


def _kind(result):
    kind = result.detected_doc_type.name if result.detected_doc_type else 'X'
    return kind if kind in REGISTRY else 'X'


def process_document(path, ordinal, engines, fields, route_observations=None, shadow_observations=None,
                     candidate_observations=None, marker_observations=None):
    """Return projected records under the caller's shared read-only guard.

    REFERENCE_ERROR has unknown reference availability. RENDER_ERROR retains
    reference eligibility but has no match opportunity. PROCESSING_ERROR keeps
    already measured field flags when a diagnostic predicate fails. These
    statuses always have counted=0 and never enter the causal denominator.
    """
    import pymupdf
    from . import ocr_baseline_runtime as runtime
    from . import own_adapter_diag_evidence as evidence
    output = []
    try:
        document = pymupdf.open(path)
    except Exception:
        return [row(ordinal, code='OPEN_ERROR')], 0
    with document:
        if document.needs_pass:
            return [row(ordinal, code='ENCRYPTED')], 0
        if not document.page_count:
            return [row(ordinal, code='EMPTY_DOCUMENT')], 0
        for index, source in enumerate(document):
            number = index + 1
            try:
                page, truth = runtime.reference_page(source, index)
                quality, _ = runtime.quality(source.get_text('text'), truth)
                if quality != 'NONE':
                    output.append(row(ordinal, number, code=quality))
                    continue
                ref_shadow, ref_candidates, ref_markers = [], [], []
                try:
                    extracted, ref_analysis = route_diag.inspect_extraction(
                        page, truth, 'text_layer', evidence.extract_with_form, ref_shadow, ref_candidates, ref_markers)
                    reference, ref_raw, form = extracted
                except Exception:
                    output.append(row(ordinal, number, code='REFERENCE_ERROR'))
                    continue
                kind = _kind(reference)
                if kind == 'NHIS_PAYMENT':
                    route_diag.record(route_observations, ordinal, number, 'text_layer', form, form, ref_analysis)
                    shadow_route.record(shadow_observations, ordinal, number, 'text_layer', form,
                                        ref_shadow[0] if ref_shadow else None)
                    shadow_route.record_candidates(candidate_observations, ordinal, number, 'text_layer', form,
                                                   ref_candidates[0] if ref_candidates else None)
                    shadow_route.record_markers(marker_observations, ordinal, number, 'text_layer', form,
                                                ref_markers[0] if ref_markers else None)
                if kind == 'X':
                    output.append(row(ordinal, number, form=form, code='CLASSIFICATION_FAILED'))
                    continue
                selected = [(code, REGISTRY[kind][code]) for selected_kind, code in fields if selected_kind == kind]
                if not selected:
                    output.append(row(ordinal, number, kind, form, code='TYPE_NOT_REQUESTED'))
                    continue
                try:
                    image, _ = runtime.variant_image(source, 'clean', runtime.page_seed('0', index+1), page.pixel_size)
                except Exception:
                    output.extend(row(ordinal, number, kind, form, code, engine, 'RENDER_ERROR',
                        eligible=int(key in ref_raw and batch._present(ref_raw[key])))
                        for engine in engines for code, key in selected)
                    continue
                for engine in engines:
                    try:
                        recognized, _, _ = runtime.recognize(engine, image)
                    except Exception as exc:
                        code = 'ENGINE_UNAVAILABLE' if isinstance(exc, (ImportError, NotImplementedError, FileNotFoundError)) else 'OCR_ERROR'
                        output.extend(row(ordinal, number, kind, form, field, engine, code,
                            eligible=int(key in ref_raw and batch._present(ref_raw[key]))) for field, key in selected)
                        continue
                    if not recognized.words:
                        output.extend(row(ordinal, number, kind, form, field, engine, 'EMPTY_OCR',
                            eligible=int(key in ref_raw and batch._present(ref_raw[key]))) for field, key in selected)
                        continue
                    path_shadow, path_candidates, path_markers = [], [], []
                    try:
                        extracted, analysis = route_diag.inspect_extraction(
                            image, recognized.words, engine, evidence.extract_with_form, path_shadow, path_candidates,
                            path_markers)
                        observed, obs_raw, observed_form = extracted
                    except Exception:
                        output.extend(row(ordinal, number, kind, form, field, engine, 'EXTRACTION_ERROR',
                            eligible=int(key in ref_raw and batch._present(ref_raw[key]))) for field, key in selected)
                        continue
                    if kind == 'NHIS_PAYMENT':
                        route_diag.record(route_observations, ordinal, number, engine, form, observed_form, analysis)
                        shadow_route.record(shadow_observations, ordinal, number, engine, observed_form,
                                            path_shadow[0] if path_shadow else None)
                        shadow_route.record_candidates(candidate_observations, ordinal, number, engine,
                                                       observed_form, path_candidates[0] if path_candidates else None)
                        shadow_route.record_markers(marker_observations, ordinal, number, engine,
                                                    observed_form, path_markers[0] if path_markers else None)
                    observed_kind = _kind(observed)
                    for field, key in selected:
                        eligible = int(key in ref_raw and batch._present(ref_raw[key]))
                        exact, normalized = (None, None)
                        try:
                            if eligible:
                                exact, normalized = (int(value) for value in evidence.comparison(
                                    kind, key, ref_raw, obs_raw, observed_kind))
                            if not eligible:
                                code = 'REFERENCE_MISSING'
                            elif normalized:
                                code = 'OK'
                            else:
                                code = evidence.diagnose(image, truth, recognized.words, kind, key,
                                    ref_raw, obs_raw, observed_kind, engine, form, observed_form)
                            require(code in CAUSES + AVAILABILITY)
                        except Exception:
                            code = 'PROCESSING_ERROR'
                        output.append(row(ordinal, number, kind, form, field, engine, code,
                            observed_form=observed_form, eligible=eligible, exact=exact, normalized=normalized))
            except Exception:
                output.append(row(ordinal, number, code='PROCESSING_ERROR'))
        return output, document.page_count


def route_summary(meta, rows):
    """Count completed dispatches once per page, independently of field count."""
    reference = {}
    observed = {engine: {} for engine in meta['engines']}
    for item in rows:
        identity = (item['document'], item['page'])
        if item['form'] is not None:
            require(identity not in reference or reference[identity] == item['form'])
            reference[identity] = item['form']
        if item['observed_form'] is not None:
            pages = observed[item['engine']]
            require(identity not in pages or pages[identity] == item['observed_form'])
            pages[identity] = item['observed_form']
    distributions = [dict(engine='text_layer', form=form, pages=sum(v == form for v in reference.values()))
                     for form in FORMS]
    cross = []
    for engine, pages in observed.items():
        distributions.extend(dict(engine=engine, form=form, pages=sum(v == form for v in pages.values()))
                             for form in FORMS)
        cross.extend(dict(engine=engine, reference_form=reference_form, observed_form=observed_form,
                          pages=sum(reference[identity] == reference_form and form == observed_form
                                    for identity, form in pages.items()))
                     for reference_form in FORMS for observed_form in FORMS)
    return dict(distributions=distributions, cross=cross)


def build_summary(meta, rows, counters, route_observations=(), shadow_observations=(), candidate_observations=(),
                  marker_observations=()):
    cells = defaultdict(list)
    for item in meta['fields']:
        for form in FORMS:
            for engine in meta['engines']:
                cells[(item['type'], form, item['field'], engine)]
    for item in rows:
        validate_row(item, meta)
        if item['field'] != 'X' and item['engine'] != 'X':
            cells[(item['type'], item['form'], item['field'], item['engine'])].append(item)
    groups = []
    for (kind, form, field, engine), items in sorted(cells.items()):
        counts = {code: sum(item['code'] == code for item in items) for code in CAUSES}
        statuses = {code: sum(item['code'] == code for item in items) for code in AVAILABILITY}
        diagnosed = sum(counts.values())
        match_opportunities = sum(item['normalized_match'] is not None for item in items)
        exact_matches = sum(item['exact_match'] == 1 for item in items)
        normalized_matches = sum(item['normalized_match'] == 1 for item in items)
        groups.append(dict(type=kind, form=form, field=field, engine=engine,
            eligible=sum(item['eligible'] for item in items), diagnosed=diagnosed,
            missing_reference=statuses['REFERENCE_MISSING'],
            unsupported_evidence=statuses['REFERENCE_UNATTRIBUTABLE'],
            match_opportunities=match_opportunities, exact_matches=exact_matches,
            normalized_matches=normalized_matches,
            exact_match_rate=exact_matches/match_opportunities if match_opportunities else None,
            normalized_match_rate=normalized_matches/match_opportunities if match_opportunities else None,
            codes=counts, statuses=statuses,
            rates={code: counts[code]/diagnosed if diagnosed else None for code in CAUSES}))
    availability = {
        'documents': {code: sum(r['code'] == code and r['page'] == 0 for r in rows) for code in AVAILABILITY},
        'pages': {code: sum(r['code'] == code and r['page'] > 0 and r['engine'] == 'X'
                            for r in rows) for code in AVAILABILITY},
        'engines': {code: len({(r['document'], r['page'], r['engine']) for r in rows
                              if r['code'] == code and r['engine'] != 'X'}) for code in AVAILABILITY},
    }
    return dict(schema_version=VERSION, counters=dict(counters), availability=availability,
                routes=route_summary(meta, rows), groups=groups,
                route_conditions=route_diag.build_summary(meta, rows, route_observations),
                shadow_routes=shadow_route.build_summary(meta, shadow_observations),
                shadow_candidates=shadow_route.build_candidate_summary(meta, candidate_observations),
                shadow_markers=shadow_route.build_marker_summary(meta, marker_observations))


def validate_summary(value, meta, rows, route_observations=(), shadow_observations=(), candidate_observations=(),
                     marker_observations=()):
    require(isinstance(value, dict) and set(value) == {
        'schema_version', 'counters', 'availability', 'routes', 'groups', 'route_conditions', 'shadow_routes',
        'shadow_candidates', 'shadow_markers'})
    require(type(value['schema_version']) is int and value['schema_version'] == VERSION)
    counters = value['counters']
    require(isinstance(counters, dict) and set(counters) == set(COUNTERS) and all(count(v) for v in counters.values()))
    expected = build_summary(meta, rows, counters, route_observations, shadow_observations, candidate_observations,
                             marker_observations)
    require(value == expected)
    require(all(count(item['pages']) for items in value['routes'].values() for item in items))
    require(all(count(number) for statuses in value['availability'].values() for number in statuses.values()))
    route_diag.validate_summary(value['route_conditions'])
    shadow_route.validate_summary(value['shadow_routes'])
    shadow_route.validate_candidate_summary(value['shadow_candidates'])
    shadow_route.validate_marker_summary(value['shadow_markers'])
    for group in value['groups']:
        require(set(group['codes']) == set(CAUSES) and set(group['statuses']) == set(AVAILABILITY))
        require(all(count(v) for v in [group['eligible'], group['diagnosed'], group['missing_reference'],
            group['unsupported_evidence'], group['match_opportunities'], group['exact_matches'], group['normalized_matches'],
            *group['codes'].values(), *group['statuses'].values()]))
        require(all(v is None or (type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1)
                    for v in [*group['rates'].values(), group['exact_match_rate'], group['normalized_match_rate']]))
    return value


def summary_text(summary):
    lines = ['OWN_ADAPTER_DIAG']
    lines.extend(f'{key.upper()} {value}' for key, value in summary['counters'].items())
    for unit, statuses in summary['availability'].items():
        lines.extend(f'{unit.upper()} {code} {number}' for code, number in statuses.items())
    for item in summary['routes']['distributions']:
        lines.append(f"ROUTE {item['engine']} {item['form']} {item['pages']}")
    for item in summary['routes']['cross']:
        lines.append(f"ROUTE_CROSS {item['engine']} {item['reference_form']} {item['observed_form']} {item['pages']}")
    for group in summary['groups']:
        for key in ('ELIGIBLE', 'DIAGNOSED', 'MATCH_OPPORTUNITIES', 'EXACT_MATCHES', 'NORMALIZED_MATCHES'):
            lines.append(' '.join((group['type'], group['form'], group['field'], group['engine'],
                                  key, str(group[key.lower()]))))
        for key in ('EXACT_MATCH_RATE', 'NORMALIZED_MATCH_RATE'):
            value = group[key.lower()]
            lines.append(' '.join((group['type'], group['form'], group['field'], group['engine'],
                                  key, 'null' if value is None else f'{value:.8f}')))
        for code, number in group['codes'].items():
            rate = group['rates'][code]
            lines.append(' '.join((group['type'], group['form'], group['field'], group['engine'],
                code, str(number), str(group['diagnosed']), 'null' if rate is None else f'{rate:.8f}')))
        for code, number in group['statuses'].items():
            lines.append(' '.join((group['type'], group['form'], group['field'], group['engine'], code, str(number))))
    lines.extend(route_diag.text_lines(summary['route_conditions']))
    lines.extend(shadow_route.text_lines(summary['shadow_routes']))
    lines.extend(shadow_route.candidate_lines(summary['shadow_candidates']))
    lines.extend(shadow_route.marker_lines(summary['shadow_markers']))
    return '\n'.join(lines)+'\n'


def summary_brief(summary):
    lines = ['OWN_ADAPTER_DIAG_BRIEF']
    lines.extend(f'{key.upper()} {value}' for key, value in summary['counters'].items())
    for unit, statuses in summary['availability'].items():
        lines.extend(f'{unit.upper()} {code} {number}' for code, number in statuses.items() if number)
    for item in summary['routes']['distributions']:
        lines.append(f"ROUTE {item['engine']} {item['form']} {item['pages']}")
    for item in summary['routes']['cross']:
        lines.append(f"ROUTE_CROSS {item['engine']} {item['reference_form']} {item['observed_form']} {item['pages']}")
    lines.extend(route_diag.text_lines(summary['route_conditions'], brief=True))
    lines.extend(shadow_route.text_lines(summary['shadow_routes'], brief=True))
    lines.extend(shadow_route.candidate_lines(summary['shadow_candidates'], brief=True))
    lines.extend(shadow_route.marker_lines(summary['shadow_markers'], brief=True))
    for group in summary['groups']:
        if not (group['eligible'] or any(group['statuses'].values())):
            continue
        prefix = ' '.join((group['type'], group['form'], group['field'], group['engine']))
        lines.append(f"FIELD_POPULATION {prefix} {group['eligible']} {group['match_opportunities']} {group['diagnosed']}")
        for code, number in {**group['codes'], **group['statuses']}.items():
            if number:
                lines.append(f'FIELD {prefix} {code} {number}')
    return '\n'.join(lines)+'\n'


def _ids_selection(root, path, out, files):
    """Expand immediate folder IDs and exact PDF IDs using the safe inventory.

    Invalid/missing counts are per skipped line. A valid selector line is a
    duplicate when repeated or when it adds no PDFs because all its candidates
    were already selected. overlapping_pdfs counts already-selected candidates
    per valid line, including a partially overlapping folder expansion. An empty
    safe folder is valid and contributes empty_folder_lines instead of missing.
    """
    actual = batch._location(path)
    if not actual.is_file() or actual.is_relative_to(out):
        raise DiagnosticError('IDS_INVALID')
    available = {item.relative_to(root).as_posix(): item for item in files}
    with os.scandir(root) as entries:
        folders = {entry.name for entry in entries if not entry.name.startswith('.')
                   and not entry.is_symlink() and entry.is_dir(follow_symlinks=False)}
    folder_files = defaultdict(set)
    for identifier in available:
        parts = identifier.split('/')
        if len(parts) > 1:
            folder_files[parts[0]].add(identifier)
    counts = dict.fromkeys(SELECTION_KEYS, 0)
    selected, seen = set(), set()
    data = actual.read_bytes()
    for number, raw in enumerate(data.split(b'\n')):
        if number == 0:
            raw = raw.removeprefix(b'\xef\xbb\xbf')
        if raw.endswith(b'\r'):
            raw = raw[:-1]
        try:
            value = raw.decode('utf-8')
        except UnicodeDecodeError:
            counts['invalid'] += 1
            continue
        if not value.strip() or value.lstrip().startswith('#'):
            continue
        parts = value.split('/')
        if Path(value).is_absolute() or '..' in parts:
            counts['outside_root'] += 1
            continue
        if (not batch._relative(value) or '\\' in value
                or any(part == '' or part.startswith('.') for part in parts)):
            counts['invalid'] += 1
            continue
        if len(parts) == 1 and value in folders:
            counts['folder_lines'] += 1
            candidates = folder_files[value]
            if not candidates:
                counts['empty_folder_lines'] += 1
        elif Path(value).suffix.lower() == '.pdf':
            if value not in available:
                counts['missing'] += 1
                continue
            counts['file_lines'] += 1
            candidates = {value}
        elif len(parts) == 1 or Path(value).suffix.lower() in batch.EXTENSIONS:
            counts['missing'] += 1
            continue
        else:
            counts['invalid'] += 1
            continue
        overlap = candidates & selected
        counts['overlapping_pdfs'] += len(overlap)
        if value in seen or (candidates and overlap == candidates):
            counts['duplicates'] += 1
        seen.add(value)
        selected.update(candidates)
    counts['selected'] = len(selected)
    counts['not_listed'] = len(available.keys() - selected)
    return [path for identifier, path in available.items() if identifier in selected], counts


def _selection(root, requested, ids):
    arguments = [root, requested] if ids is None else [root, requested, ids]
    if any(Path(path).is_symlink() for path in arguments):
        raise DiagnosticError('SYMLINK_REJECTED')
    original_root, original_out = Path(root).resolve(), Path(requested).resolve()
    if not original_root.is_dir():
        raise DiagnosticError('ROOT_NOT_DIR')
    if original_out.is_relative_to(original_root):
        raise DiagnosticError('OUT_INSIDE_ROOT')
    if original_root.is_relative_to(original_out):
        raise DiagnosticError('ROOT_INSIDE_OUT')
    if original_out.exists():
        raise DiagnosticError('OUT_EXISTS')
    root = batch._location(root)
    out = batch._location(requested)
    if ids is not None:
        original = Path(ids)
        if not original.exists():
            raise DiagnosticError('IDS_NOT_FOUND')
        if not original.is_file() or original.stat().st_nlink != 1:
            raise DiagnosticError('IDS_INVALID')
    inventory, excluded = batch.inventory(root)
    files = [path for path in inventory if path.suffix.lower() == '.pdf']
    counts = dict.fromkeys(SELECTION_KEYS, 0)
    counts['selected'] = len(files)
    if ids is not None:
        actual_ids = batch._location(ids)
        if any(os.path.samefile(actual_ids, path) for path in files):
            raise DiagnosticError('IDS_INVALID')
        files, counts = _ids_selection(root, actual_ids, out, files)
    return out, files, counts, len(inventory), sum(excluded.values())


def run(root, out, engines=ENGINES, *, ids=None, limit=None, fields=DEFAULT_FIELDS):
    from .ocr_baseline import _atomic_text
    if (not engines or any(engine not in ENGINES for engine in engines)
            or len(engines) != len(set(engines))
            or (limit is not None and (not count(limit) or limit <= 0))):
        raise DiagnosticError('ARGUMENT_ERROR')
    selected = parse_fields(fields)
    meta = validate_meta(dict(schema_version=VERSION, engines=list(engines),
        fields=[dict(type=kind, field=field) for kind, field in selected],
        clean=deepcopy(SETTINGS['variants']['clean']), limit=limit))
    # The location checker owns quiet Git calls for ignored repository inputs.
    target, files, selection, inventory_count, excluded = _selection(root, out, ids)
    counters = dict.fromkeys(COUNTERS, 0)
    counters.update(inventory_pdf=selection['selected']+selection['not_listed'],
        excluded_files=excluded+inventory_count-selection['selected']-selection['not_listed'],
        selected_documents=selection['selected'], not_listed=selection['not_listed'],
        duplicate_ids=selection['duplicates'], outside_root_ids=selection['outside_root'],
        missing_ids=selection['missing'], invalid_ids=selection['invalid'],
        folder_id_lines=selection['folder_lines'], file_id_lines=selection['file_lines'],
        empty_folder_id_lines=selection['empty_folder_lines'], overlapping_pdf_ids=selection['overlapping_pdfs'])
    pending = files if limit is None else files[:limit]
    counters['limit_remaining'] = len(files)-len(pending)
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    batch._atomic(target/'run.json', meta)
    rows = []
    route_observations = []
    shadow_observations = []
    candidate_observations = []
    marker_observations = []
    # Claim the fixed result file even when there are no selected PDFs.
    fd = batch._open(target/'results.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    os.close(fd)
    for ordinal, path in enumerate(pending, 1):
        document_observations, document_shadow, document_candidates, document_markers = [], [], [], []
        try:
            with batch.guarded():
                projected, pages = process_document(path, ordinal, engines, selected, document_observations,
                                                    document_shadow, document_candidates, document_markers)
        except KeyboardInterrupt:
            raise
        except Exception:
            projected, pages = [row(ordinal, code='PROCESSING_ERROR')], 0
            document_observations, document_shadow, document_candidates, document_markers = [], [], [], []
        for item in projected:
            validate_row(item, meta)
            batch._append(target/'results.jsonl', item)
        rows.extend(projected)
        route_observations.extend(document_observations)
        shadow_observations.extend(document_shadow)
        candidate_observations.extend(document_candidates)
        marker_observations.extend(document_markers)
        counters['attempted_documents'] += 1
        counters['processed_pages'] += pages
        unrequested = {item['page'] for item in projected if item['code'] == 'TYPE_NOT_REQUESTED'}
        requested_kinds = {kind for kind, _ in selected}
        has_requested_page = any(item['type'] in requested_kinds for item in projected)
        counters['skipped_documents'] += int(not has_requested_page)
        counters['classified_unrequested_documents'] += int(pages > 0 and len(unrequested) == pages)
    counters['diagnosed_pages'] = len({(r['document'], r['page']) for r in rows if r['counted']})
    counters['excluded_documents'] = len({r['document'] for r in rows if r['page'] == 0})
    counters['excluded_pages'] = len({(r['document'],r['page']) for r in rows
        if r['page'] > 0 and r['engine'] == 'X' and r['code'] in AVAILABILITY
        and r['code'] != 'TYPE_NOT_REQUESTED'})
    counters['unrequested_pages'] = len({(r['document'],r['page'])
        for r in rows if r['code'] == 'TYPE_NOT_REQUESTED'})
    counters['engine_errors'] = len({(r['document'],r['page'],r['engine']) for r in rows
        if r['engine'] != 'X' and r['code'] in ('ENGINE_UNAVAILABLE','OCR_ERROR','EXTRACTION_ERROR')})
    counters['empty_ocr'] = len({(r['document'],r['page'],r['engine']) for r in rows if r['code'] == 'EMPTY_OCR'})
    counters['execution_errors'] = len({(r['document'],r['page'],r['engine']) for r in rows if r['code'] in ERRORS})
    summary = validate_summary(build_summary(meta, rows, counters, route_observations, shadow_observations,
                                             candidate_observations, marker_observations),
                               meta, rows, route_observations, shadow_observations, candidate_observations,
                               marker_observations)
    batch._atomic(target/'summary.json', summary)
    _atomic_text(target/'summary.txt', summary_text(summary))
    _atomic_text(target/'summary_brief.txt', summary_brief(summary))
    print(json.dumps(dict(counters)), flush=True)
    condition_errors = sum(group['statuses'][code] for group in summary['route_conditions']['groups']
                           for code in route_diag.ANALYSIS_ERRORS)
    return int(counters['execution_errors'] > 0 or condition_errors > 0
               or shadow_route.failures(summary['shadow_routes']) > 0
               or shadow_route.candidate_failures(summary['shadow_candidates']) > 0
               or shadow_route.marker_failures(summary['shadow_markers']) > 0)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise DiagnosticError('ARGUMENT_ERROR')


def parser():
    result = SafeParser(prog='own_adapter_diag', description='VALUE_FREE_ROUTE_DIAGNOSTICS')
    result.add_argument('--root', required=True, metavar='ROOT')
    result.add_argument('--out', required=True, metavar='OUT')
    result.add_argument('--ids', metavar='IDS')
    result.add_argument('--limit', type=int, metavar='N')
    result.add_argument('--engines', nargs='+', default=list(ENGINES), metavar='ENGINE')
    result.add_argument('--fields', nargs='+', default=list(DEFAULT_FIELDS), metavar='TYPE_FIELD')
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        return run(args.root, args.out, args.engines, ids=args.ids, limit=args.limit, fields=args.fields)
    except KeyboardInterrupt:
        print(json.dumps({'code': 'INTERRUPTED'}))
        return 130
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (DiagnosticError, batch.BatchError, route_diag.RouteDiagnosticError,
            shadow_route.ShadowRouteError) as exc:
        code = exc.args[0] if exc.args and exc.args[0] in CLI_ERRORS else 'OUTPUT_ERROR'
        print(json.dumps({'code': code}))
        return 2
    except Exception as exc:
        kind = next(base.__name__ for base in type(exc).__mro__
                    if base in EXCEPTION_TYPES and getattr(builtins, base.__name__, None) is base)
        print(json.dumps({'code': 'UNEXPECTED_ERROR', 'exception_type': kind}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
