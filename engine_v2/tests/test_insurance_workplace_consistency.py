"""A–N authored challenges. No real documents, names, labels or model downloads."""
from datetime import date
import json
import unicodedata

import pytest

from engine_v2.extractors import insurance_4, insurance_workplace as contract
from engine_v2.tests.nhis_form_samples import coordinate_page, insurance_portal_cells

YS = (36, 40, 44, 48)
NAME = "가상솔빛상사"
OTHER = "가상솔빗상사"
NUMBER = "12345678901"


def synthetic_cells(form="government24", names=None, numbers=None):
    names = names if names is not None else [NAME] * 4
    numbers = numbers if numbers is not None else [NUMBER] * 4
    cells = []
    for x, y, text in insurance_portal_cells():
        if form != "portal" and text == "확인용":
            continue
        if x == 65 and y in YS:
            text = names[YS.index(y)]
        if x == 48 and y in YS:
            text = numbers[YS.index(y)]
        cells.append((x, y, text))
    if form == "government24":
        cells.append((10, 60, "문서확인번호 1234-5678-9012-3456"))
    return cells


def synthetic_pages(form="government24", names=None, numbers=None):
    return [coordinate_page(synthetic_cells(form, names, numbers))]


def extract(pages):
    return insurance_4.extract(pages, today=date(2026, 11, 13))


def flat(result):
    return {key: field.value for key, field in result.fields.items()}


@pytest.fixture(params=["government24", "portal"])
def form(request):
    return request.param


def test_A_same_names_keep_structure_and_no_review(form):
    result = extract(synthetic_pages(form))
    assert all(row.management_reliable for row in result.rows)
    assert all(check.passed for check in result.validations)
    assert not result.warnings
    assert result.fields[contract.COUNT_FIELD].value == "명칭목록기준"
    assert not contract.name_review(flat(result))


@pytest.mark.parametrize("confidence", [.4, .99])
def test_B_high_or_low_score_spelling_difference_is_not_replaced(form, confidence):
    pages = synthetic_pages(form, [NAME, OTHER, NAME, NAME])
    next(word for word in pages[0][1].words if word.text == OTHER).confidence = confidence
    result = extract(pages)
    assert contract.name_review(flat(result))
    assert result.warnings == [contract.REASON]
    assert [row.workplace_name for row in result.rows] == [NAME, OTHER, NAME, NAME]
    assert json.loads(result.fields["사업장명칭목록"].value) == [NAME, OTHER]
    assert all(check.passed for check in result.validations)
    assert all(row.acquired == date(2020, 1, 1) for row in result.rows)
    assert result.fields["성명"].confidence >= .85


def test_C_three_active_rows_do_not_vote(form):
    cells = synthetic_cells(form, [NAME, NAME, OTHER, ""])
    cells = [cell for cell in cells if cell[1] not in {48, 49}]
    cells += [(9, 48, "고용보험"), (23, 48, "미가입"), (34, 48, "미가입")]
    result = extract([coordinate_page(cells)])
    assert contract.name_review(flat(result))
    assert [row.workplace_name for row in result.rows[:3]] == [NAME, NAME, OTHER]
    assert result.rows[3].status == "미가입"


def test_F_different_numbers_never_merge_or_infer_conflict(form):
    result = extract(synthetic_pages(form, [NAME, OTHER, NAME, OTHER],
                                     ["12345678901", "12345678902", "12345678903", "12345678904"]))
    assert not contract.name_review(flat(result))
    assert json.loads(result.fields["사업장명칭목록"].value) == [NAME, OTHER]
    assert all(row.management_reliable for row in result.rows)


@pytest.mark.parametrize("score", [.849999, float("nan"), float("inf"), True, False])
def test_G_management_minimum_source_score_gate(form, score):
    pages = synthetic_pages(form, [NAME, OTHER, NAME, NAME])
    for word in pages[0][1].words:
        if word.text == NUMBER:
            word.confidence = score
    result = extract(pages)
    assert not any(row.management_reliable for row in result.rows)
    assert contract.STATE_FIELD not in result.fields


def test_G_exact_minimum_and_split_fragment_minimum(form):
    cells = synthetic_cells(form, [NAME, OTHER, NAME, NAME])
    cells = [cell for cell in cells if not (cell[0] == 48 and cell[1] in YS)]
    for y in YS:
        cells += [(48, y, "123456"), (53, y, "78901")]
    pages = [coordinate_page(cells)]
    for word in pages[0][1].words:
        if word.text in {"123456", "78901"}:
            word.confidence = .85
    assert contract.name_review(flat(extract(pages)))
    for word in pages[0][1].words:
        if word.text == "78901":
            word.confidence = .849999
    assert contract.STATE_FIELD not in extract(pages).fields


