"""서류 체크리스트 · 업로드 즉시 판정 (P2).

두배적금은 **보완 요청이 없는 사업**이다. 제출 후에 미비를 알려주면 이미 늦다.
업로드 판정은 원래대로 저장하고, 신청자에게는 업로드 완료 또는 지정된 재업로드 사유만 돌려준다.

판정 로직은 `rules/doc_check.py`(엔진 단건 검사 재사용)에, 판독은 `ocr/`의 3계층
폴백 체인에 맡긴다. 여기서는 파일을 받아 저장하고 둘을 이어붙이는 일만 한다.
"""

import re
import logging
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import select

from ..models import transactional_write, async_session_transaction, stage_file_deletion
from ..application_writes import serialized_application_write
from .. import ocr_gate
from ..models import _session_bind
from ..upload_assessment import assess_nhis_identity, assess_upload
from ..models import UNASSIGNED_SLOT, Application, Document, SubsidyItem, get_session, session_transaction, STATUS_DRAFT
from ..ocr import read_document, split_pdf_pages
from ..rules.identity import identity_of
from ..ocr.base import OcrResult
from engine_v2.pipeline.privacy import mask_data
from ..rules.doc_check import check_document
from ..rules.doc_types import DocType
from ..rules.criteria import for_application, read_criteria
from ..rules.programs import get_program
from ..rules.required_docs import (
    ACCEPTED_FORMATS,
    WORK_CATEGORIES,
    DocRequirement,
    WorkCategory,
    find_slot,
)
from .common import (
    STORAGE,
    checklist_for,
    document_dict,
    list_documents as load_documents,
    load_application,
)

router = APIRouter(prefix="/api/applications", tags=["documents"])

DOCUMENTS = STORAGE / "documents"

#: 병합 PDF 자동 분리를 요청하는 슬롯 키.
AUTO_SLOT = "auto"

#: 파일명에서 경로 구분자와 제어문자를 제거한다. fixture 매칭을 위해 원래 이름은 유지한다.
_UNSAFE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")


class DocContextRequest(BaseModel):
    """체크리스트를 결정하는 입력. 근로유형이 바뀌면 목록이 실제로 바뀐다."""

    work_category: str | None = None
    admin_fixed_term: bool = False
    workplace_count: int = 1
    handwritten_admin_consent: bool = False
    paper_forms: dict[str, bool] = Field(default_factory=dict)


#: 다른 라우터와 같은 조회·직렬화를 쓴다 (`api/common.py` 참고).
_load = load_application
_checklist = checklist_for
_document_dict = document_dict
_list_documents = load_documents


def _requirement_dict(req: DocRequirement, uploaded: list[Document]) -> dict[str, Any]:
    mine = [d for d in uploaded if d.slot_key == req.slot_key]
    return {
        "slot_key": req.slot_key,
        "doc_type": str(req.doc_type),
        "doc_type_choices": [str(d) for d in req.doc_type_choices],
        "required_fields": req.required_fields,
        "label": req.label,
        "required": req.required,
        "upload": req.upload,
        "fulfilled_by": req.fulfilled_by,
        "requires_signature": req.requires_signature,
        "check_declared_date": req.check_declared_date,
        "date_basis": req.date_basis,
        "date_basis_label": {"issue_date": "발급일", "payment_date": "결제일", "interview_date": "면접일", "exam_date": "응시일", "none": "없음"}.get(req.date_basis, "발급일"),
        "min_issue_date": req.min_issue_date.isoformat() if req.min_issue_date else None,
        "max_issue_date": req.max_issue_date.isoformat() if req.max_issue_date else None,
        "issue_rule_label": req.notes[0] if req.notes else "날짜 기준 없음",
        "issuer": req.issuer,
        "issuer_url": req.issuer_url,
        "notes": req.notes,
        "warnings": req.warnings,
        "alternatives": req.alternatives,
        "accept": req.accept,
        "documents": [_document_dict(d) for d in mine],
    }


