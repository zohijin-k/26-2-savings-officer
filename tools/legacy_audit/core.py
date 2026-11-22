"""Pure metadata rules. Audit grades never change administrative decisions."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

GRADES = ('NO_FLAG_FOUND', 'UNKNOWN', 'REVIEW_REQUIRED', 'HIGH', 'CRITICAL')


@dataclass(frozen=True)
class Requirement:
    slot: str
    accepted_types: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class Document:
    identifier: int
    slot: str
    status: str | None
    uploaded_at: str | None
    file_state: str
    merged: bool = False
    detected_type: str | None = None


@dataclass(frozen=True)
class VersionProof:
    """External submission-version evidence; absent in both current DB schemas.

    Accepted only after an independent provenance/binding adapter, synthetic in
    Phase 4A. A current hash or an unverified event alone is never such evidence.
    """
    document_id: int
    submitted_hash: str
    observed_hash: str
    submission_version_bound: bool = False


@dataclass(frozen=True)
class Application:
    identifier: int
    submitted_at: str | None
    documents: tuple[Document, ...]
    review_statuses: tuple[str, ...]
    requirements: tuple[Requirement, ...] | None
    proofs: tuple[VersionProof, ...] = ()
    metadata_incomplete: bool = False
    all_documents_must_pass: bool = False


@dataclass(frozen=True)
class Finding:
    code: str
    grade: str


@dataclass(frozen=True)
class Result:
    identifier: int
    grade: str
    findings: tuple[Finding, ...]
    review_required: bool


def timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value)
        # Current SQLite datetime fields are naive local timestamps. Do not
        # silently compare those to offset-aware external evidence.
        return result.astimezone(timezone.utc) if result.tzinfo else result
    except (TypeError, ValueError):
        return None


def classify(app: Application) -> Result:
    findings: dict[str, Finding] = {}

    def add(code: str, grade: str) -> None:
        findings[code] = Finding(code, grade)

    aggregate_pass = 'PASS' in app.review_statuses  # any stored historical PASS
    if not app.review_statuses:
        add('REVIEW_HISTORY_MISSING', 'UNKNOWN')
    if any(s not in {'PASS', 'FAIL', 'NEEDS_REVIEW'} for s in app.review_statuses):
        add('REVIEW_STATUS_UNKNOWN', 'UNKNOWN')
    if app.metadata_incomplete:
        add('METADATA_INCOMPLETE', 'UNKNOWN')
    submitted = timestamp(app.submitted_at)
    if submitted is None:
        add('SUBMISSION_TIME_UNKNOWN', 'UNKNOWN')
    legacy = any(d.slot.strip().lower() in {'', 'auto', 'unassigned'} or d.merged
                 for d in app.documents)
    if legacy:
        add('LEGACY_AUTO_OR_UNASSIGNED', 'REVIEW_REQUIRED')
        if aggregate_pass:
            add('LEGACY_WITH_AGGREGATE_PASS', 'HIGH')
    if any(d.slot.strip().lower() in {'', 'auto', 'unassigned'} for d in app.documents):
        add('DOCUMENT_UNASSIGNED', 'REVIEW_REQUIRED')
    if app.all_documents_must_pass and any(d.status != 'PASS' for d in app.documents):
        add('GENERIC_DOCUMENT_NOT_PASS', 'HIGH' if aggregate_pass else 'REVIEW_REQUIRED')
    by_slot: dict[str, list[Document]] = {}
    for doc in app.documents:
        by_slot.setdefault(doc.slot, []).append(doc)
        if doc.file_state != 'present':
            add('FILE_MISSING_OR_REFERENCE_INVALID', 'REVIEW_REQUIRED')
        uploaded = timestamp(doc.uploaded_at)
        if submitted is not None and uploaded is not None:
            if (submitted.tzinfo is None) != (uploaded.tzinfo is None):
                add('TIMESTAMP_BASIS_UNKNOWN', 'UNKNOWN')
            elif uploaded > submitted:
                add('POST_SUBMISSION_UPLOAD_SUSPECTED', 'REVIEW_REQUIRED')
        else:
            add('DOCUMENT_TIME_UNKNOWN', 'UNKNOWN')
    if any(len(rows) > 1 for rows in by_slot.values()):
        add('DUPLICATE_SLOT', 'REVIEW_REQUIRED')
    if app.requirements is None:
        add('REQUIREMENTS_UNKNOWN', 'UNKNOWN')
        if aggregate_pass:
            add('AGGREGATE_PASS_COMPLETENESS_UNPROVEN', 'REVIEW_REQUIRED')
    else:
        known_slots = {r.slot for r in app.requirements}
        for req in app.requirements:
            docs = by_slot.get(req.slot, [])
            if req.required and not docs:
                add('REQUIRED_SLOT_MISSING', 'REVIEW_REQUIRED')
            if req.required and any(d.status != 'PASS' for d in docs):
                add('REQUIRED_DOCUMENT_NOT_PASS', 'REVIEW_REQUIRED')
            if any(req.accepted_types and d.detected_type not in req.accepted_types for d in docs):
                add('SLOT_TYPE_EVIDENCE_INCOMPLETE', 'REVIEW_REQUIRED')
        if any(d.slot not in known_slots and d.slot not in {'auto', 'unassigned'} for d in app.documents):
            add('SLOT_NOT_IN_REQUIREMENTS', 'REVIEW_REQUIRED')
        incomplete_codes = {'REQUIRED_SLOT_MISSING', 'REQUIRED_DOCUMENT_NOT_PASS',
                            'SLOT_TYPE_EVIDENCE_INCOMPLETE', 'FILE_MISSING_OR_REFERENCE_INVALID',
                            'DUPLICATE_SLOT', 'SLOT_NOT_IN_REQUIREMENTS'}
        if aggregate_pass and incomplete_codes.intersection(findings):
            add('INCOMPLETE_WITH_AGGREGATE_PASS', 'HIGH')
    doc_ids = {d.identifier for d in app.documents}
    valid_proofs = {}
    for proof in app.proofs:
        valid_hashes = all(len(h) == 64 and all(c in '0123456789abcdef' for c in h)
                           for h in (proof.submitted_hash, proof.observed_hash))
        if not (proof.submission_version_bound and valid_hashes and proof.document_id in doc_ids):
            add('VERSION_EVIDENCE_UNVERIFIED', 'UNKNOWN')
            continue
        valid_proofs.setdefault(proof.document_id, []).append(proof)
    for doc in app.documents:
        proofs = valid_proofs.get(doc.identifier, [])
        if len(proofs) != 1:
            add('HISTORICAL_ORIGINAL_UNVERIFIABLE', 'UNKNOWN')
            if len(proofs) > 1:
                add('VERSION_EVIDENCE_AMBIGUOUS', 'UNKNOWN')
        elif proofs[0].submitted_hash != proofs[0].observed_hash:
            add('POST_SUBMISSION_ORIGINAL_CHANGE_PROVEN', 'CRITICAL')
    if not app.documents:
        add('HISTORICAL_ORIGINAL_UNVERIFIABLE', 'UNKNOWN')
    ordered = tuple(findings[k] for k in sorted(findings))
    grade = max((f.grade for f in ordered), key=GRADES.index, default='NO_FLAG_FOUND')
    return Result(app.identifier, grade, ordered, bool(ordered))


def summarize(results: tuple[Result, ...]) -> dict:
    """Counts are applications, deduplicated even when several rules match."""
    if len({r.identifier for r in results}) != len(results):
        raise ValueError('Duplicate normalized application')
    grades = Counter(r.grade for r in results)
    codes = Counter(f.code for r in results for f in r.findings)
    return {
        'scope': 'SYNTHETIC_ONLY', 'production_ready': False,
        'no_flag_is_safety_proof': False, 'applications_inspected': len(results),
        'grades': {g: grades[g] for g in GRADES},
        'signals_by_application': dict(sorted(codes.items())),
        'legacy_applications': codes['LEGACY_AUTO_OR_UNASSIGNED'],
        'legacy_with_aggregate_pass': codes['LEGACY_WITH_AGGREGATE_PASS'],
        'proven_post_submission_change': codes['POST_SUBMISSION_ORIGINAL_CHANGE_PROVEN'],
        'insufficient_original_history': codes['HISTORICAL_ORIGINAL_UNVERIFIABLE'],
        'review_required_applications': sum(r.review_required for r in results),
    }
