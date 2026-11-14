"""Synthetic-only tests for exact-mask structure and bounded diagnostics."""
from __future__ import annotations

from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest

from engine_v2.tools import batch_assess as batch, layout_dump, structure_dump as dump
from engine_v2.pipeline.ocr import OcrResult, OcrWord
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.tests import p2_payment_samples as sample
from engine_v2.tests.p2_form_samples import page as coordinate_page

# These authored values deliberately differ from labels and geometry.
VALUES = ("가상검증인", "123,457,891", "123457891", "37482910567", "2097.04.23", "SYNTHETIC_VALUE_ZQX")


def pdf(path, texts=None):
    import pymupdf
    document = pymupdf.open()
    for text in texts or [" ".join(VALUES) + " 고지금액"]:
        page = document.new_page()
        writer = pymupdf.TextWriter(page.rect)
        writer.append((30, 60), text, font=pymupdf.Font("cjk"), fontsize=9)
        writer.write_text(page)
    document.save(path)
    document.close()
    return path


def payment():
    cells, size = sample.payment(name=VALUES[0])
    return [coordinate_page(cells, size=size)]


def no_leak(report, captured=""):
    text = json.dumps(report, ensure_ascii=False) + captured
    for value in VALUES:
        assert value not in text
    assert all(key not in text for key in ('"raw"', '"fields"', '"source"', '"filename"'))


def test_vocabulary_is_exact_module_constants_and_only_28():
    from engine_v2.extractors import nhis_payment as l, nhis_payment_gov as g
    expected = set(l.CARE + l.HEALTH + l.OUTSIDE_HEALTH + l.MONTH_LABELS + l.TABLE_LABELS +
                   l.TABLE_LABEL_FRAGMENTS + g.COMPONENTS + g.HEADERS + g.GROUPS)
    assert dump.label_vocabulary() == expected
    assert len(expected) == 28
    assert not {"성명", "납부자번호", "가입자 성명", "보수외", "소득월액", "서울"} & expected


@pytest.mark.parametrize("word,expected", [
    ("고지금액", "고지금액"), ("고지금액:123,450", "가가가가:999,999"),
    (" 고지금액", " 가가가가"), ("고지금액 ", "가가가가 "),
    ("성명", "가가"), ("서울특별시", "가가가가가"), ("보수외", "가가가"),
    ("12월", "99가"), ("AbÉ １２٣", "AAA 999"), ("Ａｂⓒ𝐃", "AAAA"),
    ("가ᄀㄱ힣", "가가가가"), ("漢字カナαБ", "??????"),
    ("():,.-/*＊□◆©\n\t", "():,.-/*＊□◆©\n\t"),
])
def test_exact_whole_word_shape(word, expected):
    assert dump.mask_word(word, dump.label_vocabulary()) == expected


def test_projection_preserves_word_order_unrounded_boxes_and_confidence():
    words = [OcrWord(VALUES[0], .912345, (100.123456, 20.25, 161.234567, 43.875)),
             OcrWord("고지금액", .87654, (1.05, 2.5, 90.00001, 10.8))]
    projected = [dump._word(w, i, dump.label_vocabulary()) for i, w in enumerate(words)]
    assert projected[0]["bbox_px"] == list(words[0].bbox_px)
    assert projected[0]["confidence"] == words[0].confidence
    assert projected[0]["width_px"] == words[0].bbox_px[2] - words[0].bbox_px[0]
    assert [item["word_index"] for item in projected] == [0, 1]
    assert projected[1]["text"] == "고지금액"
    no_leak(projected)


@pytest.mark.parametrize("box,confidence", [
    ((1, 2, float("nan"), 4), .9), ((3, 2, 1, 4), .9),
    ((1, 2, 3, 4), float("inf")), ((1, 2, 3, 4), 1.1), ((True, 2, 3, 4), .9),
])
def test_invalid_word_geometry_is_not_serialized(box, confidence):
    with pytest.raises(ValueError):
        dump._word(OcrWord(VALUES[0], confidence, box), 0, dump.label_vocabulary())


def test_government_diagnostic_counts_actual_headers_and_months_and_restores_helpers():
    from engine_v2.extractors import nhis_payment_gov as g
    before = (g.recognizes, g._monthly_table, g._header_columns, g._header_clusters)
    result = dump.diagnose(payment(), dump.label_vocabulary())
    assert (g.recognizes, g._monthly_table, g._header_columns, g._header_clusters) == before
    assert result["state"] == "OK" and result["reader"] == "government_payment"
    assert result["header_group_count"] == result["header_groups_matched"] == result["header_groups_expected"] == 9
    assert result["header_count_scope"] == "GOVERNMENT_TABLE"
    assert result["month_count"] == 12 and result["table_months_missing"] is False
    assert set(result["recognized_headers"]) <= dump.label_vocabulary()
    assert "고지금액" in result["recognized_headers"]
    assert result["billing_cause"] == "NONE"
    no_leak(result)


