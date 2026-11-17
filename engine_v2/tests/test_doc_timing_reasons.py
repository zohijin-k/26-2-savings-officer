"""Verdict reason codes in doc_timing rows (row format 2), synthetic only."""
from dataclasses import dataclass
import json
from pathlib import Path

import pytest

from engine_v2.tools import doc_timing as tool

SECRET = '가짜이름_SYNTHETIC_REASON_SECRET_77120'


@dataclass
class Finding:
    code: str
    severity: str
    message: str = ''
    how_to_fix: str = ''
    detail: str = ''


@dataclass
class Checked:
    status: str
    findings: list


def seconds(total=1.0):
    values = {name: 0.0 for name in tool.STAGES}
    values.update(other=total, total=total)
    return values


def v2_row(**changes):
    row = dict(schema_version=2, key='a' * 16, engine='own', phase='measure', repeat=1, code='NONE',
               form='NHIS_PAYMENT', text_layer='TEXT', pages=1, page_bin='1', first_image_later_text=0,
               tier='localocr', decision='NEEDS_REVIEW', ocr_pages=0, text_pages=1, cold_start=0.0,
               seconds=seconds(), reasons=[['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']])
    row.update(changes)
    return row


def test_reason_codes_keep_registered_codes_and_severities_only():
    findings = [Finding('LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW', message=SECRET, how_to_fix=SECRET, detail=SECRET),
                Finding('LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW', message='다른 문장'),
                Finding('DOCUMENT_ISSUED_TOO_EARLY', 'FAIL'),
                Finding(f'MADE_UP_{SECRET}', 'FAIL'),
                Finding('IDENTITY_MISMATCH', f'WEIRD_{SECRET}')]
    reasons = tool.reason_codes(findings)
    assert reasons == [['DOCUMENT_ISSUED_TOO_EARLY', 'FAIL'], ['IDENTITY_MISMATCH', 'OTHER'],
                       ['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW'], ['UNKNOWN_CODE', 'FAIL']]
    assert SECRET not in json.dumps(reasons, ensure_ascii=False)
    assert tool.reason_codes([]) == [] and tool.reason_codes(None) == []


def test_measure_records_reasons_outside_the_timed_region(monkeypatch, tmp_path):
    from demo.backend import ocr as demo_ocr
    from demo.backend import upload_assessment
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_types import DocType

    ticks = iter(float(i) for i in range(100))
    timer = tool.StageTimer(clock=lambda: next(ticks))
    monkeypatch.setattr(demo_ocr, 'read_document',
                        lambda path, expected: OcrResult(detected_doc_type=DocType.NHIS_PAYMENT, tier='localocr',
                                                         fields={'성명': SECRET}))
    calls = []

    def assess(path, req, **kwargs):
        calls.append(req)
        return None, Checked('NEEDS_REVIEW', [Finding('LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW', message=SECRET),
                                               Finding('LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW')])
    monkeypatch.setattr(upload_assessment, 'assess_upload', assess)

    def no_clock_during_reasons(findings):
        assert timer.active is False
        return original(findings)
    original = tool.reason_codes
    monkeypatch.setattr(tool, 'reason_codes', no_clock_during_reasons)
    result = tool.measure(tmp_path / 'x.pdf', timer, slot=lambda kind: object())
    assert calls and result['decision'] == 'NEEDS_REVIEW' and result['code'] == 'NONE'
    assert result['reasons'] == [['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']]
    # read 0→1; decision 2→5 (its stage reads 3 and 4). Reasons never consult the clock,
    # so the next tick is still 6.
    assert result['seconds']['total'] == pytest.approx(4.0)
    assert next(ticks) == 6.0
    assert SECRET not in json.dumps(result, ensure_ascii=False)


def test_not_assessed_and_errors_have_no_reasons(monkeypatch, tmp_path):
    from demo.backend import ocr as demo_ocr
    from demo.backend.ocr.base import OcrResult
    monkeypatch.setattr(demo_ocr, 'read_document', lambda path, expected: OcrResult(tier='none'))
    result = tool.measure(tmp_path / 'x.pdf', tool.StageTimer(), slot=lambda kind: None)
    assert result['decision'] == 'NOT_ASSESSED' and result['reasons'] == []

    def broken(path, expected):
        raise RuntimeError(SECRET)
    monkeypatch.setattr(demo_ocr, 'read_document', broken)
    result = tool.measure(tmp_path / 'x.pdf', tool.StageTimer(), slot=lambda kind: object())
    assert result['code'] == 'PROCESSING_ERROR' and result['reasons'] == []
    assert SECRET not in json.dumps(result, ensure_ascii=False)


def test_row_validation_accepts_format_1_and_checks_format_2_reasons():
    legacy = {key: value for key, value in v2_row(schema_version=1).items() if key != 'reasons'}
    assert tool.validate_row(legacy) is legacy
    assert tool.validate_row(v2_row())['reasons'] == [['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']]
    for bad in (v2_row(reasons=[['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW'], ['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']]),
                v2_row(reasons=[[SECRET, 'FAIL']]),
                v2_row(reasons=[['LOW_OCR_CONFIDENCE', SECRET]]),
                v2_row(reasons=[['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW', SECRET]]),
                v2_row(reasons=[['PAGES_UNREADABLE', 'FAIL'], ['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']]),
                v2_row(decision='NOT_ASSESSED'),
                {key: value for key, value in v2_row().items() if key != 'reasons'},
                v2_row(schema_version=3)):
        with pytest.raises(Exception):
            tool.validate_row(bad)


def test_strata_from_a_format_1_run_still_loads(tmp_path):
    previous = tmp_path / 'previous'
    previous.mkdir()
    (previous / 'run.json').write_text(json.dumps(dict(schema_version=1)))
    legacy = {key: value for key, value in v2_row(schema_version=1, form='INSURANCE_4').items() if key != 'reasons'}
    (previous / 'rows.jsonl').write_text(json.dumps(legacy) + '\n')
    assert tool.load_strata(previous) == {'a' * 16: 'INSURANCE_4'}


def test_cli_rows_carry_registered_reasons_only(tmp_path, monkeypatch, capsys):
    from engine_v2.pipeline import ocr as v2ocr
    from engine_v2.tests.nhis_form_samples import text_pdf
    from demo.backend.tools.verify_upload import SAFE_CODES
    monkeypatch.setitem(v2ocr.ENGINES, 'own', lambda png, size: [])
    monkeypatch.setattr(tool, 'own_available', lambda: True)
    root = tmp_path / 'FAKE-input'
    root.mkdir()
    text_pdf(root / 'secret-text.pdf', name=SECRET[:4])
    out = tmp_path / 'out'
    assert tool.main(['--root', str(root), '--out', str(out), '--warmup', '0']) == 0
    rows = [json.loads(line) for line in (out / 'rows.jsonl').read_text().splitlines()]
    assert rows and all(row['schema_version'] == 2 and 'reasons' in row for row in rows)
    assert all(code in SAFE_CODES | {'UNKNOWN_CODE'} for row in rows for code, _ in row['reasons'])
    text = (out / 'rows.jsonl').read_text() + (out / 'summary_brief.txt').read_text() + capsys.readouterr().out
    assert SECRET[:4] not in text and 'secret' not in text and str(tmp_path) not in text
    assert 'REASON' not in (out / 'summary_brief.txt').read_text()  # no new summary lines
