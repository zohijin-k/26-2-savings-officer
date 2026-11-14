"""Numeric-only OCR metrics; source strings and geometry remain transient.

Only the line-ordering entry point lazily imports the production layout helper.
Templates and aggregation import no OCR backend, which keeps summaries offline.
"""
from __future__ import annotations

from collections import Counter
import math
from statistics import median
import unicodedata

from .ocr_baseline_settings import SETTINGS

HEIGHT_BINS = ("LT12", "12_20", "20_32", "GE32")
CONFIDENCE_BINS = ("LT50", "50_80", "80_90", "90_100", "UNAVAILABLE")


def normalized(text):
    """NFKC followed by removal of all Unicode whitespace, case-sensitive."""
    return "".join(unicodedata.normalize("NFKC", text).split())


def distance(reference, observed):
    """Exact unit-cost Levenshtein using arbitrary-width Myers bit vectors.

    Common edges are trimmed first; work is linear in the observed length in
    Python rather than a Python loop over every character pair on long pages.
    """
    if reference == observed:
        return 0
    prefix = 0
    for left, right in zip(reference, observed):
        if left != right:
            break
        prefix += 1
    reference, observed = reference[prefix:], observed[prefix:]
    suffix = 0
    for left, right in zip(reversed(reference), reversed(observed)):
        if left != right:
            break
        suffix += 1
    if suffix:
        reference, observed = reference[:-suffix], observed[:-suffix]
    if len(reference) > len(observed):
        reference, observed = observed, reference
    if not reference:
        return len(observed)
    matches = {}
    for index, char in enumerate(reference):
        matches[char] = matches.get(char, 0) | (1 << index)
    positive, negative, score = ~0, 0, len(reference)
    high = 1 << (len(reference) - 1)
    for char in observed:
        equal = matches.get(char, 0)
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        plus = negative | ~(horizontal | positive)
        minus = positive & horizontal
        score += int(bool(plus & high)) - int(bool(minus & high))
        plus, minus = (plus << 1) | 1, minus << 1
        positive, negative = minus | ~(vertical | plus), plus & vertical
    return score


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def character_metric(reference="", observed=""):
    edits = distance(reference, observed)
    return {"edits": edits, "reference": len(reference),
            "observed": len(observed), "rate": ratio(edits, len(reference))}


def _hangul(char):
    code = ord(char)
    return (0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF or
            0x3130 <= code <= 0x318F or 0xA960 <= code <= 0xA97F or
            0xD7B0 <= code <= 0xD7FF)


def _streams(reference, observed):
    ref, hyp = normalized(reference), normalized(observed)
    return {"cer": character_metric(ref, hyp),
            "digit_cer": character_metric("".join(c for c in ref if "0" <= c <= "9"),
                                          "".join(c for c in hyp if "0" <= c <= "9")),
            "hangul_cer": character_metric("".join(c for c in ref if _hangul(c)),
                                           "".join(c for c in hyp if _hangul(c)))}


def _bin_template():
    return {"lines": 0, "missed": 0, "covered": 0, "incorrect": 0,
            "cer": character_metric(), "miss_rate": None, "incorrect_rate": None}


def _region_template():
    return {"lines": 0, "missed": 0, "miss_rate": None, **_streams("", "")}


def empty_metrics():
    """Fresh closed-schema template, usable without importing any OCR backend."""
    return {
        **_streams("", ""),
        "words": {"matched": 0, "reference": 0, "observed": 0,
                  "precision": None, "recall": None, "f1": None},
        "lines": {"reference": 0, "missed": 0, "covered": 0, "covered_empty": 0,
                  "ambiguous_boxes": 0, "unmatched_boxes": 0,
                  "invalid_reference_boxes": 0, "invalid_observed_boxes": 0,
                  "miss_rate": None, "recognition": character_metric()},
        "height_bins": {name: _bin_template() for name in HEIGHT_BINS},
        "confidence_bins": {name: _bin_template() for name in CONFIDENCE_BINS},
        "table": {"measured": 0, "inside": _region_template(), "outside": _region_template()},
    }


def _valid_box(word):
    try:
        box = word.bbox_px
        return (len(box) == 4 and all(type(v) in (int, float) and math.isfinite(v) for v in box)
                and box[0] < box[2] and box[1] < box[3])
    except (AttributeError, TypeError):
        return False