def test_partial_component_header_loss_and_printed_months_are_separate_from_billing_cause():
    pairs = payment()
    page, words = pairs[0]
    # Delete one component heading cluster while retaining government recognition evidence.
    words.words = [w for w in words.words if not (390 < (w.bbox_px[0]+w.bbox_px[2])/2 < 425 and 820 < w.bbox_px[1] < 950)]
    result = dump.diagnose(pairs, dump.label_vocabulary())
    assert result["header_group_count"] == 8
    assert result["header_groups_matched"] == 8
    assert result["month_count"] == 12
    assert "payment_component_headers" in result["failed_validations"]
    assert result["table_months_missing"] is False
    # The original checker falls through to its missing monetary-map review,
    # despite the readable period and all twelve printed month anchors.
    assert result["billing_cause"] == "MONTHLY_MAP_MISSING_OR_UNREADABLE"
    no_leak(result)


def test_split_month_routes_to_legacy_and_counts_actual_months():
    pairs = payment()
    _, result = pairs[0]
    replaced = []
    for word in result.words:
        if word.text.endswith("월") and word.text[:-1].isdigit():
            x0, y0, x1, y1 = word.bbox_px
            mid = (x0 + x1) / 2
            replaced += [OcrWord(word.text[:-1], word.confidence, (x0, y0, mid, y1)),
                         OcrWord("월", word.confidence, (mid, y0, x1, y1))]
        else:
            replaced.append(word)
    result.words = replaced
    diagnostic = dump.diagnose(pairs, dump.label_vocabulary())
    assert diagnostic["reader"] == "legacy_payment"
    assert diagnostic["month_count"] == 12
    assert diagnostic["month_count_scope"] == "LEGACY_TABLE"
    assert "monthly_total_matches" in diagnostic["failed_validations"]
    no_leak(diagnostic)


def test_missing_printed_month_count_is_not_confused_with_period_uncertainty():
    pairs = payment()
    pairs[0][1].words = [w for w in pairs[0][1].words if w.text != "12월"]
    result = dump.diagnose(pairs, dump.label_vocabulary())
    assert result["month_count"] == 11
    assert result["table_months_missing"] is True
    assert result["header_groups_matched"] == 9
    assert result["billing_cause"] == "MONTHLY_MAP_MISSING_OR_UNREADABLE"


@pytest.mark.parametrize("observed,expected", [
    (["건강보험료"] * 9, 2),
    (["월"] * 9, 1),
    (["월별", "건강보험료", "장기요양보험료", "보수외소득월액(건강)", "보수외소득월액(요양)",
      "건강보험료", "장기요양보험료", "보수외소득월액(건강)", "보수외소득월액(요양)", "건강보험료"], 9),
    (["청구월", "납부금액"], 0),
])
def test_matched_header_count_respects_expected_nine_slot_quotas(observed, expected):
    from engine_v2.extractors.nhis_payment_gov import HEADERS
    assert dump._matched_headers(observed, HEADERS) == expected


@pytest.mark.parametrize("raw", [None, "invalid-json", "[]", '{}', '{"2025-10":"12"}'])
def test_historical_missing_or_damaged_monthly_map_is_a_separate_cause(raw):
    from demo.backend.ocr.base import OcrResult as DemoOcr
    from demo.backend.rules.doc_check import _check_billing_months
    fields = {} if raw is None else {"월별고지금액": raw}
    ocr = DemoOcr(fields=fields)
    requirement = batch._requirement("NHIS_PAYMENT")
    findings = _check_billing_months(ocr, requirement)
    assert findings
    assert dump._billing_cause(ocr, requirement, findings)[1] == "MONTHLY_MAP_MISSING_OR_UNREADABLE"


