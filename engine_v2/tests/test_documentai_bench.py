"""Measurement contracts; every document here is authored and fictitious."""
from __future__ import annotations

from datetime import date
import json
import logging
import os
from pathlib import Path
import subprocess

import pytest

from engine_v2.tools import documentai_bench as bench


@pytest.mark.parametrize("expected,actual,match,edits", [
    ("가상", "가상", "O", 0), ("가상", "가 정", "X", 1),
    ("가 상", "가상", "X", 0), ("", "추가", "X", 2),
    (False, 0, "X", 5), ("가", None, "X", 1),
])
def test_exact_typed_match_is_separate_from_normalized_cer(expected, actual, match, edits):
    metric = bench.field_metrics({"name": expected}, {"name": actual})["name"]
    assert metric["match"] == match
    assert metric["edits"] == edits
    assert metric["cer"] == edits / max(metric["reference_chars"], 1)


def test_missing_empty_field_is_exact_mismatch_without_inventing_characters():
    assert bench.field_metrics({"name": ""}, {})["name"] == {
        "match": "X", "edits": 0, "reference_chars": 0, "cer": 0.0,
    }


def test_dates_json_months_and_dictionary_order_are_semantic():
    truth = {"issue_date": "2026-03-03", "월별고지금액": {"2025-10": "1000", "2025-11": "2000"}}
    observed = {"issue_date": date(2026, 3, 3), "월별고지금액": '{"2025-11":"2000","2025-10":"1000"}'}
    assert all(metric["match"] == "O" for metric in bench.field_metrics(truth, observed).values())
    shifted = {"월별고지금액": {"2025-09": "1000", "2025-11": "2000"}}
    metric = bench.field_metrics({"월별고지금액": truth["월별고지금액"]}, shifted)["월별고지금액"]
    assert metric["match"] == "X" and metric["edits"] > 0


def test_insurance_row_scoring_excludes_only_reviewed_evidence_columns():
    row = dict(zip(bench.INSURANCE_COLUMNS, ("건강보험", "가짜이름", "직장가입자", "0" * 11,
                                           "가짜상사", "2020-01-01", "2020-01-02", "가입")))
    actual = json.dumps([{**row, "bbox": {"x0": 3}, "신뢰도": .3, "자격취득일신뢰도": .2}])
    metric = bench.field_metrics({"가입내역": [row]}, {"가입내역": actual})["가입내역"]
    assert metric["match"] == "O" and metric["cer"] == 0
    altered = {**row, "신고접수일": "2020-01-03"}
    assert bench.field_metrics({"가입내역": [row]}, {"가입내역": [altered]})["가입내역"]["match"] == "X"


def test_failure_attempt_contains_all_authored_fields():
    result = bench.failure_result("resident_abstract", {"name": "가상인", "birth_date": "1999-01-01"}, seconds=.5)
    assert result["failed"] == "O" and result["type_match"] == "X"
    assert result["pages"] == 0 and result["seconds"] == .5
    assert set(result["fields"]) == {"name", "birth_date"}
    assert all(metric["match"] == "X" for metric in result["fields"].values())


@pytest.fixture
def source_pdf(tmp_path):
    from engine_v2.tests.nhis_form_samples import text_pdf
    return text_pdf(tmp_path / "FAKE-source.pdf")


@pytest.fixture
def fake_own(monkeypatch, source_pdf):
    from engine_v2.engine import _load_pages
    from engine_v2.pipeline import ocr
    from engine_v2.schemas.models import DocumentInput, DocType
    pages = _load_pages(DocumentInput(doc_id="synthetic", declared_type=DocType.NHIS_ACQUISITION_LOSS,
                                     file_path=str(source_pdf)), "own")
    assert not isinstance(pages, str)
    words = pages[0][1].words
    calls = []

    def run(engine, png, size):
        assert engine == "own" and png and size[0] > 2000
        calls.append((engine, len(png), size))
        return ocr.OcrResult("own", [ocr.OcrWord(word.text, .99, word.bbox_px) for word in words])

    monkeypatch.setattr(ocr, "run_ocr", run)
    return calls


def test_measure_uses_original_classification_extraction_and_verdict(source_pdf, fake_own):
    from engine_v2.tests.nhis_form_samples import NAME, BIRTH
    result = bench.measure(source_pdf, "nhis_acquisition_loss", {
        "성명": NAME, "생년월일": BIRTH, "발급일": "2026-03-03", "가입구분": "직장",
    }, identity={"name": NAME, "birth": BIRTH}, rasterize=True)
    assert len(fake_own) == 1
    assert result["failed"] == "X" and result["detected"] == "nhis_acquisition_loss"
    assert result["type_match"] == "O" and result["status"] == "PASS"
    assert all(metric["match"] == "O" for metric in result["fields"].values())
    assert result["pages"] == 1 and result["seconds_per_page"] > 0
    assert result["confirmed_reupload_codes"] == []
    encoded = json.dumps(result, ensure_ascii=False)
    assert NAME not in encoded and BIRTH not in encoded and str(source_pdf) not in encoded