def ordered_lines(words, size, *, tolerance=SETTINGS["lines"]["tolerance"]):
    """Production center-distance grouping, independent of reference contents.

    Geometry ties are deterministic; original text is never a sorting key.
    Returns lists of the input word objects, not serializable metric records.
    """
    from engine_v2.pipeline.layout import group_lines, normalize
    ordered = sorted(words, key=lambda word: (
        (word.bbox_px[1] + word.bbox_px[3]) / 2,
        word.bbox_px[0], word.bbox_px[1], word.bbox_px[2], word.bbox_px[3]))
    layout = normalize(ordered, 0, size)
    originals = {id(item): word for item, word in zip(layout, ordered)}
    lines = group_lines(layout, tol=tolerance)
    lines.sort(key=lambda line: (sum(word.cy for word in line) / len(line),
                                 min(word.x0 for word in line)))
    return [[originals[id(item)] for item in line] for line in lines]


def _text(lines):
    return "\n".join(" ".join(word.text for word in line) for line in lines)


def _bounds(words):
    return (min(w.bbox_px[0] for w in words), min(w.bbox_px[1] for w in words),
            max(w.bbox_px[2] for w in words), max(w.bbox_px[3] for w in words))


def _overlap(left, right):
    width = max(0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0, min(left[3], right[3]) - max(left[1], right[1]))
    area = width * height
    smaller = min((left[2] - left[0]) * (left[3] - left[1]),
                  (right[2] - right[0]) * (right[3] - right[1]))
    return area / smaller if smaller else 0


def _add_metric(target, value):
    for name in ("edits", "reference", "observed"):
        target[name] += value[name]
    target["rate"] = ratio(target["edits"], target["reference"])


def _record_bin(target, metric, covered):
    target["lines"] += 1
    target["covered"] += int(covered)
    target["missed"] += int(not covered)
    target["incorrect"] += int(metric["edits"] > 0)
    _add_metric(target["cer"], metric)
    target["miss_rate"] = ratio(target["missed"], target["lines"])
    target["incorrect_rate"] = ratio(target["incorrect"], target["lines"])


def _confidence(words):
    total = weight = 0
    if not words:
        return None
    for word in words:
        score = word.confidence
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            return None
        count = max(1, len(normalized(word.text)))
        total += score * count
        weight += count
    return total / weight


