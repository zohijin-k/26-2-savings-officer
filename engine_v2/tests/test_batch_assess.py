"""Synthetic-only privacy, durability and shared-assessment contracts."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import io
import json
import logging
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from engine_v2.tools import batch_assess as batch

SECRET = "SYNTHETIC-PRIVATE-VALUE-73919"


@pytest.fixture
def tree(tmp_path):
    root, out = tmp_path / "FAKE-input", tmp_path / "FAKE-output"
    root.mkdir()
    return root, out


def pdf(path, *, text="건강보험 자격득실확인서", blank=False):
    import pymupdf
    document = pymupdf.open()
    page = document.new_page()
    if not blank:
        writer = pymupdf.TextWriter(page.rect)
        writer.append((50, 50), text, font=pymupdf.Font("cjk"), fontsize=16)
        writer.write_text(page)
    document.save(path)
    document.close()
    return path


def image(path, format="PNG"):
    from PIL import Image
    Image.new("RGB", (1000, 1400), "white").save(path, format=format)
    return path


def fake_ocr(monkeypatch, source):
    with batch.guarded():
        _, references, _ = batch._inspect(source)
    def recognize(engine, page):
        result = deepcopy(references[min(page.page, len(references) - 1)])
        result.engine = engine
        return result
    monkeypatch.setattr(batch, "_recognize", recognize)


def rows(out):
    return [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]


def assert_secret_absent(out, capfd):
    captured = capfd.readouterr()
    assert SECRET not in captured.out + captured.err
    assert captured.err == ""
    for path in out.iterdir():
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes()


def test_inventory_only_opens_directories_and_counts_excluded(tree, monkeypatch):
    root, _ = tree
    for name in ("person-b/z.PDF", "person-a/a.JPG", "person-a/b.jpeg", "person-a/c.png",
                 "person-a/d.heic", "person-a/e.gif", "person-a/f.jfif", "direct.pdf",
                 ".hidden.pdf", "person-a/.hidden.jpg", "unsupported.txt", "empty", ".private/inside.png"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not opened")
    (root / "link.pdf").symlink_to(root / "direct.pdf")
    (root / "loop").symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("content read"))
    files, excluded = batch.inventory(root)
    assert [path.relative_to(root).as_posix() for path in files] == ["direct.pdf", "person-a/a.JPG",
        "person-a/b.jpeg", "person-a/c.png", "person-a/d.heic", "person-a/e.gif", "person-a/f.jfif", "person-b/z.PDF"]
    assert excluded == {"NONE": 1, "SYMLINK": 2, "jpg": 1, "pdf": 1, "png": 1, "txt": 1}


def test_shared_pipeline_complete_record_and_resume(tree, monkeypatch, capfd):
    from engine_v2.tests.nhis_form_samples import text_pdf, NAME, BIRTH
    root, out = tree
    (root / "neutral").mkdir()
    source = text_pdf(root / "neutral" / "case.pdf")
    fake_ocr(monkeypatch, source)
    from demo.backend import upload_assessment
    original = upload_assessment.assess_upload
    calls = []
    def assess(path, req, **kwargs):
        calls.append((path, req.slot_key, kwargs["identity"], kwargs.get("identity_from_ocr")))
        return original(path, req, **kwargs)
    monkeypatch.setattr(upload_assessment, "assess_upload", assess)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    saved = rows(out)
    row = saved[0]
    assert row["id"] == "neutral/case.pdf" and row["group"] == 1
    assert row["page_count"] == row["text_layer_pages"] == 1
    assert row["open_failed"] is False and row["error_code"] == "NONE"
    assert row["detected_type"] == "NHIS_ACQUISITION_LOSS"
    assert row["slot"] == "nhis_acquisition_loss" and row["identity"] == "미검사"
    assert row["engines"]["own"]["state"] == "OK"
    assert row["engines"]["own"]["processed_pages"] == 1
    assert row["engines"]["own"]["seconds_per_page"] > 0
    assert row["text_reference"]["state"] == "OK"
    assert row["text_agreement"]["state"] == "COMPARABLE"
    assert row["text_agreement"]["fields"]["성명"] == "O"
    assert row["engines"]["applevision"]["state"] == "NOT_REQUESTED"
    assert calls == [(source, "nhis_acquisition_loss", None, None)]
    before = (out / "results.jsonl").read_bytes()
    monkeypatch.setattr(batch, "process_file", lambda *args: pytest.fail("completed file rerun"))
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    assert (out / "results.jsonl").read_bytes() == before
    assert NAME not in before.decode() and str(BIRTH) not in before.decode()
    assert_secret_absent(out, capfd)


def test_unknown_operating_status_is_fixed_processing_error(tree, monkeypatch, capfd):
    from engine_v2.tests.nhis_form_samples import text_pdf
    from demo.backend import upload_assessment
    root, out = tree
    source = text_pdf(root / "case.pdf")
    fake_ocr(monkeypatch, source)
    monkeypatch.setattr(upload_assessment, "assess_upload", lambda *a, **k:
                        (None, SimpleNamespace(status=SECRET, findings=[])))
    assert batch.main(["--root", str(root), "--out", str(out)]) == 1
    row = rows(out)[0]
    assert row["document_status"] == "ERROR"
    assert row["error_code"] == row["assessment_code"] == "ASSESSMENT_ERROR"
    assert row["exception"] == "BatchError"
    assert_secret_absent(out, capfd)


def test_later_pdf_render_failure_preserves_known_pages_and_continues(tree, monkeypatch, capfd):
    import pymupdf
    from engine_v2.pipeline.ocr import OcrResult
    root, out = tree
    with pymupdf.open() as document:
        for _ in range(2):
            page = document.new_page()
            page.insert_text((30, 30), "SYNTHETIC PAGE ONLY")
        document.save(root / "a.pdf")
    pdf(root / "b.pdf", text="SYNTHETIC UNKNOWN")
    original = pymupdf.Page.get_pixmap
    def render(page, *a, **k):
        if page.number == 1:
            raise ValueError(SECRET)
        return original(page, *a, **k)
    monkeypatch.setattr(pymupdf.Page, "get_pixmap", render)
    monkeypatch.setattr(batch, "_recognize", lambda engine, page: OcrResult(engine, []))
    assert batch.main(["--root", str(root), "--out", str(out)]) == 1
    failed, continued = rows(out)
    assert failed["page_count"] == failed["text_layer_pages"] == 2
    assert failed["error_code"] == "OPEN_ERROR" and failed["exception"] == "ValueError"
    assert continued["page_count"] == 1 and continued["error_code"] == "NONE"
    assert_secret_absent(out, capfd)


@pytest.mark.parametrize("kind,field,value,change", [
    ("NHIS_ACQUISITION_LOSS", "자격이력자료",
     {"period": ["2020-01-01", "2026-01-01"],
      "rows": [{"category": "직장가입자", "acquired": "2024-01-01", "lost": None,
                "acquired_confidence": .99, "lost_confidence": .7}],
      "coverage_basis": "full_history", "recent_five_years_covered": True}, "acquired"),
    ("DAILY_WORK_RECORD", "일용근로내역자료",
     {"period": ["2025-01", "2025-12"], "insurance_types": ["고용"],
      "rows": [{"month": "2025-10", "workplace": "가상사업장", "work_dates": [1, 2],
                "days": 2, "wage": 200000, "remuneration": 180000, "worker_category": "일용"}],
      "copies_consistent": True}, "wage"),
])
def test_mixed_history_fields_compare_semantics_not_evidence(kind, field, value, change):
    right = deepcopy(value)
    right.update(coverage_basis=SECRET, copies_consistent=False, recent_five_years_covered=False)
    right["rows"][0].update(acquired_confidence=.1, lost_confidence=.2, bbox=SECRET)
    raw = {field: json.dumps(value, ensure_ascii=False)}
    assert field in batch._field_values(kind, raw)
    result = batch.compare(kind, raw, {field: right}, kind)
    assert result["fields"][field] == "O"
    right["rows"][0][change] = SECRET
    result = batch.compare(kind, raw, {field: right}, kind)
    assert result["fields"][field] == "X" and SECRET not in json.dumps(result)


@pytest.mark.parametrize("suffix,format", [(".jpg", "JPEG"), (".jpeg", "JPEG"), (".png", "PNG"), (".jfif", "JPEG")])
def test_image_decode_support_without_converted_files(tree, suffix, format):
    root, _ = tree
    source = image(root / ("case" + suffix), format)
    with batch.guarded():
        pages, reference, coverage = batch._inspect(source)
    assert len(pages) == 1 and pages[0].png and pages[0].pixel_size == (1000, 1400)
    assert reference is None and coverage == 0
    assert list(root.iterdir()) == [source]


def test_multiframe_gif_is_counted_as_pages(tree):
    from PIL import Image
    root, _ = tree
    source = root / "case.gif"
    first = Image.new("RGB", (20, 30), "white")
    first.save(source, save_all=True, append_images=[Image.new("RGB", (20, 30), "black")], loop=0)
    with batch.guarded():
        pages, reference, coverage = batch._inspect(source)
    assert len(pages) == 2 and [page.page for page in pages] == [0, 1]
    assert reference is None and coverage == 0


def test_mixed_text_and_short_text_coverage(tree):
    import pymupdf
    root, _ = tree
    source = pdf(root / "short.pdf", text="가")
    with batch.guarded():
        pages, reference, coverage = batch._inspect(source)
    assert len(pages) == coverage == 1 and reference is not None
    with pymupdf.open(source) as document:
        document.new_page()
        mixed = root / "mixed.pdf"
        document.save(mixed)
    with batch.guarded():
        pages, reference, coverage = batch._inspect(mixed)
    assert len(pages) == 2 and coverage == 1 and reference is None


def test_decode_failures_continue_and_terminal_errors_resume(tree, capfd, monkeypatch):
    root, out = tree
    for name in ("a.heic", "b.pdf", "c.gif"):
        (root / name).write_bytes(SECRET.encode())
    assert batch.main(["--root", str(root), "--out", str(out)]) == 1
    saved = rows(out)
    assert len(saved) == 3
    assert [row["error_code"] for row in saved] == ["DECODE_ERROR", "OPEN_ERROR", "DECODE_ERROR"]
    assert all(row["open_failed"] and row["exception"] for row in saved)
    monkeypatch.setattr(batch, "process_file", lambda *a: pytest.fail("error row rerun"))
    assert batch.main(["--root", str(root), "--out", str(out)]) == 1
    assert len(rows(out)) == 3
    assert_secret_absent(out, capfd)


def test_encrypted_pdf_fixed_failure_and_known_page_count(tree):
    import pymupdf
    root, out = tree
    source = pdf(root / "original.pdf")
    with pymupdf.open(source) as document:
        document.save(root / "encrypted.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256,
                      user_pw="FAKE-password", owner_pw="FAKE-owner")
    source.unlink()
    assert batch.main(["--root", str(root), "--out", str(out)]) == 1
    assert rows(out)[0]["error_code"] == "ENCRYPTED"
    assert rows(out)[0]["page_count"] == 1


@pytest.mark.parametrize("kind,slot,category", [
    ("INSURANCE_4", "work_proof", "직장가입자"), ("BIZ_REG_PROOF", "work_proof", "사업소득 사업자"),
    ("NHIS_PAYMENT", "nhis_payment", None), ("NHIS_QUALIFICATION", "nhis_qualification", None),
    ("NHIS_ACQUISITION_LOSS", "nhis_acquisition_loss", None), ("RESIDENT_ABSTRACT", "resident_abstract", None),
    ("ADMIN_INFO_CONSENT", "admin_info_consent", None), ("LABOR_CONTRACT", "labor_contract", None),
])
def test_only_approved_requirement_contexts(kind, slot, category):
    with batch.guarded():
        req = batch._requirement(kind)
    assert req.slot_key == slot and req.upload
    assert batch.WORK_MAPPING.get(kind) == category


@pytest.mark.parametrize("kind,code", [("DAILY_WORK_RECORD", "WORK_CATEGORY_UNMAPPED"),
    ("FARM_BIZ_CERT", "WORK_CATEGORY_UNMAPPED"), ("FISHERY_BIZ_CERT", "WORK_CATEGORY_UNMAPPED"),
    ("PAYMENT_RECEIPT", "SLOT_UNAVAILABLE"), ("RESIDENT_CERTIFICATE", "SLOT_UNAVAILABLE"),
    ("BIZ_REG_CERT", "SLOT_UNAVAILABLE"), ("X", "CLASSIFICATION_FAILED")])
def test_unassessed_kinds_do_not_invent_slot(kind, code):
    with batch.guarded():
        result = batch._assess(Path("FAKE.pdf"), kind, None)
    assert result == (None, None, "NOT_ASSESSED", code, [])


def test_admin_consent_calls_existing_paper_path(tree, monkeypatch):
    from demo.backend import upload_assessment
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_types import DocType
    root, _ = tree
    source = pdf(root / "paper.pdf")
    ocr = OcrResult(detected_doc_type=DocType.ADMIN_INFO_CONSENT)
    calls = []
    def assess(path, req, **kwargs):
        calls.append(kwargs)
        return ocr, SimpleNamespace(status="NEEDS_REVIEW", findings=[])
    monkeypatch.setattr(upload_assessment, "assess_upload", assess)
    with batch.guarded():
        batch._assess(source, "ADMIN_INFO_CONSENT", ocr)
    assert calls[0]["paper_admin_consent"] is True and calls[0]["identity"] is None


@pytest.mark.parametrize("left,right,expected", [
    ({"성명": "가상인"}, {"성명": "가상인"}, "O"), ({}, {}, "X"),
    ({"성명": "가상인"}, {}, "X"), ({"성명": 0}, {"성명": False}, "X"),
    ({"성명": "가 상인"}, {"성명": "가상인"}, "X"),
])
def test_exact_semantic_agreement_missing_both_never_matches(left, right, expected):
    with batch.guarded():
        result = batch.compare("NHIS_PAYMENT", left, right, "NHIS_PAYMENT")
    assert result["fields"]["성명"] == expected


def test_kind_disagreement_is_counted_as_x_and_unreviewed_keys_not_emitted():
    with batch.guarded():
        result = batch.compare("NHIS_PAYMENT", {"성명": SECRET}, {"성명": SECRET}, "NHIS_QUALIFICATION")
    assert result["fields"]["성명"] == "X" and result["code"] == "DIFFERENT_KIND"
    assert batch._field_values("NHIS_PAYMENT", {SECRET: SECRET, "성명": "", "건강보험료": 0}) == {"건강보험료": 0}
    assert batch._present(False) and not batch._present([])


def test_structured_insurance_ignores_evidence_only():
    left = [{"보험": "건강보험", "성명": "가상인", "신뢰도": .8}]
    right = [{"보험": "건강보험", "성명": "가상인", "신뢰도": .1}]
    with batch.guarded():
        result = batch.compare("INSURANCE_4", {"가입내역": left}, {"가입내역": json.dumps(right)}, "INSURANCE_4")
    assert result["fields"]["가입내역"] == "O"


def test_optional_apple_skip_and_classification_failure(tree, monkeypatch):
    root, out = tree
    source = pdf(root / "unknown.pdf", text="미분류 합성 문서")
    fake_ocr(monkeypatch, source)
    monkeypatch.setattr(batch.sys, "platform", "linux")
    assert batch.main(["--root", str(root), "--out", str(out), "--engines", "own", "applevision"]) == 0
    row = rows(out)[0]
    assert row["detected_type"] == "X" and row["assessment_code"] == "CLASSIFICATION_FAILED"
    assert row["engines"]["applevision"]["state"] == "SKIPPED"
    assert row["agreement"]["state"] == "NOT_COMPARABLE"


def test_memory_apple_bridge_keeps_production_bbox_conversion(tree, monkeypatch):
    from engine_v2.pipeline import ocr
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    from PIL import Image
    fake_module = SimpleNamespace()
    seen = []
    class OCR:
        def __init__(self, value, **kwargs):
            assert isinstance(value, Image.Image)
            seen.append(kwargs)
        def recognize(self):
            return [(SECRET, .9, (.1, .2, .3, .4))]
    fake_module.ocrmac = SimpleNamespace(OCR=OCR)
    monkeypatch.setitem(sys.modules, "ocrmac", fake_module)
    png = io.BytesIO()
    Image.new("RGB", (100, 200)).save(png, format="PNG")
    page = PageImage(0, PageSource.UPLOAD, (595, 842), png=png.getvalue(), pixel_size=(100, 200))
    with batch.guarded():
        result = batch._recognize("applevision", page)
    assert result.words[0].bbox_px == pytest.approx((10, 80, 40, 160))
    assert seen == [{"language_preference": ["ko-KR", "en-US"]}]


def test_memory_bridge_patch_restored_after_interrupt(monkeypatch):
    from engine_v2.pipeline import ocr
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    original = ocr._with_tempfile
    def interrupted(png, size):
        assert ocr._with_tempfile is batch._memory_bridge
        raise KeyboardInterrupt
    monkeypatch.setitem(ocr.ENGINES, "applevision", interrupted)
    page = PageImage(0, PageSource.UPLOAD, (595, 842), png=b"FAKE", pixel_size=(10, 10))
    with pytest.raises(KeyboardInterrupt):
        with batch.guarded():
            batch._recognize("applevision", page)
    assert ocr._with_tempfile is original
    assert batch._NETWORK == []


def test_durable_append_fsync_observes_complete_row(tree, monkeypatch):
    _, out = tree
    out.mkdir()
    target = out / "results.jsonl"
    seen = []
    original = os.fsync
    def fsync(fd):
        seen.append(target.read_bytes().endswith(b"\n"))
        original(fd)
    monkeypatch.setattr(os, "fsync", fsync)
    batch._append(target, batch._blank("FAKE.pdf", 0))
    assert seen == [True, True]
    assert len(batch.load_rows(target)) == 1


@pytest.mark.parametrize("event", ["write", "db", "network", "subprocess"])
def test_guard_blocks_even_swallowed_attempts(tree, event, capfd):
    root, _ = tree
    with pytest.raises(Exception):
        with batch.guarded():
            try:
                if event == "write":
                    (root / "forbidden").write_text(SECRET)
                elif event == "db":
                    sqlite3.connect(":memory:")
                elif event == "network":
                    socket.getaddrinfo("FAKE.invalid", 443)
                else:
                    subprocess.run(["FAKE-no-command"])
            except Exception:
                pass
    assert not (root / "forbidden").exists()
    assert capfd.readouterr().out == ""


def test_dependency_noise_exception_and_key_values_never_escape(tree, monkeypatch, capfd):
    root, out = tree
    source = pdf(root / "case.pdf")
    def noisy(*args):
        print(SECRET)
        print(SECRET, file=sys.stderr)
        logging.error(SECRET)
        os.write(1, SECRET.encode())
        os.write(2, SECRET.encode())
        raise ValueError(SECRET)
    monkeypatch.setattr(batch, "_recognize", noisy)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 1
    row = rows(out)[0]
    assert row["engines"]["own"]["exception"] == "ValueError"
    assert row["engines"]["own"]["code"] == "OCR_ERROR"
    assert_secret_absent(out, capfd)
    assert list(root.iterdir()) == [source]


def fake_process(path, identifier, group, engines):
    row = batch._blank(identifier, group)
    row["page_count"] = 1
    return row


def test_interruption_preserves_fsynced_rows_and_groups(tree, monkeypatch):
    root, out = tree
    for name in ("b/a.pdf", "b/b.pdf"):
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    calls = []
    def stop(path, identifier, group, engines):
        calls.append(identifier)
        if len(calls) == 2:
            assert len(rows(out)) == 1
            raise KeyboardInterrupt
        return fake_process(path, identifier, group, engines)
    monkeypatch.setattr(batch, "process_file", stop)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 130
    assert [r["id"] for r in rows(out)] == ["b/a.pdf"]
    (root / "a").mkdir()
    (root / "a" / "c.pdf").touch()
    monkeypatch.setattr(batch, "process_file", fake_process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    assert [(r["id"], r["group"]) for r in rows(out)] == [("b/a.pdf", 1), ("a/c.pdf", 2), ("b/b.pdf", 1)]


@pytest.mark.parametrize("tail", [b'{"id":', '{"id":"한'.encode()[:-1], b'', b'{"ok":tru', b'{"time":1e-'])
def test_partial_final_row_recovery_preserves_complete_bytes(tree, monkeypatch, tail):
    root, out = tree
    (root / "a.pdf").touch()
    monkeypatch.setattr(batch, "process_file", fake_process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    original = (out / "results.jsonl").read_bytes()
    with (out / "results.jsonl").open("ab") as stream:
        stream.write(tail)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    assert (out / "results.jsonl").read_bytes() == original


def test_valid_final_json_without_newline_is_completed(tree, monkeypatch):
    root, out = tree
    (root / "a.pdf").touch()
    monkeypatch.setattr(batch, "process_file", fake_process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    path = out / "results.jsonl"
    original = path.read_bytes()
    path.write_bytes(original.rstrip(b"\n"))
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    assert path.read_bytes() == original


@pytest.mark.parametrize("tail", [b'{"id":"a","id":"b"}', b'{"time":NaN}',
                                  b'{"id":"a",}', b'{"id":@}', b'\xff'])
def test_complete_invalid_final_json_is_not_truncated(tree, monkeypatch, tail):
    root, out = tree
    (root / "a.pdf").touch()
    monkeypatch.setattr(batch, "process_file", fake_process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    target = out / "results.jsonl"
    with target.open("ab") as stream:
        stream.write(tail)
    before = target.read_bytes()
    assert batch.main(["--root", str(root), "--out", str(out)]) == 2
    assert target.read_bytes() == before


@pytest.mark.parametrize("corruption", ["interior", "duplicate", "unsafe", "schema"])
def test_corrupt_resume_rejected_without_echo_or_changing_rows(tree, monkeypatch, capfd, corruption):
    root, out = tree
    (root / "a.pdf").touch()
    monkeypatch.setattr(batch, "process_file", fake_process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    path = out / "results.jsonl"
    if corruption == "interior":
        path.write_bytes(path.read_bytes() + SECRET.encode() + b"\n")
    elif corruption == "duplicate":
        path.write_bytes(path.read_bytes() * 2)
    else:
        row = rows(out)[0]
        row["identity" if corruption == "unsafe" else "schema_version"] = SECRET
        path.write_text(json.dumps(row) + "\n")
    before = path.read_bytes()
    assert batch.main(["--root", str(root), "--out", str(out)]) == 2
    assert path.read_bytes() == before
    assert SECRET not in capfd.readouterr().out


def test_settings_incompatible_and_exclusions_not_added_twice(tree, monkeypatch):
    root, out = tree
    (root / "a.pdf").touch()
    (root / "ignored.txt").touch()
    monkeypatch.setattr(batch, "process_file", fake_process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    assert json.loads((out / "run.json").read_text())["excluded"] == {"txt": 1}
    assert batch.main(["--root", str(root), "--out", str(out), "--engines", "own", "applevision"]) == 2


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    from demo.backend.tools import verify_cases
    root = tmp_path / "FAKE-git"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("ignored/\n")
    (root / "ignored").mkdir()
    monkeypatch.setattr(verify_cases, "REPOSITORY_ROOT", root)
    return root


def test_location_ignored_untracked_tracked_and_outside_fixture(git_repo, tmp_path):
    good = git_repo / "ignored" / "out"
    assert batch._location(good) == good
    with pytest.raises(batch.BatchError):
        batch._location(git_repo / "out")
    tracked = git_repo / "ignored" / "tracked"
    tracked.touch()
    subprocess.run(["git", "add", "-f", str(tracked)], cwd=git_repo, check=True)
    with pytest.raises(batch.BatchError):
        batch._location(tracked)
    with pytest.raises(batch.BatchError):
        batch._location(git_repo / "ignored")
    assert batch._location(tmp_path / "FAKE-external-to-fixture") == tmp_path / "FAKE-external-to-fixture"


def test_output_symlinks_hardlinks_and_root_overlap_rejected(tree):
    root, out = tree
    source = root / "a.pdf"
    source.touch()
    out.mkdir()
    (out / "results.jsonl").symlink_to(source)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 2
    (out / "results.jsonl").unlink()
    os.link(source, out / "results.jsonl")
    assert batch.main(["--root", str(root), "--out", str(out)]) == 2
    (out / "results.jsonl").unlink()
    assert batch.main(["--root", str(root), "--out", str(root)]) == 2
    assert not (root / "errors.jsonl").exists()
    assert source.read_bytes() == b""


def test_summary_policy_quality_denominators_and_no_backend_processing(tree, monkeypatch, capfd):
    root, out = tree
    (root / "a.pdf").touch()
    def process(path, identifier, group, engines):
        row = batch._blank(identifier, group)
        row.update(document_status="FAIL", assessment_code="NONE", detected_type="NHIS_PAYMENT", page_count=1)
        record = batch._engine_record("OK", "NONE")
        record.update(detected_type="NHIS_PAYMENT", fields={field: "X" for field in batch.FIELDS["NHIS_PAYMENT"]},
                      seconds=.5, processed_pages=1, seconds_per_page=.5)
        record["fields"]["성명"] = "O"
        row["fields"] = ["성명"]
        row["engines"]["own"] = record
        row["reasons"] = [{"code": "DOCUMENT_ISSUED_TOO_EARLY", "severity": "FAIL"},
                          {"code": "PAGES_INCOMPLETE", "severity": "FAIL"}]
        return row
    monkeypatch.setattr(batch, "process_file", process)
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    capfd.readouterr()
    monkeypatch.setattr(batch, "inventory", lambda *a: pytest.fail("summary traversed root"))
    monkeypatch.setattr(batch, "_engine", lambda *a: pytest.fail("summary ran OCR"))
    monkeypatch.setattr(batch, "_assess", lambda *a: pytest.fail("summary ran assessment"))
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert batch.main(["--summarize", "--out", str(out)]) == 0
    output = capfd.readouterr().out
    policy = output.split("기준일 정책 사유\n")[1].split("판독 품질 사유\n")[0]
    quality = output.split("판독 품질 사유\n")[1].split("기타 서류 단위 사유\n")[0]
    assert "DOCUMENT_ISSUED_TOO_EARLY\t1/1 100.00%" in policy
    assert "DOCUMENT_ISSUED_TOO_EARLY" not in quality and "PAGES_INCOMPLETE\t1/1 100.00%" in quality
    assert "성명\t1/1 100.00%" in output and "NOT_ASSESSED\t0/1 0.00%" in output
    assert "SKIPPED\t0/1 0.00%" in output and "ERROR\t0/1 0.00%" in output
    assert "INSURANCE_4\t직장가입자" in output and "BIZ_REG_PROOF\t사업소득 사업자" in output
    assert str(root) not in output and "a.pdf" not in output
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_invalid_summary_is_read_only_and_zero_denominators(tree, monkeypatch, capfd):
    root, out = tree
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    capfd.readouterr()
    assert batch.main(["--summarize", "--out", str(out)]) == 0
    assert "0/0 N/A" in capfd.readouterr().out
    (out / "results.jsonl").write_text(SECRET + "\n")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert batch.main(["--summarize", "--out", str(out)]) == 2
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert capfd.readouterr().out == ""


def test_summary_fresh_process_imports_no_ocr_or_models(tree):
    root, out = tree
    assert batch.main(["--root", str(root), "--out", str(out)]) == 0
    code = """import sys
from engine_v2.tools.batch_assess import main
assert main(['--summarize','--out',sys.argv[1]]) == 0
assert 'demo.backend.ocr' not in sys.modules
assert 'engine_v2.pipeline.ocr' not in sys.modules
assert 'onnxruntime' not in sys.modules
assert 'pymupdf' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, str(out)], capture_output=True, check=False)
    assert result.returncode == 0 and not result.stderr


@pytest.mark.parametrize("arguments", [[], ["--out"], ["--out", "FAKE", "--root", "FAKE", "--engines", SECRET],
    ["--out", "FAKE", "--root", "FAKE", "--summarize"], ["--unknown", SECRET]])
def test_argument_errors_do_not_echo(arguments, capfd):
    assert batch.main(arguments) == 2
    assert capfd.readouterr().out == ""