def test_wrong_expected_type_does_not_supply_oracle_fields(source_pdf, fake_own):
    result = bench.measure(source_pdf, "nhis_qualification", {"성명": "가짜이름"}, rasterize=True)
    assert result["detected"] == "nhis_acquisition_loss" and result["type_match"] == "X"
    assert result["status"] == "FAIL"
    assert result["confirmed_reupload_codes"] == ["WRONG_DOCUMENT_TYPE"]
    assert result["fields"]["성명"]["match"] == "X"


def test_remote_and_fixture_adapters_are_excluded_and_restored(monkeypatch, source_pdf, fake_own):
    from demo.backend import ocr
    class Forbidden:
        def read(self, *_):
            raise AssertionError("remote or fixture reader called")
    chain = [Forbidden()]
    monkeypatch.setattr(ocr, "CHAIN", chain)
    monkeypatch.setenv("ENGINE_V2_OCR", "applevision")
    assert bench.measure(source_pdf, "nhis_acquisition_loss", {}, rasterize=True)["failed"] == "X"
    assert ocr.CHAIN is chain and os.environ["ENGINE_V2_OCR"] == "applevision"


def test_own_error_is_visible_and_dependency_noise_is_discarded(monkeypatch, source_pdf, capfd):
    from engine_v2.pipeline import ocr
    def fail(*_):
        print("SECRET-NOISE")
        os.write(2, b"SECRET-NATIVE")
        logging.warning("SECRET-LOG")
        return ocr.OcrResult("own", error="SECRET-ERROR")
    monkeypatch.setattr(ocr, "run_ocr", fail)
    result = bench.measure(source_pdf, "nhis_acquisition_loss", {"성명": "SECRET-VALUE"}, rasterize=True)
    assert result["failed"] == "O" and result["fields"]["성명"]["match"] == "X"
    assert "SECRET" not in json.dumps(result)
    assert capfd.readouterr() == ("", "")


def test_assessment_rejects_source_writes_even_when_reader_swallows_exception(monkeypatch, source_pdf):
    from engine_v2.pipeline import ocr
    original = source_pdf.read_bytes()
    def mutate(*_):
        source_pdf.write_bytes(b"changed")
        raise AssertionError("unreachable")
    monkeypatch.setattr(ocr, "run_ocr", mutate)
    with pytest.raises(Exception):
        bench.measure(source_pdf, "nhis_acquisition_loss", {}, rasterize=True)
    assert source_pdf.read_bytes() == original


def test_unreviewed_truth_key_rejected_before_document_read(tmp_path):
    with pytest.raises(bench.BenchmarkError):
        bench.measure(tmp_path / "never-opened.pdf", "resident_abstract", {"SECRET-FIELD": "value"})


def manifest(tmp_path, source, *, doc="nhis_acquisition_loss"):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"schema_version": 1, "cases": [{"file": str(source), "doc": doc}]}))
    return path


def test_private_synthetic_pdf_agreement_is_value_free(tmp_path, source_pdf, fake_own):
    source_bytes = source_pdf.read_bytes()
    output = tmp_path / "numeric.json"
    result = bench.run_private(manifest(tmp_path, source_pdf), output)
    assert result["failed"] == 0 and result["attempted"] == 1
    case = result["cases"][0]
    assert case["reference_fields"] > 0 and case["type_match"] == "O"
    assert all(metric["match"] == "O" for metric in case["fields"].values())
    encoded = output.read_text()
    assert source_pdf.name not in encoded and str(tmp_path) not in encoded and "가짜이름" not in encoded
    assert source_pdf.read_bytes() == source_bytes


@pytest.mark.parametrize("document", [
    '{"schema_version":1,"schema_version":1,"cases":[]}',
    '{"schema_version":true,"cases":[]}',
    '{"schema_version":1,"cases":[],"SECRET":"value"}',
    '{"schema_version":1,"cases":[{"doc":"SECRET","file":"x.pdf"}]}',
])
def test_private_manifest_rejects_duplicate_unknown_and_invalid_members(tmp_path, document):
    path = tmp_path / "cases.json"
    path.write_text(document)
    with pytest.raises(Exception):
        bench._private_manifest(path)