def _checklist_response(app: Application) -> dict[str, Any]:
    checklist = _checklist(app)
    program = get_program(app.program_code)
    criteria_version = for_application(app)
    criteria = read_criteria(criteria_version)
    uploaded = _list_documents(app.id or 0)
    items = [_requirement_dict(r, uploaded) for r in checklist]
    upload_items = [i for i in items if i["upload"]]
    done = [i for i in upload_items if i["documents"]]
    unassigned = [d for d in uploaded if d.slot_key == UNASSIGNED_SLOT]
    return {
        "context": app.doc_context_json or {},
        "work_categories": [str(c) for c in WORK_CATEGORIES],
        "accepted_formats": ACCEPTED_FORMATS,
        # 화면이 사업 코드로 분기하지 않도록, 무엇을 물어야 하는지를 여기서 알려준다.
        "program": {
            "code": program.code,
            "name": program.name,
            "selection": program.selection,
            "allows_supplement": criteria["supplement"]["allowed"],
            "supplement_days": criteria["supplement"]["days"],
            "announcement_date": criteria["announcement_date"],
            "application_period": criteria["application_period"],
            "application_period_2": criteria.get("application_period_2"),
            "criteria_version": criteria_version.version,
            "paper_forms": criteria["paper_forms"],
            "nhis_payment_months": criteria["nhis_payment_months"],
            "nhis_acquisition_loss_years": criteria["nhis_acquisition_loss_years"],
            #: 근로확인서류가 있는 사업에서만 근로유형을 묻는다.
            "asks_work_category": program.has_work_requirement,
            #: 지원 항목을 먼저 골라야 추가서류가 생기는 사업인가.
            "has_subsidy_items": program.has_subsidy_items,
        },
        "items": items,
        "upload_total": len(upload_items),
        "upload_done": len(done),
        "unassigned": [_document_dict(d) for d in unassigned],
        # Preserve response shape without exposing internal verdict thresholds.
        "assumption_notes": [],
    }


@router.get("/{application_id}/required-documents")
def required_documents(application_id: int) -> dict[str, Any]:
    """저장된 근로유형 기준의 맞춤 체크리스트 (R3.2)."""
    return _checklist_response(_load(application_id))


@router.put("/{application_id}/doc-context")
@transactional_write
def set_doc_context(application_id: int, body: DocContextRequest) -> dict[str, Any]:
    """근로유형 등을 저장하고, 바뀐 체크리스트를 바로 돌려준다."""
    if body.work_category:
        try:
            WorkCategory(body.work_category)
        except ValueError:
            raise HTTPException(400, f"알 수 없는 근로유형: {body.work_category}") from None

    with get_session() as s:
        app = s.get(Application, application_id)
        if app is None:
            raise HTTPException(404, "신청 건을 찾을 수 없습니다.")
        from ..models import STATUS_DRAFT
        if app.status != STATUS_DRAFT:
            raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
        criteria = read_criteria(for_application(app))
        for form_no, enabled in body.paper_forms.items():
            if form_no not in criteria["paper_forms"] or not isinstance(enabled, bool):
                raise HTTPException(400, "스캔본 제출 서식 설정이 올바르지 않습니다.")
            if enabled and not criteria["paper_forms"][form_no]:
                raise HTTPException(400, "이 서식은 스캔본 제출을 허용하지 않습니다.")
        old = app.doc_context_json or {}
        new_context = body.model_dump()
        # Partial client updates preserve other independent choices.
        if not body.paper_forms:
            new_context["paper_forms"] = old.get("paper_forms", {})
        app.doc_context_json = new_context
        app.updated_at = datetime.now()
        s.add(app)
        s.commit()
        s.refresh(app)
        return _checklist_response(app)


#: 업로드 본문을 옮겨 적는 조각 크기.
_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _receive_upload(file: UploadFile) -> Path:
    """업로드 본문을 조각 단위로 신청 저장소 **밖**의 임시 파일에 받는다 (11-27 자원 보호).

    전에는 `await file.read()`로 파일 전체를 메모리에 올렸다(크기 제한 없는 계약은 그대로 둔다: 프런트는 20MB부터
    '시간이 더 걸릴 수 있다'고만 알린다). 본문을 기다리는 동안 신청이 제출될 수 있으므로 저장소에는 아직 아무것도 만들지
    않는다 — 호출하는 쪽이 초안 상태를 다시 확인한 뒤 `_place_upload`로 옮긴다(제출된 신청의 저장소 불변).
    """
    import os
    import tempfile

    descriptor, name = tempfile.mkstemp(prefix="jeonbuk-upload-")
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as out:
            while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
                out.write(chunk)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return staged


