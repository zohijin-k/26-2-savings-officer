"""Synthetic numeric tests for conditional paired-stage report denominators."""
import pytest

from engine_v2.tools import documentai_staged_report as reporting
from engine_v2.tools.documentai_staged import pair_metrics


def metric(state="MATCH", *, raw="O", normalized="O", edits=0, chars=4, norm_edits=None, norm_chars=None):
    unavailable = state in {"UNEXTRACTED_CLASSIFICATION", "ERROR"}
    return {
        "state": state, "raw_match": None if unavailable else raw,
        "normalized_match": None if unavailable else normalized,
        "raw_edits": None if unavailable else edits, "raw_reference_chars": None if unavailable else chars,
        "normalized_edits": None if unavailable else edits if norm_edits is None else norm_edits,
        "normalized_reference_chars": None if unavailable else chars if norm_chars is None else norm_chars,
    }


def stage(fields=None, *, kind="O", invoked="O", status="PASS", failed="X", codes=(), seconds=2, pages=1):
    return {"failed": failed, "type_match": kind, "status": status, "extractor_invoked": invoked,
            "confirmed_reupload_codes": list(codes), "seconds": seconds, "pages": pages,
            "fields": fields if fields is not None else {"성명": metric()}, "ocr_chars": 4, "ocr_words": 1}


def row(*, reference=None, own=None, condition="original", group="normal_baseline", expected="VALID"):
    a, b = reference or stage(), own or stage()
    return {"doc": "nhis_payment", "condition": condition, "group": group, "expected": expected,
            "reference": a, "own": b, "attribution": pair_metrics(a, b)}


def test_uncalled_fields_are_excluded_not_counted_as_wrong():
    a = stage({"성명": metric(), "생년월일": metric("MISSING", raw="X", normalized="X", edits=10, chars=10)})
    b = stage({"성명": metric("UNEXTRACTED_CLASSIFICATION"), "생년월일": metric("UNEXTRACTED_CLASSIFICATION")},
              kind="X", invoked="X", status="NEEDS_REVIEW")
    data = reporting.summarize([row(reference=a, own=b)])["overall"]
    assert data["reference"]["field_totals"]["called"] == 2
    assert data["reference"]["field_totals"]["normalized_accuracy"] == .5
    bf = data["own"]["field_totals"]
    assert bf["possible"] == 2 and bf["called"] == 0 and bf["unextracted"] == 2
    assert bf["normalized_wrong"] == 0 and bf["missing"] == 0
    assert bf["normalized_accuracy"] is None and bf["normalized_cer"] is None
    assert data["attribution"]["ocr_unextracted"] == 1
    assert data["attribution"]["reference_field_errors"] == 1
    assert data["attribution"]["own_field_errors"] == 0


def test_raw_and_normalized_match_counts_are_independent():
    own = stage({"성명": metric(raw="X", normalized="O", edits=2, chars=4, norm_edits=0, norm_chars=3)})
    data = reporting.summarize([row(own=own)])["overall"]["own"]["field_totals"]
    assert data["raw_correct"] == 0 and data["normalized_correct"] == 1
    assert data["raw_accuracy"] == 0 and data["normalized_accuracy"] == 1
    assert data["raw_cer"] == .5 and data["normalized_cer"] == 0
    assert data["format_only"] == 1


def test_cer_is_micro_averaged_and_empty_reference_insertions_survive():
    data = reporting.summarize([
        row(own=stage({"성명": metric("MISMATCH", raw="X", normalized="X", edits=1, chars=1)})),
        row(own=stage({"성명": metric("MISMATCH", raw="X", normalized="X", edits=1, chars=9)})),
        row(own=stage({"성명": metric("MISMATCH", raw="X", normalized="X", edits=2, chars=0)})),
    ])["overall"]["own"]
    assert data["field_totals"]["raw_cer"] == pytest.approx(.4)
    assert data["fields"]["성명"]["normalized_cer"] == pytest.approx(.4)


def test_quality_and_content_defects_have_own_false_pass_denominators():
    rows = [row(),
            row(condition="phone", group="stress", own=stage(status="FAIL", codes=["LOW_IMAGE_QUALITY"])),
            row(condition="low_resolution", group="quality_defect", expected="FAIL", own=stage(status="FAIL", codes=["LOW_IMAGE_QUALITY"])),
            row(condition="identity_mismatch", group="content_defect", expected="FAIL", own=stage()),
            row(condition="pages_incomplete", group="content_defect", expected="FAIL", own=stage(status="NEEDS_REVIEW"))]
    result = reporting.summarize(rows)
    normal = result["by_group"]["normal_baseline"]["own"]
    stress = result["by_group"]["stress"]["own"]
    quality = result["by_group"]["quality_defect"]["own"]
    defect = result["by_group"]["content_defect"]["own"]
    assert normal["false_reject_rate"] == 0 and normal["false_accept_rate"] is None
    assert stress["false_reject_count"] == 1 and stress["false_reject_rate"] == 1
    assert quality["valid_count"] == 0 and quality["false_reject_rate"] is None
    assert quality["false_accept_count"] == 0 and quality["false_accept_rate"] == 0
    assert quality["confirmed_code_counts"] == {"LOW_IMAGE_QUALITY": 1}
    assert defect["false_accept_count"] == 1 and defect["false_accept_rate"] == .5
    assert result["overall"]["own"]["false_reject_rate"] == .5
    assert result["overall"]["own"]["false_accept_rate"] == pytest.approx(1 / 3)