def measure(reference_words, observed_words, size, *, height_scale=1.0,
            table_bounds=None, settings=SETTINGS):
    """Compare common-coordinate words without returning text or coordinates.

    `size` describes the common page-coordinate system. `height_scale` maps
    those coordinates to actual variant pixels for box-height bins. An optional
    table rectangle is in the same common coordinates and derived from truth.
    """
    if (len(size) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in size)
            or type(height_scale) not in (int, float) or not math.isfinite(height_scale) or height_scale <= 0):
        raise ValueError("METRIC_INPUT_INVALID")
    if table_bounds is not None:
        if (len(table_bounds) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in table_bounds)
                or table_bounds[0] >= table_bounds[2] or table_bounds[1] >= table_bounds[3]):
            raise ValueError("METRIC_INPUT_INVALID")
    result = empty_metrics()
    refs = [word for word in reference_words if _valid_box(word)]
    hyps = [word for word in observed_words if _valid_box(word)]
    result["lines"]["invalid_reference_boxes"] = len(reference_words) - len(refs)
    result["lines"]["invalid_observed_boxes"] = len(observed_words) - len(hyps)
    ref_lines = ordered_lines(refs, size, tolerance=settings["lines"]["tolerance"])
    hyp_lines = ordered_lines(hyps, size, tolerance=settings["lines"]["tolerance"])
    ref_text, hyp_text = _text(ref_lines), _text(hyp_lines)
    result.update(_streams(ref_text, hyp_text))
    ref_tokens = Counter(unicodedata.normalize("NFKC", ref_text).split())
    hyp_tokens = Counter(unicodedata.normalize("NFKC", hyp_text).split())
    matched = sum((ref_tokens & hyp_tokens).values())
    ref_count, hyp_count = sum(ref_tokens.values()), sum(hyp_tokens.values())
    result["words"] = {"matched": matched, "reference": ref_count, "observed": hyp_count,
                       "precision": ratio(matched, hyp_count), "recall": ratio(matched, ref_count),
                       "f1": ratio(2 * matched, ref_count + hyp_count)}
    boxes = [_bounds(line) for line in ref_lines]
    covered = [False] * len(ref_lines)
    assigned = [[] for _ in ref_lines]
    for word in hyps:
        candidates = [(index, _overlap(box, word.bbox_px)) for index, box in enumerate(boxes)]
        candidates = [(index, overlap) for index, overlap in candidates
                      if overlap >= settings["lines"]["overlap_min_fraction"] and overlap > 0]
        for index, _ in candidates:
            covered[index] = True
        result["lines"]["ambiguous_boxes"] += int(len(candidates) > 1)
        if not candidates:
            result["lines"]["unmatched_boxes"] += 1
            continue
        winner, _ = max(candidates, key=lambda item: (item[1], -item[0]))
        assigned[winner].append(word)
    result["lines"].update(reference=len(ref_lines), missed=sum(not value for value in covered),
                            covered=sum(covered), miss_rate=ratio(sum(not value for value in covered), len(ref_lines)))
    for index, line in enumerate(ref_lines):
        observed = sorted(assigned[index], key=lambda word: (word.bbox_px[0], word.bbox_px[1]))
        metric = character_metric(normalized(_text([line])), normalized(_text([observed])))
        height = median(word.bbox_px[3] - word.bbox_px[1] for word in line) * height_scale
        height_index = sum(height >= boundary for boundary in settings["height_boundaries"])
        _record_bin(result["height_bins"][HEIGHT_BINS[height_index]], metric, covered[index])
        if covered[index]:
            _add_metric(result["lines"]["recognition"], metric)
            result["lines"]["covered_empty"] += int(not normalized(_text([observed])))
            score = _confidence(observed)
            conf_name = ("UNAVAILABLE" if score is None else
                         CONFIDENCE_BINS[sum(score >= boundary for boundary in settings["confidence_boundaries"])])
            _record_bin(result["confidence_bins"][conf_name], metric, True)
    if table_bounds is not None:
        result["table"]["measured"] = 1
        def inside(word):
            x0, y0, x1, y1 = word.bbox_px
            return (table_bounds[0] <= (x0 + x1) / 2 <= table_bounds[2] and
                    table_bounds[1] <= (y0 + y1) / 2 <= table_bounds[3])
        # Text membership is geometric on both sides, including OCR insertions.
        # Detection membership uses reference line centers and global coverage.
        for name, selected in (("inside", True), ("outside", False)):
            ref_subset = [[word for word in line if inside(word) == selected] for line in ref_lines]
            hyp_subset = [[word for word in line if inside(word) == selected] for line in hyp_lines]
            region = result["table"][name]
            region.update(_streams(_text(ref_subset), _text(hyp_subset)))
            indices = [index for index, box in enumerate(boxes)
                       if (table_bounds[0] <= (box[0] + box[2]) / 2 <= table_bounds[2] and
                           table_bounds[1] <= (box[1] + box[3]) / 2 <= table_bounds[3]) == selected]
            region["lines"] = len(indices)
            region["missed"] = sum(not covered[index] for index in indices)
            region["miss_rate"] = ratio(region["missed"], region["lines"])
    return result


def aggregate_metrics(records):
    """Pool only numeric counts; never reprocess words or import a backend."""
    result = empty_metrics()
    for record in records:
        for name in ("cer", "digit_cer", "hangul_cer"):
            _add_metric(result[name], record[name])
        for name in ("matched", "reference", "observed"):
            result["words"][name] += record["words"][name]
        for name in result["lines"]:
            if name not in ("miss_rate", "recognition"):
                result["lines"][name] += record["lines"][name]
        _add_metric(result["lines"]["recognition"], record["lines"]["recognition"])
        for family in ("height_bins", "confidence_bins"):
            for name, target in result[family].items():
                value = record[family][name]
                for key in ("lines", "covered", "missed", "incorrect"):
                    target[key] += value[key]
                _add_metric(target["cer"], value["cer"])
        result["table"]["measured"] += record["table"]["measured"]
        for name in ("inside", "outside"):
            target, value = result["table"][name], record["table"][name]
            for key in ("lines", "missed"):
                target[key] += value[key]
            for key in ("cer", "digit_cer", "hangul_cer"):
                _add_metric(target[key], value[key])
    words = result["words"]
    words.update(precision=ratio(words["matched"], words["observed"]),
                 recall=ratio(words["matched"], words["reference"]),
                 f1=ratio(2 * words["matched"], words["reference"] + words["observed"]))
    result["lines"]["miss_rate"] = ratio(result["lines"]["missed"], result["lines"]["reference"])
    for family in ("height_bins", "confidence_bins"):
        for target in result[family].values():
            target["miss_rate"] = ratio(target["missed"], target["lines"])
            target["incorrect_rate"] = ratio(target["incorrect"], target["lines"])
    for name in ("inside", "outside"):
        target = result["table"][name]
        target["miss_rate"] = ratio(target["missed"], target["lines"])
    return result