def test_private_requires_text_on_every_page(tmp_path):
    import pymupdf
    path = tmp_path / "FAKE-blank.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(path)
    with pytest.raises(bench.BenchmarkError):
        bench._text_reference(path, "resident_abstract")


def test_private_failure_output_does_not_echo_sources_values_or_exceptions(tmp_path, source_pdf, monkeypatch, capfd):
    def fail(*_):
        print("SECRET-PYTHON")
        os.write(1, b"SECRET-NATIVE")
        raise ValueError("SECRET-ERROR " + str(source_pdf))
    monkeypatch.setattr(bench, "_text_reference", fail)
    case_file = manifest(tmp_path, source_pdf)
    assert bench.main(["private", "--cases", str(case_file)]) == 1
    out, err = capfd.readouterr()
    assert err == "" and "SECRET" not in out and str(tmp_path) not in out
    assert json.loads(out)["cases"][0]["error"] == "MEASUREMENT_ERROR"


@pytest.mark.parametrize("output_kind", ["source", "manifest", "symlink", "hardlink"])
def test_private_output_cannot_alias_inputs(tmp_path, source_pdf, output_kind):
    case_file = manifest(tmp_path, source_pdf)
    if output_kind == "source":
        output = source_pdf
    elif output_kind == "manifest":
        output = case_file
    else:
        output = tmp_path / "output.json"
        if output_kind == "symlink":
            output.symlink_to(source_pdf)
        else:
            os.link(source_pdf, output)
    with pytest.raises(bench.BenchmarkError):
        bench.run_private(case_file, output)