@pytest.mark.parametrize("number", ["", "1234567890", "123456789O1", "１２３４５６７８９０１", "12345.678901"])
def test_G_missing_invalid_or_nonascii_number_cannot_establish_group(form, number):
    result = extract(synthetic_pages(form, [NAME, OTHER, NAME, NAME], [number] * 4))
    assert contract.STATE_FIELD not in result.fields


@pytest.mark.parametrize("number", ["123-45-67890-1", "123–45–67890–1", "123 45 67890 1"])
def test_G_clean_general_separators_preserve_existing_reading(number):
    result = extract(synthetic_pages(names=[NAME, OTHER, NAME, NAME], numbers=[number] * 4))
    assert contract.name_review(flat(result))
    assert [row.management_number for row in result.rows] == [NUMBER] * 4


@pytest.mark.parametrize("defect", ["fallback", "duplicate", "weak-header", "crossing"])
def test_G_observed_independent_column_proof_required(form, defect):
    pages = synthetic_pages(form, [NAME, OTHER, NAME, NAME])
    words = pages[0][1].words
    if defect == "fallback":
        words[:] = [word for word in words if word.text != "관리번호"]
    elif defect == "duplicate":
        from dataclasses import replace
        words.append(replace(next(word for word in words if word.text == "관리번호")))
    elif defect == "weak-header":
        next(word for word in words if word.text == "관리번호").confidence = .84
    else:
        for word in words:
            if word.text == NUMBER:
                word.bbox_px = (*word.bbox_px[:2], 660, word.bbox_px[3])
    assert contract.STATE_FIELD not in extract(pages).fields


def test_H_exact_selection_transformation_join_and_final_stages(form):
    cells = [cell for cell in synthetic_cells(form) if not (cell[0] == 65 and cell[1] in YS)]
    for y in YS:
        cells += [(65, y, "(가상)"), (70, y + .9, "[솔빛]")]
    result = extract([coordinate_page(cells)])
    for row in result.rows:
        assert [word.text for word in row.workplace_words] == ["(가상)", "[솔빛]"]
        if form == "government24":
            assert row.workplace_fragments == ["가상", "솔빛"]
            assert row.workplace_joined == row.workplace_name == "가상솔빛"
        else:
            assert row.workplace_fragments == ["(가상)", "[솔빛]"]
            assert row.workplace_joined == "(가상)[솔빛]"
            assert row.workplace_name == "가상)[솔빛"


def test_I_inactive_stale_name_is_excluded(form):
    cells = synthetic_cells(form, [NAME, NAME, NAME, OTHER])
    cells = [(x, y, "미가입" if y == 48 and x in {23, 34} else text) for x, y, text in cells]
    result = extract([coordinate_page(cells)])
    assert contract.STATE_FIELD not in result.fields
    assert json.loads(result.fields["사업장명칭목록"].value) == [NAME]


def test_J_same_names_different_numbers_are_only_an_observed_name_list(form):
    result = extract(synthetic_pages(form, numbers=[f"1234567890{i}" for i in range(1, 5)]))
    assert len({row.management_number for row in result.rows}) == 4
    assert json.loads(result.fields["사업장명칭목록"].value) == [NAME]
    assert result.fields[contract.COUNT_FIELD].value == "명칭목록기준"


def test_L_unknown_form_does_not_gain_trust():
    result = extract(synthetic_pages("unknown", [NAME, OTHER, NAME, NAME]))
    assert result.form_kind == "unknown"
    assert contract.STATE_FIELD not in result.fields
    assert result.structure_complete is False


def test_M_fused_number_name_keeps_extraction_but_cannot_prove_group():
    cells = [cell for cell in synthetic_cells(names=[NAME, OTHER, NAME, NAME])
             if not (cell[0] in {48, 65} and cell[1] in YS)]
    for y, name in zip(YS, [NAME, OTHER, NAME, NAME]):
        cells.append((48, y, NUMBER + name))
    result = extract([coordinate_page(cells)])
    assert [row.workplace_name for row in result.rows] == [NAME, OTHER, NAME, NAME]
    assert all(row.workplace_fused and not row.management_reliable for row in result.rows)
    assert contract.STATE_FIELD not in result.fields


