"""In-memory, symmetric field comparison and reference-only table geometry.

No document values or regions returned here may be persisted. Only the closed
numeric field comparison is an output projection. Imports are lazy so summary
mode does not load extraction or OCR dependencies.
"""
from __future__ import annotations

from copy import deepcopy
import math
import unicodedata
from unittest.mock import patch


FIELD_COUNTS = ("eligible", "match", "missing_reference", "ocr_cause",
                "structure_cause", "unattributable")


def normalize_words(words):
    """Use one idempotent NFKC/masking boundary for both extraction inputs.

    Whitespace remains available to production parsers. Field-specific whitespace,
    date and numeric normalization happens symmetrically after extraction.
    Original OCR/reference word objects are never mutated.
    """
    from engine_v2.pipeline.privacy import mask_words

    copied = deepcopy(list(words))
    for word in copied:
        word.text = unicodedata.normalize("NFKC", word.text)
    return mask_words(copied)


def prepare_pairs(page, words, engine):
    """Build the identical production word/result boundary on either side."""
    from engine_v2.pipeline.ocr import OcrResult

    return [(page, OcrResult(engine, normalize_words(words)))]


def _stream(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def _leaves(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _leaves(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _leaves(item)
    elif value is not None:
        text = _stream(str(value))
        if text:
            yield text


def _canonical_field(key, value):
    from engine_v2.pipeline.privacy import mask_data
    from engine_v2.tools.batch_assess import _semantic_field
    from engine_v2.tools.documentai_staged import canonicalize

    # The raw extractor projection is captured before reader finalization. It
    # therefore needs the same final masking on BOTH sides, even if the OCR
    # adapter masked words already. NFKC precedes masking for fullwidth digits.
    return mask_data(canonicalize(key, _semantic_field(key, value)))


def compare_fields(kind, ref_raw, obs_raw, observed_kind, reference_text="", observed_text=""):
    """Return only reviewed field keys and numeric comparison/attribution counts.

    Type disagreement remains a mismatch. A missing reference never enters the
    agreement denominator. Derived/nonliteral reference values are not assigned
    a made-up OCR/structure cause.
    """
    from engine_v2.pipeline.privacy import mask_rrn
    from engine_v2.tools.batch_assess import FIELDS, _present, _typed_equal

    reference_stream = mask_rrn(_stream(reference_text))
    observed_stream = mask_rrn(_stream(observed_text))
    metrics = {}
    for key in FIELDS.get(kind, ()):
        counts = dict.fromkeys(FIELD_COUNTS, 0)
        metrics[key] = counts
        if key not in ref_raw or not _present(ref_raw[key]):
            counts["missing_reference"] = 1
            continue
        expected = _canonical_field(key, ref_raw[key])
        counts["eligible"] = 1
        actual_present = key in obs_raw and _present(obs_raw[key])
        if observed_kind == kind and actual_present and _typed_equal(expected, _canonical_field(key, obs_raw[key])):
            counts["match"] = 1
            continue
        leaves = list(_leaves(expected))
        if not leaves or not all(leaf in reference_stream for leaf in leaves):
            counts["unattributable"] = 1
        elif all(leaf in observed_stream for leaf in leaves):
            counts["structure_cause"] = 1
        else:
            counts["ocr_cause"] = 1
    return metrics


def _bounds(words):
    if not words:
        return None
    box = (min(word.px[0] for word in words), min(word.px[1] for word in words),
           max(word.px[2] for word in words), max(word.px[3] for word in words))
    if not all(math.isfinite(value) for value in box) or box[0] >= box[2] or box[1] >= box[3]:
        return None
    return box


def _legacy_payment_region(page, result, lines):
    from engine_v2.extractors import nhis_payment as payment
    from engine_v2.extractors import nhis_common as common
    from engine_v2.pipeline.layout import line_text, squash

    pairs = [(page, result)]
    headers = payment._month_header(lines)
    if not headers or not payment._header_x(pairs, ("고지금액", "고지보험료")):
        return None
    parsed = payment._extract_monthly(pairs)
    monthly, row_words = parsed[0], parsed[12]
    if not monthly or not row_words:
        return None
    header_index = max(headers)  # Same last-header selection as _extract_monthly.
    block = payment._header_block(lines, header_index)
    # _header_block deliberately tolerates adjacent prose for extraction. Only
    # its exact matched header words establish the measurement rectangle.
    selected = [word for label, matched in common.label_hits(block, payment.TABLE_LABELS)
                if squash("".join(word.text for word in matched)) == squash(label)
                for word in matched]
    selected.extend(word for row in row_words.values() for word in row)
    last_month_y = max(word.cy for row in row_words.values() for word in row)
    for row in lines[header_index + 1:]:
        flat = squash(line_text(row))
        if "확인합니다" in flat or "국민건강보험공단" in flat:
            break
        if ("합계" in flat or "납부총액" in flat) and row[0].cy >= last_month_y:
            if payment._money_words(row):
                selected.extend(row)
            break
    return _bounds(selected)


def _government_payment_region(page, result, lines):
    from engine_v2.extractors import nhis_payment_gov as gov
    from engine_v2.pipeline.layout import line_text, squash
    from engine_v2.extractors.format_text import normalize_format_text
    import re

    group_labels = [word for label in gov.GROUPS for word in gov._unique_label(lines, label)]
    if not group_labels:
        return None
    table_top = min(word.y0 for word in group_labels)
    # Mirror the production metadata boundary; a date in the table cannot be
    # mistaken for a page-wide month-header candidate.
    period_rows = [row for row in lines if min(word.y0 for word in row) < table_top and
                   ("납부내역" in squash(line_text(row)) or re.search(
                       r"20\d{2}년\d{1,2}월[~～-]", normalize_format_text(squash(line_text(row)))))]
    metadata_bottom = max((word.y1 for row in period_rows for word in row), default=0)
    header_words = []
    column_boundaries = []
    original_headers, original_columns = gov._header_columns, gov.forms.table_columns

    def observe_headers(words, expected=gov.HEADERS):
        found = original_headers(words, expected=expected)
        if found is not None:
            header_words.extend(word for column in found for word in column)
        return found

    def observe_columns(*args, **kwargs):
        found = original_columns(*args, **kwargs)
        if found is not None:
            column_boundaries.append(found)
        return found

    # Delegation only: retain all production validation and argument behavior.
    with patch.object(gov, "_header_columns", observe_headers), patch.object(gov.forms, "table_columns", observe_columns):
        _, _, _, checks, _ = gov._monthly_table(lines, allow_correction=False, metadata_bottom=metadata_bottom)
    structural = {"payment_group_headers", "monthly_rows_found", "months_continuous",
                  "payment_component_headers", "payment_columns", "payment_sum_row"}
    passed = {check.name for check in checks if check.passed}
    if not structural <= passed or not column_boundaries or not header_words:
        return None
    words = [word for row in lines for word in row]
    months = [word for word in words if word.y0 > metadata_bottom and gov.MONTH.fullmatch(squash(word.text))]
    sums = gov._unique_label(lines, "합계")
    first_y = min(word.y0 for word in months)
    last_y = max(word.y1 for word in sums)
    left, right = column_boundaries[-1][0], column_boundaries[-1][-1]
    selected = header_words + [word for word in words if first_y <= word.cy <= last_y and
                               word.x1 >= left and word.x0 <= right]
    return _bounds(selected)


def table_region(kind, page, result):
    """Return a confirmed reference-only pixel region; never guess on OCR text.

    Caller supplies original text-layer words only. Resident output is a
    full-width table band; NHIS payment output is bounded by its production
    headers/month rows. None means unmeasured, never an empty-table score.
    """
    if kind not in {"NHIS_PAYMENT", "RESIDENT_ABSTRACT", "RESIDENT_CERTIFICATE"}:
        return None
    from engine_v2.extractors import nhis_common as common

    lines = common.page_lines(page, result)
    if not lines or not page.pixel_size:
        return None
    if kind == "NHIS_PAYMENT":
        from engine_v2.extractors import nhis_payment_gov as gov
        if gov.recognizes([(page, result)]):
            return _government_payment_region(page, result, lines)
        return _legacy_payment_region(page, result, lines)
    from engine_v2.extractors import resident_abstract

    band = resident_abstract._table_bounds(lines)
    if band is None:
        return None
    width, height = page.pixel_size
    return (0.0, band[0] / 100 * height, float(width), band[1] / 100 * height)
