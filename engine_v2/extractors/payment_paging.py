"""Payment-only folio evidence, independent of table extraction and confidence."""
from __future__ import annotations

import math
import re

from . import nhis_common as common
from ..pipeline.layout import squash

FIELD = "납부쪽표기자료"
MIN_CONFIDENCE = .85
POLICIES = {"REQUIRED", "NOT_REQUIRED", "UNRESOLVED"}
_MARKER = re.compile(r"([1-9][0-9]?)[/／]([1-9][0-9]?)")
_LIKE = re.compile(r"(?<![0-9A-Za-z])([0-9A-Za-z]{0,2})[/／]([0-9A-Za-z]{0,2})(?![0-9A-Za-z])")
_DATE_PART = r"[0-9]{4}(?:[./／-]|년)[0-9]{1,2}(?:(?:[./／-]|월)[0-9]{1,2}일?|월)?"
_DATE_RUN = re.compile(_DATE_PART + r"(?:[~～–—-]" + _DATE_PART + r")?")
_MONEY_RUN = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})+(?:[/／][0-9,]+){1,2}")


def _non_counter_words(row):
    """Account for whole date/money runs before dividing horizontal regions."""
    excluded = set()
    for start in range(len(row)):
        for end in range(start + 1, min(len(row), start + 12) + 1):
            if end > start + 1:
                previous, current = row[end - 2:end]
                height = max(previous.y1 - previous.y0, current.y1 - current.y0, .3)
                if current.x0 - previous.x1 > height * 2:
                    break  # A separate distant counter is not part of the date.
            words = row[start:end]
            text = squash("".join(w.text for w in words))
            if _DATE_RUN.fullmatch(text) or _MONEY_RUN.fullmatch(text):
                excluded.update(id(w) for w in words)
    return excluded


def _margin_candidates(page, result):
    """Whole observations in isolated margin cells, never cropped table tokens."""
    lines = common.page_lines(page, result)
    table_top = min((w.y0 for row in lines for w in row
                     if squash(w.text) in {"월별", "년월", "고지금액", "납부금액"}), default=100)
    sums = [w.y1 for row in lines for w in row if squash(w.text) == "합계"]
    # An unreadable table ending cannot turn a late body cell into a footer.
    table_bottom = max(sums) if sums else 100 if table_top < 100 else 0
    candidates = []
    for row in lines:
        full_text = squash("".join(w.text for w in row))
        if any(label in full_text for label in ("발급일", "조회기간", "생년월일", "출력일시")):
            continue
        excluded = _non_counter_words(row)
        row = [w for w in row if id(w) not in excluded]
        for left, right in ((0, 30), (35, 65), (65, 100)):
            touching = [w for w in row if w.x1 > left and w.x0 < right]
            words = [w for w in touching if left <= w.x0 <= w.x1 <= right]
            if any(_LIKE.search(squash(w.text)) for w in touching if w not in words):
                continue
            if not words:
                continue
            bounded = all(left <= w.x0 <= w.x1 <= right for w in words)
            margin = (all(0 <= w.y0 <= w.y1 <= min(18, table_top) for w in words) or
                      all(max(88, table_bottom) <= w.y0 <= w.y1 <= 100 for w in words))
            if not bounded or not margin:
                continue
            text = squash("".join(w.text for w in words))
            # Dates, query intervals and money must not become counter fragments.
            if (re.search(r"[0-9]{3,}|[.,~～년월일]", text) or text.count("/") + text.count("／") > 1 or
                    re.fullmatch(r"0[0-9][/／][0-9]{1,2}", text)):
                continue
            if _LIKE.search(text):
                candidates.append((text, min(w.conf for w in words)))
    return candidates


def shape_adopted(page, result):
    """Shape-only probe; never interpret masked digits as actual page values."""
    candidates = _margin_candidates(page, result)
    return (len(candidates) == 1 and _MARKER.fullmatch(candidates[0][0]) is not None and
            candidates[0][1] >= MIN_CONFIDENCE)


def _page_marker(page, result):
    candidates = _margin_candidates(page, result)
    if not candidates:
        return None, None, "ABSENT"
    if len(candidates) != 1:
        return None, None, "AMBIGUOUS"
    text, confidence = candidates[0]
    match = _MARKER.fullmatch(text)
    marker = [int(match[1]), int(match[2])] if match else None
    if marker is None or marker[0] > marker[1]:
        marker = None
    return marker, confidence, "READABLE" if marker and confidence >= MIN_CONFIDENCE else "UNREADABLE"


def _summary(markers, confidences, states, policy):
    certain = [m for m, c, s in zip(markers, confidences, states) if s == "READABLE"]
    totals = {m[1] for m in certain}
    expected = next(iter(totals)) if len(totals) == 1 else None
    if "AMBIGUOUS" in states or len(totals) > 1 or len({m[0] for m in certain}) != len(certain):
        status = "AMBIGUOUS"
    elif all(s == "ABSENT" for s in states):
        status = "NOT_REQUIRED" if policy == "NOT_REQUIRED" else "ABSENT"
    elif all(s == "READABLE" for s in states):
        status = "READABLE"
    else:
        status = "UNREADABLE"
    return status, expected


def collect(pages, *, policy="UNRESOLVED", uploaded_page_count=None):
    """Absence alone never identifies a markerless form; no such catalog is inferred."""
    if policy not in POLICIES:
        raise ValueError("INVALID_PAYMENT_PAGING_POLICY")
    observations = [_page_marker(page, result) for page, result in pages]
    markers = [value[0] for value in observations]
    confidences = [value[1] for value in observations]
    states = [value[2] for value in observations]
    if any(state != "ABSENT" for state in states):
        policy = "REQUIRED"
    status, expected = _summary(markers, confidences, states, policy)
    return {"version": 1, "policy": policy, "status": status,
            "uploaded_page_count": len(pages) if uploaded_page_count is None else uploaded_page_count,
            "form_page_indices": [page.page for page, _ in pages],
            "markers": markers, "marker_confidences": confidences, "marker_states": states,
            "expected_total": expected}


