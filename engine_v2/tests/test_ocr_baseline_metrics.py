"""Authored strings/geometry prove numeric OCR baseline metric contracts."""
from __future__ import annotations

from copy import deepcopy
import itertools
import json
import math
import random
import subprocess
import sys
from types import SimpleNamespace

import pytest

from engine_v2.tools import ocr_baseline_metrics as metrics


def word(text, x=10, y=10, width=100, height=10, confidence=.95):
    return SimpleNamespace(text=text, confidence=confidence, bbox_px=(x, y, x + width, y + height))


def _slow_distance(reference, observed):
    row = list(range(len(observed) + 1))
    for i, char in enumerate(reference, 1):
        next_row = [i]
        for j, other in enumerate(observed, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (char != other)))
        row = next_row
    return row[-1]


def test_distance_matches_independent_dynamic_programming_exhaustively():
    strings = ["".join(chars) for length in range(5) for chars in itertools.product("ab", repeat=length)]
    for reference, observed in itertools.product(strings, repeat=2):
        assert metrics.distance(reference, observed) == _slow_distance(reference, observed)
    rng = random.Random(718)
    for _ in range(40):
        reference = "".join(rng.choices("가나ᄃA12", k=rng.randrange(100)))
        observed = "".join(rng.choices("가나ᄃA12", k=rng.randrange(100)))
        assert metrics.distance(reference, observed) == _slow_distance(reference, observed)


def test_nfkc_whitespace_digit_hangul_streams_have_known_counts():
    result = metrics.measure([word("Ａ １２\t가\u3000나")], [word("A13가다")], (1000, 1000))
    assert result["cer"] == {"edits": 2, "reference": 5, "observed": 5, "rate": .4}
    assert result["digit_cer"] == {"edits": 1, "reference": 2, "observed": 2, "rate": .5}
    assert result["hangul_cer"] == {"edits": 1, "reference": 2, "observed": 2, "rate": .5}


def test_hangul_includes_composed_syllables_and_remaining_jamo():
    result = metrics.measure([word("각ᄂ")], [word("각ᄃ")], (1000, 1000))
    assert result["hangul_cer"]["reference"] == 2
    assert result["hangul_cer"]["edits"] == 1


def test_reading_order_is_geometric_and_independent_of_insertion_order():
    reference = [word("바닥", y=70), word("오른쪽", x=200), word("왼쪽")]
    observed = list(reversed(reference))
    result = metrics.measure(reference, observed, (1000, 1000))
    assert result["cer"]["edits"] == 0
    assert [[item.text for item in line] for line in metrics.ordered_lines(reference, (1000, 1000))] == [
        ["왼쪽", "오른쪽"], ["바닥"]]


def test_words_use_multiset_matching_and_ignore_geometric_order():
    result = metrics.measure([word("가 가 나")], [word("나 가 다")], (1000, 1000))
    assert result["words"] == {"matched": 2, "reference": 3, "observed": 3,
                               "precision": 2 / 3, "recall": 2 / 3, "f1": 2 / 3}
    assert result["cer"]["edits"] > 0


def test_box_tokenization_does_not_replace_unicode_whitespace_word_policy():
    result = metrics.measure([word("보험료 1000")], [word("보험료1000")], (1000, 1000))
    assert result["cer"]["edits"] == 0
    assert result["words"]["matched"] == 0
    assert result["words"]["reference"] == 2
    assert result["words"]["observed"] == 1


def test_empty_denominators_stay_null_and_insertions_are_preserved():
    empty = metrics.measure([], [], (1000, 1000))
    inserted = metrics.measure([], [word("123")], (1000, 1000))
    assert empty["cer"]["rate"] is None and empty["words"]["f1"] is None
    assert inserted["cer"] == {"edits": 3, "reference": 0, "observed": 3, "rate": None}
    assert inserted["words"]["precision"] == 0 and inserted["words"]["recall"] is None
    assert inserted["words"]["f1"] == 0
    assert inserted["lines"]["unmatched_boxes"] == 1


def test_cer_above_one_is_not_clamped():
    result = metrics.measure([word("A")], [word("ABCDE")], (1000, 1000))
    assert result["cer"]["rate"] == 4


def test_detection_miss_and_covered_recognition_error_have_separate_denominators():
    result = metrics.measure([word("abcd"), word("ef", y=50)], [word("abXd")], (1000, 1000))
    assert result["lines"]["reference"] == 2
    assert result["lines"]["missed"] == 1
    assert result["lines"]["miss_rate"] == .5
    assert result["lines"]["recognition"] == {"edits": 1, "reference": 4, "observed": 4, "rate": .25}
    assert result["cer"]["edits"] == 3