def test_codes_are_deduplicated_per_case_and_require_final_fail():
    fail = stage(status="FAIL", codes=["LOW_IMAGE_QUALITY", "LOW_IMAGE_QUALITY", "PAGES_INCOMPLETE"])
    review = stage(status="NEEDS_REVIEW", codes=["LOW_IMAGE_QUALITY"])
    result = reporting.summarize([row(own=fail), row(own=review)])["overall"]["own"]
    assert result["false_reject_count"] == 1
    assert result["false_reject_codes"] == {"LOW_IMAGE_QUALITY": 1, "PAGES_INCOMPLETE": 1}
    assert result["confirmed_code_counts"] == result["false_reject_codes"]


def test_paired_losses_and_recoveries_are_not_replaced_with_signed_delta():
    unavailable = stage({"성명": metric("UNEXTRACTED_CLASSIFICATION")}, kind="X", invoked="X", status="NEEDS_REVIEW")
    wrong = stage({"성명": metric("MISMATCH", raw="X", normalized="X", edits=1)})
    result = reporting.summarize([row(own=unavailable), row(reference=wrong)])["overall"]["attribution"]
    assert result["ocr_unextracted"] == 1
    assert result["ocr_classification_losses"] == 1
    assert result["field_recoveries"] == 1
    assert result["field_error_delta"] == -1
    assert result["classification_error_delta"] == 1


def test_execution_error_fields_do_not_poison_called_accuracy():
    error = stage({"성명": metric("ERROR")}, kind="X", invoked="X", failed="O", status="X", pages=0, seconds=1)
    result = reporting.summarize([row(own=error)])["overall"]["own"]
    assert result["attempted"] == 1 and result["failed"] == 1 and result["completed"] == 0
    assert result["field_totals"]["errors"] == 1
    assert result["field_totals"]["called"] == 0 and result["field_totals"]["normalized_wrong"] == 0
    assert result["seconds_per_page"] is None


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(doc="SECRET-value"),
    lambda r: r.update(condition="/SECRET/path"),
    lambda r: r["own"]["fields"].update({"SECRET-field": metric()}),
    lambda r: r["own"].update(confirmed_reupload_codes=["SECRET-code"]),
    lambda r: r["own"].update(seconds=float("nan")),
    lambda r: r["own"]["fields"]["성명"].update(raw_edits=-1),
])
def test_unreviewed_identifiers_and_nonfinite_metrics_are_rejected(mutation):
    data = row(); mutation(data)
    with pytest.raises(ValueError):
        reporting.summarize([data])


def test_markdown_contains_complete_paired_fields_and_no_input_values():
    data = row(own=stage({"성명": metric("UNEXTRACTED_CLASSIFICATION")}, kind="X", invoked="X", status="NEEDS_REVIEW"))
    data["unused_private_value"] = "SECRET-not-a-metric"
    result = {"seed": 7, "samples": 5, "summary": reporting.summarize([data])}
    text = reporting.markdown(result)
    assert "Complete field × type × condition" in text
    assert "nhis_payment | original | 성명" in text
    assert "UNEXTRACTED_CLASSIFICATION" in text and "N/A" in text
    assert "A/B s/page" in text and "Raw / normalized" in text
    assert "SECRET" not in text
    assert all(code in text for code in reporting.REUPLOAD_CODES)


def test_summary_has_all_requested_views_and_preserves_empty_groups():
    result = reporting.summarize([row()])
    assert set(result) == {"overall", "by_group", "by_document", "by_document_group", "by_condition", "by_cell", "by_field"}
    assert result["by_cell"]["nhis_payment"]["original"]["attempted"] == 1
    assert result["by_document_group"]["nhis_payment"]["quality_defect"]["attempted"] == 0
    assert result["by_field"]["nhis_payment"]["own"]["성명"]["called"] == 1


def test_weak_rankings_do_not_mix_deliberately_defective_cases():
    wrong = stage({"성명": metric("MISMATCH", raw="X", normalized="X", edits=4)})
    rows = [row(), row(condition="phone", group="stress", own=wrong),
            row(condition="low_resolution", group="quality_defect", expected="FAIL", own=wrong),
            row(condition="identity_mismatch", group="content_defect", expected="FAIL", own=wrong)]
    text = reporting.markdown({"seed": 7, "samples": 5, "summary": reporting.summarize(rows)})
    weak = text.split("## Weakest diagnostic groups", 1)[1].split("## Source decisions", 1)[0]
    assert "normal_baseline" in weak and "stress" in weak and "phone" in weak
    assert "quality_defect" not in weak and "content_defect" not in weak
    assert "low_resolution" not in weak and "identity_mismatch" not in weak


