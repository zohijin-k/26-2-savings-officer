"""Read-only own-OCR/extraction/verdict measurement with value-free results.

Run sequentially: the production quiet/audit boundary and observation patches
are process global. Observation delegates the original functions unchanged.
Private PDF references are silver references, never independent ground truth.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
from contextlib import ExitStack
from datetime import date
import json
import os
from pathlib import Path
import time
from unittest.mock import patch
import uuid

DOCS = ("resident_abstract", "nhis_payment", "nhis_qualification", "nhis_acquisition_loss", "insurance_4")
REUPLOAD_CODES = frozenset({
    "DOCUMENT_ISSUED_TOO_EARLY", "DOCUMENT_ISSUED_AFTER_APPLICATION", "IDENTITY_MISMATCH",
    "IMAGE_RESOLUTION_TOO_LOW", "LOW_IMAGE_QUALITY", "PAGES_INCOMPLETE", "UNREADABLE_FILE",
    "MISSING_ADDRESS_DATES", "MISSING_BILLING_MONTHS", "WRONG_DOCUMENT_TYPE",
})
FIELD_NAMES = {
    "resident_abstract": ("name", "birth_date", "issue_date", "current_address", "address_history_count",
                          "applicant_name", "applicant_birth_date"),
    "nhis_payment": ("성명", "생년월일", "발급일", "사업장명칭", "납부자번호", "문서확인번호", "용도구분",
                     "조회기간", "월별고지금액", "월별장기요양보험료", "건강보험료", "장기요양보험료", "납부총액"),
    "nhis_qualification": ("성명", "생년월일", "발급일", "가구원수", "가구원목록", "자격확인요청일", "사업장관리번호"),
    "nhis_acquisition_loss": ("성명", "생년월일", "발급일", "가입구분", "취득일", "변동내역"),
    "insurance_4": ("성명", "생년월일", "발급일", "발급번호", "가입내역"),
}
INSURANCE_COLUMNS = ("보험", "성명", "가입자종별", "사업장관리번호", "사업장명칭", "자격취득일", "신고접수일", "상태")
_MISSING = object()


class BenchmarkError(Exception):
    """Fixed diagnostic only; dependency exception messages never escape CLI."""


def _json_value(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _semantic_value(key, value):
    if value is _MISSING:
        return value
    if isinstance(value, str) and key in {
        "조회기간", "월별고지금액", "월별장기요양보험료", "가구원목록", "가입내역",
    }:
        try:
            value = json.loads(value)
        except ValueError:
            return value
    if key == "가입내역" and isinstance(value, list):
        # Geometry and OCR confidence are evidence, not semantic field values.
        value = [{column: row[column] for column in INSURANCE_COLUMNS if column in row}
                 if isinstance(row, dict) else row for row in value]
    return _json_value(value)


def _stream(value):
    """Value-only CER, preserving sequence order and variable month-map keys.

    Fixed schema keys and JSON punctuation do not make a broken field look
    accurate. Exact matching separately checks complete typed JSON structure.
    """
    if value is _MISSING or value is None:
        return ""
    if isinstance(value, dict):
        pieces = []
        for key, item in sorted(value.items()):
            if len(key) == 7 and key[:4].isdigit() and key[4] == "-" and key[5:].isdigit():
                pieces.append(key)
            pieces.append(_stream(item))
        return "\n".join(pieces)
    if isinstance(value, list):
        return "\n".join(_stream(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def field_metrics(truth, actual):
    """Exact typed equality, plus NFC/whitespace-normalized Levenshtein CER.

    A missing empty-valued field is still an exact mismatch. Empty-reference
    CER uses denominator one, so hallucinated insertions remain measurable.
    """
    from .private_bench import quiet_dependencies
    with quiet_dependencies():
        from .synth_bench import alignment, normalize_text
    result = {}
    for key, expected in truth.items():
        reference = _semantic_value(key, expected)
        observed = _semantic_value(key, actual.get(key, _MISSING))
        same = (observed is not _MISSING and
                json.dumps(reference, ensure_ascii=False, sort_keys=True) ==
                json.dumps(observed, ensure_ascii=False, sort_keys=True))
        reference_text = _stream(reference)
        edits, _ = alignment(reference_text, _stream(observed))
        count = len(normalize_text(reference_text))
        result[key] = {"match": "O" if same else "X", "edits": edits,
                       "reference_chars": count, "cer": edits / max(count, 1)}
    return result


def _modules():
    from ..extractors import resident_abstract, nhis_payment, nhis_qualification, nhis_acquisition_loss, insurance_4
    return dict(zip(DOCS, (resident_abstract, nhis_payment, nhis_qualification, nhis_acquisition_loss, insurance_4)))


def requirement(doc):
    """Fixed, explicit benchmark policy; no application/DB state is consulted."""
    from demo.backend.rules.doc_types import DocType
    from demo.backend.rules.required_docs import DocRequirement
    slot = "work_proof" if doc == "insurance_4" else doc
    return DocRequirement(slot_key=slot, doc_type=getattr(DocType, doc.upper()), label="", check_declared_date=False,
                          min_issue_date=date(2026, 3, 1), max_issue_date=date(2026, 11, 13),
                          premium_months=["2025-10", "2025-11", "2025-12"] if doc == "nhis_payment" else [],
                          recent_years=5 if doc in {"resident_abstract", "nhis_acquisition_loss"} else None)


def measure(path: Path, doc: str, truth: dict, *, identity: dict | None = None,
            rasterize: bool = False) -> dict:
    """Measure one original input; return only reviewed identifiers and metrics.

    The local reader chooses classification independently of `doc`. Captured
    extraction for another type never supplies the expected type's fields.
    `rasterize` forces PDF pages through own OCR in memory for private agreement.
    No original is rewritten, and no OCR fallback engine is permitted.
    """
    if doc not in DOCS or not isinstance(truth, dict) or not set(truth) <= set(FIELD_NAMES[doc]):
        raise BenchmarkError("ARGUMENT_ERROR")
    from demo.backend.tools.verify_upload import quiet_assessment
    with quiet_assessment():
        from demo.backend import ocr as demo_ocr
        from demo.backend.ocr import localocr, pdftext
        from demo.backend.rules.identity import identity_of
        from demo.backend.upload_assessment import assess_upload
        from ..pipeline import ocr as ocr_module
        from ..pipeline import preprocess as prep_module
        from .private_bench import raster_pages

    captured, observed_ocr, source_pages = {}, [], []
    original_run, original_preprocess = ocr_module.run_ocr, prep_module.preprocess

    def observed_run(engine, png, size):
        if engine != "own":
            raise BenchmarkError("ENGINE_REJECTED")
        result = original_run(engine, png, size)
        observed_ocr.append(result)
        return result

    def observed_preprocess(value):
        pages = raster_pages(Path(value)) if rasterize else original_preprocess(value)
        source_pages[:] = pages
        return pages

    def observe_extract(kind, function):
        def call(*args, **kwargs):
            result = function(*args, **kwargs)
            captured[kind] = {key: value.model_dump(mode="json")["value"] for key, value in result.fields.items()}
            return result
        return call

    started = time.perf_counter()
    with quiet_assessment(), ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"ENGINE_V2_OCR": "own"}))
        # PdfText reads file/encryption/quality evidence only for raster input;
        # forcing a text PDF through images must not fall back to its text layer.
        adapters = [localocr.LocalOcr()] if rasterize else [localocr.LocalOcr(), pdftext.PdfTextOcr()]
        stack.enter_context(patch.object(demo_ocr, "CHAIN", adapters))
        stack.enter_context(patch.object(ocr_module, "run_ocr", observed_run))
        stack.enter_context(patch.object(prep_module, "preprocess", observed_preprocess))
        if rasterize:
            stack.enter_context(patch.object(localocr, "_tier2_can_read", return_value=False))
        for kind, module in _modules().items():
            stack.enter_context(patch.object(module, "extract", observe_extract(kind, module.extract)))
        ocr, assessment = assess_upload(Path(path), requirement(doc), identity=identity_of(identity),
                                        reader=demo_ocr.read_document)
        seconds = time.perf_counter() - started
        detected = ocr.detected_doc_type.name.lower() if ocr.detected_doc_type else "X"
        detected = detected if detected in DOCS else "X"
        codes = sorted({finding.code for finding in assessment.findings
                        if assessment.status == "FAIL" and finding.severity == "FAIL" and finding.code in REUPLOAD_CODES})
        count = len(source_pages) if source_pages else max(ocr.page_count, 0)
        failed = any(result.error or result.engine != "own" for result in observed_ocr)
        status = assessment.status if assessment.status in {"PASS", "FAIL", "NEEDS_REVIEW"} else "X"
    metrics = field_metrics(truth, captured.get(doc, {}))
    return {"failed": "O" if failed else "X", "detected": detected,
            "type_match": "O" if detected == doc else "X", "status": status,
            "confirmed_reupload_codes": codes, "fields": metrics, "pages": count,
            "seconds": seconds, "seconds_per_page": seconds / max(count, 1)}


def failure_result(doc, truth, seconds=0.0):
    """A failed attempt still contributes every authored field and denominator."""
    return {"failed": "O", "detected": "X", "type_match": "X", "status": "X",
            "confirmed_reupload_codes": [], "fields": field_metrics(truth, {}),
            "pages": 0, "seconds": seconds, "seconds_per_page": 0.0}


def _text_reference(path, doc):
    """Transient text-layer reference; no source-derived strings leave the caller."""
    import pymupdf
    from ..engine import _load_pages
    from ..pipeline.preprocess import PageSource, TEXT_LAYER_MIN_CHARS
    from ..schemas.models import DocType, DocumentInput
    with pymupdf.open(path) as document:
        if document.needs_pass or not document.page_count:
            raise BenchmarkError("TEXT_LAYER_REQUIRED")
        if any(len(page.get_text().strip()) < TEXT_LAYER_MIN_CHARS for page in document):
            raise BenchmarkError("TEXT_LAYER_REQUIRED")
    pages = _load_pages(DocumentInput(doc_id="measurement", declared_type=DocType(doc), file_path=str(path)), "own")
    if isinstance(pages, str) or not pages or any(page.source != PageSource.TEXT_LAYER for page, _ in pages):
        raise BenchmarkError("TEXT_LAYER_REQUIRED")
    # The reference must independently identify the claimed type too. Otherwise
    # an expected slot could act as an oracle and select an unrelated reader.
    from demo.backend.ocr import pdftext
    # Match LocalOcr's text-PDF routing: first read the original unsorted text
    # layer, whose word order can differ from OcrResult.text's geometry buckets.
    # Geometry is only the same production fallback when that raw read has no
    # type. Reordering a silver reference would create a benchmark-only miss.
    classified = pdftext._read_pdf(Path(path))
    detected = classified.detected_doc_type if classified is not None else None
    if detected is None:
        detected, _ = pdftext.classify_pages_with_evidence(pages)
    if detected is None or detected.name.lower() != doc:
        raise BenchmarkError("REFERENCE_TYPE_MISMATCH")
    if doc == "resident_abstract":
        # The resident production reader retains its complete page history.
        extracted = _modules()[doc].extract(pages, today=date(2026, 11, 13))
    else:
        from ..extractors.attached_pages import extract_form
        extracted, _ = extract_form(_modules()[doc].extract, pages, today=date(2026, 11, 13))
    truth = {key: field.model_dump(mode="json")["value"] for key, field in extracted.fields.items()
             if key in FIELD_NAMES[doc]}
    if not truth:
        raise BenchmarkError("REFERENCE_UNAVAILABLE")
    return truth


def _private_manifest(path):
    from demo.backend.tools import verify_cases
    actual = verify_cases._private_location(path)
    raw = verify_cases._read_json(actual, "MANIFEST_INVALID")
    if (not isinstance(raw, dict) or set(raw) != {"schema_version", "cases"}
            or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or not isinstance(raw["cases"], list) or not raw["cases"]):
        raise BenchmarkError("MANIFEST_INVALID")
    cases = []
    for item in raw["cases"]:
        if (not isinstance(item, dict) or set(item) != {"file", "doc"}
                or item["doc"] not in DOCS or not isinstance(item["file"], str) or not item["file"].strip()):
            raise BenchmarkError("MANIFEST_INVALID")
        source = Path(item["file"])
        source = (source if source.is_absolute() else actual.parent / source).resolve()
        if source.suffix.lower() != ".pdf" or not source.is_file():
            raise BenchmarkError("INPUT_UNAVAILABLE")
        cases.append((source, item["doc"]))
    return actual, cases


def _same_file(left, right):
    return left == right or (left.exists() and right.exists() and os.path.samefile(left, right))


def _private_output(output, protected):
    from demo.backend.tools.verify_cases import _private_location
    actual = _private_location(output)
    if any(_same_file(actual, path) for path in protected):
        raise BenchmarkError("OUTPUT_REJECTED")
    return actual


def _write_private(output, report, protected):
    from demo.backend.tools.verify_cases import _private_location
    actual = _private_output(output, protected)
    temporary = _private_location(actual.with_name(actual.name + "." + uuid.uuid4().hex + ".tmp"))
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        # Re-resolve targets immediately before replacement as well.
        if _private_output(output, protected) != actual:
            raise BenchmarkError("OUTPUT_REJECTED")
        os.replace(temporary, actual)
    finally:
        if temporary.exists():
            temporary.unlink()


def run_private(manifest, output=None):
    """No real case is run by the synthetic benchmark command."""
    from demo.backend.tools.verify_upload import quiet_assessment
    actual, cases = _private_manifest(Path(manifest))
    protected = [actual, *(source for source, _ in cases)]
    if output is not None:
        _private_output(Path(output), protected)
    rows = []
    for index, (source, doc) in enumerate(cases, 1):
        # Suppress failures at reference extraction too, before any output.
        try:
            with quiet_assessment():
                truth = _text_reference(source, doc)
            row = measure(source, doc, truth, rasterize=True)
            row["reference_fields"] = len(truth)
            row["reference_missing_fields"] = len(FIELD_NAMES[doc]) - len(truth)
        except BenchmarkError as exc:
            allowed = {"TEXT_LAYER_REQUIRED", "REFERENCE_UNAVAILABLE", "REFERENCE_TYPE_MISMATCH"}
            code = exc.args[0] if exc.args and exc.args[0] in allowed else "MEASUREMENT_ERROR"
            row = {"failed": "O", "error": code}
        except Exception:
            row = {"failed": "O", "error": "MEASUREMENT_ERROR"}
        rows.append({"case": index, "doc": doc, **row})
    report = {"schema_version": 1, "cases": rows,
              "attempted": len(rows), "failed": sum(row["failed"] == "O" for row in rows)}
    if output is not None:
        _write_private(Path(output), report, protected)
    return report


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise BenchmarkError("ARGUMENT_ERROR")


def parser():
    result = SafeParser(prog="documentai_bench", description="Value-free DocumentAI measurement")
    modes = result.add_subparsers(dest="mode", required=True, parser_class=SafeParser)
    synthetic = modes.add_parser("synthetic")
    synthetic.add_argument("--output", type=Path, required=True)
    synthetic.add_argument("--samples", type=int, default=1)
    synthetic.add_argument("--seed", type=int, default=20261113)
    private = modes.add_parser("private")
    private.add_argument("--cases", type=Path, required=True)
    private.add_argument("--output", type=Path)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.mode == "synthetic":
            if not 1 <= args.samples <= 20:
                raise BenchmarkError("ARGUMENT_ERROR")
            from .documentai_synth import run
            report = run(args.output, samples=args.samples, seed=args.seed)
            overall = report["summary"]["overall"]
            report = {key: overall[key] for key in ("attempted", "completed", "failed")}
        else:
            report = run_private(args.cases, args.output)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 1 if report.get("failed", 0) else 0
    except (Exception, KeyboardInterrupt):
        print("error: MEASUREMENT_ERROR")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
