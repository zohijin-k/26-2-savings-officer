"""Synthetic-only payment folio projections and read-only aggregate reporting."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine_v2.tools import batch_assess as batch
from engine_v2.tests.test_batch_assess import tree

SECRET = "SYNTHETIC-FOLIO-SENTINEL-73919"
UNKNOWN = {"adopted": "X", "total_bucket": "UNREADABLE", "count_mismatch": "UNREADABLE"}


def payment_record(projection=None):
    record = batch._engine_record("OK", "NONE")
    record.update(detected_type="NHIS_PAYMENT", processed_pages=1, seconds_per_page=0,
                  fields={name: "X" for name in batch.FIELDS["NHIS_PAYMENT"]})
    if projection is not None:
        record["payment_paging"] = projection
    return record


@pytest.mark.parametrize("projection", [UNKNOWN,
    {"adopted": "O", "total_bucket": "1", "count_mismatch": "X"},
    {"adopted": "O", "total_bucket": "2", "count_mismatch": "O"},
    {"adopted": "O", "total_bucket": "3_PLUS", "count_mismatch": "O"}])
def test_optional_value_free_projection_is_valid(projection):
    batch._validate_engine(payment_record(deepcopy(projection)))


@pytest.mark.parametrize("projection", [None, [], {},
    {**UNKNOWN, "value": SECRET}, {**UNKNOWN, "adopted": SECRET},
    {**UNKNOWN, "total_bucket": 2}, {**UNKNOWN, "total_bucket": "3"},
    {**UNKNOWN, "count_mismatch": True}, {**UNKNOWN, "count_mismatch": []},
    {**UNKNOWN, "total_bucket": "1"}, {**UNKNOWN, "adopted": "O"},
    {**UNKNOWN, "adopted": "O", "total_bucket": "2"}])
def test_projection_closed_vocabulary_rejects_arbitrary_values(projection):
    record = payment_record()
    record["payment_paging"] = projection
    with pytest.raises(batch.BatchError):
        batch._validate_engine(record)


def test_existing_record_is_accepted_without_mutation():
    record = payment_record()
    original = deepcopy(record)
    batch._validate_engine(record)
    assert record == original
    assert "payment_paging" not in record


@pytest.mark.parametrize("mark", ["O", "X", "UNREADABLE"])
def test_optional_period_waiver_projection_accepts_only_fixed_marks(mark):
    record = payment_record()
    record["payment_period_waiver"] = mark
    batch._validate_engine(record)


@pytest.mark.parametrize("mark", [None, True, [], SECRET, "READABLE"])
def test_optional_period_waiver_projection_rejects_arbitrary_values(mark):
    record = payment_record()
    record["payment_period_waiver"] = mark
    with pytest.raises(batch.BatchError):
        batch._validate_engine(record)


@pytest.mark.parametrize("state,kind", [("ERROR", "NHIS_PAYMENT"), ("OK", "NHIS_QUALIFICATION")])
def test_paging_projection_is_only_for_successful_payment_reads(state, kind):
    record = payment_record(dict(UNKNOWN))
    record.update(state=state, detected_type=kind,
                  fields={name: "X" for name in batch.FIELDS[kind]})
    with pytest.raises(batch.BatchError):
        batch._validate_engine(record)


def test_fresh_engine_projects_only_shared_statistics(monkeypatch):
    from engine_v2.extractors import payment_paging

    projection = {"adopted": "O", "total_bucket": "2", "count_mismatch": "O"}
    observed = []

    def statistics(data):
        observed.append(data)
        return deepcopy(projection)

    monkeypatch.setattr(payment_paging, "statistics", statistics, raising=False)
    ocr = SimpleNamespace(detected_doc_type=SimpleNamespace(name="NHIS_PAYMENT"),
                          fields={payment_paging.FIELD: json.dumps({"private": SECRET})})
    monkeypatch.setattr(batch, "_recognize", lambda *args: object())
    monkeypatch.setattr(batch, "_read_pages", lambda *args: (ocr, {"성명": SECRET}))
    record, returned, values = batch._engine(Path("FAKE.pdf"), [SimpleNamespace(page=0)], "own")
    assert returned is ocr and values == {"성명": SECRET}
    assert observed == [{"private": SECRET}]
    assert record["payment_paging"] == projection
    assert SECRET not in json.dumps(record, ensure_ascii=False)
    batch._validate_engine(record)


def test_invalid_json_becomes_unreadable_projection(monkeypatch):
    from engine_v2.extractors import payment_paging

    observed = []
    monkeypatch.setattr(payment_paging, "statistics", lambda data: observed.append(data) or dict(UNKNOWN), raising=False)
    ocr = SimpleNamespace(detected_doc_type=SimpleNamespace(name="NHIS_PAYMENT"),
                          fields={payment_paging.FIELD: SECRET})
    monkeypatch.setattr(batch, "_recognize", lambda *args: object())
    monkeypatch.setattr(batch, "_read_pages", lambda *args: (ocr, {}))
    record, returned, _ = batch._engine(Path("FAKE.pdf"), [SimpleNamespace(page=0)], "own")
    assert returned is ocr and record["state"] == "OK"
    assert record["payment_paging"] == UNKNOWN and observed == [None]
    assert SECRET not in json.dumps(record)


def test_engine_uses_shared_period_statistics_without_persisting_values(monkeypatch):
    from engine_v2.extractors import payment_completeness, payment_paging

    observed = []
    monkeypatch.setattr(payment_paging, "statistics", lambda data: dict(UNKNOWN))
    monkeypatch.setattr(payment_completeness, "period_statistics",
                        lambda data: observed.append(data) or "O", raising=False)
    ocr = SimpleNamespace(detected_doc_type=SimpleNamespace(name="NHIS_PAYMENT"),
                          fields={payment_completeness.FIELD: json.dumps({"period": SECRET})})
    monkeypatch.setattr(batch, "_recognize", lambda *args: object())
    monkeypatch.setattr(batch, "_read_pages", lambda *args: (ocr, {}))
    record, returned, _ = batch._engine(Path("FAKE.pdf"), [SimpleNamespace(page=0)], "own")
    assert returned is ocr and observed == [{"period": SECRET}]
    assert record["payment_period_waiver"] == "O"
    assert SECRET not in json.dumps(record)
    batch._validate_engine(record)


@pytest.mark.parametrize("marker,expected", [
    ("1/1", {"adopted": "O", "total_bucket": "1", "count_mismatch": "X"}),
    ("1/2", {"adopted": "O", "total_bucket": "2", "count_mismatch": "O"}),
    ("1/3", {"adopted": "O", "total_bucket": "3_PLUS", "count_mismatch": "O"}),
    (None, UNKNOWN),
])
def test_shared_collector_statistics_reach_batch_record(monkeypatch, marker, expected):
    from engine_v2.extractors import payment_paging
    from engine_v2.tests import p2_payment_samples as sample

    cells, size = sample.payment()
    if marker is not None:
        cells.append(sample.cell(1770, 35, 1930, 82, marker, 1))
    pair = sample.page(cells, size=size)
    evidence = payment_paging.collect([pair])
    ocr = SimpleNamespace(detected_doc_type=SimpleNamespace(name="NHIS_PAYMENT"),
                          fields={payment_paging.FIELD: json.dumps(evidence)})
    monkeypatch.setattr(batch, "_recognize", lambda *args: object())
    monkeypatch.setattr(batch, "_read_pages", lambda *args: (ocr, {}))
    record, returned, _ = batch._engine(Path("FAKE.pdf"), [pair[0]], "own")
    assert returned is ocr and record["payment_paging"] == expected
    batch._validate_engine(record)


def test_summary_routes_denominators_history_and_file_local_scope(tree, monkeypatch, capfd):
    root, out = tree
    projections = [
        {"adopted": "O", "total_bucket": "1", "count_mismatch": "X"},
        {"adopted": "O", "total_bucket": "2", "count_mismatch": "O"},
        {"adopted": "O", "total_bucket": "3_PLUS", "count_mismatch": "O"},
        UNKNOWN, None,
    ]
    for i in range(len(projections)):
        (root / f"FAKE-{i}.pdf").touch()

    def process(path, identifier, group, engines):
        i = int(path.stem.rsplit("-", 1)[1])
        row = batch._blank(identifier, group)
        row.update(detected_type="NHIS_PAYMENT", document_status="NEEDS_REVIEW", assessment_code="NONE", page_count=1)
        row["engines"]["own"] = payment_record(deepcopy(projections[i]))
        if i < 2:
            row["engines"]["applevision"] = payment_record(deepcopy(projections[i]))
        else:
            row["engines"]["applevision"] = batch._engine_record("SKIPPED", "ENGINE_UNAVAILABLE")
        if i == 0:
            row["text_reference"] = payment_record(deepcopy(projections[i]))
        return row

    monkeypatch.setattr(batch, "process_file", process)
    assert batch.main(["--root", str(root), "--out", str(out), "--engines", "own", "applevision"]) == 0
    capfd.readouterr()
    monkeypatch.setattr(batch, "inventory", lambda *args: pytest.fail("summary traversed inputs"))
    monkeypatch.setattr(batch, "_engine", lambda *args: pytest.fail("summary ran recognition"))
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert batch.main(["--summarize", "--out", str(out)]) == 0
    output = capfd.readouterr().out
    own = output.split("납부확인서 쪽수 표시 own\n")[1].split("납부확인서 쪽수 표시 applevision\n")[0]
    assert "ADOPTED_O\t3/5 60.00%" in own
    assert "ADOPTED_X\t2/5 40.00%" in own
    assert "TOTAL_1\t1/5 20.00%" in own and "TOTAL_2\t1/5 20.00%" in own
    assert "TOTAL_3_PLUS\t1/5 20.00%" in own and "TOTAL_UNREADABLE\t2/5 40.00%" in own
    assert "FILE_LOCAL_MISMATCH_O\t2/5 40.00%" in own
    assert "EVIDENCE_ABSENT\t1/5 20.00%" in own
    apple = output.split("납부확인서 쪽수 표시 applevision\n")[1].split("납부확인서 쪽수 표시 text_layer\n")[0]
    assert "ADOPTED_O\t2/2 100.00%" in apple
    assert "SKIPPED\t3/5 60.00%" in apple
    reference = output.split("납부확인서 쪽수 표시 text_layer\n")[1]
    assert "ADOPTED_O\t1/1 100.00%" in reference
    assert "NOT_APPLICABLE\t4/5 80.00%" in reference
    assert SECRET not in output and str(root) not in output and "FAKE-0.pdf" not in output
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_invalid_projection_summary_has_no_output_or_writes(tree, monkeypatch, capfd):
    root, out = tree
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    capfd.readouterr()
    row = batch._blank("FAKE.pdf", 0)
    row.update(detected_type="NHIS_PAYMENT", page_count=1)
    row["engines"]["own"] = payment_record({**UNKNOWN, "total_bucket": SECRET})
    (out / "results.jsonl").write_text(json.dumps(row) + "\n")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert batch.main(["--summarize", "--out", str(out)]) == 2
    assert capfd.readouterr().out == ""
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_summary_period_waiver_routes_and_historical_unknowns(tree, monkeypatch, capfd):
    root, out = tree
    marks = ["O", "O", "X", "UNREADABLE", None]
    for i in range(len(marks)):
        (root / f"FAKE-{i}.pdf").touch()

    def process(path, identifier, group, engines):
        i = int(path.stem.rsplit("-", 1)[1])
        row = batch._blank(identifier, group)
        row.update(detected_type="NHIS_PAYMENT", page_count=1)
        record = payment_record()
        if marks[i] is not None:
            record["payment_period_waiver"] = marks[i]
        row["engines"]["own"] = record
        if i < 2:
            row["engines"]["applevision"] = deepcopy(record)
        if i == 2:
            row["text_reference"] = deepcopy(record)
        return row

    monkeypatch.setattr(batch, "process_file", process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    capfd.readouterr()
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert batch.main(["--summarize", "--out", str(out)]) == 0
    output = capfd.readouterr().out
    own = output.split("납부확인서 쪽수 표시 own\n")[1].split("납부확인서 쪽수 표시 applevision\n")[0]
    assert "QUERY_PERIOD_UNCERTAIN_WAIVER_BLOCKED\t2/5 40.00%" in own
    assert "QUERY_PERIOD_READABLE\t1/5 20.00%" in own
    assert "QUERY_PERIOD_UNREADABLE\t2/5 40.00%" in own
    assert "PERIOD_EVIDENCE_ABSENT\t1/5 20.00%" in own
    apple = output.split("납부확인서 쪽수 표시 applevision\n")[1].split("납부확인서 쪽수 표시 text_layer\n")[0]
    assert "QUERY_PERIOD_UNCERTAIN_WAIVER_BLOCKED\t2/2 100.00%" in apple
    reference = output.split("납부확인서 쪽수 표시 text_layer\n")[1]
    assert "QUERY_PERIOD_UNCERTAIN_WAIVER_BLOCKED\t0/1 0.00%" in reference
    assert "QUERY_PERIOD_READABLE\t1/1 100.00%" in reference
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_folder_duplicate_type_counts_are_route_local_and_not_applicant_links(tree, monkeypatch, capfd):
    root, out = tree
    specs = {
        "alpha/0.pdf": "NHIS_PAYMENT", "alpha/1.pdf": "NHIS_PAYMENT", "alpha/2.pdf": "NHIS_PAYMENT",
        "alpha/3.pdf": "NHIS_QUALIFICATION", "alpha/4.pdf": "NHIS_QUALIFICATION",
        "beta/0.pdf": "NHIS_PAYMENT", "beta/1.pdf": "NHIS_PAYMENT",
        "gamma/0.pdf": "NHIS_PAYMENT", "gamma/1.pdf": "NHIS_QUALIFICATION",
        "excluded/0.pdf": "ERROR", "excluded/1.pdf": "ERROR", "excluded/2.pdf": "X",
        "root0.pdf": "NHIS_PAYMENT", "root1.pdf": "NHIS_PAYMENT",
    }
    for name in specs:
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.touch()

    def process(path, identifier, group, engines):
        kind = specs[identifier]
        row = batch._blank(identifier, group)
        row["page_count"] = 1
        record = batch._engine_record("ERROR", "OCR_ERROR") if kind == "ERROR" else batch._engine_record("OK", "NONE")
        if kind not in {"ERROR", "X"}:
            record.update(detected_type=kind, fields={k: "X" for k in batch.FIELDS[kind]})
        row["detected_type"] = record["detected_type"]
        row["engines"]["own"] = record
        if identifier.startswith("alpha/"):
            row["engines"]["applevision"] = deepcopy(record)
            if identifier in {"alpha/0.pdf", "alpha/1.pdf"}:
                row["text_reference"] = deepcopy(record)
        return row

    monkeypatch.setattr(batch, "process_file", process)
    # The authored ERROR records retain the existing processing-error exit.
    assert batch.main(["--root", str(root), "--out", str(out)]) == 1
    capfd.readouterr()
    assert batch.main(["--summarize", "--out", str(out)]) == 0
    output = capfd.readouterr().out
    own = output.split("폴더별 동일 종류 복수 파일 own\n")[1].split("폴더별 동일 종류 복수 파일 applevision\n")[0]
    assert "DUPLICATE_GROUPS\t2/3 66.67%" in own
    assert "NHIS_PAYMENT\t2/3 66.67%" in own
    assert "NHIS_QUALIFICATION\t1/2 50.00%" in own
    assert "ROOT_CLASSIFIED_FILES\t2/11 18.18%" in own
    assert "EXCLUDED_ERROR_OR_UNCLASSIFIED_FILES\t3/14 21.43%" in own
    apple = output.split("폴더별 동일 종류 복수 파일 applevision\n")[1].split("폴더별 동일 종류 복수 파일 text_layer\n")[0]
    assert "DUPLICATE_GROUPS\t1/1 100.00%" in apple
    assert "NHIS_PAYMENT\t1/1 100.00%" in apple
    reference = output.split("폴더별 동일 종류 복수 파일 text_layer\n")[1]
    assert "DUPLICATE_GROUPS\t1/1 100.00%" in reference
    for name in ["alpha", "beta", "gamma", "excluded", "root0.pdf", str(root)]:
        assert name not in output
