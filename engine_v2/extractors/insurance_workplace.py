"""Local, value-free proof envelope for scoped insurance-name review.

A digest binds the existing membership payload; it is not a registry or spelling
proof. This envelope must never be included in external summary projections.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping

CODE = "INSURANCE_WORKPLACE_NAME_INCONSISTENT"
REASON = "SAME_MANAGEMENT_NAME_CONFLICT"
STATE_FIELD = "사업장명칭상태"
REASON_FIELD = "사업장명칭불확실사유"
PROOF_FIELD = "사업장명칭불확실근거"
COUNT_FIELD = "사업장수상태"


def comparison_key(value: str) -> str:
    """Comparison only: preserve punctuation, suffixes and Hangul spelling."""
    return unicodedata.normalize("NFC", " ".join(value.split()))


def _rows_digest(rows_json: str) -> str:
    # Byte-separated hex cannot resemble an RRN in the existing privacy masker.
    return hashlib.sha256(rows_json.encode()).digest().hex(":")


def proof(rows_json: str, groups: list[list[int]]) -> str:
    return json.dumps({"version": 1, "rows_sha256": _rows_digest(rows_json),
                       "groups": groups}, separators=(",", ":"))


def name_review(fields: Mapping) -> bool:
    """Recognize a fresh conflict bound to the current membership observations.

    Fail closed for legacy, malformed, stale or mismatching states. The extractor
    owns source reliability; consumers validate its proof and current relation.
    """
    if (fields.get(STATE_FIELD) != "불확실" or fields.get(REASON_FIELD) != REASON or
            fields.get(COUNT_FIELD) != "미확정"):
        return False
    raw, evidence = fields.get("가입내역"), fields.get(PROOF_FIELD)
    if not isinstance(raw, str) or not isinstance(evidence, str):
        return False
    try:
        rows, data = json.loads(raw), json.loads(evidence)
        if (not isinstance(rows, list) or not isinstance(data, dict) or
                type(data.get("version")) is not int or data["version"] != 1 or
                data.get("rows_sha256") != _rows_digest(raw)):
            return False
        groups = data.get("groups")
        if not isinstance(groups, list) or not groups:
            return False
        used = set()
        for indices in groups:
            if (not isinstance(indices, list) or len(indices) < 2 or
                    any(type(i) is not int or i < 0 or i >= len(rows) for i in indices) or
                    len(set(indices)) != len(indices) or used.intersection(indices)):
                return False
            used.update(indices)
            numbers, names = set(), set()
            for i in indices:
                row = rows[i]
                if not isinstance(row, dict) or row.get("상태") != "가입":
                    return False
                number, name = row.get("사업장관리번호"), row.get("사업장명칭")
                if (not isinstance(number, str) or not re.fullmatch(r"[0-9]{11}", number) or
                        not isinstance(name, str) or not comparison_key(name)):
                    return False
                numbers.add(number)
                names.add(comparison_key(name))
            if len(numbers) != 1 or len(names) < 2:
                return False
        listed = json.loads(fields.get("사업장명칭목록", "null"))
        observed = list(dict.fromkeys(row.get("사업장명칭") for row in rows
                                     if isinstance(row, dict) and row.get("상태") == "가입"
                                     and isinstance(row.get("사업장명칭"), str) and row["사업장명칭"]))
        return listed == observed
    except (ValueError, TypeError, KeyError):
        return False
