"""Select observed calendar dates by policy meaning, never by a legacy alias."""
from datetime import date
import re
from collections.abc import Mapping

DATE_FIELDS = {
    "issue_date": "발급일", "payment_date": "결제일",
    "interview_date": "면접일", "exam_date": "응시일",
}


def document_date(fields: Mapping, basis: str) -> date | None:
    """A document date is a full ISO calendar day, not an instant or a prefix."""
    label = DATE_FIELDS.get(basis)
    value = fields.get(label) if label else None
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def requires_date(req, declared: date | None = None) -> bool:
    return req.date_basis != "none" and (
        (req.check_declared_date and declared is not None)
        or req.min_issue_date is not None or req.max_issue_date is not None
    )
