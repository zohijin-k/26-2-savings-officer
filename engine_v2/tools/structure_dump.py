"""Closed, character-masked NHIS payment structure projection for layout_dump.

Only the explicit projection below may leave the read-only processing guard.
The diagnostic is a scoped payment probe, not an upload verdict.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

from contextlib import ExitStack
from collections import Counter
from datetime import date
import json
import math
import os
from pathlib import Path
import unicodedata
from unittest.mock import patch

from . import batch_assess as batch

ENGINES = ("text_layer", "own", "applevision")


def label_vocabulary():
    """Literal preservation comes exclusively from existing extractor constants."""
    from ..extractors import nhis_payment as legacy, nhis_payment_gov as government
    return frozenset((*legacy.CARE, *legacy.HEALTH, *legacy.OUTSIDE_HEALTH,
                      *legacy.MONTH_LABELS, *legacy.TABLE_LABELS,
                      *legacy.TABLE_LABEL_FRAGMENTS, *government.COMPONENTS,
                      *government.HEADERS, *government.GROUPS))


def mask_word(text, labels):
    if not isinstance(text, str):
        raise ValueError("INVALID_WORD")
    if text in labels:
        return text
    from .privacy import _is_hangul
    out = []
    for char in text:
        if char.isdigit():
            out.append("9")
        elif _is_hangul(ord(char)):
            out.append("가")
        elif (char.isascii() and char.isalpha() or "LATIN" in unicodedata.name(char, "")
              or (unicodedata.normalize("NFKC", char).isascii()
                  and unicodedata.normalize("NFKC", char).isalpha())):
            out.append("A")
        elif char.isspace() or unicodedata.category(char).startswith(("P", "S", "Z")):
            out.append(char)
        else:
            out.append("?")
    return "".join(out)


def _numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def _word(word, index, labels):
    box = word.bbox_px
    if (not isinstance(box, (tuple, list)) or len(box) != 4
            or not all(_numeric(item) for item in box)
            or box[2] < box[0] or box[3] < box[1]
            or not _numeric(word.confidence) or not 0 <= word.confidence <= 1):
        raise ValueError("INVALID_WORD")
    return {"word_index": index, "text": mask_word(word.text, labels),
            "bbox_px": list(box), "width_px": box[2] - box[0],
            "height_px": box[3] - box[1], "confidence": word.confidence}


def _page(page, state="OK", code="NONE", words=None):
    if (type(page.page) is not int or page.page < 0
            or not isinstance(page.pixel_size, (tuple, list)) or len(page.pixel_size) != 2
            or not all(_numeric(n) and n > 0 for n in page.pixel_size)
            or not isinstance(page.page_size_pt, (tuple, list)) or len(page.page_size_pt) != 2
            or not all(_numeric(n) and n > 0 for n in page.page_size_pt)):
        raise ValueError("INVALID_PAGE")
    return {"page": page.page, "state": state, "code": code,
            "page_size_pt": list(page.page_size_pt), "pixel_size": list(page.pixel_size),
            "coordinate_units": "px", "words": words or []}


def _not_run(state="NOT_RUN", code="NONE"):
    return {"state": state, "code": code, "scope": "PAYMENT_DIAGNOSTIC",
            "reader": "NOT_RUN", "recognized_headers": [],
            "header_group_count": None, "header_groups_expected": 9,
            "header_groups_matched": None,
            "header_count_scope": "NOT_RUN", "month_count": None,
            "month_count_scope": "NOT_RUN", "table_months_missing": None,
            "failed_validations": [], "missing_billing_months": None,
            "billing_cause": "NOT_RUN", "billing_severity": "NOT_RUN"}


def _matched_headers(values, expected):
    """Count covered expected slots, respecting each repeated component's quota.

    Ordering is still validated exclusively by the original extractor.
    """
    remaining = Counter(expected)
    count = 0
    for value in values:
        # These are the original government reader's month-column alternatives.
        if value in {"월별", "년월", "월"}:
            value = expected[0]
        if remaining[value] > 0:
            remaining[value] -= 1
            count += 1
    return count


def _billing_cause(ocr, requirement, findings):
    """Project existing billing-check branches without retaining their values."""
    from ..extractors.payment_period import FIELD
    from demo.backend.rules.doc_check import CODE_MISSING_BILLING_MONTHS
    finding = next((item for item in findings if item.code == CODE_MISSING_BILLING_MONTHS), None)
    if finding is None:
        return False, "NONE", "NONE"
    severity = finding.severity if finding.severity in {"NEEDS_REVIEW", "FAIL"} else "UNKNOWN"
    raw = ocr.fields.get(FIELD)
    if raw is None:
        return True, "MONTHLY_MAP_MISSING_OR_UNREADABLE", severity
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return True, "PERIOD_UNCERTAIN_OR_MISSING", severity
    if not isinstance(data, dict):
        return True, "PERIOD_UNCERTAIN_OR_MISSING", severity
    if data.get("status") == "CONFLICT":
        return True, "PERIOD_CONFLICT", severity
    period = data.get("period")
    if (data.get("version") != 1 or data.get("status") != "READABLE"
            or not isinstance(period, list) or len(period) != 2
            or not all(isinstance(value, str) and len(value) == 7 for value in period)):
        return True, "PERIOD_UNCERTAIN_OR_MISSING", severity
    try:
        if any(date.fromisoformat(value + "-01").strftime("%Y-%m") != value for value in period) or period[0] > period[1]:
            return True, "PERIOD_UNCERTAIN_OR_MISSING", severity
    except ValueError:
        return True, "PERIOD_UNCERTAIN_OR_MISSING", severity
    if any(not period[0] <= month <= period[1] for month in requirement.premium_months):
        return True, "QUERY_RANGE_MISSING_REQUIRED_MONTHS", severity
    if data.get("amounts_certain") is True:
        absent, uncertain = data.get("absent_amount_months"), data.get("uncertain_absent_amount_months")
        if (not isinstance(absent, list) or not isinstance(uncertain, list)
                or not all(isinstance(value, str) for value in absent + uncertain)):
            return True, "AMOUNT_EVIDENCE_INVALID", severity
        if any(month in absent for month in requirement.premium_months):
            return True, "CONFIRMED_AMOUNT_MONTHS_MISSING", severity
        if any(month in uncertain for month in requirement.premium_months):
            return True, "AMOUNT_ABSENCE_UNCERTAIN", severity
    # Production continues into the monthly-map fallback even with a readable
    # independent period. This is distinct from losing printed month anchors.
    return True, "MONTHLY_MAP_MISSING_OR_UNREADABLE", severity


def diagnose(pairs, labels):
    """Observe original payment helpers; never substitute extraction algorithms."""
    from ..extractors import nhis_payment as legacy, nhis_payment_gov as gov, nhis_common as common
    from ..pipeline.layout import line_text, squash
    from ..schemas.models import DocType as V2Type
    from demo.backend.ocr import localocr
    from demo.backend.rules.doc_types import DocType
    from demo.backend.rules.doc_check import _check_billing_months
    from demo.backend.tools.verify_upload import SAFE_VALIDATIONS

    result = _not_run()
    names = set()
    recognizing = [False]
    original_clusters = gov._header_clusters
    original_columns = gov._header_columns
    original_recognizes = gov.recognizes
    original_table = gov._monthly_table
    original_legacy = legacy._extract_monthly
    original_hits = common.label_hits

    def observe_clusters(words):
        clusters = original_clusters(words)
        if recognizing[0]:
            result["header_group_count"] = len(clusters)
            result["header_groups_matched"] = matched(clusters)
            result["header_count_scope"] = "GOVERNMENT_RECOGNITION"
            remember(clusters)
        return clusters

    def remember(clusters):
        for cluster in clusters:
            value = squash("".join(line_text(row) for row in common.group_lines(cluster, tol=.25)))
            if value in labels:
                names.add(value)

    def matched(clusters):
        values = [squash("".join(line_text(row) for row in common.group_lines(cluster, tol=.25)))
                  for cluster in clusters]
        return _matched_headers(values, gov.HEADERS)

    def observe_columns(words, expected=gov.HEADERS):
        clusters = original_clusters(words)
        remember(clusters)
        if expected == gov.HEADERS:
            result["header_group_count"] = len(clusters)
            result["header_groups_matched"] = matched(clusters)
            result["header_count_scope"] = "GOVERNMENT_TABLE"
        return original_columns(words, expected)

    def observe_recognizes(pages):
        recognizing[0] = True
        try:
            return original_recognizes(pages)
        finally:
            recognizing[0] = False

    def observe_table(lines, *, allow_correction, metadata_bottom):
        result["month_count"] = sum(
            bool(gov.MONTH.fullmatch(squash(word.text)))
            for row in lines for word in row if word.y0 > metadata_bottom)
        result["month_count_scope"] = "GOVERNMENT_TABLE"
        return original_table(lines, allow_correction=allow_correction, metadata_bottom=metadata_bottom)

    def observe_legacy(pages):
        parsed = original_legacy(pages)
        result["month_count"] = len(parsed[11])
        result["month_count_scope"] = "LEGACY_TABLE"
        return parsed

    def observe_hits(lines, aliases):
        hits = original_hits(lines, aliases)
        for label, words in hits:
            if label in labels and squash("".join(word.text for word in words)) == squash(label):
                names.add(label)
        return hits

    with ExitStack() as stack:
        for module, name, wrapper in ((gov, "_header_clusters", observe_clusters),
                                      (gov, "_header_columns", observe_columns),
                                      (gov, "recognizes", observe_recognizes),
                                      (gov, "_monthly_table", observe_table),
                                      (legacy, "_extract_monthly", observe_legacy),
                                      (common, "label_hits", observe_hits)):
            stack.enter_context(patch.object(module, name, wrapper))
        extraction = legacy.extract(pairs)
    converted = localocr._from_nhis(extraction, pairs, V2Type, detected_override=DocType.NHIS_PAYMENT)
    requirement = batch._requirement("NHIS_PAYMENT")
    if requirement is None:
        raise ValueError("DIAGNOSTIC_REQUIREMENT_UNAVAILABLE")
    findings = _check_billing_months(converted, requirement)
    missing, cause, severity = _billing_cause(converted, requirement, findings)
    failed = sorted({check.name if check.name in SAFE_VALIDATIONS else "UNKNOWN_VALIDATION"
                     for check in extraction.validations if not check.passed})
    table_check = next((check.passed for check in extraction.validations
                        if check.name == "monthly_rows_found"), None)
    result.update(state="OK", reader="government_payment" if extraction.form_kind == "government_payment" else "legacy_payment",
                  recognized_headers=sorted(names), table_months_missing=not table_check if table_check is not None else None,
                  failed_validations=failed, missing_billing_months=missing,
                  billing_cause=cause, billing_severity=severity)
    return result


def _partial_text(path):
    import pymupdf
    from ..pipeline.ocr import OcrResult, OcrWord
    results = []
    with pymupdf.open(path) as document:
        for page in document:
            words = [OcrWord(item[4], 1.0, tuple(n * 300 / 72 for n in item[:4]))
                     for item in page.get_text("words", sort=True) if item[4].strip()]
            results.append(OcrResult("text_layer", words))
    return results


def build(path):
    """Build a safe report inside an existing processing guard."""
    pages, reference, _ = batch._inspect(path)
    if path.suffix.lower() == ".pdf" and reference is None:
        reference = _partial_text(path)
    labels = label_vocabulary()
    report = {"schema_version": 1, "masking_policy": "nhis_payment_exact_constants_v1",
              "page_count": len(pages), "engines": {}}
    errors = False
    for engine in ENGINES:
        records, pairs = [], []
        for index, page in enumerate(pages):
            if engine == "text_layer" and (reference is None or not reference[index].words):
                records.append(_page(page, "NOT_APPLICABLE", "TEXT_LAYER_ABSENT"))
                continue
            try:
                recognized = reference[index] if engine == "text_layer" else batch._recognize(engine, page)
                if recognized.error:
                    raise ValueError("OCR_ERROR")
                words = [_word(word, position, labels) for position, word in enumerate(recognized.words)]
                records.append(_page(page, words=words))
                pairs.append((page, recognized))
            except Exception as exc:
                optional = engine == "applevision" and isinstance(exc, (ImportError, NotImplementedError))
                records.append(_page(page, "SKIPPED" if optional else "ERROR",
                                     "ENGINE_UNAVAILABLE" if optional else "ENGINE_OR_WORD_ERROR"))
                errors |= not optional
        if len(pairs) == len(pages):
            try:
                diagnostic = diagnose(pairs, labels)
            except Exception:
                diagnostic = _not_run("ERROR", "DIAGNOSTIC_ERROR")
                errors = True
        else:
            diagnostic = _not_run(code="INCOMPLETE_ENGINE_PAGES")
        report["engines"][engine] = {"pages": records, "diagnostics": diagnostic}
    return report, errors


def _protected_target(path, source):
    actual = batch._target(path)
    if actual == source or actual.exists() and os.path.samefile(actual, source):
        raise ValueError("OUTPUT_SOURCE_ALIAS")
    return actual


def run(source, output):
    """Only fixed status/counts reach the console; no exception is rendered."""
    try:
        source = Path(source).resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in batch.EXTENSIONS:
            raise ValueError("INPUT_UNAVAILABLE")
        requested = Path(output)
        actual = _protected_target(requested, source)
        if not actual.parent.is_dir():
            raise ValueError("OUTPUT_PARENT_UNAVAILABLE")
        with batch.guarded():
            report, errors = build(source)
        if _protected_target(requested, source) != actual:
            raise ValueError("OUTPUT_CHANGED")
        batch._atomic(actual, report)
        print(json.dumps({"ok": not errors, "pages": report["page_count"],
                          "engines": len(ENGINES)}, separators=(",", ":")))
        return 1 if errors else 0
    except KeyboardInterrupt:
        print('{"ok":false,"code":"INTERRUPTED"}')
        return 130
    except Exception:
        print('{"ok":false,"code":"STRUCTURE_DUMP_FAILED"}')
        return 2