def assess(data):
    """Validate persisted evidence before returning a payment-only paging state."""
    try:
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            return "UNCERTAIN"
        count, indices = data["uploaded_page_count"], data["form_page_indices"]
        markers, confidences, states = data["markers"], data["marker_confidences"], data["marker_states"]
        policy = data["policy"]
        if (policy not in POLICIES or type(count) is not int or count < 1 or
                not isinstance(indices, list) or not indices or
                any(type(i) is not int or not 0 <= i < count for i in indices) or
                indices != sorted(set(indices)) or
                not all(isinstance(v, list) and len(v) == len(indices) for v in (markers, confidences, states))):
            return "UNCERTAIN"
        for marker, confidence, state in zip(markers, confidences, states):
            if state not in {"READABLE", "UNREADABLE", "ABSENT", "AMBIGUOUS"}:
                return "UNCERTAIN"
            if marker is not None and (not isinstance(marker, list) or len(marker) != 2 or
                    any(type(v) is not int for v in marker) or not 1 <= marker[0] <= marker[1] <= 99):
                return "UNCERTAIN"
            if confidence is not None and (type(confidence) not in (float, int) or
                    not math.isfinite(confidence) or not 0 <= confidence <= 1):
                return "UNCERTAIN"
            if state == "READABLE" and (marker is None or confidence is None or confidence < MIN_CONFIDENCE):
                return "UNCERTAIN"
            if state in {"ABSENT", "AMBIGUOUS"} and (marker is not None or confidence is not None):
                return "UNCERTAIN"
        status, expected = _summary(markers, confidences, states, policy)
        if data["status"] != status or data["expected_total"] != expected or (
                data["expected_total"] is not None and type(data["expected_total"]) is not int):
            return "UNCERTAIN"
        if status == "AMBIGUOUS":
            return "UNCERTAIN"
        # Even a partly unreadable received set cannot contain more physical
        # form pages than were uploaded. Do not use the document confidence.
        if expected is not None and expected > len(indices):
            return "INCOMPLETE"
        if status == "NOT_REQUIRED":
            return "NOT_REQUIRED"
        if status == "READABLE" and expected == len(indices):
            return "COMPLETE"
    except (KeyError, TypeError, ValueError):
        pass
    return "UNCERTAIN"


def statistics(data):
    """Value-free, file-local observations. Never a submission verdict."""
    empty = {"adopted": "X", "total_bucket": "UNREADABLE", "count_mismatch": "UNREADABLE"}
    if (not isinstance(data, dict) or data.get("status") == "AMBIGUOUS" or
            not _valid_uncertain(data)):
        return empty
    total = data.get("expected_total")
    if type(total) is not int:
        return empty
    return {"adopted": "O", "total_bucket": str(total) if total < 3 else "3_PLUS",
            "count_mismatch": "O" if total != len(data["form_page_indices"]) else "X"}


def fallback_allowed(data, page_count):
    """Only valid noncontradictory evidence can use separate table proof.

    A reliable excess is never waived by table proof. Explicit slots retain one
    file, so the assessment boundary compares that claim with physical pages.
    """
    state = assess(data)
    if not isinstance(data, dict) or type(page_count) is not int or data.get("uploaded_page_count") != page_count:
        return False
    if state == "INCOMPLETE":
        return False
    # Revalidate uncertain states with the same schema, substituting no values.
    if data.get("status") not in {"ABSENT", "UNREADABLE", "READABLE", "NOT_REQUIRED"}:
        return False
    expected = data.get("expected_total")
    if expected is not None and expected != len(data.get("form_page_indices", [])):
        return False
    if state == "UNCERTAIN":
        # assess() returns uncertainty both for malformed and unreadable records.
        # Only a byte-for-byte canonical collect payload shape can use fallback.
        return _valid_uncertain(data)
    return True


def _valid_uncertain(data):
    try:
        if type(data.get("version")) is not int or data["version"] != 1:
            return False
        count, indices = data["uploaded_page_count"], data["form_page_indices"]
        markers, confidences, states = data["markers"], data["marker_confidences"], data["marker_states"]
        if (data["policy"] not in POLICIES or type(count) is not int or count < 1 or
                not isinstance(indices, list) or not indices or indices != sorted(set(indices)) or
                any(type(i) is not int or not 0 <= i < count for i in indices) or
                not all(isinstance(v, list) and len(v) == len(indices) for v in (markers, confidences, states))):
            return False
        for marker, confidence, state in zip(markers, confidences, states):
            if state not in {"READABLE", "UNREADABLE", "ABSENT"}:
                return False
            if marker is not None and (not isinstance(marker, list) or len(marker) != 2 or
                    any(type(v) is not int for v in marker) or not 1 <= marker[0] <= marker[1] <= 99):
                return False
            if confidence is not None and (type(confidence) not in (int, float) or
                    not math.isfinite(confidence) or not 0 <= confidence <= 1):
                return False
            if state == "ABSENT" and (marker is not None or confidence is not None):
                return False
            if state == "READABLE" and (marker is None or confidence is None or confidence < MIN_CONFIDENCE):
                return False
            if state == "UNREADABLE" and confidence is None:
                return False
        status, expected = _summary(markers, confidences, states, data["policy"])
        return (status == data["status"] and expected == data["expected_total"] and
                (expected is None or type(data["expected_total"]) is int))
    except (KeyError, TypeError, ValueError):
        return False