def _place_upload(staged: Path, path: Path) -> None:
    """임시 파일을 저장 위치로 옮겨 적고 임시 파일을 지운다 (기다림 없음: 초안 확인과 저장 사이에 다른 요청이 끼지 않는다)."""
    import shutil

    try:
        with staged.open("rb") as source, path.open("wb") as out:
            shutil.copyfileobj(source, out, _UPLOAD_CHUNK_BYTES)
    finally:
        staged.unlink(missing_ok=True)


async def _store_upload(file: UploadFile, path: Path) -> None:
    """업로드 파일을 조각 단위로 `path`에 바로 옮겨 적는다 (저장 위치를 이미 만든 흐름용)."""
    with path.open("wb") as out:
        while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
            out.write(chunk)


def _safe_name(name: str) -> str:
    cleaned = _UNSAFE.sub("_", Path(name).name).strip()
    return cleaned or "upload"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    from ..rules.document_dates import document_date

    parsed = document_date({"발급일": value}, "issue_date")
    if parsed is None:
        raise HTTPException(400, "발급일은 YYYY-MM-DD 형식으로 입력해 주세요.")
    return parsed


def _ocr_json(ocr: OcrResult) -> dict[str, Any]:
    return mask_data({
        "detected_doc_type": str(ocr.detected_doc_type) if ocr.detected_doc_type else None,
        "confidence": ocr.confidence,
        "image_quality": ocr.image_quality,
        "issue_date": ocr.issue_date.isoformat() if ocr.issue_date else None,
        "fields": dict(ocr.fields),
        "bboxes": ocr.bboxes_as_dict(),
        "is_encrypted": ocr.is_encrypted,
        "is_screen_capture": ocr.is_screen_capture,
        "page_count": ocr.page_count,
        "tier": ocr.tier,
        # 판독 엔진·대체 사유는 담당자 화면(officer.py)만 읽는다. 신청자 응답(document_dict)에는 없다.
        "engine": ocr.engine,
        "fallback_reason": ocr.fallback_reason,
        "quality_note": ocr.quality_note,
        "classification_evidence": ocr.classification_evidence,
        "classification_confidence": ocr.classification_confidence,
        "elapsed_ms": ocr.elapsed_ms,
    })


def _require_draft(application_id: int) -> Application:
    # Read the current row, not an Application detached before lock acquisition.
    app = _load(application_id)
    if app.status != STATUS_DRAFT:
        raise HTTPException(409, "제출한 신청서의 서류는 변경하거나 삭제할 수 없습니다.")
    return app


@serialized_application_write
@transactional_write
def _save_row(
    app: Application,
    req: DocRequirement | None,
    slot_key: str,
    path: Path,
    ocr: OcrResult,
    declared: date | None,
    findings: list[dict[str, str]],
    status: str,
    *,
    page_index: int | None = None,
    source_file_path: str | None = None,
) -> Document:
    _require_draft(app.id or 0)
    row = Document(
        application_id=app.id or 0,
        slot_key=slot_key,
        doc_type=str(ocr.detected_doc_type) if ocr.detected_doc_type else None,
        expected_doc_type=str(req.doc_type) if req else None,
        file_path=str(path.relative_to(STORAGE.parent)),
        file_format=path.suffix.lstrip(".").lower(),
        declared_issue_date=declared,
        ocr_json=_ocr_json(ocr),
        stage1_status=status,
        findings_json=mask_data(findings),
        page_index=page_index,
        source_file_path=source_file_path,
    )
    with get_session() as s:
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


