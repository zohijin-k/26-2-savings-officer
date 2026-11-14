"""Observed payment table proof; folios cannot supply completeness or income."""
from __future__ import annotations

from datetime import date
import json
import re

from . import nhis_payment, payment_period, nhis_common as common
from ..pipeline.layout import squash

FIELD = "납부표완전성자료"
FINANCIAL_FIELDS = (
    "월별고지금액", "월별장기요양보험료", "월별보수외소득월액_건강", "월별납부내역",
    "합계자료", "납부총액", "건강보험료", "장기요양보험료", "보수외소득월액_건강",
)


def period_statistics(data):
    """Value-free necessary-condition observation; other blockers may coexist."""
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        return "UNREADABLE"
    status = data.get("period_status")
    if status not in {"READABLE", "UNDETERMINED", "CONFLICT"}:
        return "UNREADABLE"
    return "X" if status == "READABLE" else "O"


def _issue_read(extraction, pages):
    issue = extraction.fields.get("발급일")
    if issue is None or issue.bbox is None or issue.confidence < .85:
        return False
    try:
        date.fromisoformat(str(issue.value))
    except (TypeError, ValueError):
        return False
    box = issue.bbox
    observed = []
    for page, result in pages:
        if page.page != box.page:
            continue
        for word in result.words:
            x0,y0,x1,y1 = word.bbox_px
            x,y = page.px_to_pt((x0+x1)/2,(y0+y1)/2)
            if box.x0-.1 <= x <= box.x1+.1 and box.y0-.1 <= y <= box.y1+.1:
                observed.append(word.confidence)
    return bool(observed) and min(observed) >= .85


def collect(pages, extraction):
    checks = {v.name: v.passed for v in extraction.validations}
    required = ["monthly_rows_found", "months_continuous", "monthly_amounts_numeric", "monthly_total_matches"]
    printed = False
    if "합계자료" in extraction.fields:
        required += ["paid_total_matches", "payment_columns", "payment_component_headers",
                     "payment_group_headers", "payment_sum_row", "numeric_cell_corrections"]
        required += [f"payment_column_{i}_sum" for i in range(1,9)]
        totals = extraction.fields["합계자료"].value
        if isinstance(totals, str):
            try:
                totals = json.loads(totals)
            except (ValueError, TypeError):
                totals = None
        printed = isinstance(totals, list) and len(totals) == 8
    else:
        parsed = nhis_payment._extract_monthly(pages)
        printed = bool(parsed[3]) and parsed[13]
        if parsed[5]:
            required.append("paid_total_matches")
    # Do not trust arithmetic's legacy 'no total means no mismatch' shortcut.
    sum_rows = [row for page,result in pages for row in common.page_lines(page,result)
                if any(squash(w.text) == "합계" for w in row)]
    printed = bool(printed and sum_rows and all(w.conf >= .85 for row in sum_rows for w in row))
    months = []
    monthly = None
    try:
        monthly = json.loads(extraction.fields["월별고지금액"].value)
        if isinstance(monthly, dict):
            months = sorted(monthly)
    except (KeyError, ValueError, TypeError):
        pass
    period = payment_period.collect(pages, extraction)
    issue = extraction.fields.get("발급일")
    return {"version": 1, "months": months, "period": period["period"],
            "monthly_values": monthly, "issue_date": str(issue.value) if issue else None,
            "financial_fields": {key: str(extraction.fields[key].value)
                                 for key in FINANCIAL_FIELDS if key in extraction.fields},
            "period_status": period["status"], "printed_total_observed": bool(printed),
            "arithmetic_complete": all(checks.get(name) is True for name in required),
            "issue_information_read": _issue_read(extraction,pages)}


def confirmed(data, fields, issue_date, requested_months):
    """Validate persisted source proof and require every printed query month."""
    try:
        if (not isinstance(data,dict) or type(data.get("version")) is not int or data["version"] != 1 or
                data.get("period_status") != "READABLE" or
                any(data.get(k) is not True for k in ("printed_total_observed", "arithmetic_complete", "issue_information_read"))):
            return False
        if data.get("financial_fields") != {key: fields[key] for key in FINANCIAL_FIELDS if key in fields}:
            return False
        period, months = data["period"], data["months"]
        if (not isinstance(period,list) or len(period)!=2 or not isinstance(months,list) or not months or
                any(not isinstance(m,str) or not re.fullmatch(r"20[0-9]{2}-(?:0[1-9]|1[0-2])",m) for m in period+months) or
                months != sorted(set(months)) or period[0]>period[1]):
            return False
        independent = json.loads(fields[payment_period.FIELD])
        if independent.get("status") != "READABLE" or independent.get("period") != period:
            return False
        monthly = json.loads(fields["월별고지금액"])
        if (not isinstance(monthly,dict) or sorted(monthly) != months or
                any(not isinstance(v,str) or re.fullmatch(r"[0-9]+",v) is None for v in monthly.values()) or
                data.get("monthly_values") != monthly):
            return False
        if (issue_date is None or data.get("issue_date") != fields["발급일"] or
                date.fromisoformat(fields["발급일"]) != issue_date):
            return False
        needed = set(requested_months)
        year,month = map(int,period[0].split("-"))
        while f"{year:04}-{month:02}" <= period[1]:
            needed.add(f"{year:04}-{month:02}")
            month+=1
            if month==13:
                year+=1;month=1
        return all(m in months for m in needed)
    except (KeyError, ValueError, TypeError, AttributeError):
        return False