def validate_metrics(value):
    """Reject nonnumeric payloads and contradictory per-page metric records.

    This validates persisted *page* measurements, not pooled summary records.
    Failures deliberately contain only a fixed tool-owned code.
    """
    def require(condition):
        if not condition:
            raise ValueError("METRIC_RECORD_INVALID")

    def shape(actual, template):
        if isinstance(template, dict):
            require(isinstance(actual, dict) and actual.keys() == template.keys())
            for key in template:
                shape(actual[key], template[key])
        elif template is None:
            require(actual is None or (type(actual) in (int, float) and math.isfinite(actual) and actual >= 0))
        else:
            require(type(actual) is int and actual >= 0)

    def rate(actual, numerator, denominator):
        expected = ratio(numerator, denominator)
        require(actual is None if expected is None else actual is not None and
                math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12))

    def characters(metric, *, pooled=False):
        upper = (metric["reference"] + metric["observed"] if pooled else
                 max(metric["reference"], metric["observed"]))
        require(abs(metric["reference"] - metric["observed"]) <= metric["edits"] <=
                upper)
        rate(metric["rate"], metric["edits"], metric["reference"])

    shape(value, empty_metrics())
    for name in ("cer", "digit_cer", "hangul_cer"):
        characters(value[name])
        if name != "cer":
            require(value[name]["reference"] <= value["cer"]["reference"] and
                    value[name]["observed"] <= value["cer"]["observed"])
    words = value["words"]
    require(words["matched"] <= min(words["reference"], words["observed"]))
    rate(words["precision"], words["matched"], words["observed"])
    rate(words["recall"], words["matched"], words["reference"])
    rate(words["f1"], 2 * words["matched"], words["reference"] + words["observed"])
    lines = value["lines"]
    require(lines["missed"] + lines["covered"] == lines["reference"] and
            lines["covered_empty"] <= lines["covered"])
    rate(lines["miss_rate"], lines["missed"], lines["reference"])
    characters(lines["recognition"], pooled=True)
    for family in ("height_bins", "confidence_bins"):
        for item in value[family].values():
            require(item["missed"] + item["covered"] == item["lines"] and item["incorrect"] <= item["lines"])
            characters(item["cer"], pooled=True)
            rate(item["miss_rate"], item["missed"], item["lines"])
            rate(item["incorrect_rate"], item["incorrect"], item["lines"])
        expected = lines["reference"] if family == "height_bins" else lines["covered"]
        require(sum(item["lines"] for item in value[family].values()) == expected)
        require(sum(item["covered"] for item in value[family].values()) == lines["covered"])
        require(sum(item["missed"] for item in value[family].values()) ==
                (lines["missed"] if family == "height_bins" else 0))
    for key in ("reference", "observed"):
        require(sum(item["cer"][key] for item in value["confidence_bins"].values()) == lines["recognition"][key])
    table = value["table"]
    require(table["measured"] in (0, 1))
    if not table["measured"]:
        require(table == empty_metrics()["table"])
    else:
        require(sum(table[name]["lines"] for name in ("inside", "outside")) == lines["reference"])
        require(sum(table[name]["missed"] for name in ("inside", "outside")) == lines["missed"])
        for name in ("inside", "outside"):
            region = table[name]
            require(region["missed"] <= region["lines"])
            rate(region["miss_rate"], region["missed"], region["lines"])
            for metric_name in ("cer", "digit_cer", "hangul_cer"):
                characters(region[metric_name])
    return value