def test_A_comparison_is_nfc_and_collapsed_whitespace_only():
    assert contract.comparison_key(" 가상  솔빛 ") == "가상 솔빛"
    assert contract.comparison_key(unicodedata.normalize("NFD", NAME)) == NAME
    assert contract.comparison_key(NAME) != contract.comparison_key(OTHER)
    assert contract.comparison_key("(주)" + NAME) != NAME
    assert contract.comparison_key("가상 솔빛") != "가상솔빛"


def test_M_identical_plausible_wrong_names_are_an_explicit_detection_limit(form):
    result = extract(synthetic_pages(form, [OTHER] * 4))
    assert not contract.name_review(flat(result))
    assert [row.workplace_name for row in result.rows] == [OTHER] * 4


def test_N_normal_and_conflicting_extraction_never_calls_ocr(form, monkeypatch):
    from engine_v2.pipeline import ocr
    def forbidden(*args, **kwargs):
        pytest.fail("Extraction must not add an OCR call")
    monkeypatch.setattr(ocr, "run_ocr", forbidden)
    assert not contract.name_review(flat(extract(synthetic_pages(form))))
    assert contract.name_review(flat(extract(synthetic_pages(form, [NAME, OTHER, NAME, NAME]))))


def test_B_direct_engine_receives_review_and_keeps_confirmed_failure():
    from engine_v2.engine import evaluate_document
    from engine_v2.schemas.models import ApplicationInput, ApplicantInput, DocType, DocumentInput, ProgramId, Verdict
    from engine_v2.tests.nhis_form_samples import NAME as PERSON
    pages = synthetic_pages(names=[NAME, OTHER, NAME, NAME])
    document = DocumentInput(doc_id="FAKE", declared_type=DocType.INSURANCE_4, file_path="FAKE.pdf")
    app = ApplicationInput(application_id="FAKE", program_id=ProgramId.DOUBLING_SAVINGS,
        announcement_date=date(2026, 3, 3), applicant=ApplicantInput(name=PERSON, birth_date=date(1990, 1, 1)),
        documents=[document])
    result = evaluate_document(document, pages, app, {"documents": {}}, extractor_result=extract(pages))
    assert result.verdict == Verdict.NEEDS_REVIEW and contract.REASON in result.review_reasons
    rules = {"documents": {"insurance_4": {"rules": [{"id": "FAKE-TYPE", "type": "doc_type_is",
             "params": {"expected": "resident_abstract"}, "applicant": "가상 불일치", "reviewer": "가상"}]}}}
    result = evaluate_document(document, pages, app, rules, extractor_result=extract(pages))
    assert result.verdict == Verdict.UNSUITABLE
    assert contract.REASON in result.review_reasons


def test_K_proof_survives_privacy_masking_even_when_hash_contains_rrn_shape(monkeypatch):
    from engine_v2.pipeline.privacy import mask_data, mask_rrn
    fields = flat(extract(synthetic_pages(names=[NAME, OTHER, NAME, NAME])))
    hexadecimal = "a" + date(1990, 1, 1).strftime("%y%m%d") + "1" + "234567b" + "f" * 49
    class FictitiousDigest:
        def hexdigest(self): return hexadecimal
        def digest(self): return bytes.fromhex(hexadecimal)
    assert mask_rrn(hexadecimal) != hexadecimal  # Demonstrate the original collision.
    monkeypatch.setattr(contract.hashlib, "sha256", lambda value: FictitiousDigest())
    fields[contract.PROOF_FIELD] = contract.proof(fields["가입내역"], [[0, 1, 2, 3]])
    assert mask_data(fields) == fields
    assert contract.name_review(mask_data(fields))


@pytest.mark.parametrize("variant", ["unicode", "whitespace"])
def test_A_representation_comparison_does_not_rewrite_the_public_name_list(form, variant):
    if variant == "unicode":
        first, second = NAME, unicodedata.normalize("NFD", NAME)
    else:
        first, second = "가상 솔빛", "가상  솔빛"
    result = extract(synthetic_pages(form, [first, second, first, second]))
    assert all(row.management_reliable for row in result.rows)
    assert contract.STATE_FIELD not in result.fields
    if form == "portal" and variant == "whitespace":
        assert [row.workplace_name for row in result.rows] == ["가상솔빛"] * 4
        assert json.loads(result.fields["사업장명칭목록"].value) == ["가상솔빛"]
    else:
        assert [row.workplace_name for row in result.rows] == [first, second, first, second]
        assert json.loads(result.fields["사업장명칭목록"].value) == [first, second]
