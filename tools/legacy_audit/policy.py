"""Repository policy boundary: reuse only pure checklist builders, never sessions."""
from __future__ import annotations

import re

from .core import Requirement

REPOSITORY = 'officer'


def requirements(program: str, context: dict, criteria: dict | None,
                 selections: list[dict], snapshot: dict | None) -> tuple[Requirement, ...] | None:
    if re.fullmatch(r'posting_[1-9][0-9]*', program):
        if REPOSITORY != 'youth' or not isinstance(snapshot, dict):
            return None
        raw = snapshot.get('requirements')
        if not isinstance(raw, list):
            return None
        try:
            rows = tuple(Requirement(
                r['slot_key'], tuple(r.get('accepted_doc_types') or [r['doc_type']]),
                r.get('required', True)) for r in raw)
            if any(not isinstance(r.slot, str) or not r.slot or not isinstance(r.required, bool)
                   or any(not isinstance(t, str) for t in r.accepted_types) for r in rows):
                return None
            return rows if len({r.slot for r in rows}) == len(rows) else None
        except (KeyError, TypeError):
            return None
    if program not in {'double_savings', 'job_package'} or not isinstance(criteria, dict):
        return None
    # No imports from models, criteria, generic_programs or API common: those
    # transitively load writable engine/session/default initialization paths.
    from demo.backend.rules.programs import get_program
    from demo.backend.rules.required_docs import ApplicantDocInput, WorkCategory, build_checklist
    from demo.backend.rules.subsidy import ITEM_ORDER, Selection

    try:
        category = context.get('work_category')
        category = WorkCategory(category) if category else None
        if program == 'double_savings' and category is None:
            return None  # dynamic work-proof requirements cannot be inferred
        if any(r.get('item_type') not in {str(k) for k in ITEM_ORDER} for r in selections):
            return None
        grouped = []
        for kind in ITEM_ORDER:
            selected = sorted((r for r in selections if r['item_type'] == str(kind)),
                              key=lambda r: r['count_index'])
            if selected:
                grouped.append(Selection(item_type=kind, count=len(selected),
                    receipts=[], linked_interview_indices=[r['linked_interview_index'] for r in selected]))
        if program == 'job_package' and (not grouped or not isinstance(criteria.get('subsidy_catalog'), list)):
            return None
        count = int(context.get('workplace_count') or 1)
        if not 1 <= count <= 100:
            return None
        rows = build_checklist(get_program(program), ApplicantDocInput(
            work_category=category, admin_fixed_term=bool(context.get('admin_fixed_term')),
            workplace_count=count,
            handwritten_admin_consent=bool(context.get('handwritten_admin_consent')),
            paper_admin_consent=bool((context.get('paper_forms') or {}).get('서식5')),
            subsidy_selections=grouped), criteria.get('subsidy_catalog', []))
        return tuple(Requirement(r.slot_key,
            () if r.slot_key == 'bank_account' else tuple(str(t) for t in r.doc_type_choices),
            r.required) for r in rows if r.upload or r.slot_key == 'bank_account')
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