@pytest.mark.parametrize("data,months,cause", [
    ({"status": "CONFLICT"}, ["2025-10"], "PERIOD_CONFLICT"),
    ({"status": "UNDETERMINED"}, ["2025-10"], "PERIOD_UNCERTAIN_OR_MISSING"),
    ({"version": 1, "status": "READABLE", "period": ["2025-99", "2026-12"]}, ["2025-10"], "PERIOD_UNCERTAIN_OR_MISSING"),
    ({"version": 1, "status": "READABLE", "period": ["2025-12", "2025-01"]}, ["2025-10"], "PERIOD_UNCERTAIN_OR_MISSING"),
    ({"version": 1, "status": "READABLE", "period": ["2025-11", "2025-12"]}, ["2025-10"], "QUERY_RANGE_MISSING_REQUIRED_MONTHS"),
    ({"version": 1, "status": "READABLE", "period": ["2025-01", "2025-12"], "amounts_certain": True,
      "absent_amount_months": ["2025-10"], "uncertain_absent_amount_months": []}, ["2025-10"], "CONFIRMED_AMOUNT_MONTHS_MISSING"),
    ({"version": 1, "status": "READABLE", "period": ["2025-01", "2025-12"], "amounts_certain": True,
      "absent_amount_months": [], "uncertain_absent_amount_months": ["2025-10"]}, ["2025-10"], "AMOUNT_ABSENCE_UNCERTAIN"),
])
def test_cause_projection_agrees_with_existing_billing_checker(data, months, cause):
    from demo.backend.ocr.base import OcrResult as DemoOcr
    from demo.backend.rules.doc_check import _check_billing_months
    from engine_v2.extractors.payment_period import FIELD
    requirement = deepcopy(batch._requirement("NHIS_PAYMENT"))
    requirement.premium_months = months
    ocr = DemoOcr(fields={FIELD: json.dumps(data)})
    findings = _check_billing_months(ocr, requirement)
    assert findings
    missing, actual, severity = dump._billing_cause(ocr, requirement, findings)
    assert missing is True and actual == cause
    assert severity in {"FAIL", "NEEDS_REVIEW"}


def test_unknown_validation_is_fixed_marker(monkeypatch):
    from engine_v2.extractors import nhis_payment as l, nhis_common as c
    original = l.extract
    def injected(*a, **kw):
        result = original(*a, **kw)
        result.validations.append(c.Validation(VALUES[-1], False))
        return result
    monkeypatch.setattr(l, "extract", injected)
    result = dump.diagnose(payment(), dump.label_vocabulary())
    assert "UNKNOWN_VALIDATION" in result["failed_validations"]
    no_leak(result)


def test_saved_dump_and_console_contain_no_synthetic_document_values(tmp_path, monkeypatch, capfd):
    source, out = pdf(tmp_path / (VALUES[-1] + ".pdf")), tmp_path / "safe.json"
    def recognize(engine, page):
        # Exercise dependency/native output suppression, not just pure projection.
        print(VALUES[0]); logging.warning(VALUES[1]); os.write(2, VALUES[2].encode())
        return OcrResult(engine, [OcrWord(v, .98, (20+i*50, 20, 60+i*50, 40)) for i, v in enumerate(VALUES)] +
                         [OcrWord("고지금액", .99, (20, 100, 110, 125))])
    monkeypatch.setattr(batch, "_recognize", recognize)
    assert layout_dump.main([str(source), "--out", str(out)]) == 0
    report = json.loads(out.read_text())
    captured = capfd.readouterr()
    assert captured.err == ""
    assert str(source) not in captured.out and str(out) not in captured.out
    no_leak(report, captured.out)
    # Scan every saved dump artifact, including unexpected temporary siblings.
    for path in tmp_path.iterdir():
        if path != source and path.is_file():
            for value in VALUES:
                assert value.encode() not in path.read_bytes()
    assert set(report["engines"]) == set(dump.ENGINES)
    assert all(item["diagnostics"]["state"] == "OK" for item in report["engines"].values())
    assert report["engines"]["own"]["pages"][0]["words"][0]["text"] == "가가가가가"


def test_partial_text_keeps_page_words_and_marks_unavailable_diagnostics(tmp_path, monkeypatch):
    source, out = pdf(tmp_path / "partial.pdf", [" ".join(VALUES), ""]), tmp_path / "safe.json"
    monkeypatch.setattr(batch, "_recognize", lambda engine, page: OcrResult(engine, []))
    assert dump.run(source, out) == 0
    text = json.loads(out.read_text())["engines"]["text_layer"]
    assert len(text["pages"]) == 2
    assert text["pages"][0]["state"] == "OK" and text["pages"][0]["words"]
    assert text["pages"][1]["state"] == "NOT_APPLICABLE" and text["pages"][1]["words"] == []
    assert text["diagnostics"]["state"] == "NOT_RUN"
    no_leak(text)


