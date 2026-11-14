"""Sequential, resumable local assessment; never retain document values.

Run with ``python -B -m engine_v2.tools.batch_assess``. Only this tool's
explicit metadata projection reaches disk. Private values live for one file;
all production callables run under the shared quiet/read-only boundary.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
import fcntl
import io
import json
import math
import os
from pathlib import Path
import re
import time
from types import SimpleNamespace
from unittest.mock import patch
import uuid

VERSION = 1
POLICY = "double_savings_document_v1"
EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".heic", ".gif", ".jfif"})
KINDS = frozenset("""ADMIN_INFO_CONSENT INSURANCE_4 DAILY_WORK_RECORD LABOR_CONTRACT
BIZ_REG_PROOF FARM_BIZ_CERT FISHERY_BIZ_CERT NHIS_PAYMENT NHIS_QUALIFICATION
NHIS_ACQUISITION_LOSS RESIDENT_ABSTRACT INTERVIEW_CONFIRMATION PAYMENT_RECEIPT
ID_PHOTO_COPY EXAM_CONFIRMATION EXAM_TRANSCRIPT RESIDENT_CERTIFICATE BIZ_REG_CERT
REGISTRATION_CONFIRMATION ADMISSION_TICKET X""".split())
_PERSON = ("성명", "생년월일", "발급일")
_RESIDENT = ("name", "birth_date", "issue_date", "issuer", "applicant_name",
             "applicant_birth_date", "address_history_count", "address_history", "current_address")
_GENERIC = ("성명", "생년월일", "발급일", "전입일", "가구원수", "건강보험료")
# Fixed semantic extractor keys only; no confidence, validation or evidence keys.
FIELDS = {kind: _GENERIC for kind in KINDS - {"X"}}
FIELDS.update({
    "RESIDENT_ABSTRACT": _RESIDENT, "RESIDENT_CERTIFICATE": _RESIDENT,
    "NHIS_PAYMENT": _PERSON + ("사업장명칭", "납부자번호", "문서확인번호", "용도구분",
        "조회기간", "가입구분", "월별고지금액", "월별장기요양보험료", "월별보수외소득월액_건강",
        "보수외소득월액_건강", "고지월", "건강보험료", "장기요양보험료", "납부총액", "월별납부내역"),
    "NHIS_QUALIFICATION": _PERSON + ("가구원수", "가구원목록", "자격확인요청일", "사업장관리번호"),
    "NHIS_ACQUISITION_LOSS": _PERSON + ("가입구분", "취득일", "변동내역", "자격이력자료"),
    "INSURANCE_4": _PERSON + ("문서확인번호", "발급번호", "가입내역", "보험별가입여부",
        "보험별가입자종별", "근로관련가입여부", "근로관련최초취득일", "근로관련최근취득일", "사업장명칭목록"),
    "BIZ_REG_PROOF": ("발급번호", "과세유형", "상호", "사업자등록번호", "성명", "생년월일",
        "사업장소재지", "개업일", "사업자등록일", "업태", "종목", "공동사업자유무", "발급일"),
    "DAILY_WORK_RECORD": _PERSON + ("발급번호", "조회기간", "보험구분", "발급번호목록", "일용근로내역자료"),
    "PAYMENT_RECEIPT": ("결제금액", "결제일", "상호", "받는분", "사업자등록번호", "결제수단", "공급가액", "부가세", "품목수"),
    "EXAM_CONFIRMATION": _PERSON + ("시험명", "응시일"),
    "EXAM_TRANSCRIPT": _PERSON + ("시험명", "응시일"),
    "INTERVIEW_CONFIRMATION": ("성명", "생년월일", "회사명", "업태업종", "면접장소", "응시직군", "면접일", "면접시간", "확인일"),
    "ADMIN_INFO_CONSENT": _PERSON + ("동의여부", "서명잉크확인"),
})
WORK_MAPPING = {"INSURANCE_4": "직장가입자", "BIZ_REG_PROOF": "사업소득 사업자"}
DATE_CODES = frozenset({"DOCUMENT_ISSUED_TOO_EARLY", "DOCUMENT_ISSUED_AFTER_APPLICATION"})
QUALITY_CODES = frozenset({"UNKNOWN_DOCUMENT_TYPE", "LOW_OCR_CONFIDENCE", "LOW_IMAGE_QUALITY",
    "IMAGE_RESOLUTION_TOO_LOW", "PAGES_INCOMPLETE", "PAGES_DUPLICATED", "PAGES_UNREADABLE",
    "UNREADABLE_FILE", "REQUIRED_FIELD_UNREADABLE", "MISSING_REQUIRED_FIELD"})
CODES = frozenset("""NONE ARGUMENT_ERROR LOCATION_REJECTED INPUT_UNAVAILABLE INPUT_OUTPUT_OVERLAP
RESUME_INVALID RUN_INCOMPATIBLE OUTPUT_ERROR OUTPUT_LOCKED OPEN_ERROR DECODE_ERROR ENCRYPTED
EMPTY_DOCUMENT OCR_ERROR EXTRACTION_ERROR ASSESSMENT_ERROR PROCESSING_ERROR ENGINE_UNAVAILABLE
ENGINE_NOT_REQUESTED CLASSIFICATION_FAILED SLOT_UNAVAILABLE WORK_CATEGORY_UNMAPPED
NOT_APPLICABLE ENGINE_FAILED DIFFERENT_KIND REFERENCE_ERROR INTERRUPTED GUARD_BLOCKED""".split())
STATES = frozenset({"OK", "ERROR", "SKIPPED", "NOT_REQUESTED", "NOT_APPLICABLE"})
_NETWORK = []
_HOOK = False


class BatchError(Exception):
    """Carries only a tool-owned fixed code."""


def _fail(code):
    raise BatchError(code)


def _exception(exc):
    name = type(exc).__name__
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name) else "Exception"


def _network_audit(event, args):
    if _NETWORK and event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo",
                               "socket.gethostbyname", "socket.sendto", "urllib.Request"}:
        for guard in _NETWORK:
            guard[0] = True
        _fail("GUARD_BLOCKED")


@contextmanager
def guarded():
    """Suppress Python/native/log output and reject even swallowed write/network attempts."""
    global _HOOK
    from demo.backend.tools.verify_upload import quiet_assessment
    if not _HOOK:
        sys.addaudithook(_network_audit)
        _HOOK = True
    flag = [False]
    with quiet_assessment():
        _NETWORK.append(flag)
        try:
            yield
        finally:
            _NETWORK.pop()
            if flag[0]:
                _fail("GUARD_BLOCKED")


def _location(path):
    from demo.backend.tools.verify_cases import _private_location
    try:
        return _private_location(path)
    except Exception:
        _fail("LOCATION_REJECTED")


def _target(path):
    path = Path(path)
    if path.is_symlink():
        _fail("LOCATION_REJECTED")
    actual = _location(path)
    if actual.exists() and (not actual.is_file() or actual.stat().st_nlink != 1):
        _fail("LOCATION_REJECTED")
    return actual


def _open(path, flags):
    path = _target(path)
    return os.open(path, flags | os.O_NOFOLLOW, 0o600)


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("RESUME_INVALID")
        result[key] = value
    return result


def _load(data):
    try:
        return json.loads(data, object_pairs_hook=_pairs,
                          parse_constant=lambda _: _fail("RESUME_INVALID"))
    except (ValueError, UnicodeError):
        _fail("RESUME_INVALID")


def _incomplete_tail(data):
    """Recognize encoder prefixes, never complete-but-invalid metadata records."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        if exc.reason != "unexpected end of data" or exc.end != len(data):
            return False
        text = data[:exc.start].decode("utf-8")
    if not text.lstrip().startswith("{"):
        return False
    try:
        # Default parsing is intentional here: duplicate keys/NaN are complete
        # JSON syntax, so they must be rejected by _load, never truncated.
        json.loads(text)
    except json.JSONDecodeError as exc:
        end = len(text.rstrip())
        if exc.pos >= end or exc.msg.startswith("Unterminated string"):
            return True
        suffix = text[exc.pos:]
        if exc.msg == "Expecting value":
            return suffix == "-" or any(token.startswith(suffix) for token in ("true", "false", "null"))
        if exc.msg == "Invalid \\uXXXX escape":
            return bool(re.fullmatch(r"u[0-9a-fA-F]{0,3}", suffix))
        if exc.msg == "Expecting ',' delimiter" and re.fullmatch(r"(?:\.|[eE][+-]?)", suffix):
            return bool(re.search(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$", text[:exc.pos]))
    return False


def _atomic(path, value):
    temporary = _target(path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp"))
    try:
        fd = _open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "wb") as stream:
            stream.write(_json(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        _target(path)
        os.replace(temporary, path)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _extension(path):
    ext = path.suffix.lower().lstrip(".")
    return ext if re.fullmatch(r"[a-z0-9]{1,12}", ext) else "NONE" if not ext else "OTHER"


def inventory(root):
    """Return paths only for processable files; excluded contents are never opened."""
    files, excluded = [], Counter()
    def walk(directory, hidden=False):
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda item: item.name)
        for entry in ordered:
            path = Path(entry.path)
            if entry.is_symlink():
                excluded["SYMLINK"] += 1
            elif entry.is_dir(follow_symlinks=False):
                walk(path, hidden or entry.name.startswith("."))
            elif entry.is_file(follow_symlinks=False):
                if hidden or entry.name.startswith(".") or path.suffix.lower() not in EXTENSIONS:
                    excluded[_extension(path)] += 1
                else:
                    files.append(path)
    walk(root)
    return files, dict(sorted(excluded.items()))


def _ids_selection(root, path, out, files):
    """Read exact relative IDs and project selection issues to counts only.

    The list is private input, never run identity. Keeping it outside the
    output tree also protects every atomic sibling, not just current filenames.
    """
    actual = _location(path)
    if not actual.is_file() or actual.is_relative_to(out):
        _fail("LOCATION_REJECTED")
    for target in (out / ".lock", out / "run.json", out / "results.jsonl"):
        if target.exists() and os.path.samefile(actual, target):
            _fail("INPUT_OUTPUT_OVERLAP")
    try:
        with actual.open("r", encoding="utf-8", newline="") as stream:
            text = stream.read()
    except (OSError, UnicodeError):
        _fail("INPUT_UNAVAILABLE")
    available = {item.relative_to(root).as_posix() for item in files}
    selected, seen = set(), set()
    counts = dict(selected=0, not_listed=0, duplicates=0, outside_root=0, missing=0, invalid=0)
    # splitlines would also split characters legal in a filename, such as vertical tabs
    # and Unicode line separators. Only LF/CRLF are list delimiters.
    for raw in text.split("\n"):
        value = raw[:-1] if raw.endswith("\r") else raw
        if not value:
            continue
        if value in seen:
            counts["duplicates"] += 1
            continue
        seen.add(value)
        parts = value.split("/")
        if Path(value).is_absolute() or ".." in parts:
            counts["outside_root"] += 1
        elif ("\x00" in value or "\\" in value or any(part in {"", "."} for part in parts)
              or any(part.startswith(".") for part in parts) or Path(value).suffix.lower() not in EXTENSIONS):
            counts["invalid"] += 1
        elif value not in available:
            counts["missing"] += 1
        else:
            selected.add(value)
    counts["selected"] = len(selected)
    counts["not_listed"] = len(available - selected)
    return [item for item in files if item.relative_to(root).as_posix() in selected], counts


def _selection_progress(counts):
    print("ids " + " ".join(f"{key} {value}" for key, value in counts.items()), flush=True)


def _member(value, allowed):
    return isinstance(value, str) and value in allowed


def _number(value):
    return type(value) in {int, float} and math.isfinite(value) and value >= 0


def _count(value):
    return type(value) is int and value >= 0


def _require(value):
    if not value:
        _fail("RESUME_INVALID")


def _relative(value):
    return (isinstance(value, str) and bool(value) and not Path(value).is_absolute()
            and all(part not in {".", ".."} for part in value.split("/"))
            and "\x00" not in value)


def _field_map(value, kind, complete=False):
    _require(isinstance(value, dict))
    names = set(FIELDS.get(kind, ()))
    _require(set(value) == names if complete else set(value) <= names)
    _require(all(_member(mark, {"O", "X"}) for mark in value.values()))


def _engine_record(state="NOT_REQUESTED", code="ENGINE_NOT_REQUESTED", exception=None):
    return {"state": state, "code": code, "exception": exception, "detected_type": "X",
            "fields": {}, "seconds": 0.0, "processed_pages": 0, "seconds_per_page": None}


def _validate_engine(value):
    _require(isinstance(value, dict) and set(value) == set(_engine_record()))
    _require(_member(value["state"], STATES) and _member(value["code"], CODES))
    _require(_member(value["detected_type"], KINDS))
    _require(value["exception"] is None or (isinstance(value["exception"], str) and
             re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", value["exception"])))
    _require(_number(value["seconds"]) and _count(value["processed_pages"]))
    per = value["seconds_per_page"]
    _require(per is None if value["processed_pages"] == 0 else _number(per) and
             math.isclose(per, value["seconds"] / value["processed_pages"], rel_tol=1e-9))
    _field_map(value["fields"], value["detected_type"], value["state"] == "OK")


def _comparison(code="NOT_APPLICABLE"):
    return {"state": "NOT_COMPARABLE", "code": code, "fields": {}}


def _blank(identifier, group):
    return {"schema_version": VERSION, "id": identifier, "group": group, "page_count": 0,
        "text_layer_pages": 0, "open_failed": False, "error_code": "NONE", "exception": None,
        "detected_type": "X", "slot": None, "work_category": None,
        "document_status": "NOT_ASSESSED", "assessment_code": "CLASSIFICATION_FAILED",
        "reasons": [], "identity": "미검사", "fields": [],
        "engines": {"own": _engine_record(), "applevision": _engine_record()},
        "text_reference": _engine_record("NOT_APPLICABLE", "NOT_APPLICABLE"),
        "agreement": _comparison(), "text_agreement": _comparison()}


def validate_row(value):
    from demo.backend.tools.verify_upload import SAFE_CODES
    _require(isinstance(value, dict) and set(value) == set(_blank("fake.pdf", 0)))
    _require(type(value["schema_version"]) is int and value["schema_version"] == VERSION)
    _require(_relative(value["id"]) and _count(value["group"]))
    _require(_count(value["page_count"]) and _count(value["text_layer_pages"]) and
             value["text_layer_pages"] <= value["page_count"])
    _require(type(value["open_failed"]) is bool and _member(value["error_code"], CODES))
    _require(value["exception"] is None or (isinstance(value["exception"], str) and
             re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", value["exception"])))
    kind = value["detected_type"]
    _require(_member(kind, KINDS) and _member(value["assessment_code"], CODES))
    _require(value["slot"] in {None, "resident_abstract", "nhis_payment", "nhis_qualification",
        "nhis_acquisition_loss", "work_proof", "admin_info_consent", "labor_contract"})
    _require(value["work_category"] in {None, *WORK_MAPPING.values()})
    _require(_member(value["document_status"], {"PASS", "FAIL", "NEEDS_REVIEW", "NOT_ASSESSED", "ERROR"}))
    _require(value["identity"] == "미검사" and isinstance(value["reasons"], list))
    for reason in value["reasons"]:
        _require(isinstance(reason, dict) and set(reason) == {"code", "severity"})
        _require(_member(reason["code"], SAFE_CODES | {"UNKNOWN_CODE"}) and
                 _member(reason["severity"], {"PASS", "FAIL", "NEEDS_REVIEW", "INFO", "X"}))
    _require(isinstance(value["fields"], list) and len(value["fields"]) == len(set(value["fields"])) and
             all(_member(key, FIELDS.get(kind, ())) for key in value["fields"]))
    _require(isinstance(value["engines"], dict) and set(value["engines"]) == {"own", "applevision"})
    for engine in [*value["engines"].values(), value["text_reference"]]:
        _validate_engine(engine)
    _require(value["engines"]["own"]["detected_type"] == kind)
    for name in ("agreement", "text_agreement"):
        comparison = value[name]
        _require(isinstance(comparison, dict) and set(comparison) == {"state", "code", "fields"})
        _require(_member(comparison["state"], {"COMPARABLE", "NOT_COMPARABLE"}) and
                 _member(comparison["code"], CODES))
        _field_map(comparison["fields"], kind, comparison["state"] == "COMPARABLE")
        if comparison["state"] == "NOT_COMPARABLE":
            _require(not comparison["fields"])
    return value


def _validate_meta(meta):
    _require(isinstance(meta, dict) and set(meta) == {"schema_version", "policy", "root", "engines", "groups", "excluded"})
    _require(type(meta["schema_version"]) is int and meta["schema_version"] == VERSION and meta["policy"] == POLICY)
    _require(isinstance(meta["root"], str) and Path(meta["root"]).is_absolute())
    _require(meta["engines"] in [["own"], ["own", "applevision"]])
    groups = meta["groups"]
    _require(isinstance(groups, dict) and all(_relative(key) and "/" not in key and
             _count(number) and number > 0 for key, number in groups.items()))
    _require(len(set(groups.values())) == len(groups))
    _require(isinstance(meta["excluded"], dict) and all(isinstance(key, str) and
             (re.fullmatch(r"[a-z0-9]{1,12}", key) or key in {"NONE", "OTHER", "SYMLINK"}) and
             _count(count) for key, count in meta["excluded"].items()))
    return meta


def load_rows(path, *, repair=False):
    """Stream complete rows; only an incomplete, nonterminated final row is repairable."""
    rows, identifiers = [], set()
    if not path.exists():
        return rows
    fd = _open(path, os.O_RDWR if repair else os.O_RDONLY)
    with os.fdopen(fd, "r+b" if repair else "rb") as stream:
        while True:
            start = stream.tell()
            line = stream.readline()
            if not line:
                break
            terminated = line.endswith(b"\n")
            try:
                raw = _load(line)
            except BatchError:
                if terminated or not repair or not _incomplete_tail(line):
                    raise
                stream.seek(start)
                stream.truncate()
                stream.flush()
                os.fsync(stream.fileno())
                break
            row = validate_row(raw)
            _require(row["id"] not in identifiers)
            identifiers.add(row["id"])
            rows.append(row)
            if not terminated:
                if repair:
                    stream.seek(0, os.SEEK_END)
                    stream.write(b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                break
    return rows


def _append(path, value):
    fd = _open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    with os.fdopen(fd, "wb", buffering=0) as stream:
        payload = memoryview(_json(value) + b"\n")
        while payload:
            written = stream.write(payload)
            if not written:
                _fail("OUTPUT_ERROR")
            payload = payload[written:]
        os.fsync(stream.fileno())
    # Persist creation of the first JSONL directory entry as well as its bytes.
    parent_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _inspect(path):
    """Decoded page images and reference words never leave this file's memory."""
    from PIL import Image, ImageSequence
    import pymupdf
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    from engine_v2.pipeline.ocr import OcrWord, OcrResult
    pages, references, coverage = [], [], 0
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as document:
            count = document.page_count
            try:
                if document.needs_pass:
                    _fail("ENCRYPTED")
                if not count:
                    _fail("EMPTY_DOCUMENT")
                for index, page in enumerate(document):
                    text = page.get_text()
                    coverage += bool(text.strip())
                    pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csRGB, alpha=False)
                    image = PageImage(index, PageSource.RENDER, (page.rect.width, page.rect.height),
                        png=pix.tobytes("png"), pixel_size=(pix.width, pix.height), dpi=300)
                    pages.append(image)
                    words = [OcrWord(item[4], 1.0, tuple(v * 300 / 72 for v in item[:4]))
                             for item in page.get_text("words", sort=True) if item[4].strip()]
                    references.append(OcrResult("text_layer", words))
            except Exception as exc:
                error = BatchError(exc.args[0] if isinstance(exc, BatchError) else "OPEN_ERROR")
                error.page_count, error.text_layer_pages = count, coverage
                error.exception_class = _exception(exc)
                raise error from None
    else:
        with Image.open(path) as source:
            for index, frame in enumerate(ImageSequence.Iterator(source)):
                image = frame.convert("RGB")
                data = io.BytesIO()
                image.save(data, format="PNG")
                pages.append(PageImage(index, PageSource.UPLOAD, (595.0, 842.0),
                    png=data.getvalue(), pixel_size=image.size, dpi=None))
    if not pages:
        _fail("EMPTY_DOCUMENT")
    return pages, references if coverage == len(pages) else None, coverage


def _memory_bridge(png, call):
    from PIL import Image
    with Image.open(io.BytesIO(png)) as image:
        return call(image)


def _recognize(engine, page):
    """Delegate original engine callable so exception messages are never retained."""
    from engine_v2.pipeline import ocr
    if engine == "applevision":
        with patch.object(ocr, "_with_tempfile", _memory_bridge):
            words = ocr.ENGINES[engine](page.png, page.pixel_size)
    else:
        words = ocr.ENGINES[engine](page.png, page.pixel_size)
    return ocr.OcrResult(engine, words)


def _read_pages(path, pages):
    """Invocation routing only: all extraction/conversion algorithms remain production-owned."""
    from demo.backend.ocr import localocr as local, pdftext
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_types import DocType
    from engine_v2.schemas.models import DocType as V2Type
    from engine_v2.extractors import (resident_abstract, nhis_payment, nhis_qualification,
        nhis_acquisition_loss, insurance_4, business_registration, daily_work_record)
    detected, evidence = pdftext.classify_pages_with_evidence(pages)
    ex = None
    if detected in {DocType.RESIDENT_ABSTRACT, DocType.RESIDENT_CERTIFICATE}:
        ex = resident_abstract.extract(pages)
        result = local._from_resident(ex, pages, resident_abstract, V2Type)
    elif detected == DocType.BIZ_REG_PROOF:
        ex = business_registration.extract(pages)
        result = local._from_business_proof(ex, pages, evidence)
    elif detected == DocType.DAILY_WORK_RECORD:
        ex = daily_work_record.extract(pages)
        result = local._from_nhis(ex, pages, V2Type, evidence, detected)
    elif detected in local._JOB_DOCS:
        ex = local._job_extractor(detected)(pages)
        result = local._from_job_doc(ex, pages, evidence, detected)
    elif detected in {DocType.NHIS_PAYMENT, DocType.NHIS_QUALIFICATION,
                      DocType.NHIS_ACQUISITION_LOSS, DocType.INSURANCE_4}:
        module = {DocType.NHIS_PAYMENT: nhis_payment, DocType.NHIS_QUALIFICATION: nhis_qualification,
            DocType.NHIS_ACQUISITION_LOSS: nhis_acquisition_loss, DocType.INSURANCE_4: insurance_4}[detected]
        # Preserve LocalOcr's legacy generic qualification branch.
        if detected == DocType.NHIS_QUALIFICATION and not nhis_qualification.is_notification("\n".join(r.text for _, r in pages)):
            result = local._generic(pages, path)
        else:
            original_extract = module.extract
            def observe_extract(*args, **kwargs):
                nonlocal ex
                ex = original_extract(*args, **kwargs)
                return ex
            with patch.object(module, "extract", observe_extract):
                result = local._from_supported_form(module, pages, V2Type, evidence, detected)
    else:
        result = local._generic(pages, path) if detected else None
    if result is None:
        result = OcrResult(page_count=len(pages), tier=local.NAME,
                          image_quality=local._quality([p for p, _ in pages]))
    result.detected_doc_type = detected
    result.page_count = len(pages)
    result.engine = pages[0][1].engine
    result.classification_evidence = evidence
    if detected:
        result.classification_confidence = result.classification_confidence or .95
    if path.suffix.lower() != ".pdf":
        local._merge_image_heuristics(result, path)
    raw = {key: field.value for key, field in ex.fields.items()} if ex is not None else dict(result.fields)
    # Reuse all production final header filtering/completeness/file-evidence steps.
    from demo.backend import ocr as demo_ocr
    adapter = SimpleNamespace(read=lambda file_path, expected: result)
    with patch.object(demo_ocr, "CHAIN", [adapter]):
        result = demo_ocr.read_document(str(path), None)
    return result, raw


def _present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple)):
        return bool(value)
    return True


def _field_values(kind, raw):
    return {key: raw[key] for key in FIELDS.get(kind, ()) if key in raw and _present(raw[key])}


def _engine(path, pages, engine, reference=None):
    record = _engine_record("OK", "NONE")
    started = time.perf_counter()
    stage = "OCR_ERROR"
    try:
        recognized = []
        for index, page in enumerate(pages):
            result = deepcopy(reference[index]) if reference is not None else _recognize(engine, page)
            recognized.append((page, result))
            record["processed_pages"] += 1
        stage = "EXTRACTION_ERROR"
        ocr, raw = _read_pages(path, recognized)
        kind = ocr.detected_doc_type.name if ocr.detected_doc_type else "X"
        kind = kind if kind in KINDS else "X"
        record["detected_type"] = kind
        values = _field_values(kind, raw)
        record["fields"] = {key: "O" if key in values else "X" for key in FIELDS.get(kind, ())}
        return record, ocr, values
    except Exception as exc:
        optional_missing = engine == "applevision" and stage == "OCR_ERROR" and isinstance(exc, (ImportError, NotImplementedError))
        record.update(state="SKIPPED" if optional_missing else "ERROR",
                      code="ENGINE_UNAVAILABLE" if optional_missing else stage,
                      exception=_exception(exc))
        return record, None, {}
    finally:
        record["seconds"] = time.perf_counter() - started
        count = record["processed_pages"]
        record["seconds_per_page"] = record["seconds"] / count if count else None


def _requirement(kind):
    from demo.backend.tools.verify_upload import _context
    from demo.backend.api.common import checklist_from_inputs
    from demo.backend.rules.doc_types import DocType
    from demo.backend.rules.required_docs import ApplicantDocInput, WorkCategory
    category = {"INSURANCE_4": WorkCategory.EMPLOYEE, "BIZ_REG_PROOF": WorkCategory.BUSINESS}.get(kind)
    args = SimpleNamespace(program="double_savings", work_category=category)
    program, _, criteria, _ = _context(args)
    context = ApplicantDocInput(work_category=category, admin_fixed_term=kind == "LABOR_CONTRACT",
                               paper_admin_consent=kind == "ADMIN_INFO_CONSENT")
    if kind == "LABOR_CONTRACT":
        context.work_category = WorkCategory.EMPLOYEE
    checklist = checklist_from_inputs(program, context, criteria, date.fromisoformat(criteria["application_period"][0]))
    return next((req for req in checklist if req.upload and req.doc_type == getattr(DocType, kind, None)), None)


def _assess(path, kind, ocr):
    from demo.backend.tools.verify_upload import _code, _enum
    from demo.backend.upload_assessment import assess_upload
    if kind == "X":
        return None, None, "NOT_ASSESSED", "CLASSIFICATION_FAILED", []
    if kind in {"DAILY_WORK_RECORD", "FARM_BIZ_CERT", "FISHERY_BIZ_CERT"}:
        return None, None, "NOT_ASSESSED", "WORK_CATEGORY_UNMAPPED", []
    req = _requirement(kind)
    if req is None:
        return None, None, "NOT_ASSESSED", "SLOT_UNAVAILABLE", []
    _, checked = assess_upload(path, req, identity=None, paper_admin_consent=kind == "ADMIN_INFO_CONSENT",
                              reader=lambda file_path, expected: ocr)
    status = _enum(checked.status, {"PASS", "FAIL", "NEEDS_REVIEW"}, "ERROR")
    if status == "ERROR":
        _fail("ASSESSMENT_ERROR")
    reasons = sorted({(_code(f.code), _enum(f.severity, {"PASS", "FAIL", "NEEDS_REVIEW", "INFO"})) for f in checked.findings})
    return req.slot_key, WORK_MAPPING.get(kind), status, "NONE", [dict(code=c, severity=s) for c, s in reasons]


def _typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def compare(kind, left, right, other_kind):
    return {"state": "COMPARABLE", "code": "NONE" if kind == other_kind else "DIFFERENT_KIND",
        "fields": {key: "O" if kind == other_kind and key in left and key in right and
                   _typed_equal(_semantic_field(key, left[key]), _semantic_field(key, right[key])) else "X"
                   for key in FIELDS.get(kind, ())}}


def _semantic_field(key, value):
    """Retain authored history columns while removing evidence-only metadata."""
    from engine_v2.tools.documentai_bench import _semantic_value
    columns = {
        "자격이력자료": ("category", "acquired", "lost"),
        "일용근로내역자료": ("month", "workplace", "work_dates", "days", "wage", "remuneration", "worker_category"),
    }
    if key in columns:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return value
        if isinstance(value, dict):
            selected = {name: value[name] for name in ("period", "rows") if name in value}
            if key == "일용근로내역자료" and "insurance_types" in value:
                selected["insurance_types"] = value["insurance_types"]
            if isinstance(selected.get("rows"), list):
                selected["rows"] = [
                    {column: row[column] for column in columns[key] if column in row}
                    if isinstance(row, dict) else row for row in selected["rows"]
                ]
            value = selected
    return _semantic_value(key, value)


def process_file(path, identifier, group, engines):
    row = _blank(identifier, group)
    try:
        with guarded():
            try:
                pages, reference, coverage = _inspect(path)
            except Exception as exc:
                row.update(open_failed=True, error_code=exc.args[0] if isinstance(exc, BatchError) else
                           "OPEN_ERROR" if path.suffix.lower() == ".pdf" else "DECODE_ERROR",
                           exception=getattr(exc, "exception_class", _exception(exc)))
                row["page_count"] = getattr(exc, "page_count", 0)
                row["text_layer_pages"] = getattr(exc, "text_layer_pages", 0)
                for engine in engines:
                    row["engines"][engine] = _engine_record("ERROR", row["error_code"], row["exception"])
                row["document_status"] = "ERROR"
                return row
            row["page_count"], row["text_layer_pages"] = len(pages), coverage
            values, own_ocr = {}, None
            for engine in engines:
                if engine == "applevision" and sys.platform != "darwin":
                    record, ocr, fields = _engine_record("SKIPPED", "ENGINE_UNAVAILABLE"), None, {}
                else:
                    record, ocr, fields = _engine(path, pages, engine)
                row["engines"][engine] = record
                values[engine] = fields
                if engine == "own":
                    own_ocr = ocr
            own, apple = row["engines"]["own"], row["engines"]["applevision"]
            kind = row["detected_type"] = own["detected_type"]
            row["fields"] = sorted(values.get("own", {}))
            if own["state"] == "OK":
                try:
                    row["slot"], row["work_category"], row["document_status"], row["assessment_code"], row["reasons"] = _assess(path, kind, own_ocr)
                except Exception as exc:
                    row.update(document_status="ERROR", assessment_code="ASSESSMENT_ERROR",
                               error_code="ASSESSMENT_ERROR", exception=_exception(exc))
            else:
                row.update(document_status="ERROR", error_code=own["code"], exception=own["exception"])
            if kind != "X" and own["state"] == apple["state"] == "OK":
                row["agreement"] = compare(kind, values["own"], values["applevision"], apple["detected_type"])
            else:
                row["agreement"] = _comparison("ENGINE_NOT_REQUESTED" if "applevision" not in engines else
                                               "ENGINE_FAILED" if apple["state"] == "ERROR" or own["state"] == "ERROR" else
                                               "ENGINE_UNAVAILABLE" if apple["state"] == "SKIPPED" else "CLASSIFICATION_FAILED")
            if reference is not None:
                ref, _, ref_values = _engine(path, pages, "text_layer", reference)
                row["text_reference"] = ref
                if kind != "X" and ref["state"] == own["state"] == "OK":
                    row["text_agreement"] = compare(kind, values["own"], ref_values, ref["detected_type"])
                else:
                    row["text_agreement"] = _comparison("REFERENCE_ERROR" if ref["state"] != "OK" else "CLASSIFICATION_FAILED")
            return row
    except Exception as exc:
        # Shared guards may raise on context exit even if a dependency swallowed it.
        row.update(error_code="GUARD_BLOCKED" if isinstance(exc, BatchError) else "PROCESSING_ERROR",
                   exception=_exception(exc), document_status="ERROR")
        return row


def _progress(done, skipped, total, started):
    print(f"{done} {skipped} {total} {time.perf_counter() - started:.1f}", flush=True)


def run(root, out, engines=("own",), ids=None):
    started = time.perf_counter()
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        _fail("INPUT_UNAVAILABLE")
    requested = Path(out).absolute()
    if requested.is_symlink():
        _fail("LOCATION_REJECTED")
    out = _location(requested)
    if out.is_relative_to(root) or root.is_relative_to(out):
        _fail("INPUT_OUTPUT_OVERLAP")
    # Validate private selection input before mkdir/locking/tail repair. No-ID
    # runs retain their original inventory and mutation order.
    selected = None
    if ids is not None:
        inventory_files, excluded = inventory(root)
        selected, counts = _ids_selection(root, ids, out, inventory_files)
        _selection_progress(counts)
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    _location(out)
    lock_path = _target(out / ".lock")
    fd = _open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _fail("OUTPUT_LOCKED")
        meta_path, records = _target(out / "run.json"), _target(out / "results.jsonl")
        if ids is None:
            inventory_files, excluded = inventory(root)
        files = inventory_files if selected is None else selected
        meta = {"schema_version": VERSION, "policy": POLICY, "root": str(root),
                "engines": list(engines), "groups": {}, "excluded": excluded}
        if meta_path.exists():
            old = _validate_meta(_load(meta_path.read_bytes()))
            if any(old[key] != meta[key] for key in ("schema_version", "policy", "root", "engines")):
                _fail("RUN_INCOMPATIBLE")
            meta["groups"] = old["groups"]
        elif records.exists() and records.stat().st_size:
            _fail("RESUME_INVALID")
        rows = load_rows(records, repair=True)
        completed = {row["id"] for row in rows}
        for row in rows:
            parts = Path(row["id"]).parts
            _require(row["group"] == (meta["groups"].get(parts[0]) if len(parts) > 1 else 0))
        # Full inventory determines groups, independently of selection order.
        for path in inventory_files:
            parts = path.relative_to(root).parts
            if len(parts) > 1 and parts[0] not in meta["groups"]:
                meta["groups"][parts[0]] = max(meta["groups"].values(), default=0) + 1
        _atomic(meta_path, meta)
        done, skipped = 0, sum(path.relative_to(root).as_posix() in completed for path in files)
        errors = any(row["error_code"] != "NONE" or any(e["state"] == "ERROR" for e in row["engines"].values()) for row in rows)
        _progress(done, skipped, len(files), started)
        for path in files:
            identifier = path.relative_to(root).as_posix()
            if identifier in completed:
                continue
            parts = path.relative_to(root).parts
            row = validate_row(process_file(path, identifier, meta["groups"][parts[0]] if len(parts) > 1 else 0, engines))
            _append(records, row)
            completed.add(identifier)
            done += 1
            errors |= row["error_code"] != "NONE" or any(e["state"] == "ERROR" for e in row["engines"].values())
            _progress(done, skipped, len(files), started)
        return 1 if errors else 0
    finally:
        os.close(fd)


def _rate(numerator, denominator):
    return f"{numerator}/{denominator} " + (f"{100 * numerator / denominator:.2f}%" if denominator else "N/A")


def _table(title, rows):
    print(title)
    for cells in rows:
        print("\t".join(str(cell) for cell in cells))


def _quantile(values, probability):
    if not values:
        return None
    index = (len(values) - 1) * probability
    low = math.floor(index)
    return values[low] + (values[math.ceil(index)] - values[low]) * (index - low)


def summarize(out):
    out = _location(out)
    meta = _validate_meta(_load(_target(out / "run.json").read_bytes()))
    rows = load_rows(_target(out / "results.jsonl"))
    total = len(rows)
    _table("종류별 개수", [(kind, count, _rate(count, total)) for kind, count in sorted(Counter(r["detected_type"] for r in rows).items())])
    _table("판독 품질 지표", [("CLASSIFICATION_FAILED", _rate(sum(r["detected_type"] == "X" and r["engines"]["own"]["state"] == "OK" for r in rows), total)),
        ("OPEN_FAILED", _rate(sum(r["open_failed"] for r in rows), total))])
    status = Counter(r["document_status"] for r in rows)
    _table("문서 상태", [(key, _rate(status[key], total)) for key in ("PASS", "FAIL", "NEEDS_REVIEW", "NOT_ASSESSED", "ERROR")])
    for engine in ("own", "applevision"):
        states = Counter(r["engines"][engine]["state"] for r in rows)
        _table("엔진 상태 " + engine, [(key, _rate(states[key], total)) for key in ("OK", "SKIPPED", "ERROR", "NOT_REQUESTED")])
    reasons = Counter(reason["code"] for row in rows for reason in {item["code"]: item for item in row["reasons"]}.values())
    for title, selected in (("기준일 정책 사유", DATE_CODES), ("판독 품질 사유", QUALITY_CODES),
                            ("기타 서류 단위 사유", set(reasons) - DATE_CODES - QUALITY_CODES)):
        _table(title, [(code, _rate(reasons[code], total)) for code in sorted(selected)
                       if reasons[code] or title == "기준일 정책 사유"])
    outcomes = Counter(row["assessment_code"] for row in rows if row["document_status"] == "NOT_ASSESSED")
    _table("미판정 사유", [(code, _rate(count, total)) for code, count in sorted(outcomes.items())])
    _table("work_proof 매핑 규칙", [(kind, category) for kind, category in WORK_MAPPING.items()] +
           [("OTHER_WORK_KIND", "NOT_ASSESSED WORK_CATEGORY_UNMAPPED")])
    _table("제외 확장자", [(ext, count) for ext, count in meta["excluded"].items()])
    for engine in ("own", "applevision"):
        metric = defaultdict(lambda: [0, 0])
        for row in rows:
            record = row["engines"][engine]
            if record["state"] == "OK":
                for field, mark in record["fields"].items():
                    metric[(record["detected_type"], field)][0] += mark == "O"
                    metric[(record["detected_type"], field)][1] += 1
        _table("필드 추출률 " + engine, [(kind, field, _rate(*counts)) for (kind, field), counts in sorted(metric.items())])
    for name, title in (("agreement", "own·applevision 일치율"), ("text_agreement", "글자층·own 일치율")):
        metric = defaultdict(lambda: [0, 0])
        states = Counter()
        for row in rows:
            comparison = row[name]
            states[comparison["state"]] += 1
            for field, mark in comparison["fields"].items():
                metric[(row["detected_type"], field)][0] += mark == "O"
                metric[(row["detected_type"], field)][1] += 1
        _table(title + " 상태", [(state, _rate(states[state], total)) for state in ("COMPARABLE", "NOT_COMPARABLE")])
        _table(title, [(kind, field, _rate(*counts)) for (kind, field), counts in sorted(metric.items())])
    for engine in ("own", "applevision"):
        records = [row["engines"][engine] for row in rows]
        successful = [record for record in records if record["state"] == "OK" and record["processed_pages"]]
        values = sorted(record["seconds_per_page"] for record in successful)
        pages = sum(record["processed_pages"] for record in successful)
        seconds = sum(record["seconds"] for record in successful)
        _table("쪽당 시간 " + engine, [(key, value if value is not None else "N/A") for key, value in
            (("files", len(values)), ("pages", pages), ("seconds", seconds),
             ("weighted_seconds_per_page", f"{seconds / pages:.6f} ({seconds:.6f}/{pages})" if pages else "0/0 N/A"),
             ("min", min(values) if values else None), ("p50", _quantile(values, .5)),
             ("p90", _quantile(values, .9)), ("p95", _quantile(values, .95)), ("max", max(values) if values else None),
             ("failed_attempt_seconds", sum(record["seconds"] for record in records if record["state"] == "ERROR")))])
    return 0


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        _fail("ARGUMENT_ERROR")


def parser():
    result = SafeParser(prog="batch_assess", description="Value-free sequential local assessment")
    result.add_argument("--root")
    result.add_argument("--out", required=True)
    result.add_argument("--engines", nargs="+", default=["own"])
    result.add_argument("--summarize", action="store_true")
    result.add_argument("--ids", help="Private UTF-8 list of root-relative IDs; report counts only")
    return result


def main(argv=None):
    args = None
    try:
        args = parser().parse_args(argv)
        if args.engines not in [["own"], ["own", "applevision"]] or (not args.summarize and not args.root) or (args.summarize and (args.root or args.ids is not None)):
            _fail("ARGUMENT_ERROR")
        return summarize(args.out) if args.summarize else run(args.root, args.out, args.engines, ids=args.ids)
    except KeyboardInterrupt:
        return 130
    except Exception:
        # No argument echo, exception text, traceback or unsafe error destination.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
