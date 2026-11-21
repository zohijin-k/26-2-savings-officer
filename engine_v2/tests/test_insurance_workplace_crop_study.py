"""D/E/N synthetic-only retry budgets and conservative outcome handling."""
import pytest

from engine_v2.pipeline.ocr import OcrWord
from engine_v2.tools import insurance_workplace_crop_study as study


def test_D_unanimously_correct_candidates_still_do_not_authorize_recovery():
    calls = []
    def recognize(png, size):
        calls.append(size)
        return [OcrWord(study.TRUTH, .99, (0, 0, *size))]
    result = study.run_study(recognize)
    assert len(calls) == result["region_calls"] == 8
    assert all(w * h <= 1_000_000 for w, h in calls)
    assert all(result["variants"][v]["correct"] == 4 for v in study.VARIANTS)
    assert result["automatic_recovery_enabled"] is False
    assert result["cold"]["n"] == 1 and result["warm"]["n"] == 7
    assert result["retained_crop_bytes"] == 0


@pytest.mark.parametrize("outcome", ["wrong", "empty", "timeout", "error", "disagree"])
def test_E_all_bad_retry_outcomes_are_counted_and_never_applied(outcome):
    calls = 0
    def recognize(png, size):
        nonlocal calls
        calls += 1
        if outcome == "timeout": raise TimeoutError
        if outcome == "error": raise RuntimeError("FICTITIOUS_SECRET_MUST_NOT_LEAK")
        if outcome == "empty": return []
        text = study.TRUTH if outcome == "disagree" and calls % 2 else "가상솔빗상사"
        return [OcrWord(text, .999, (0, 0, *size))]
    result = study.run_study(recognize)
    assert calls == 8 and result["automatic_recovery_enabled"] is False
    if outcome == "disagree": assert result["disagreement_rows"] == 4
    else: assert sum(result["variants"][v][outcome] for v in study.VARIANTS) == 8
    if outcome == "wrong": assert sum(result["variants"][v]["high_score_wrong"] for v in study.VARIANTS) == 8
    assert "FICTITIOUS_SECRET" not in str(result)
