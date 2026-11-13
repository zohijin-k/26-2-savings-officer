"""Paired synthetic measurement through unchanged image-reader production paths.

Reference words are a benchmark input substitution, never a type/extractor
oracle. Public results contain only reviewed identifiers, states and metrics.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
from contextlib import ExitStack
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
import time
import unicodedata
from unittest.mock import patch

from . import documentai_bench as legacy

DOCS = legacy.DOCS
FIELD_NAMES = legacy.FIELD_NAMES
REUPLOAD_CODES = legacy.REUPLOAD_CODES
STATES = frozenset({"MATCH", "MISMATCH", "MISSING", "UNEXTRACTED_CLASSIFICATION", "ERROR"})
_MISSING = object()
_DASHES = str.maketrans({char: "-" for char in "‐‑‒–—−﹘﹣－"})
_DATE_KEYS = frozenset({"birth_date", "issue_date", "applicant_birth_date", "생년월일", "발급일",
                        "자격확인요청일", "자격취득일", "자격상실일", "신고접수일", "취득일"})
_MONTH_KEYS = frozenset({"조회기간", "월별고지금액", "월별장기요양보험료"})
_NUMBER_KEYS = frozenset({"건강보험료", "장기요양보험료", "납부총액", "가구원수", "address_history_count",
                          "월별고지금액", "월별장기요양보험료"})


def _normalized_string(value: str, key: str) -> str:
    text = "".join(unicodedata.normalize("NFKC", value).translate(_DASHES).split())
    if key in _DATE_KEYS:
        matched = re.fullmatch(r"(\d{4})[-./년](\d{1,2})[-./월](\d{1,2})(?:일|\.)?", text)
        if matched is None and re.fullmatch(r"\d{8}", text):
            parts = (text[:4], text[4:6], text[6:8])
        else:
            parts = matched.groups() if matched else None
        if parts:
            try:
                return date(*(int(part) for part in parts)).isoformat()
            except ValueError:
                pass  # An invalid date remains an invalid observed value.
    if key in _MONTH_KEYS:
        matched = re.fullmatch(r"(\d{4})[-./년](\d{1,2})월?", text)
        if matched:
            year, month = (int(part) for part in matched.groups())
            if 1 <= month <= 12:
                return f"{year:04}-{month:02}"
    if key in _NUMBER_KEYS and re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
        return text.replace(",", "")
    return text


def canonicalize(key: str, value):
    """Symmetric field-aware canonicalization; never strip semantic punctuation.

    Number strings retain leading zeros and types. Dates are full-match,
    calendar-validated values. Hyphens are mapped, not deleted. Missing fields
    remain missing; lists retain their source order and complete structure.
    """
    if value is _MISSING:
        return value
    if isinstance(value, str):
        return _normalized_string(value, key)
    if isinstance(value, list):
        return [canonicalize(key, item) for item in value]
    if isinstance(value, dict):
        result = {}
        for child_key, item in value.items():
            normalized_key = _normalized_string(child_key, key) if key in _MONTH_KEYS else child_key
            # A normalization collision must stay distinguishable rather than
            # silently discard a semantically conflicting observed cell.
            if normalized_key in result:
                return value
            nested_key = key if key in _NUMBER_KEYS else child_key
            result[normalized_key] = canonicalize(nested_key, item)
        return result
    return value


def _equal(reference, observed):
    return (observed is not _MISSING and
            json.dumps(reference, ensure_ascii=False, sort_keys=True) ==
            json.dumps(observed, ensure_ascii=False, sort_keys=True))


def _distance(reference: str, observed: str) -> int:
    """Literal Levenshtein distance, without hidden whitespace normalization."""
    previous = list(range(len(observed) + 1))
    for index, char in enumerate(reference, 1):
        current = [index]
        for other_index, other in enumerate(observed, 1):
            current.append(min(previous[other_index - 1] + (char != other),
                               previous[other_index] + 1, current[-1] + 1))
        previous = current
    return previous[-1]


def _empty_metric(state):
    return {"state": state, "raw_match": None, "normalized_match": None,
            "raw_edits": None, "raw_reference_chars": None, "raw_cer": None,
            "normalized_edits": None, "normalized_reference_chars": None, "normalized_cer": None}


def field_metrics(doc, truth, actual, *, invoked=True, failed=False):
    """Score only attempted extraction; unavailable classification is a state."""
    if doc not in DOCS or not isinstance(truth, dict) or not set(truth) <= set(FIELD_NAMES[doc]):
        raise legacy.BenchmarkError("ARGUMENT_ERROR")
    result = {}
    for key, expected in truth.items():
        if failed or not invoked:
            result[key] = _empty_metric("ERROR" if failed else "UNEXTRACTED_CLASSIFICATION")
            continue
        reference = legacy._semantic_value(key, expected)
        observed = legacy._semantic_value(key, actual[key]) if key in actual else _MISSING
        normalized_reference = canonicalize(key, reference)
        normalized_observed = canonicalize(key, observed)
        raw_match = _equal(reference, observed)
        normalized_match = _equal(normalized_reference, normalized_observed)
        raw_reference = legacy._stream(reference)
        raw_observed = "" if observed is _MISSING else legacy._stream(observed)
        normalized_reference_text = "".join(legacy._stream(normalized_reference).split())
        normalized_observed_text = "" if observed is _MISSING else "".join(legacy._stream(normalized_observed).split())
        raw_edits = _distance(raw_reference, raw_observed)
        normalized_edits = _distance(normalized_reference_text, normalized_observed_text)
        state = "MISSING" if observed is _MISSING else "MATCH" if normalized_match else "MISMATCH"
        result[key] = {"state": state, "raw_match": "O" if raw_match else "X",
                       "normalized_match": "O" if normalized_match else "X",
                       "raw_edits": raw_edits, "raw_reference_chars": len(raw_reference),
                       "raw_cer": raw_edits / max(len(raw_reference), 1),
                       "normalized_edits": normalized_edits,
                       "normalized_reference_chars": len(normalized_reference_text),
                       "normalized_cer": normalized_edits / max(len(normalized_reference_text), 1)}
    return result


def failure_stage(doc, truth, *, source="OWN", seconds=0.0):
    return {"source": source if source in {"OWN", "TEXT_LAYER_REFERENCE"} else "OWN",
            "failed": "O", "detected": "X", "type_match": "X", "status": "X",
            "confirmed_reupload_codes": [], "extractor_invoked": "X",
            "fields": field_metrics(doc, truth, {}, invoked=False, failed=True),
            "pages": 0, "seconds": seconds, "seconds_per_page": 0.0,
            "ocr_chars": 0, "ocr_words": 0}


def _reference_pages(words):
    if not isinstance(words, (list, tuple)):
        raise legacy.BenchmarkError("REFERENCE_INVALID")
    if not words or all(hasattr(word, "bbox_px") and hasattr(word, "text") for word in words):
        return [list(words)]
    if all(isinstance(page, (list, tuple)) and
           all(hasattr(word, "bbox_px") and hasattr(word, "text") for word in page) for page in words):
        return [list(page) for page in words]
    raise legacy.BenchmarkError("REFERENCE_INVALID")


def measure_stage(path: Path, doc: str, truth: dict, *, identity=None,
                  reference_words=None, slot_doc=None):
    """Read the same image through production routing using perfect or own words.

    `doc` is the actual source type; `slot_doc` changes only the upload policy.
    Reference confidence is one. The injected engine tag remains own so the
    identical image-source adapter path is exercised, but the public stage
    explicitly identifies TEXT_LAYER_REFERENCE and never claims model inference.
    """
    if doc not in DOCS or (slot_doc is not None and slot_doc not in DOCS):
        raise legacy.BenchmarkError("ARGUMENT_ERROR")
    field_metrics(doc, truth, {}, invoked=False)  # Validate reviewed field names.
    source = "TEXT_LAYER_REFERENCE" if reference_words is not None else "OWN"
    references = _reference_pages(reference_words) if reference_words is not None else None
    from demo.backend.tools.verify_upload import quiet_assessment
    started = time.perf_counter()
    try:
        with quiet_assessment():
            from ..pipeline import ocr as ocr_module
            from ..tools.synth_bench import normalize_text
            module = legacy._modules()[doc]
        original_extract, original_run = module.extract, ocr_module.run_ocr
        captured, observations = [], []
        reference_error = False
        observed_exception = False
        extraction_calls = 0

        def observe_extract(*args, **kwargs):
            nonlocal observed_exception, extraction_calls
            extraction_calls += 1
            try:
                result = original_extract(*args, **kwargs)
            except Exception:
                observed_exception = True
                raise
            captured.append({key: field.model_dump(mode="json")["value"]
                             for key, field in result.fields.items()})
            return result

        def observe_ocr(engine, png, size):
            nonlocal reference_error, observed_exception
            if references is not None:
                if len(observations) >= len(references):
                    reference_error = True
                    raise legacy.BenchmarkError("REFERENCE_PAGE_MISMATCH")
                from ..pipeline.ocr import OcrResult
                words = deepcopy(references[len(observations)])
                for word in words:
                    word.confidence = 1.0
                result = OcrResult("own", words)
            else:
                try:
                    result = original_run(engine, png, size)
                except Exception:
                    observed_exception = True
                    raise
            observations.append(result)
            return result

        with ExitStack() as stack:
            stack.enter_context(patch.object(module, "extract", observe_extract))
            stack.enter_context(patch.object(ocr_module, "run_ocr", observe_ocr))
            legacy_result = legacy.measure(Path(path), slot_doc or doc, {}, identity=identity)
        failed = legacy_result["failed"] == "O" or reference_error or observed_exception
        # No OCR invocation is legitimate for an unreadable-file defect.
        if references is not None and observations and len(observations) != len(references):
            failed = True
        chars = len(normalize_text("\n".join(word.text for output in observations for word in output.words)))
        word_count = sum(len(output.words) for output in observations)
        actual = captured[-1] if captured else {}
        return {"source": source, "failed": "O" if failed else "X",
                "detected": legacy_result["detected"],
                "type_match": "O" if legacy_result["detected"] == doc else "X",
                "status": legacy_result["status"],
                "confirmed_reupload_codes": legacy_result["confirmed_reupload_codes"],
                "extractor_invoked": "O" if extraction_calls else "X",
                "fields": field_metrics(doc, truth, actual, invoked=bool(extraction_calls), failed=failed),
                "pages": legacy_result["pages"], "seconds": legacy_result["seconds"],
                "seconds_per_page": legacy_result["seconds_per_page"],
                "ocr_chars": chars, "ocr_words": word_count}
    except Exception:
        return failure_stage(doc, truth, source=source, seconds=time.perf_counter() - started)


def pair_metrics(reference, own):
    """Paired losses/recoveries; not a causal estimate of glyph errors alone."""
    reference_ok, own_ok = reference["failed"] == "X", own["failed"] == "X"
    reference_type = reference_ok and reference["type_match"] == "O"
    own_type = own_ok and own["type_match"] == "O"
    both = reference_ok and own_ok
    values = {"reference_execution_errors": int(not reference_ok), "own_execution_errors": int(not own_ok),
              "paired_execution_complete": int(both),
              "reference_classification_errors": int(reference_ok and not reference_type),
              "own_classification_errors": int(own_ok and not own_type),
              "ocr_classification_losses": int(both and reference_type and not own_type),
              "classification_recoveries": int(both and not reference_type and own_type),
              "reference_field_errors": 0, "own_field_errors": 0,
              "reference_unextracted": 0, "own_unextracted": 0,
              "ocr_field_losses": 0, "ocr_unextracted": 0, "field_recoveries": 0,
              "reference_raw_field_errors": 0, "own_raw_field_errors": 0,
              "ocr_raw_field_losses": 0, "ocr_raw_unextracted": 0, "raw_field_recoveries": 0}
    for key in reference["fields"].keys() | own["fields"].keys():
        a, b = reference["fields"].get(key), own["fields"].get(key)
        if a is None or b is None:
            continue
        a_unread = a["state"] == "UNEXTRACTED_CLASSIFICATION"
        b_unread = b["state"] == "UNEXTRACTED_CLASSIFICATION"
        a_error = a["state"] in {"MISSING", "MISMATCH"}
        b_error = b["state"] in {"MISSING", "MISMATCH"}
        a_correct, b_correct = a["normalized_match"] == "O", b["normalized_match"] == "O"
        a_raw, b_raw = a.get("raw_match", a["normalized_match"]), b.get("raw_match", b["normalized_match"])
        values["reference_raw_field_errors"] += int(a_raw == "X")
        values["own_raw_field_errors"] += int(b_raw == "X")
        values["reference_unextracted"] += int(a_unread)
        values["own_unextracted"] += int(b_unread)
        values["reference_field_errors"] += int(a_error)
        values["own_field_errors"] += int(b_error)
        if both:
            values["ocr_raw_field_losses"] += int(a_raw == "O" and b_raw == "X")
            values["ocr_raw_unextracted"] += int(a_raw == "O" and b_unread)
            values["raw_field_recoveries"] += int(a_raw == "X" and b_raw == "O")
            values["ocr_field_losses"] += int(a_correct and b_error)
            values["ocr_unextracted"] += int(a_correct and b_unread)
            values["field_recoveries"] += int(a_error and b_correct)
    values["raw_field_error_delta"] = values["own_raw_field_errors"] - values["reference_raw_field_errors"]
    values["field_error_delta"] = values["own_field_errors"] - values["reference_field_errors"]
    values["classification_error_delta"] = values["own_classification_errors"] - values["reference_classification_errors"]
    return values


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise legacy.BenchmarkError("ARGUMENT_ERROR")


def main(argv=None):
    parser = SafeParser(prog="documentai_staged", description="Paired synthetic DocumentAI measurement")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20261113)
    try:
        args = parser.parse_args(argv)
        if not 1 <= args.samples <= 20:
            raise legacy.BenchmarkError("ARGUMENT_ERROR")
        from .documentai_corpus_v2 import run
        report = run(args.output, samples=args.samples, seed=args.seed)
        print(json.dumps({"attempted": len(report["rows"]),
                          "failed": sum(row["reference"]["failed"] == "O" or row["own"]["failed"] == "O"
                                        for row in report["rows"])}))
        return int(any(row["reference"]["failed"] == "O" or row["own"]["failed"] == "O" for row in report["rows"]))
    except (Exception, KeyboardInterrupt):
        print("error: MEASUREMENT_ERROR")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
