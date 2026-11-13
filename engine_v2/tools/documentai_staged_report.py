"""Numeric aggregation for paired text-reference/own synthetic measurements.

Uncalled extractors are an explicit outcome, never field errors or accuracy
opportunities. Authored case groups and expectations determine verdict-rate
populations before the observed verdict is examined.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math

from .documentai_bench import DOCS, FIELD_NAMES, REUPLOAD_CODES

GROUPS = ("normal_baseline", "stress", "quality_defect", "content_defect")
CONDITIONS = (
    "original", "monochrome", "rotate_plus5", "rotate_minus5", "rotate90", "low_resolution", "phone",
    "layout_variant", "issued_too_early", "issued_after_application", "identity_mismatch", "pages_incomplete",
    "wrong_document_type", "missing_address_dates", "missing_billing_months", "defect_low_resolution",
    "low_image_quality", "unreadable_file",
)
STAGES = ("reference", "own")
STATES = frozenset({"MATCH", "MISMATCH", "MISSING", "UNEXTRACTED_CLASSIFICATION", "ERROR"})
ATTRIBUTIONS = (
    "reference_classification_errors", "own_classification_errors", "ocr_classification_losses",
    "classification_recoveries", "reference_field_errors", "own_field_errors", "reference_unextracted",
    "own_unextracted", "ocr_field_losses", "ocr_unextracted", "field_recoveries", "field_error_delta",
    "classification_error_delta", "reference_execution_errors", "own_execution_errors", "paired_execution_complete",
    "reference_raw_field_errors", "own_raw_field_errors", "ocr_raw_field_losses", "ocr_raw_unextracted",
    "raw_field_recoveries", "raw_field_error_delta",
)


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("invalid metric count")
    return value


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid metric number")
    return value


def _rate(numerator, denominator):
    return numerator / denominator if denominator else None


def _validate_rows(rows):
    for row in rows:
        if row.get("doc") not in DOCS or row.get("condition") not in CONDITIONS or row.get("group") not in GROUPS:
            raise ValueError("invalid metric identifier")
        if row.get("expected") not in {"VALID", "FAIL"}:
            raise ValueError("invalid expected class")
        for stage in STAGES:
            result = row[stage]
            if result.get("failed") not in {"O", "X"} or result.get("type_match") not in {"O", "X"}:
                raise ValueError("invalid stage marker")
            if result.get("status") not in {"PASS", "FAIL", "NEEDS_REVIEW", "X"}:
                raise ValueError("invalid verdict")
            if result.get("extractor_invoked") not in {"O", "X"}:
                raise ValueError("invalid invocation marker")
            if not set(result["fields"]) <= set(FIELD_NAMES[row["doc"]]):
                raise ValueError("invalid field identifier")
            if not set(result.get("confirmed_reupload_codes", [])) <= REUPLOAD_CODES:
                raise ValueError("invalid code identifier")
            for metric in result["fields"].values():
                if metric.get("state") not in STATES:
                    raise ValueError("invalid field state")
                if metric["state"] not in {"UNEXTRACTED_CLASSIFICATION", "ERROR"}:
                    for prefix in ("raw", "normalized"):
                        if metric.get(prefix + "_match") not in {"O", "X"}:
                            raise ValueError("invalid exact marker")
                        _count(metric[prefix + "_edits"])
                        _count(metric[prefix + "_reference_chars"])
            _count(result["pages"])
            _number(result["seconds"])
        for key, value in row.get("attribution", {}).items():
            if key not in ATTRIBUTIONS or type(value) is not int or (value < 0 and not key.endswith("_delta")):
                raise ValueError("invalid attribution")


def _field_summary(metrics):
    result = {
        "possible": len(metrics), "called": 0, "unextracted": 0, "errors": 0, "missing": 0,
        "raw_correct": 0, "normalized_correct": 0, "raw_edits": 0, "raw_reference_chars": 0,
        "normalized_edits": 0, "normalized_reference_chars": 0, "format_only": 0,
    }
    for metric in metrics:
        state = metric["state"]
        if state == "UNEXTRACTED_CLASSIFICATION":
            result["unextracted"] += 1
            continue
        if state == "ERROR":
            result["errors"] += 1
            continue
        result["called"] += 1
        result["missing"] += state == "MISSING"
        result["raw_correct"] += metric["raw_match"] == "O"
        result["normalized_correct"] += metric["normalized_match"] == "O"
        result["format_only"] += metric["raw_match"] == "X" and metric["normalized_match"] == "O"
        for key in ("raw_edits", "raw_reference_chars", "normalized_edits", "normalized_reference_chars"):
            result[key] += metric[key]
    result["raw_accuracy"] = _rate(result["raw_correct"], result["called"])
    result["normalized_accuracy"] = _rate(result["normalized_correct"], result["called"])
    result["raw_cer"] = result["raw_edits"] / max(result["raw_reference_chars"], 1) if result["called"] else None
    result["normalized_cer"] = result["normalized_edits"] / max(result["normalized_reference_chars"], 1) if result["called"] else None
    result["raw_wrong"] = result["called"] - result["raw_correct"]
    result["normalized_wrong"] = result["called"] - result["normalized_correct"]
    result["extracted_coverage"] = _rate(result["called"] - result["missing"], result["possible"])
    # Coverage has an all-authored-fields denominator; it is not field accuracy.
    result["normalized_correct_coverage"] = _rate(result["normalized_correct"], result["possible"])
    return result


def _stage_summary(rows, stage):
    data = [row[stage] for row in rows]
    fields = defaultdict(list)
    for result in data:
        for field, metric in result["fields"].items():
            fields[field].append(metric)
    field_totals = _field_summary([metric for result in data for metric in result["fields"].values()])
    valid_rows = [row for row in rows if row["expected"] == "VALID"]
    defect_rows = [row for row in rows if row["expected"] == "FAIL"]
    wrong_fail_codes = Counter(
        code for row in valid_rows if row[stage]["status"] == "FAIL"
        for code in set(row[stage].get("confirmed_reupload_codes", []))
    )
    wrong_fail = sum(row[stage]["status"] == "FAIL" and bool(row[stage].get("confirmed_reupload_codes"))
                     for row in valid_rows)
    false_pass = sum(row[stage]["status"] == "PASS" for row in defect_rows)
    all_codes = Counter(code for result in data if result["status"] == "FAIL"
                        for code in set(result.get("confirmed_reupload_codes", [])))
    pages = sum(result["pages"] for result in data)
    seconds = sum(result["seconds"] for result in data)
    page_seconds = sum(result["seconds"] for result in data if result["pages"] > 0)
    nonpage_seconds = sum(result["seconds"] for result in data if result["pages"] == 0)
    nonpage_attempts = sum(result["pages"] == 0 for result in data)
    return {
        "attempted": len(rows), "completed": sum(result["failed"] == "X" for result in data),
        "failed": sum(result["failed"] == "O" for result in data),
        "type_correct": sum(result["type_match"] == "O" for result in data),
        "type_accuracy": _rate(sum(result["type_match"] == "O" for result in data), len(rows)),
        "extractor_invoked": sum(result["extractor_invoked"] == "O" for result in data),
        "field_totals": field_totals, "fields": {field: _field_summary(values) for field, values in sorted(fields.items())},
        "valid_count": len(valid_rows), "expected_fail_count": len(defect_rows),
        "false_reject_count": wrong_fail, "false_reject_rate": _rate(wrong_fail, len(valid_rows)),
        "false_reject_codes": dict(sorted(wrong_fail_codes.items())),
        "false_accept_count": false_pass, "false_accept_rate": _rate(false_pass, len(defect_rows)),
        "confirmed_code_counts": dict(sorted(all_codes.items())),
        "status_counts": dict(sorted(Counter(result["status"] for result in data).items())),
        "pages": pages, "seconds": seconds, "page_seconds": page_seconds,
        "nonpage_seconds": nonpage_seconds, "nonpage_attempts": nonpage_attempts,
        "seconds_per_page": page_seconds / pages if pages else None,
        "ocr_chars": sum(_count(result.get("ocr_chars", 0)) for result in data),
        "ocr_words": sum(_count(result.get("ocr_words", 0)) for result in data),
    }



def _opportunity_changes(rows):
    """Decompose normalized error deltas while called opportunities change.

    Only completed stage pairs contribute. Classification-gated outcomes remain
    unavailable rather than errors, but a recovery can expose a newly-called
    wrong field and a loss can hide a formerly visible wrong field.
    """
    counts = {
        "complete_pairs": 0, "skipped_pairs": 0, "comparable_fields": 0, "unpaired_fields": 0,
        "newly_called_field_errors": 0, "newly_called_field_correct": 0,
        "hidden_reference_field_errors": 0, "shared_field_errors": 0, "both_unextracted": 0,
        "reference_field_errors": 0, "own_field_errors": 0,
        "ocr_field_losses": 0, "field_recoveries": 0,
    }
    called_states = {"MATCH", "MISMATCH", "MISSING"}
    for row in rows:
        a, b = row["reference"], row["own"]
        if a["failed"] != "X" or b["failed"] != "X":
            counts["skipped_pairs"] += 1
            continue
        counts["complete_pairs"] += 1
        a_fields, b_fields = a["fields"], b["fields"]
        counts["unpaired_fields"] += len(a_fields.keys() ^ b_fields.keys())
        for field in a_fields.keys() & b_fields.keys():
            am, bm = a_fields[field], b_fields[field]
            if am["state"] == "ERROR" or bm["state"] == "ERROR":
                counts["unpaired_fields"] += 1
                continue
            counts["comparable_fields"] += 1
            a_uncalled = am["state"] == "UNEXTRACTED_CLASSIFICATION"
            b_uncalled = bm["state"] == "UNEXTRACTED_CLASSIFICATION"
            a_wrong = am["state"] in called_states and am["normalized_match"] == "X"
            b_wrong = bm["state"] in called_states and bm["normalized_match"] == "X"
            a_correct = am["state"] in called_states and am["normalized_match"] == "O"
            b_correct = bm["state"] in called_states and bm["normalized_match"] == "O"
            counts["reference_field_errors"] += a_wrong
            counts["own_field_errors"] += b_wrong
            counts["newly_called_field_errors"] += a_uncalled and b_wrong
            counts["newly_called_field_correct"] += a_uncalled and b_correct
            counts["hidden_reference_field_errors"] += a_wrong and b_uncalled
            counts["shared_field_errors"] += a_wrong and b_wrong
            counts["both_unextracted"] += a_uncalled and b_uncalled
            counts["ocr_field_losses"] += a_correct and b_wrong
            counts["field_recoveries"] += a_wrong and b_correct
    counts["field_error_delta"] = counts["own_field_errors"] - counts["reference_field_errors"]
    counts["reconstructed_field_error_delta"] = (counts["ocr_field_losses"] + counts["newly_called_field_errors"]
                                                 - counts["field_recoveries"] - counts["hidden_reference_field_errors"])
    return counts

def _aggregate(rows):
    return {
        "attempted": len(rows),
        "group_counts": dict(sorted(Counter(row["group"] for row in rows).items())),
        "expected_counts": dict(sorted(Counter(row["expected"] for row in rows).items())),
        "reference": _stage_summary(rows, "reference"), "own": _stage_summary(rows, "own"),
        "attribution": {key: sum(row.get("attribution", {}).get(key, 0) for row in rows) for key in ATTRIBUTIONS},
        "opportunity_changes": _opportunity_changes(rows),
    }


def summarize(rows):
    """Aggregate fixed identifiers only; never serialize extraction values."""
    rows = list(rows)
    _validate_rows(rows)
    conditions = [condition for condition in CONDITIONS if any(row["condition"] == condition for row in rows)]
    by_cell = {doc: {condition: _aggregate([row for row in rows if row["doc"] == doc and row["condition"] == condition])
                     for condition in conditions if any(row["doc"] == doc and row["condition"] == condition for row in rows)}
               for doc in DOCS if any(row["doc"] == doc for row in rows)}
    by_document = {doc: _aggregate([row for row in rows if row["doc"] == doc]) for doc in by_cell}
    return {
        "overall": _aggregate(rows),
        "by_group": {group: _aggregate([row for row in rows if row["group"] == group]) for group in GROUPS},
        "by_document": by_document,
        "by_document_group": {doc: {group: _aggregate([row for row in rows if row["doc"] == doc and row["group"] == group])
                                     for group in GROUPS} for doc in by_cell},
        "by_condition": {condition: _aggregate([row for row in rows if row["condition"] == condition]) for condition in conditions},
        "by_cell": by_cell,
        "by_field": {doc: {stage: group[stage]["fields"] for stage in STAGES} for doc, group in by_document.items()},
    }


def _pct(value):
    return "N/A" if value is None else f"{100 * value:.2f}%"


def _num(value):
    return "N/A" if value is None else f"{value:.4f}"


def _accuracy(stage):
    f = stage["field_totals"]
    return f"{f['raw_correct']}/{f['called']} ({_pct(f['raw_accuracy'])}) / {f['normalized_correct']}/{f['called']} ({_pct(f['normalized_accuracy'])})"


def _verdict_rate(stage, kind):
    numerator = stage["false_reject_count"] if kind == "reject" else stage["false_accept_count"]
    denominator = stage["valid_count"] if kind == "reject" else stage["expected_fail_count"]
    return f"{numerator}/{denominator} ({_pct(_rate(numerator, denominator))})"


def _table(lines, header, rows):
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    lines.append("")


def markdown(report):
    """Render paired stages, complete field cells, causal limits and weak groups."""
    summary = report["summary"]
    lines = [
        "# DocumentAI paired-stage synthetic measurement v2", "",
        f"Seed: {report['seed']}; distinct samples per type/condition: {report['samples']}; actual case count: {summary['overall']['attempted']}.", "",
        "A = exact generated text-layer words mapped into the same image geometry and fed through the unchanged image reader; B = actual own OCR of that image. Both classify independently and use the same policy, metadata and production extraction/verdict path. A uses perfect recognition/confidence, while B contributes recognition, segmentation, boxes and confidence effects. The difference is a paired operational attribution, not a glyph-only causal experiment.", "",
        "No original layout was repaired without evidence: ambiguous purpose/title proximity and payment table layout remain, with their failures visible in A. A reference-stage failure is a baseline classification/extraction/source interaction, not an OCR error. No real document or production OCR/classifier/extractor/verdict code was changed. The old report is retained.", "",
        "Field accuracy is conditional on the expected source-type extractor being called. Called-but-missing fields are errors; UNEXTRACTED_CLASSIFICATION and ERROR are separate outcomes and are excluded from field-accuracy/CER denominators. Raw and normalized exact figures are both shown. Correct-field coverage uses all authored fields and is explicitly not called field accuracy.", "",
        "Raw CER compares literal semantic-value streams. Normalized CER compares field-aware canonical streams; fixed JSON keys/punctuation and insurance geometry/confidence are excluded. CER is summed edits / max(reference characters, 1), not the mean of field ratios. Empty fields and absent fields remain distinct. List order and identifier zeros are preserved.", "",
        "Case group and expected VALID/FAIL are authored before observing results. expected=FAIL identifies a negative/defective cohort where PASS is forbidden, not an assertion that every content defect must produce final FAIL: production review policies remain valid and visible. Quality-defect inputs specifically have designed FAIL as the desired quality outcome. Normal baseline, stress, quality defects and content defects have separate verdict populations. Confirmed false rejection requires final FAIL plus an allowlisted FAIL-severity reupload code on expected VALID. False acceptance is PASS on expected FAIL. NEEDS_REVIEW is neither. N/A means no applicable denominator. A low false-accept rate with many reviews is not automatic defect diagnosis.", "",
        "Timing is processing seconds for physical-page inputs / processed input pages, excluding source generation and metric/report calculations. Total seconds retain all attempts; nonpage attempts and their seconds are accounted separately and cannot enter the per-page numerator. A performs no model inference; B does. Cold initialization may affect the first own page. Malformed input bytes have no physical page throughput interpretation and are shown separately from normal/stress timing.", "",
        "## Case groups and verdict rates", "",
    ]
    rows = []
    for group, data in summary["by_group"].items():
        for stage in STAGES:
            g = data[stage]; f = g["field_totals"]
            status = g["status_counts"]
            rows.append((group, "A" if stage == "reference" else "B", g["attempted"],
                         f"{g['type_correct']}/{g['attempted']} ({_pct(g['type_accuracy'])})", _accuracy(g),
                         f["unextracted"], f["errors"], g["failed"],
                         f"{g['nonpage_attempts']}/{_num(g['nonpage_seconds'])}", _verdict_rate(g, "reject"), _verdict_rate(g, "accept"),
                         f"{status.get('PASS',0)}/{status.get('NEEDS_REVIEW',0)}/{status.get('FAIL',0)}/{status.get('X',0)}",
                         _num(g["seconds_per_page"])))
    _table(lines, ("Group", "Stage", "n", "Type", "Raw / normalized exact", "Unextracted", "Error fields", "Failed cases", "Nonpage attempts/seconds", "False reject", "False pass", "PASS/review/FAIL/X", "s/page"), rows)
    lines += ["## Original normal baseline by document", ""]
    rows = []
    for doc, groups in summary["by_document_group"].items():
        data = groups["normal_baseline"]
        for stage in STAGES:
            g = data[stage]; f = g["field_totals"]
            rows.append((doc, "A" if stage == "reference" else "B", g["attempted"],
                         f"{g['type_correct']}/{g['attempted']}", _accuracy(g),
                         f"{_num(f['raw_cer'])} / {_num(f['normalized_cer'])}",
                         f"{f['called']}/{f['possible']}", f["unextracted"], _num(g["seconds_per_page"])))
    _table(lines, ("Type", "Stage", "n", "Type correct", "Raw / normalized exact", "Raw / normalized CER", "Called/possible fields", "Unextracted", "s/page"), rows)
    lines += ["## Classification/extraction versus OCR contribution by document", "",
              "This attribution table covers expected-valid normal baseline and stress groups only. Deliberately unreadable/defective inputs are excluded from weakness attribution; their raw paired counts remain in JSON and their stage outcomes remain in the full tables. Reference field errors are A-called fields whose value is wrong or missing; raw/normalized counts are displayed together. Reference unextracted fields are A classification-gated outcomes. OCR field losses require an A-correct field and a B-called wrong/missing field. OCR unextracted losses require an A-correct field and B classification-gated extraction. Recoveries are shown separately; simple signed error differences must not be treated as total introduced errors.", ""]
    rows = []
    for doc, groups in summary["by_document_group"].items():
        for group, data in groups.items():
            if group not in {"normal_baseline", "stress"}:
                continue
            a = data["attribution"]
            rows.append((doc, group, data["attempted"], a["reference_classification_errors"], f"{a['reference_raw_field_errors']}/{a['reference_field_errors']}",
                         a["reference_unextracted"], a["ocr_classification_losses"], f"{a['ocr_raw_field_losses']}/{a['ocr_field_losses']}",
                         f"{a['ocr_raw_unextracted']}/{a['ocr_unextracted']}", a["classification_recoveries"], f"{a['raw_field_recoveries']}/{a['field_recoveries']}",
                         a["classification_error_delta"], f"{a['raw_field_error_delta']}/{a['field_error_delta']}"))
    _table(lines, ("Type", "Group", "n", "A type errors", "A field errors raw/norm", "A unextracted", "OCR type losses", "OCR field losses raw/norm", "OCR unextracted raw/norm", "Type recoveries", "Field recoveries raw/norm", "B−A type errors", "B−A field errors raw/norm"), rows)
    lines += ["## Field opportunity-change decomposition", "",
              "Normalized counts below use completed shared-field pairs in baseline/stress only. Newly called errors arise when A was classification-gated and B invokes the extractor but emits a wrong/missing field. Hidden A errors arise when an A-called wrong field becomes classification-gated in B. These opportunity changes explain why introduced OCR field losses alone do not equal the signed error delta. Newly called correct fields and shared errors are shown separately; none of the unextracted outcomes becomes a field error.", "",
              "Identity: B field errors − A field errors = OCR field losses + newly called field errors − field recoveries − hidden A field errors. It reconciles these completed shared-field pairs; execution/unpaired exclusions are retained in the numeric summary.", ""]
    rows = []
    for doc, groups in summary["by_document_group"].items():
        for group, data in groups.items():
            if group not in {"normal_baseline", "stress"}:
                continue
            o = data["opportunity_changes"]
            rows.append((doc, group, o["reference_field_errors"], o["own_field_errors"], o["ocr_field_losses"],
                         o["newly_called_field_errors"], o["newly_called_field_correct"], o["field_recoveries"],
                         o["hidden_reference_field_errors"], o["shared_field_errors"], o["both_unextracted"],
                         o["field_error_delta"], o["reconstructed_field_error_delta"]))
    _table(lines, ("Type", "Group", "A errors", "B errors", "OCR field losses", "Newly called wrong", "Newly called correct",
                   "Field recoveries", "A errors hidden by B gating", "Shared errors", "Both unextracted", "B−A errors", "Reconstructed delta"), rows)
    lines += ["## Complete type × condition comparison", ""]
    rows = []
    for doc, cells in summary["by_cell"].items():
        for condition, data in cells.items():
            a, b = data["reference"], data["own"]
            af, bf = a["field_totals"], b["field_totals"]
            rows.append((doc, condition, "/".join(data["group_counts"]), data["attempted"], f"{a['type_correct']}/{a['attempted']}", f"{b['type_correct']}/{b['attempted']}",
                         _accuracy(a), _accuracy(b), f"{_num(af['raw_cer'])}/{_num(af['normalized_cer'])}",
                         f"{_num(bf['raw_cer'])}/{_num(bf['normalized_cer'])}", f"{af['unextracted']}/{bf['unextracted']}",
                         f"{_verdict_rate(a, 'reject')} / {_verdict_rate(b, 'reject')}",
                         f"{_verdict_rate(a, 'accept')} / {_verdict_rate(b, 'accept')}",
                         f"{_num(a['seconds_per_page'])}/{_num(b['seconds_per_page'])}"))
    _table(lines, ("Type", "Condition", "Group", "n", "A type", "B type", "A raw / norm exact", "B raw / norm exact", "A raw/norm CER", "B raw/norm CER", "A/B unextracted", "A/B false reject", "A/B false pass", "A/B s/page"), rows)
    lines += ["## Complete field × type × condition metrics", ""]
    rows = []
    for doc, cells in summary["by_cell"].items():
        for condition, data in cells.items():
            fields = sorted(set(data["reference"]["fields"]) | set(data["own"]["fields"]))
            for field in fields:
                a = data["reference"]["fields"][field]; b = data["own"]["fields"][field]
                rows.append((doc, condition, field, f"{a['raw_correct']}/{a['called']}", f"{a['normalized_correct']}/{a['called']}",
                             f"{b['raw_correct']}/{b['called']}", f"{b['normalized_correct']}/{b['called']}",
                             f"{_num(a['raw_cer'])}/{_num(a['normalized_cer'])}", f"{_num(b['raw_cer'])}/{_num(b['normalized_cer'])}",
                             f"{a['unextracted']}/{b['unextracted']}", f"{a['missing']}/{b['missing']}"))
    _table(lines, ("Type", "Condition", "Field", "A raw", "A norm", "B raw", "B norm", "A raw/norm CER", "B raw/norm CER", "A/B unextracted", "A/B missing after call"), rows)
    lines += ["## Reupload codes by group", "", "All ten requested codes are shown, including zeros. A document can contribute to more than one code count.", ""]
    rows = []
    for group, data in summary["by_group"].items():
        for code in sorted(REUPLOAD_CODES):
            rows.append((group, code, data["reference"]["false_reject_codes"].get(code, 0),
                         data["own"]["false_reject_codes"].get(code, 0),
                         data["reference"]["confirmed_code_counts"].get(code, 0),
                         data["own"]["confirmed_code_counts"].get(code, 0)))
    _table(lines, ("Group", "Code", "A wrong FAIL", "B wrong FAIL", "A all confirmed", "B all confirmed"), rows)
    lines += ["## Weakest diagnostic groups", "",
              "Rankings exclude deliberately defective cases and keep baseline and stress document views separate. They keep conditional field accuracy, field coverage and independent type accuracy separate. An uncalled extractor is ranked by classification/coverage, not assigned 0% conditional field accuracy.", ""]
    document_rankings = [(doc + " / " + group, data)
                         for doc, groups in summary["by_document_group"].items()
                         for group, data in groups.items() if group in {"normal_baseline", "stress"} and data["attempted"]]
    condition_rankings = [(condition, data) for condition, data in summary["by_condition"].items()
                          if data["own"]["valid_count"]]
    for groups, title in ((document_rankings, "Document types (baseline and stress kept separate)"),
                          (condition_rankings, "Expected-valid conditions only")):
        lines += [f"### {title}", ""]
        groups.sort(key=lambda item: (item[1]["own"]["type_accuracy"] if item[1]["own"]["type_accuracy"] is not None else 1,
                                      item[1]["own"]["field_totals"]["normalized_correct_coverage"] or 0,
                                      item[0]))
        _table(lines, ("Group", "n", "B type accuracy", "B conditional raw/norm exact", "B correct coverage", "B unextracted"),
               [(label, g["attempted"], _pct(g["own"]["type_accuracy"]), _accuracy(g["own"]),
                 _pct(g["own"]["field_totals"]["normalized_correct_coverage"]), g["own"]["field_totals"]["unextracted"])
                for label, g in groups[:8]])
    lines += ["### Fields (called opportunities only)", ""]
    fields = [(doc, group, field, metric) for doc, groups in summary["by_document_group"].items()
              for group, data in groups.items() if group in {"normal_baseline", "stress"}
              for field, metric in data["own"]["fields"].items() if metric["called"]]
    fields.sort(key=lambda item: (item[3]["normalized_accuracy"], -(item[3]["normalized_cer"] or 0), item[0], item[1], item[2]))
    _table(lines, ("Type", "Group", "Field", "Raw correct/called", "Normalized correct/called", "Normalized CER", "Unextracted"),
           [(doc, group, field, f"{m['raw_correct']}/{m['called']}", f"{m['normalized_correct']}/{m['called']}",
             _num(m["normalized_cer"]), m["unextracted"]) for doc, group, field, m in fields[:15]])
    lines += ["## Source decisions and interpretation", "",
              "Five samples are different fictitious identity/date parameter sets; they share source layout/font families. They are not five independent issuer templates and do not establish real-document population accuracy. Purpose marks and ambiguous source/table layouts are retained in baseline and stress runs. Stage A exposes those interactions without modifying operational recognition.", "",
              "No improvement to OCR, classification, extraction or decision logic was implemented. Candidate work must first distinguish A-baseline failures from A-correct/B-lost fields, then inspect template/geometry/segmentation evidence. Quality FAIL on deliberately undersized originals is expected and cannot enter normal false-rejection rates. More review outcomes do not establish correct automatic detection.", ""]
    evidence = report.get("source_changes", [])
    if not isinstance(evidence, (tuple, list)) or any(not isinstance(item, str) for item in evidence):
        raise ValueError("invalid source evidence")
    if evidence:
        lines += ["### Source-change evidence", ""]
        lines.extend("- " + item for item in evidence)
        lines.append("")
    return "\n".join(lines)
