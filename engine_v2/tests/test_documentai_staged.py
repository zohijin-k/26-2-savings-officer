"""Stage accounting/normalization tests; every document is fabricated here."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pymupdf
import pytest

from engine_v2.tools import documentai_staged as staged
from engine_v2.tools import documentai_bench as legacy
from engine_v2.tools import documentai_synth as synth
from engine_v2.pipeline.ocr import OcrResult, OcrWord


@pytest.mark.parametrize("key,expected,actual", [
    ("생년월일", "1990-01-01", "１９９０．１．１．"),
    ("issue_date", "2026-03-03", "2026 년 3 월 3 일"),
    ("issue_date", "2026-03-03", "20260303"),
    ("성명", "가상인", "가 상 인"),
    ("건강보험료", "100000", "１００，０００"),
    ("문서확인번호", "0000-0000", "００００－００００"),
    ("조회기간", ["2025-10", "2025-12"], '["2025.10", "2025년12월"]'),
])
def test_format_normalization_is_symmetric_and_raw_is_retained(key, expected, actual):
    doc = "resident_abstract" if key in {"issue_date"} else "nhis_payment"
    metrics = staged.field_metrics(doc, {key: expected}, {key: actual})[key]
    assert metrics["raw_match"] == "X"
    assert metrics["normalized_match"] == "O"
    assert metrics["state"] == "MATCH"
    reverse = staged.field_metrics(doc, {key: actual}, {key: expected})[key]
    assert reverse["normalized_match"] == "O"
    assert metrics["normalized_edits"] == 0
    assert metrics["raw_edits"] > 0


@pytest.mark.parametrize("key,expected,actual", [
    ("문서확인번호", "0001-02", "1-02"),
    ("문서확인번호", "0001-02", "000102"),
    ("current_address", "가상동1-2", "가상동12"),
    ("생년월일", "1990-01-01", "1990-01-02"),
    ("생년월일", "1990-01-01", "1990.99.99"),
    ("건강보험료", "10000", "10,00"),
    ("가구원수", "2", 2),
])
def test_normalization_does_not_erase_real_differences(key, expected, actual):
    doc = "resident_abstract" if key == "current_address" else "nhis_qualification" if key == "가구원수" else "nhis_payment"
    metric = staged.field_metrics(doc, {key: expected}, {key: actual})[key]
    assert metric["normalized_match"] == "X"
    assert metric["state"] == "MISMATCH"


def test_missing_empty_field_is_error_but_uncalled_extractor_is_not():
    truth = {"사업장명칭": ""}
    called = staged.field_metrics("nhis_payment", truth, {})["사업장명칭"]
    unavailable = staged.field_metrics("nhis_payment", truth, {}, invoked=False)["사업장명칭"]
    failed = staged.field_metrics("nhis_payment", truth, {}, failed=True)["사업장명칭"]
    assert called["state"] == "MISSING" and called["raw_match"] == "X" and called["raw_edits"] == 0
    assert unavailable["state"] == "UNEXTRACTED_CLASSIFICATION"
    assert unavailable["raw_match"] is None and unavailable["normalized_match"] is None
    assert unavailable["normalized_edits"] is None
    assert failed["state"] == "ERROR" and failed["raw_match"] is None


def test_structured_values_keep_order_columns_and_identifier_zeros():
    truth = [{"보험": "건강보험", "사업장관리번호": "00001", "자격취득일": "2020-01-01", "성명": "가상인"},
             {"보험": "국민연금", "사업장관리번호": "00002", "자격취득일": "2020-01-02", "성명": "가상인"}]
    actual = deepcopy(truth)
    actual[0].update(성명="가 상 인", 자격취득일="2020.1.1", bbox={"ignored": "SECRET"}, 신뢰도=.1)
    metric = staged.field_metrics("insurance_4", {"가입내역": truth}, {"가입내역": json.dumps(actual)})["가입내역"]
    assert metric["raw_match"] == "X" and metric["normalized_match"] == "O"
    actual.reverse()
    assert staged.field_metrics("insurance_4", {"가입내역": truth}, {"가입내역": actual})["가입내역"]["normalized_match"] == "X"
    assert "SECRET" not in json.dumps(metric)


def test_month_key_normalization_does_not_collapse_conflicting_rows():
    expected = {"2025-10": "100000"}
    actual = {"2025.10": "100,000", "2025-10": "200000"}
    metric = staged.field_metrics("nhis_payment", {"월별고지금액": expected}, {"월별고지금액": actual})["월별고지금액"]
    assert metric["normalized_match"] == "X"


@pytest.fixture
def synthetic_qualification(tmp_path):
    source = next(source for source in synth.sources() if source.doc == "nhis_qualification")
    image = synth.render(source)[0]
    path = tmp_path / "FAKE.png"
    image.save(path)
    with pymupdf.open(stream=synth.pdf_bytes(source), filetype="pdf") as document:
        words = [OcrWord(item[4], .2, tuple(float(v) * 300 / 72 for v in item[:4]))
                 for item in document[0].get_text("words", sort=True)]
    return path, source, words


def test_reference_and_own_use_same_independent_reader_and_do_not_change_words(synthetic_qualification, monkeypatch):
    from engine_v2.pipeline import ocr
    path, source, words = synthetic_qualification
    original = deepcopy(words)
    real_run = ocr.run_ocr
    called = []
    def forbidden(*_):
        called.append(1)
        raise AssertionError("MODEL SHOULD NOT RUN FOR REFERENCE")
    monkeypatch.setattr(ocr, "run_ocr", forbidden)
    reference = staged.measure_stage(path, source.doc, source.truth, identity=source.identity, reference_words=words)
    assert called == []
    assert reference["source"] == "TEXT_LAYER_REFERENCE"
    assert reference["type_match"] == "O" and reference["extractor_invoked"] == "O"
    assert reference["failed"] == "X" and reference["ocr_chars"] > 0
    assert all(metric["normalized_match"] == "O" for metric in reference["fields"].values())
    assert words == original
    assert ocr.run_ocr is forbidden
    def fake_own(engine, png, size):
        copied = deepcopy(words)
        for word in copied:
            word.confidence = 1.0
        return OcrResult("own", copied)
    monkeypatch.setattr(ocr, "run_ocr", fake_own)
    own = staged.measure_stage(path, source.doc, source.truth, identity=source.identity)
    assert own["source"] == "OWN"
    assert own["type_match"] == reference["type_match"]
    assert own["detected"] == reference["detected"]
    assert own["fields"] == reference["fields"]
    monkeypatch.setattr(ocr, "run_ocr", real_run)


def test_wrong_slot_affects_verdict_not_actual_type_or_field_truth(synthetic_qualification):
    path, source, words = synthetic_qualification
    result = staged.measure_stage(path, source.doc, source.truth, identity=source.identity,
                                  reference_words=words, slot_doc="resident_abstract")
    assert result["type_match"] == "O" and result["extractor_invoked"] == "O"
    assert result["status"] == "FAIL"
    assert "WRONG_DOCUMENT_TYPE" in result["confirmed_reupload_codes"]
    assert all(metric["normalized_match"] == "O" for metric in result["fields"].values())


def test_unrecognized_reference_does_not_call_expected_extractor(synthetic_qualification):
    path, source, _ = synthetic_qualification
    words = [OcrWord("FICTITIOUS UNKNOWN PAGE", 1., (100, 100, 400, 150))]
    result = staged.measure_stage(path, source.doc, source.truth, reference_words=words)
    assert result["type_match"] == "X" and result["extractor_invoked"] == "X"
    assert all(metric["state"] == "UNEXTRACTED_CLASSIFICATION" for metric in result["fields"].values())
    assert all(metric["raw_match"] is None for metric in result["fields"].values())


def test_invalid_file_defect_is_completed_assessment_without_ocr(tmp_path):
    path = tmp_path / "FAKE.png"
    path.write_bytes(b"FICTITIOUS INVALID IMAGE")
    result = staged.measure_stage(path, "nhis_payment", {"성명": "가상인"}, reference_words=[])
    assert result["failed"] == "X" and result["status"] == "FAIL"
    assert "UNREADABLE_FILE" in result["confirmed_reupload_codes"]
    assert result["ocr_chars"] == 0 and result["extractor_invoked"] == "X"


def test_native_logs_and_dependency_errors_do_not_escape(synthetic_qualification, monkeypatch, capfd):
    from engine_v2.pipeline import ocr
    path, source, words = synthetic_qualification
    def noisy(*_):
        print("SECRET PYTHON")
        os.write(1, b"SECRET NATIVE")
        raise RuntimeError("SECRET EXCEPTION " + str(path))
    monkeypatch.setattr(ocr, "run_ocr", noisy)
    result = staged.measure_stage(path, source.doc, source.truth)
    out, err = capfd.readouterr()
    assert "SECRET" not in out + err + json.dumps(result)
    assert str(path) not in json.dumps(result)
    assert result["failed"] == "O"
    assert all(metric["state"] == "ERROR" for metric in result["fields"].values())


def _stage(*, type_match="O", failed="X", fields=None):
    return {"type_match": type_match, "failed": failed, "fields": fields or {}}


def _field(state, match=None):
    return {"state": state, "normalized_match": match}


def test_paired_losses_recoveries_and_unextracted_have_separate_counts():
    reference = _stage(fields={
        "a": _field("MATCH", "O"), "b": _field("MATCH", "O"),
        "c": _field("MISSING", "X"), "d": _field("MISMATCH", "X"),
        "e": _field("UNEXTRACTED_CLASSIFICATION"),
    })
    own = _stage(type_match="X", fields={
        "a": _field("MISMATCH", "X"), "b": _field("UNEXTRACTED_CLASSIFICATION"),
        "c": _field("MATCH", "O"), "d": _field("MISSING", "X"),
        "e": _field("UNEXTRACTED_CLASSIFICATION"),
    })
    result = staged.pair_metrics(reference, own)
    assert result["reference_field_errors"] == 2 and result["own_field_errors"] == 2
    assert result["reference_unextracted"] == 1 and result["own_unextracted"] == 2
    assert result["ocr_field_losses"] == 1 and result["ocr_unextracted"] == 1
    assert result["field_recoveries"] == 1 and result["field_error_delta"] == 0
    assert result["ocr_classification_losses"] == 1 and result["classification_error_delta"] == 1


def test_execution_errors_are_not_classification_or_field_errors():
    reference = staged.failure_stage("nhis_payment", {"성명": "가상인"})
    own = _stage(fields={"성명": _field("MATCH", "O")})
    result = staged.pair_metrics(reference, own)
    assert result["reference_execution_errors"] == 1 and result["paired_execution_complete"] == 0
    assert result["reference_classification_errors"] == 0 and result["reference_field_errors"] == 0
    assert result["ocr_field_losses"] == 0 and result["field_recoveries"] == 0


@pytest.mark.parametrize("truth", [{"UNREVIEWED": "SECRET"}, {"성명": "fine", "path": "SECRET"}])
def test_unreviewed_output_field_names_are_rejected(truth):
    with pytest.raises(legacy.BenchmarkError):
        staged.field_metrics("nhis_payment", truth, {})


def test_cli_argument_error_does_not_echo_sensitive_arguments(capsys):
    assert staged.main(["--output", "SECRET-PATH", "--samples", "invalid"]) == 2
    assert capsys.readouterr().out == "error: MEASUREMENT_ERROR\n"


def test_raw_attribution_retains_format_losses_hidden_by_normalization():
    reference = _stage(fields={"a": {"state": "MATCH", "raw_match": "O", "normalized_match": "O"},
                                "b": {"state": "MATCH", "raw_match": "X", "normalized_match": "O"}})
    own = _stage(fields={"a": {"state": "MATCH", "raw_match": "X", "normalized_match": "O"},
                          "b": {"state": "MATCH", "raw_match": "O", "normalized_match": "O"}})
    result = staged.pair_metrics(reference, own)
    assert result["reference_raw_field_errors"] == result["own_raw_field_errors"] == 1
    assert result["ocr_raw_field_losses"] == result["raw_field_recoveries"] == 1
    assert result["reference_field_errors"] == result["own_field_errors"] == 0
    assert result["ocr_field_losses"] == result["field_recoveries"] == 0


def test_read_only_guard_rejects_source_mutation(synthetic_qualification, monkeypatch):
    from engine_v2.pipeline import ocr
    path, source, _ = synthetic_qualification
    original = path.read_bytes()
    def writes(*_):
        path.write_bytes(b"SECRET MUTATION")
    monkeypatch.setattr(ocr, "run_ocr", writes)
    result = staged.measure_stage(path, source.doc, source.truth)
    assert result["failed"] == "O"
    assert all(metric["state"] == "ERROR" for metric in result["fields"].values())
    assert path.read_bytes() == original


def test_swallowed_extractor_exception_is_execution_error_not_classification_missing(synthetic_qualification, monkeypatch):
    path, source, words = synthetic_qualification
    module = legacy._modules()[source.doc]
    def broken(*args, **kwargs):
        raise RuntimeError("SECRET EXTRACTOR ERROR")
    monkeypatch.setattr(module, "extract", broken)
    result = staged.measure_stage(path, source.doc, source.truth, reference_words=words)
    assert result["failed"] == "O" and result["extractor_invoked"] == "O"
    assert all(metric["state"] == "ERROR" for metric in result["fields"].values())
    assert "SECRET" not in json.dumps(result)
