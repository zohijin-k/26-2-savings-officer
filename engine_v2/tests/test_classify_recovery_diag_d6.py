"""D6: TOO_EARLY issue-date source and gap bins, months read on MISSING_BILLING_MONTHS FAILs (synthetic only)."""
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from engine_v2.tools import classify_recovery_diag as tool
from engine_v2.tests.test_classify_recovery_diag_s3 import acquisition

CUTOFF, TODAY = date(2026, 3, 3), date(2026, 11, 18)


@pytest.mark.parametrize('issue, gap', [
    (CUTOFF - timedelta(days=1), 'D1_30'), (CUTOFF - timedelta(days=30), 'D1_30'),
    (CUTOFF - timedelta(days=31), 'D31_365'), (CUTOFF - timedelta(days=365), 'D31_365'),
    (CUTOFF - timedelta(days=366), 'D366P'), (TODAY + timedelta(days=1), 'FUTURE'),
    (CUTOFF, 'NA'), (None, 'NA'),
])
def test_early_gap_bins(issue, gap):
    assert tool.early_gap(issue, CUTOFF, TODAY) == gap


@pytest.mark.parametrize('months, expected', [
    ({}, 'M0'), ({'2025-10': 1}, 'M1_2'), ({f'2025-{m:02d}': 1 for m in range(1, 4)}, 'M3_5'),
    ({f'2025-{m:02d}': 1 for m in range(1, 7)}, 'M6_11'), ({f'2025-{m:02d}': 1 for m in range(1, 13)}, 'M12P'),
])
def test_billing_bins(months, expected):
    assert tool.billing_bin(json.dumps(months)) == expected
    assert tool.billing_bin(None) == 'NA' and tool.billing_bin('not json') == 'NA'


def test_too_early_fail_records_source_and_gap_only(tmp_path):
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_types import DocType
    from engine_v2.tools import doc_timing
    cutoff = doc_timing.requirement('NHIS_ACQUISITION_LOSS').min_issue_date
    early = (cutoff - timedelta(days=40)).isoformat()
    pages = acquisition((300, 140, '발급일', 8), (360, 140, early, 8))
    ocr = OcrResult(detected_doc_type=DocType.NHIS_ACQUISITION_LOSS, confidence=.95, tier='localocr',
                    fields={'성명': '가상시험', '생년월일': '1990-01-01', '발급일': early})
    path = tmp_path / 'a.pdf'
    path.write_bytes(b'%PDF-1.7')
    row = tool.blank_row('0' * 16)
    row['form'] = 'NHIS_ACQUISITION_LOSS'
    row['decision'], row['reasons'] = tool._assess(path, row['form'], ocr)
    assert ['DOCUMENT_ISSUED_TOO_EARLY', 'FAIL'] in row['reasons']
    tool.failure_detail(SimpleNamespace(read_pages=pages), path, row, ocr)
    assert row['early'] == dict(source='LABEL', gap='D31_365') and row['billing'] is None
    tool.validate_row(row)
    lines = tool.summarize([row], dict(counts={}))
    assert 'D6_EARLY 1' in lines and 'D6_EARLY NHIS_ACQUISITION_LOSS LABEL D31_365 1' in lines


def test_documents_without_those_fails_get_no_detail(tmp_path):
    row = tool.blank_row('0' * 16)
    row['form'], row['reasons'] = 'NHIS_PAYMENT', [['MISSING_BILLING_MONTHS', 'NEEDS_REVIEW']]
    from demo.backend.ocr.base import OcrResult
    tool.failure_detail(SimpleNamespace(read_pages=None), tmp_path, row, OcrResult(None, 0.0))
    assert row['early'] is None and row['billing'] is None
    row['reasons'] = [['MISSING_BILLING_MONTHS', 'FAIL']]
    tool.failure_detail(SimpleNamespace(read_pages=None), tmp_path, row,
                        OcrResult(None, 0.0, fields={'월별고지금액': json.dumps({'2024-01': 1, '2024-02': 1})}))
    assert row['billing'] == dict(months='M1_2')
    tool.validate_row(row)