@serialized_application_write
@transactional_write
def _refresh_nhis_identity(application_id: int, app: Application, checklist: list[DocRequirement]) -> None:
    """건강보험 납부·자격확인서는 짝 서류가 도착할 때마다 함께 다시 대조한다."""
    _require_draft(application_id)
    all_rows = _list_documents(application_id)
    for row, result in assess_nhis_identity(identity_of(app.identity_json), checklist, all_rows):
        with get_session() as session:
            saved = session.get(Document, row.id)
            if saved is not None:
                saved.stage1_status = result.status
                saved.findings_json = mask_data([finding.as_dict() for finding in result.findings])
                session.add(saved)
                session.commit()


@serialized_application_write
@transactional_write
def _replace_existing(application_id: int, slot_key: str) -> None:
    """같은 슬롯에 다시 올리면 이전 것을 지운다. 재업로드가 기본 동선이다."""
    _require_draft(application_id)
    with get_session() as s:
        for old in s.exec(
            select(Document)
            .where(Document.application_id == application_id)
            .where(Document.slot_key == slot_key)
        ).all():
            s.delete(old)
        s.commit()


@router.post("/{application_id}/documents")
@serialized_application_write
async def upload_document(
    application_id: int,
    file: UploadFile = File(...),
    slot_key: str = Form(AUTO_SLOT),
    declared_issue_date: str | None = Form(None),
) -> dict[str, Any]:
    """파일 1개를 받아 즉시 1단계 판정을 돌려준다 (R2.1).

    자동 분류 업로드는 지원하지 않으므로 서류 종류에 맞는 슬롯을 명시해야 한다.
    """
    if not slot_key or slot_key == AUTO_SLOT:
        raise HTTPException(
            400,
            "자동 서류 분류 업로드는 현재 지원하지 않습니다. 서류 종류에 맞는 업로드 항목을 선택해 다시 제출해 주세요.",
        )

    app = _load(application_id)
    checklist = _checklist(app)

    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    if suffix not in ACCEPTED_FORMATS:
        raise HTTPException(
            400,
            f"pdf, jpg, png 파일만 올릴 수 있습니다. (올리신 형식: {suffix or '알 수 없음'})",
        )

    target_slot = slot_key
    req = find_slot(checklist, target_slot)
    if req is None or not req.upload:
        raise HTTPException(400, f"업로드 대상이 아닌 슬롯입니다: {target_slot}")

    _require_draft(application_id)
    declared = _parse_date(declared_issue_date)
    # 11-28: 판독 자리를 먼저 잡는다. 판독 대기열이 가득하면 본문을 옮기거나 저장소에 쓰기 전에 503으로 거절한다.
    with ocr_gate.reserve() as reading:
        return await _assess_and_save(application_id, app, checklist, req, file, declared, reading)


def _discard_upload(path: Path, dest_dir: Path) -> None:
    """저장하지 못한 업로드의 파일과 그 판(版) 폴더를 지운다."""
    path.unlink(missing_ok=True)
    dest_dir.rmdir()


