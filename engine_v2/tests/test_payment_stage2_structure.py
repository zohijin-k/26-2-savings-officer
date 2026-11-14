"""Synthetic regression shapes for conservative government payment repairs."""
import json

import pytest

from engine_v2.extractors import nhis_payment
from engine_v2.tests import p2_payment_samples as base, payment_stage2_samples as shapes


def extract(cells, size, **geometry):
    return nhis_payment.extract([base.page(cells, size=size, **geometry)])


@pytest.mark.parametrize("optional", [False, True])
@pytest.mark.parametrize("corrected", [False, True])
@pytest.mark.parametrize("scale", [.8, 1, 1.6])
def test_adjustment_is_separate_from_twelve_months_and_income_average(optional, corrected, scale):
    cells, size, _ = shapes.adjustment(optional=optional, corrected=corrected)
    result = extract(cells, size, scale=scale)
    assert result.form_kind == "government_payment"
    assert result.structure_complete, [v.name for v in result.validations if not v.passed]
    rows = json.loads(result.fields["월별납부내역"].value)
    assert len(rows) == 12
    assert json.loads(result.fields["월별고지금액"].value)["2025-12"] == "30000"
    assert result.fields["건강보험료"].value == "50000"
    assert result.fields["장기요양보험료"].value == "5000"
    assert result.fields["납부총액"].value == str((166100 if optional else 165000) + (352 if optional else 330))
    assert all(v.passed for v in result.validations if v.name.startswith("payment_column_"))


def test_observed_zero_adjustment_does_not_pollute_month_values():
    cells, size, _ = shapes.adjustment(amounts=[0, 0, None, None, 0, 0, None, None])
    result = extract(cells, size)
    assert result.structure_complete
    assert result.fields["건강보험료"].value == "50000"
    assert result.fields["납부총액"].value == "165000"


def test_adjustment_never_fills_missing_monthly_health_cells():
    cells, size, _ = shapes.adjustment()
    cells = [c for c in cells if not (c[1] == 1611 and c[4] == "30,000")]
    result = extract(cells, size)
    assert result.structure_complete is False
    assert "건강보험료" not in result.fields
    assert "2025-12" not in json.loads(result.fields["월별고지금액"].value)


@pytest.mark.parametrize("label", ["연말 정산", "연말정산액", "(연말정산)", "다른항목", ""])
def test_unproven_adjustment_label_remains_incomplete(label):
    cells, size, _ = shapes.adjustment(label=label)
    assert extract(cells, size).structure_complete is False


@pytest.mark.parametrize("defect", ["duplicate", "low-label-confidence", "missing-required", "unknown-value",
                                  "negative", "low-value-confidence", "sum-mismatch", "grand-mismatch",
                                  "extra-label", "misplaced", "crossing"])
def test_uncertain_adjustment_cannot_make_form_complete(defect):
    cells, size, y = shapes.adjustment()
    changed = []
    for x0, y0, x1, y1, text, confidence in cells:
        if y0 == y and text == "연말정산":
            if defect == "low-label-confidence":
                confidence = .4
            if defect == "misplaced":
                y0 -= 120
                y1 -= 120
        if y0 == y and text == "700":
            if defect == "missing-required":
                continue
            if defect in {"unknown-value", "negative"}:
                text = "Z" if defect == "unknown-value" else "-700"
            if defect == "low-value-confidence":
                confidence = .3
            if defect == "crossing":
                x1 += 220
        if defect == "sum-mismatch" and y0 > y and text == "150,700":
            text = "150,701"
        if defect == "grand-mismatch" and x0 == 738:
            text = "165,331"
        changed.append((x0, y0, x1, y1, text, confidence))
    if defect in {"duplicate", "extra-label"}:
        changed.append(base.cell(182, y, 274, y + 48, "연말정산" if defect == "duplicate" else "추가", 1))
    result = extract(changed, size)
    assert result.structure_complete is False
    assert all(f.confidence <= .4 for f in result.fields.values())


@pytest.mark.parametrize("scale", [.7, 1, 1.7])
@pytest.mark.xfail(strict=True, reason="C2 header-edge recovery held")
def test_clipped_upper_fragments_require_complete_unique_heading_evidence(scale):
    cells, size = shapes.clipped_headers()
    result = extract(cells, size, scale=scale)
    assert result.form_kind == "government_payment"
    assert result.structure_complete, [v.name for v in result.validations if not v.passed]
    assert result.fields["건강보험료"].value == "50000"


@pytest.mark.parametrize("defect", ["missing", "extra", "swapped", "conflicting", "low-confidence"])
def test_clipped_header_recovery_does_not_invent_fragments(defect):
    cells, size = shapes.clipped_headers()
    upper = [c for c in cells if c[4] == "보수외"]
    selected = upper[1]
    if defect == "missing":
        cells.remove(selected)
    elif defect == "extra":
        cells.append(base.cell(selected[0], selected[1] + 8, selected[2], selected[3] + 8, "다른", 1))
    elif defect == "swapped":
        cells = [(*c[:4], "(건강)" if c[4] == "(요양)" else c[4], c[5]) for c in cells]
    elif defect == "low-confidence":
        cells = [(*c[:5], .3) if c == selected else c for c in cells]
    else:
        cells.append(base.cell(selected[0], selected[1], selected[2], selected[3], "보수외", 1))
    assert extract(cells, size).structure_complete is False


@pytest.mark.parametrize("scale", [.7, 1, 1.7])
def test_fused_neighbor_headers_use_unique_complete_labels_and_body_corridors(scale):
    cells, size = shapes.fused_headers()
    result = extract(cells, size, scale=scale)
    assert result.form_kind == "government_payment"
    assert result.structure_complete, [v.name for v in result.validations if not v.passed]
    assert result.fields["건강보험료"].value == "50000"
    assert len(json.loads(result.fields["월별납부내역"].value)) == 12


@pytest.mark.parametrize("defect", ["missing-fragment", "duplicate-fragment", "swapped", "unknown-fragment",
                                  "merged-observation", "crossing-body", "ambiguous-corridor"])
def test_fused_headers_without_unique_evidence_keep_original_review(defect):
    cells, size = shapes.fused_headers()
    selected = next(c for c in cells if c[4] == "소득월액")
    if defect == "missing-fragment":
        cells.remove(selected)
    elif defect == "duplicate-fragment":
        cells.append(selected)
    elif defect == "swapped":
        cells = [(*c[:4], "(요양)" if c[4] == "(건강)" else c[4], c[5]) for c in cells]
    elif defect == "unknown-fragment":
        cells.append(base.cell(selected[0], selected[1], selected[2], selected[3], "미상", 1))
    elif defect == "merged-observation":
        care = next(c for c in cells if c[4] == "장기요양")
        upper = next(c for c in cells if c[4] == "보수외")
        cells = [c for c in cells if c not in (care, upper)]
        cells.append(base.cell(539, 820, 869, 889, "장기요양보수외", 1))
    elif defect == "crossing-body":
        cells.append(base.cell(660, 962, 800, 1011, "7", 1))
    else:
        # A second persistent amount corridor is not a license to choose one.
        cells.append(base.cell(695, 962, 710, 1011, "7", 1))
    assert extract(cells, size).structure_complete is False


def test_fused_headers_with_empty_optional_corridors_remain_unresolved():
    cells, size = shapes.fused_headers(optional=False)
    assert extract(cells, size).structure_complete is False