def test_geometry_overlap_not_text_similarity_controls_detection():
    result = metrics.measure([word("same")], [word("same", y=60)], (1000, 1000))
    assert result["cer"]["rate"] == 0
    assert result["lines"]["miss_rate"] == 1
    assert result["lines"]["recognition"]["rate"] is None


@pytest.mark.parametrize("x,missed", [(99, 0), (100, 0), (100.1, 1), (110, 1)])
def test_overlap_threshold_is_intersection_over_smaller_box(x, missed):
    result = metrics.measure([word("A", x=10, width=100)], [word("A", x=x, width=100)], (1000, 1000))
    assert result["lines"]["missed"] == missed


def test_multiline_box_is_covered_but_never_duplicated_for_recognition():
    result = metrics.measure([word("A", y=10), word("B", y=40)],
                             [word("AB", y=10, height=40)], (1000, 1000))
    assert result["lines"]["covered"] == 2
    assert result["lines"]["ambiguous_boxes"] == 1
    assert result["lines"]["covered_empty"] == 1
    assert result["lines"]["recognition"]["observed"] == 2


@pytest.mark.parametrize("height,expected", [(11.99, "LT12"), (12, "12_20"), (20, "20_32"), (32, "GE32")])
def test_height_bin_boundaries_use_variant_pixel_scale(height, expected):
    result = metrics.measure([word("A", height=height / 2)], [], (1000, 1000), height_scale=2)
    assert result["height_bins"][expected]["lines"] == 1
    assert result["height_bins"][expected]["miss_rate"] == 1
    assert result["height_bins"][expected]["cer"]["rate"] == 1


@pytest.mark.parametrize("score,expected", [(0, "LT50"), (.5, "50_80"), (.8, "80_90"), (.9, "90_100"),
                                          (1, "90_100"), (-.1, "UNAVAILABLE"),
                                          (math.nan, "UNAVAILABLE"), (True, "UNAVAILABLE")])
def test_confidence_bins_report_actual_character_and_line_errors(score, expected):
    result = metrics.measure([word("A")], [word("X", confidence=score)], (1000, 1000))
    target = result["confidence_bins"][expected]
    assert target["lines"] == target["incorrect"] == 1
    assert target["cer"]["rate"] == target["incorrect_rate"] == 1


def test_confidence_uses_character_weighted_mean_not_box_mean():
    result = metrics.measure([word("ABCDEFGH X")],
                             [word("ABCDEFGH", width=60, confidence=1),
                              word("X", x=80, width=20, confidence=0)], (1000, 1000))
    assert result["confidence_bins"]["80_90"]["lines"] == 1


def test_table_inside_digit_error_and_missing_row_are_separate_from_outside():
    reference = [word("제목", y=10), word("월 금액", y=40), word("1월 1000", y=70),
                 word("2월 2000", y=100), word("끝", y=150)]
    observed = [word("제목", y=10), word("월 금액", y=40), word("1월 1009", y=70), word("끝", y=150)]
    result = metrics.measure(reference, observed, (1000, 1000), table_bounds=(5, 35, 200, 120))
    table = result["table"]
    assert table["measured"] == 1
    assert table["inside"]["lines"] == 3 and table["inside"]["missed"] == 1
    assert table["inside"]["miss_rate"] == 1 / 3
    assert table["inside"]["digit_cer"] == {"edits": 6, "reference": 10, "observed": 5, "rate": .6}
    assert table["outside"]["cer"]["rate"] == 0
    assert table["outside"]["miss_rate"] == 0


def test_table_unconfirmed_is_unmeasured_not_zero_error():
    result = metrics.measure([word("1000")], [word("1009")], (1000, 1000))
    assert result["table"]["measured"] == 0
    assert result["table"]["inside"]["cer"]["rate"] is None
    assert result["table"]["outside"]["cer"]["rate"] is None


def test_unmatched_table_insertions_are_counted_in_inside_cer():
    result = metrics.measure([word("1", y=40)], [word("1", y=40), word("999", y=80)],
                             (1000, 1000), table_bounds=(0, 30, 200, 100))
    assert result["table"]["inside"]["digit_cer"]["edits"] == 3
    assert result["lines"]["unmatched_boxes"] == 1