def test_optional_apple_missing_is_distinct_from_engine_failure(tmp_path, monkeypatch):
    source, out = pdf(tmp_path / "fake.pdf"), tmp_path / "safe.json"
    def recognize(engine, page):
        if engine == "applevision":
            raise ImportError(VALUES[-1])
        return OcrResult(engine, [])
    monkeypatch.setattr(batch, "_recognize", recognize)
    assert dump.run(source, out) == 0
    report = json.loads(out.read_text())
    assert report["engines"]["applevision"]["pages"][0]["code"] == "ENGINE_UNAVAILABLE"
    assert report["engines"]["applevision"]["pages"][0]["state"] == "SKIPPED"
    no_leak(report)
    def fail(engine, page):
        raise RuntimeError(VALUES[-1])
    monkeypatch.setattr(batch, "_recognize", fail)
    assert dump.run(source, out) == 1
    no_leak(json.loads(out.read_text()))


@pytest.mark.parametrize("attempt", ["write", "network"])
def test_swallowed_guard_attempt_preserves_prior_output(tmp_path, monkeypatch, capfd, attempt):
    source, out = pdf(tmp_path / "fake.pdf"), tmp_path / "safe.json"
    out.write_bytes(b"previous safe output")
    def recognize(engine, page):
        try:
            if attempt == "write":
                (tmp_path / VALUES[-1]).write_text(VALUES[0])
            else:
                socket.getaddrinfo("example.invalid", 443)
        except Exception:
            pass
        return OcrResult(engine, [])
    monkeypatch.setattr(batch, "_recognize", recognize)
    assert dump.run(source, out) == 2
    assert out.read_bytes() == b"previous safe output"
    assert not (tmp_path / VALUES[-1]).exists()
    no_leak({}, "".join(capfd.readouterr()))


def test_source_alias_and_hardlink_rejected_without_echo(tmp_path, capfd):
    source = pdf(tmp_path / "fake.pdf")
    before = source.read_bytes()
    assert dump.run(source, source) == 2
    alias = tmp_path / "alias.json"
    os.link(source, alias)
    assert dump.run(source, alias) == 2
    assert source.read_bytes() == before
    assert str(source) not in capfd.readouterr().out


def test_tracked_and_unignored_outputs_rejected_before_processing(tmp_path, monkeypatch, capfd):
    from demo.backend.tools import verify_cases

    source = pdf(tmp_path / "fake.pdf")
    repo = tmp_path / "FAKE-checkout"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("ignored/\n")
    (repo / "ignored").mkdir()
    tracked = repo / "ignored" / "tracked.json"
    tracked.write_bytes(b"previous tracked content")
    subprocess.run(["git", "add", "-f", "--", "ignored/tracked.json"], cwd=repo, check=True)
    monkeypatch.setattr(verify_cases, "REPOSITORY_ROOT", repo)
    before = tracked.read_bytes()
    monkeypatch.setattr(dump, "build", lambda *_: pytest.fail("unsafe destination processed"))
    assert dump.run(source, tracked) == 2
    unignored = repo / "FAKE-unignored-structure.json"
    assert not unignored.exists()
    assert dump.run(source, unignored) == 2
    assert not unignored.exists() and tracked.read_bytes() == before
    assert str(tracked) not in capfd.readouterr().out


def test_symlink_output_rejected_without_changing_target(tmp_path, monkeypatch):
    source = pdf(tmp_path / "fake.pdf")
    target, alias = tmp_path / "safe.json", tmp_path / "alias.json"
    target.write_bytes(b"old safe output")
    alias.symlink_to(target)
    monkeypatch.setattr(dump, "build", lambda *_: pytest.fail("symlink destination processed"))
    assert dump.run(source, alias) == 2
    assert target.read_bytes() == b"old safe output"


def test_atomic_failure_retains_prior_bytes_and_path_free_error(tmp_path, monkeypatch, capfd):
    source, out = pdf(tmp_path / "fake.pdf"), tmp_path / "safe.json"
    out.write_bytes(b"previous safe output")
    monkeypatch.setattr(batch, "_recognize", lambda engine, page: OcrResult(engine, []))
    def fail(*a):
        raise OSError(VALUES[-1])
    monkeypatch.setattr(os, "replace", fail)
    assert dump.run(source, out) == 2
    assert out.read_bytes() == b"previous safe output"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fake.pdf", "safe.json"]
    no_leak({}, "".join(capfd.readouterr()))


def test_cli_conflicts_and_invalid_args_do_not_echo(tmp_path, capfd):
    assert layout_dump.main([str(tmp_path / VALUES[-1]), "--out", "fake", "--engine", "own"]) == 2
    assert layout_dump.main(["--unknown", VALUES[-1]]) == 2
    output = "".join(capfd.readouterr())
    assert VALUES[-1] not in output and str(tmp_path) not in output