async def _assess_and_save(
    application_id: int,
    app: Application,
    checklist: list[DocRequirement],
    req: DocRequirement,
    file: UploadFile,
    declared: date | None,
    reading: ocr_gate.OcrTicket,
) -> dict[str, Any]:
    """본문을 받아 저장소에 두고, 판독·판정(작업 스레드)한 뒤 초안 상태를 다시 확인해 한 번에 저장한다."""
    # Keep the original basename for the fixture/reader contract, but stage
    # each version in a unique directory so existing bytes are never overwritten.
    staged = await _receive_upload(file)
    try:
        _require_draft(application_id)
        dest_dir = DOCUMENTS / app.application_no / req.slot_key / uuid4().hex
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / _safe_name(file.filename or "upload")
    except BaseException:
        staged.unlink(missing_ok=True)
        raise

    def receipt_amount_loader() -> int | None:
        parts = req.slot_key.split("_")
        try:
            item_type, index = parts[0], int(parts[1])
        except (IndexError, ValueError):
            item_type, index = "", 0
        with get_session() as session:
            item = session.exec(select(SubsidyItem)
                                .where(SubsidyItem.application_id == application_id)
                                .where(SubsidyItem.item_type == item_type)
                                .where(SubsidyItem.count_index == index)).first()
        return item.receipt_amount if item is not None else None

    try:
        _place_upload(staged, path)
        prepared_inputs = app.model_dump()
        with get_session() as session:
            prepared_items = [item.model_dump() for item in session.exec(
                select(SubsidyItem).where(SubsidyItem.application_id == application_id)
                .order_by(SubsidyItem.id)).all()]
        # 11-28: 판독·판정은 이벤트 루프가 아니라 판독 작업 스레드에서 돈다(ocr_gate: 프로세스당 한 건씩, 대기 상한).
        # 기다리는 동안 다른 요청이 처리되므로, 아래에서 초안 상태와 입력값을 지금까지처럼 다시 확인한 뒤 저장한다.
        if _session_bind.get() is not None:
            raise RuntimeError("document reads must be dispatched outside the SQLite writer reservation")
        ocr, result = await reading.run(
            assess_upload,
            path, req,
            identity=identity_of(app.identity_json),
            declared=declared,
            checklist=checklist,
            uploaded_loader=lambda: _list_documents(application_id),
            paper_admin_consent=bool(((app.doc_context_json or {}).get("paper_forms") or {}).get("서식5")),
            receipt_amount_loader=receipt_amount_loader,
            reader=read_document,
        )

        async with async_session_transaction():
            current = _require_draft(application_id)
            with get_session() as session:
                current_items = [item.model_dump() for item in session.exec(
                    select(SubsidyItem).where(SubsidyItem.application_id == application_id)
                    .order_by(SubsidyItem.id)).all()]
            if current.model_dump() != prepared_inputs or current_items != prepared_items:
                raise HTTPException(409, "신청 내용이 바뀌었습니다. 서류를 다시 업로드해 주세요.")
            app = current
            _require_draft(application_id)
            _replace_existing(application_id, req.slot_key)
            row = _save_row(
                app,
                req,
                req.slot_key,
                path,
                ocr,
                declared,
                [f.as_dict() for f in result.findings],
                result.status,
            )
            if req.doc_type in (DocType.NHIS_PAYMENT, DocType.NHIS_QUALIFICATION) or ocr.detected_doc_type in (
                DocType.NHIS_PAYMENT, DocType.NHIS_QUALIFICATION,
            ):
                _refresh_nhis_identity(application_id, app, checklist)
                row = next((d for d in _list_documents(application_id) if d.id == row.id), row)
            return _document_dict(row)
    except BaseException:
        # 취소된 요청의 판독이 아직 작업 스레드에서 돌고 있으면 그 판독이 끝난 뒤에 지운다(읽는 중인 파일을 지우지 않는다).
        reading.after_read(lambda: _discard_upload(path, dest_dir))
        raise