def test_invalid_boxes_never_emit_nonfinite_metrics():
    bad = word("PRIVATE-SENTINEL")
    bad.bbox_px = (0, 0, math.inf, 30)
    result = metrics.measure([bad, word("A")], [bad, word("A")], (1000, 1000))
    assert result["lines"]["invalid_reference_boxes"] == result["lines"]["invalid_observed_boxes"] == 1
    assert "PRIVATE-SENTINEL" not in json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("kwargs", [{"size": (0, 100)}, {"size": (100, math.nan)},
                                    {"height_scale": 0}, {"table_bounds": (1, 2, 0, 3)}])
def test_invalid_metric_configuration_has_only_fixed_error(kwargs):
    config = {"size": (1000, 1000), **kwargs}
    with pytest.raises(ValueError, match="^METRIC_INPUT_INVALID$"):
        metrics.measure([], [], **config)


def test_output_contains_only_fixed_keys_and_numbers_not_values_or_coordinates():
    result = metrics.measure([word("SYNTHETIC-SENTINEL-73919")], [], (1000, 1000))
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key not in {"text", "bbox", "bbox_px", "x0", "y0", "x1", "y1"}
                visit(child)
        else:
            assert value is None or type(value) in (int, float)
    visit(result)
    assert "SYNTHETIC-SENTINEL-73919" not in json.dumps(result)


def test_aggregation_pools_counts_and_has_no_layout_dependency(monkeypatch):
    first = metrics.measure([word("AB")], [word("AX")], (1000, 1000), table_bounds=(0, 0, 200, 50))
    second = metrics.measure([word("CDE")], [], (1000, 1000))
    monkeypatch.setattr(metrics, "ordered_lines", lambda *a, **k: pytest.fail("summary tried to process source"))
    result = metrics.aggregate_metrics([first, second])
    assert result["cer"] == {"edits": 4, "reference": 5, "observed": 2, "rate": .8}
    assert result["lines"]["miss_rate"] == .5
    assert result["table"]["measured"] == 1
    assert result["table"]["inside"]["cer"]["rate"] == .5
    assert metrics.aggregate_metrics([]) == metrics.empty_metrics()


def test_templates_are_independent_and_aggregate_does_not_mutate_inputs():
    record = metrics.empty_metrics()
    before = deepcopy(record)
    metrics.aggregate_metrics([record])
    assert record == before
    other = metrics.empty_metrics()
    other["height_bins"]["LT12"]["lines"] = 5
    assert record["height_bins"]["LT12"]["lines"] == 0


def test_import_template_and_aggregation_do_not_import_ocr_or_demo_backend():
    script = """import sys
from engine_v2.tools.ocr_baseline_metrics import empty_metrics, aggregate_metrics
empty_metrics(); aggregate_metrics([])
assert not any(name.startswith(('engine_v2.pipeline', 'demo.backend')) for name in sys.modules)
"""
    process = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True)
    assert process.returncode == 0, process.stderr.decode()


@pytest.mark.parametrize("path,replacement", [
    (("cer", "edits"), .5),
    (("cer", "rate"), .2),
    (("cer", "reference"), 999),
    (("words", "matched"), 99),
    (("lines", "missed"), 2),
    (("height_bins", "LT12", "lines"), 9),
    (("confidence_bins", "90_100", "cer", "rate"), math.nan),
    (("table", "measured"), 2),
    (("table", "inside", "lines"), 1),
])
def test_persisted_metric_validation_rejects_fractional_or_contradictory_counts(path, replacement):
    record = metrics.measure([word("ABC")], [word("AXC")], (1000, 1000))
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(ValueError, match="^METRIC_RECORD_INVALID$"):
        metrics.validate_metrics(record)


def test_persisted_metric_validation_accepts_empty_missing_and_table_populations():
    for record in [metrics.empty_metrics(), metrics.measure([], [word("X")], (1000, 1000)),
                   metrics.measure([word("ABC"), word("DEF", y=60)], [word("AXC")],
                                   (1000, 1000), table_bounds=(0, 0, 200, 30))]:
        assert metrics.validate_metrics(record) is record


def test_pooled_line_edits_can_exceed_global_character_maximum():
    # One coarse box covers both lines but is assigned once to the earlier
    # short line. Substitutions/insertions there plus deletions on the long
    # line are independent costs, unlike a page-wide Levenshtein alignment.
    record = metrics.measure([word("A", y=10), word("B" * 20, y=40)],
                             [word("A" * 10, y=10, height=40)], (1000, 1000))
    assert record["lines"]["recognition"]["edits"] == 29
    assert metrics.validate_metrics(record) is record