def test_atomic_private_output_preserves_old_bytes_on_replace_failure(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    output.write_text("previous")
    def fail(*_):
        raise OSError("SECRET")
    monkeypatch.setattr(bench.os, "replace", fail)
    with pytest.raises(OSError):
        bench._write_private(output, {"attempted": 1}, [])
    assert output.read_text() == "previous"
    assert list(tmp_path.iterdir()) == [output]


@pytest.fixture
def private_repository(tmp_path, monkeypatch):
    from demo.backend.tools import verify_cases
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("ignored/\n")
    (root / "ignored").mkdir()
    monkeypatch.setattr(verify_cases, "REPOSITORY_ROOT", root)
    return root


def test_private_location_reuses_ignored_untracked_policy(private_repository):
    from demo.backend.tools.verify_cases import _private_location
    root = private_repository
    accepted = root / "ignored" / "cases.json"
    accepted.write_text("{}")
    assert _private_location(accepted) == accepted
    with pytest.raises(Exception):
        _private_location(root / "cases.json")
    subprocess.run(["git", "add", "-f", str(accepted)], cwd=root, check=True)
    with pytest.raises(Exception):
        _private_location(accepted)


def test_private_location_checks_resolved_symlink_target(private_repository, tmp_path):
    from demo.backend.tools.verify_cases import _private_location
    root = private_repository
    rejected = root / "tracked-zone.json"
    rejected.write_text("{}")
    outward = root / "ignored" / "link.json"
    outward.symlink_to(rejected)
    with pytest.raises(Exception):
        _private_location(outward)
    external = tmp_path / "external.json"
    external.write_text("{}")
    outward.unlink()
    outward.symlink_to(external)
    assert _private_location(outward) == external


def test_external_manifest_and_output_do_not_need_git(tmp_path, source_pdf, monkeypatch):
    from demo.backend.tools import verify_cases
    def forbid(*_, **__):
        raise AssertionError("git must not run for external targets")
    monkeypatch.setattr(verify_cases.subprocess, "run", forbid)
    path = manifest(tmp_path, source_pdf)
    assert bench._private_manifest(path)[0] == path
    assert bench._private_output(tmp_path / "result.json", [path, source_pdf]).parent == tmp_path


@pytest.mark.parametrize("arguments", [["SECRET-PATH"], ["private", "--cases"],
                                         ["private", "--secret", "SECRET-VALUE"],
                                         ["synthetic", "--output", "SECRET", "--samples", "0"]])
def test_cli_errors_are_fixed_and_value_free(arguments, capsys):
    assert bench.main(arguments) == 2
    assert capsys.readouterr() == ("error: MEASUREMENT_ERROR\n", "")


@pytest.mark.parametrize("status,expected", [("FAIL", ["WRONG_DOCUMENT_TYPE"]), ("NEEDS_REVIEW", []), ("PASS", [])])
def test_confirmed_reupload_codes_require_overall_fail(monkeypatch, tmp_path, status, expected):
    from types import SimpleNamespace
    from demo.backend import upload_assessment
    from demo.backend.rules.doc_types import DocType
    def assess(*_, **__):
        return SimpleNamespace(detected_doc_type=DocType.NHIS_QUALIFICATION, page_count=1), SimpleNamespace(
            status=status, findings=[SimpleNamespace(severity="FAIL", code="WRONG_DOCUMENT_TYPE")])
    monkeypatch.setattr(upload_assessment, "assess_upload", assess)
    result = bench.measure(tmp_path / "unopened.pdf", "resident_abstract", {})
    assert result["confirmed_reupload_codes"] == expected


@pytest.mark.parametrize("failed,exit_code", [(0, 0), (1, 1)])
def test_synthetic_cli_reports_compact_counts_and_fails_on_execution_errors(monkeypatch, tmp_path, capsys, failed, exit_code):
    from engine_v2.tools import documentai_synth
    def run(output, samples, seed):
        assert output == tmp_path / "result.json" and samples == 1 and seed == 20261113
        return {"rows": ["SHOULD_NOT_PRINT"], "summary": {"overall": {"attempted": 2, "completed": 2 - failed, "failed": failed}}}
    monkeypatch.setattr(documentai_synth, "run", run)
    assert bench.main(["synthetic", "--output", str(tmp_path / "result.json")]) == exit_code
    out, err = capsys.readouterr()
    assert err == "" and json.loads(out) == {"attempted": 2, "completed": 2 - failed, "failed": failed}


def test_synthetic_cli_sample_limit_matches_generator(capsys):
    assert bench.main(["synthetic", "--output", "not-written.json", "--samples", "21"]) == 2
    assert capsys.readouterr() == ("error: MEASUREMENT_ERROR\n", "")


def test_private_reference_and_own_share_supported_form_attachment_scope(tmp_path, source_pdf, monkeypatch):
    import pymupdf
    from engine_v2.engine import _load_pages
    from engine_v2.pipeline import ocr
    from engine_v2.schemas.models import DocumentInput, DocType
    path = tmp_path / "FAKE-with-appendix.pdf"
    with pymupdf.open(source_pdf) as document:
        appendix = document.new_page(width=595, height=842)
        appendix.insert_text((60, 80), "FICTITIOUS SYNTHETIC APPENDIX. " * 4, fontsize=8)
        document.save(path)
    pages = _load_pages(DocumentInput(doc_id="synthetic", declared_type=DocType.NHIS_ACQUISITION_LOSS,
                                     file_path=str(path)), "own")
    assert not isinstance(pages, str) and len(pages) == 2
    observed = []
    def run(engine, png, size):
        assert engine == "own"
        words = pages[len(observed)][1].words
        observed.append(size)
        return ocr.OcrResult("own", [ocr.OcrWord(word.text, .99, word.bbox_px) for word in words])
    monkeypatch.setattr(ocr, "run_ocr", run)
    reference = bench._text_reference(path, "nhis_acquisition_loss")
    assert reference["발급일"] == "2026-03-03"
    result = bench.run_private(manifest(tmp_path, path))
    case = result["cases"][0]
    assert result["failed"] == 0 and len(observed) == case["pages"] == 2
    assert all(metric["match"] == "O" for metric in case["fields"].values())
    assert case["reference_missing_fields"] == 0


def test_private_reference_rejects_wrong_declared_type_without_oracle_extraction(tmp_path, source_pdf, monkeypatch):
    module = bench._modules()["nhis_qualification"]
    def forbidden(*_, **__):
        raise AssertionError("wrong expected type must not choose the reference extractor")
    monkeypatch.setattr(module, "extract", forbidden)
    with pytest.raises(bench.BenchmarkError, match="REFERENCE_TYPE_MISMATCH"):
        bench._text_reference(source_pdf, "nhis_qualification")
    result = bench.run_private(manifest(tmp_path, source_pdf, doc="nhis_qualification"))
    assert result["failed"] == 1
    assert result["cases"][0]["error"] == "REFERENCE_TYPE_MISMATCH"


def test_private_reference_uses_production_raw_text_type_before_geometry(tmp_path, monkeypatch):
    from demo.backend.ocr import pdftext
    from engine_v2.tools import documentai_synth
    source = next(source for source in documentai_synth.sources() if source.doc == "insurance_4")
    path = tmp_path / "FAKE-insurance.pdf"
    path.write_bytes(documentai_synth.pdf_bytes(source))
    def forbidden(*_):
        raise AssertionError("an established raw-text type must not be replaced by geometric text order")
    monkeypatch.setattr(pdftext, "classify_pages_with_evidence", forbidden)
    truth = bench._text_reference(path, "insurance_4")
    assert truth["성명"] == source.truth["성명"]
    assert all(metric["match"] == "O" for metric in bench.field_metrics(source.truth, truth).values())
