"""Measurement integrity tests use authored synthetic files exclusively."""
from copy import deepcopy
import json

import numpy as np
import pytest
from PIL import Image

from engine_v2.tools import documentai_synth as synth
from engine_v2.tools.documentai_bench import field_metrics, _text_reference


def test_independently_authored_truth_matches_every_synthetic_text_source(tmp_path):
    documents = list(synth.sources())
    assert [source.doc for source in documents] == list(synth.DOCS)
    for source in documents:
        path = tmp_path / "FAKE.pdf"
        path.write_bytes(synth.pdf_bytes(source))
        metrics = field_metrics(source.truth, _text_reference(path, source.doc))
        assert metrics
        assert all(metric["match"] == "O" for metric in metrics.values()), (source.doc, metrics)
        assert all(metric["edits"] == 0 for metric in metrics.values())


def test_condition_matrix_is_complete_and_transforms_do_not_crop():
    image = Image.new("RGB", (100, 140), "white")
    image.putpixel((30, 40), (35, 40, 45))
    rng = np.random.default_rng(9)
    transformed = {condition: synth.transform(image, condition, rng) for condition in synth.CONDITIONS}
    assert len(transformed) == 7
    assert transformed["rotate_plus5"].width > image.width
    assert transformed["rotate_minus5"].height > image.height
    assert transformed["rotate90"].size == (140, 100)
    assert transformed["low_resolution"].size == (24, 34)
    assert transformed["phone"].width > image.width
    assert set(transformed["monochrome"].get_flattened_data()) <= {(0, 0, 0), (255, 255, 255)}
    assert image.getpixel((30, 40)) == (35, 40, 45)


def test_defects_mutate_source_content_and_preserve_normal():
    for source in synth.sources():
        original = deepcopy(source)
        damaged = dict(synth.defects(source))
        assert source == original
        assert {"issued_too_early", "issued_after_application", "identity_mismatch", "pages_incomplete",
                "wrong_document_type", "low_resolution", "low_image_quality", "unreadable_file"} <= damaged.keys()
        assert "2024" in str(damaged["issued_too_early"].pages)
        assert "2027" in str(damaged["issued_after_application"].pages)
        assert damaged["identity_mismatch"].identity != source.identity
        assert any(cell[2] == "1 / 2" for cells, _ in damaged["pages_incomplete"].pages for cell in cells)
        if source.doc == "resident_abstract":
            assert not any(cell[2] == "2020-01-01" for cells, _ in damaged["missing_address_dates"].pages for cell in cells)
        if source.doc == "nhis_payment":
            assert not any(cell[2] == "11월" for cells, _ in damaged["missing_billing_months"].pages for cell in cells)


def _row(*, doc="nhis_payment", condition="original", defect="none", match="O", failed="X",
         status="PASS", codes=(), edits=0, chars=4, seconds=2, pages=1):
    return {"doc": doc, "condition": condition, "defect": defect, "failed": failed,
            "type_match": match, "status": status, "confirmed_reupload_codes": list(codes),
            "fields": {"성명": {"match": match, "edits": edits, "reference_chars": chars}},
            "seconds": seconds, "pages": pages}


def test_aggregation_keeps_failed_attempts_denominators_and_deduplicates_codes():
    rows = [_row(), _row(match="X", failed="O", status="X", edits=4),
            _row(match="X", status="FAIL", codes=["LOW_IMAGE_QUALITY"] * 2, edits=2, chars=2),
            _row(defect="identity_mismatch"), _row(defect="identity_mismatch", status="NEEDS_REVIEW")]
    summary = synth.summarize(rows)
    overall = summary["overall"]
    assert overall["attempted"] == 5 and overall["failed"] == 1
    assert overall["normal_count"] == 3 and overall["defect_count"] == 2
    assert overall["field_accuracy"] == pytest.approx(1 / 3)
    assert overall["cer"] == pytest.approx(6 / 10)
    assert overall["type_accuracy"] == pytest.approx(1 / 3)
    assert overall["false_reject_rate"] == pytest.approx(1 / 3)
    assert overall["false_reject_codes"] == {"LOW_IMAGE_QUALITY": 1}
    assert overall["false_accept_rate"] == .5
    assert summary["by_cell"]["nhis_payment"]["original"]["attempted"] == 3
    assert summary["by_condition"]["original"]["defect_count"] == 0


def test_cer_is_micro_averaged_and_empty_insertions_survive():
    group = synth._aggregate([_row(edits=1, chars=1), _row(edits=1, chars=9), _row(edits=2, chars=0)])
    assert group["cer"] == .4
    assert group["fields"]["성명"]["cer"] == .4


def test_execution_exceptions_do_not_abort_remaining_matrix_or_leak(monkeypatch, tmp_path, capsys):
    from engine_v2.tools import documentai_bench as bench
    source = next(synth.sources())
    monkeypatch.setattr(synth, "sources", lambda sample: iter([source]))
    monkeypatch.setattr(synth, "render", lambda source: [Image.new("RGB", (100, 140), "white")])
    monkeypatch.setattr(synth, "defects", lambda source: iter([]))
    calls = []
    def broken(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("SECRET-SYNTHETIC-PATH-VALUE")
    monkeypatch.setattr(bench, "measure", broken)
    output = tmp_path / "result.json"
    report = synth.run(output)
    assert len(calls) == 7
    assert report["summary"]["overall"]["failed"] == 7
    assert report["summary"]["overall"]["field_count"] == 49
    assert "SECRET" not in output.read_text() + output.with_suffix(".md").read_text() + capsys.readouterr().out
    assert json.loads(output.read_text())["schema_version"] == 1