@serialized_application_write
async def _upload_merged(
    app: Application, checklist: list[DocRequirement], file: UploadFile
) -> dict[str, Any]:
    """병합 PDF를 페이지 단위로 쪼개 슬롯에 자동 배정한다 (R3.5).

    공고문은 "1개의 파일로 압축하여 올려야 함"을 요구한다. 기존 방식대로 합쳐
    올린 신청자도 그대로 받되, 페이지별 판별 결과로 슬롯을 채운다. 배정되지 않은
    페이지만 신청자에게 되묻는다.
    """
    _require_draft(app.id or 0)
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "여러 서류를 한 파일로 올리는 기능은 pdf만 지원합니다.")

    base = DOCUMENTS / app.application_no / "_merged"
    base.mkdir(parents=True, exist_ok=True)
    source = base / _safe_name(file.filename or "merged.pdf")
    await _store_upload(file, source)

    pages = split_pdf_pages(str(source), base, source.stem)
    if not pages:
        # 암호 PDF 등으로 쪼개지 못한 경우. 판독을 돌려 사유를 그대로 보여준다.
        ocr = read_document(str(source), None)
        placeholder = DocRequirement(
            slot_key=UNASSIGNED_SLOT,
            doc_type=DocType.RESIDENT_ABSTRACT,
            label="병합 업로드 파일",
            check_declared_date=False,
        )
        result = check_document(placeholder, ocr, None, "pdf")
        row = _save_row(
            app,
            None,
            UNASSIGNED_SLOT,
            source,
            ocr,
            None,
            [f.as_dict() for f in result.findings],
            result.status,
        )
        return {
            "mode": "merged",
            "source_file": source.name,
            "page_count": 0,
            "assigned": [],
            "unassigned": [_document_dict(row)],
        }

    taken = {d.slot_key for d in _list_documents(app.id or 0)}
    assigned: list[dict[str, Any]] = []
    unassigned: list[dict[str, Any]] = []
    rel_source = str(source.relative_to(STORAGE.parent))

    for index, page_path, ocr in pages:
        req = None
        if ocr.detected_doc_type is not None:
            for candidate in checklist:
                if (
                    candidate.upload
                    and candidate.accepts(ocr.detected_doc_type)
                    and candidate.slot_key not in taken
                ):
                    req = candidate
                    break

        if req is None:
            row = _save_row(
                app,
                None,
                UNASSIGNED_SLOT,
                page_path,
                ocr,
                None,
                [],
                "NEEDS_REVIEW",
                page_index=index,
                source_file_path=rel_source,
            )
            unassigned.append(_document_dict(row))
            continue

        taken.add(req.slot_key)
        result = check_document(req, ocr, None, "pdf", identity_of(app.identity_json))
        _replace_existing(app.id or 0, req.slot_key)
        row = _save_row(
            app,
            req,
            req.slot_key,
            page_path,
            ocr,
            None,
            [f.as_dict() for f in result.findings],
            result.status,
            page_index=index,
            source_file_path=rel_source,
        )
        assigned.append(_document_dict(row))

    if any(doc["slot_key"] in {"nhis_payment", "nhis_qualification"} for doc in assigned):
        _refresh_nhis_identity(app.id or 0, app, checklist)
        refreshed = {d.id: d for d in _list_documents(app.id or 0)}
        assigned = [
            _document_dict(refreshed[doc["document_id"]])
            if doc["document_id"] in refreshed else doc
            for doc in assigned
        ]

    return {
        "mode": "merged",
        "source_file": source.name,
        "page_count": len(pages),
        "assigned": assigned,
        "unassigned": unassigned,
    }


@router.get("/{application_id}/documents")
def list_documents(application_id: int) -> list[dict[str, Any]]:
    _load(application_id)
    return [_document_dict(d) for d in _list_documents(application_id)]


@router.delete("/{application_id}/documents/{document_id}")
@serialized_application_write
def delete_document(application_id: int, document_id: int) -> dict[str, str]:
    """재업로드를 위한 삭제. 파일도 같이 지운다."""
    app = _require_draft(application_id)
    checklist = _checklist(app)
    nhis_types = {str(DocType.NHIS_PAYMENT), str(DocType.NHIS_QUALIFICATION)}
    refresh_nhis = False
    target = None
    staged = None
    try:
        with session_transaction():
            app = _require_draft(application_id)
            checklist = _checklist(app)
            with get_session() as s:
                row = s.get(Document, document_id)
                if row is None or row.application_id != application_id:
                    raise HTTPException(404, "서류를 찾을 수 없습니다.")
                refresh_nhis = row.doc_type in nhis_types or row.expected_doc_type in nhis_types
                target = STORAGE.parent / row.file_path
                if target.exists():
                    staged = target.with_name(target.name + ".deleting-" + uuid4().hex)
                    stage_file_deletion(target, staged)
                s.delete(row)
                s.commit()
            if refresh_nhis:
                _refresh_nhis_identity(application_id, app, checklist)
    except BaseException:
        if staged is not None and staged.exists():
            staged.rename(target)
        raise
    if staged is not None:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            # The logical deletion has committed. Retain the tombstone for
            # operational cleanup; do not turn a committed delete into a 500.
            logging.getLogger(__name__).warning("문서 삭제 후 임시 파일 정리를 완료하지 못했습니다.")
    return {"deleted": str(document_id)}