def test_main_attribution_excludes_designed_negative_inputs():
    rows = [row(), row(condition="unreadable_file", group="content_defect", expected="FAIL")]
    text = reporting.markdown({"seed": 1, "samples": 5, "summary": reporting.summarize(rows)})
    attribution = text.split("## Classification/extraction versus OCR contribution by document", 1)[1].split("## Complete type", 1)[0]
    assert "normal_baseline" in attribution and "content_defect" not in attribution
    assert reporting.summarize(rows)["by_document_group"]["nhis_payment"]["content_defect"]["attempted"] == 1


def test_mixed_page_and_nonpage_timing_uses_only_physical_page_seconds():
    rows = [row(own=stage(seconds=6, pages=2)),
            row(own=stage(seconds=2, pages=1)),
            row(condition="unreadable_file", group="content_defect", expected="FAIL",
                own=stage(status="FAIL", seconds=100, pages=0))]
    overall = reporting.summarize(rows)["overall"]["own"]
    assert overall["seconds"] == 108
    assert overall["page_seconds"] == 8 and overall["pages"] == 3
    assert overall["nonpage_seconds"] == 100 and overall["nonpage_attempts"] == 1
    assert overall["seconds_per_page"] == pytest.approx(8 / 3)
    assert overall["page_seconds"] + overall["nonpage_seconds"] == overall["seconds"]
    unreadable = reporting.summarize(rows)["by_condition"]["unreadable_file"]["own"]
    assert unreadable["seconds_per_page"] is None and unreadable["page_seconds"] == 0
    assert unreadable["nonpage_seconds"] == 100


def test_source_change_evidence_is_preserved_in_new_report():
    report = {"seed": 1, "samples": 5, "summary": reporting.summarize([row()]),
              "source_changes": ["S01: Original purpose mark retained; source fixture evidence.",
                                 "S02: Five distinct parameter sets; modulo-four generator evidence."]}
    text = reporting.markdown(report)
    assert "### Source-change evidence" in text
    assert all(entry in text for entry in report["source_changes"])
    assert "Nonpage attempts/seconds" in text


def test_opportunity_changes_exhaustively_reconcile_changed_called_denominators():
    good = stage()
    bad = stage({"성명": metric("MISSING", raw="X", normalized="X", edits=4)})
    uncalled = stage({"성명": metric("UNEXTRACTED_CLASSIFICATION")}, kind="X", invoked="X", status="NEEDS_REVIEW")
    cases = [row(reference=good, own=bad),  # OCR loses an A-correct field.
             row(reference=uncalled, own=bad),  # A gate opens, exposing an error.
             row(reference=uncalled, own=bad),  # A second newly called error.
             row(reference=uncalled, own=good),  # A gate opens, exposing a correct field.
             row(reference=bad, own=good),  # A visible field error is recovered.
             row(reference=bad, own=uncalled),  # A visible field error is hidden by B gating.
             row(reference=bad, own=bad),  # Shared error, no delta.
             row(reference=uncalled, own=uncalled)]
    summary = reporting.summarize(cases)
    changes = summary["overall"]["opportunity_changes"]
    assert changes["reference_field_errors"] == 3 and changes["own_field_errors"] == 4
    assert changes["newly_called_field_errors"] == 2 and changes["newly_called_field_correct"] == 1
    assert changes["hidden_reference_field_errors"] == 1
    assert changes["shared_field_errors"] == 1 and changes["both_unextracted"] == 1
    assert changes["ocr_field_losses"] == 1 and changes["field_recoveries"] == 1
    assert changes["field_error_delta"] == changes["reconstructed_field_error_delta"] == 1
    assert changes["field_error_delta"] == summary["overall"]["attribution"]["field_error_delta"]
    assert changes["complete_pairs"] == 8 and changes["skipped_pairs"] == 0
    text = reporting.markdown({"seed": 1, "samples": 5, "summary": summary})
    assert "## Field opportunity-change decomposition" in text
    assert "Newly called wrong" in text and "A errors hidden by B gating" in text


def test_opportunity_changes_exclude_execution_failed_pairs():
    error = stage({"성명": metric("ERROR")}, kind="X", invoked="X", failed="O", status="X", pages=0)
    changes = reporting.summarize([row(own=error)])["overall"]["opportunity_changes"]
    assert changes["complete_pairs"] == 0 and changes["skipped_pairs"] == 1
    assert changes["comparable_fields"] == 0 and changes["newly_called_field_errors"] == 0
    assert changes["field_error_delta"] == changes["reconstructed_field_error_delta"] == 0
