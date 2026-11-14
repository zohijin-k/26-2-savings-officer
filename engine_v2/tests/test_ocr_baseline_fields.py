"""Synthetic-only reference geometry and symmetric masking field contracts."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest

from engine_v2.tools import ocr_baseline_fields as fields


def _word(text, x, y, width=100):
    from engine_v2.pipeline.ocr import OcrWord
    return OcrWord(text, 1.0, (x, y, x + width, y + 10))


def _page(words, size=(1000, 1400)):
    from engine_v2.pipeline.ocr import OcrResult
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    page = PageImage(0, PageSource.TEXT_LAYER, (595, 842), pixel_size=size, dpi=300)
    return page, OcrResult("text_layer", deepcopy(words))


def _legacy():
    words = [_word("건강보험료 납부확인서", 100, 50, 400),
             _word("가짜이름", 100, 120), _word("년월", 100, 300, 70),
             _word("고지금액", 400, 300), _word("납부금액", 750, 300)]
    for index, (month, value) in enumerate((("2025.10", "100,000"), ("2025.11", "110,000"), ("2025.12", "120,000"))):
        words.extend([_word(month, 100, 350 + index * 40),
                      _word(value, 400, 350 + index * 40),
                      _word(value, 750, 350 + index * 40)])
    words.extend([_word("합계", 100, 480), _word("330,000", 400, 480),
                  _word("국민건강보험공단", 100, 600, 300)])
    return _page(words)


def _government():
    from engine_v2.pipeline.ocr import OcrWord
    from engine_v2.tests.p2_payment_samples import payment
    cells, size = payment(corrected=False)
    words = [OcrWord(text, 1.0, (x0, y0, x1, y1)) for x0, y0, x1, y1, text, _ in cells]
    return _page(words, size)


def test_module_import_does_not_load_engines_or_backend():
    code = ("import sys; import engine_v2.tools.ocr_baseline_fields; "
            "assert not any(k.startswith('demo.backend') or k.startswith('engine_v2.pipeline') "
            "for k in sys.modules)")
    subprocess.run([sys.executable, "-B", "-c", code], check=True, capture_output=True)


@pytest.mark.parametrize("chunks", [["900101-1234567"], ["900101-", "123", "4567"], ["９００１０１－", "１２３", "４５６７"]])
def test_reference_and_pre_masked_ocr_have_identical_idempotent_boundary(chunks):
    words, x = [], 10
    for chunk in chunks:
        words.append(_word(chunk, x, 10, len(chunk) * 10))
        x += len(chunk) * 10 + 1
    before = deepcopy(words)
    reference = fields.normalize_words(words)
    observed = fields.normalize_words(fields.normalize_words(words))
    assert [word.text for word in reference] == [word.text for word in observed]
    assert [word.text for word in words] == [word.text for word in before]
    assert "".join(word.text for word in reference) == "900101-1******"
    assert [word.bbox_px for word in reference] == [word.bbox_px for word in words]


def test_prepare_pairs_retains_same_word_boundary_for_both_engines():
    words = [_word("９００１０１－１２３４５６７", 10, 10, 150)]
    page, _ = _page([])
    left = fields.prepare_pairs(page, words, "text_layer")[0][1]
    right = fields.prepare_pairs(page, words, "own")[0][1]
    assert left.words[0].text == right.words[0].text == "900101-1******"
    assert words[0].text == "９００１０１－１２３４５６７"


@pytest.mark.parametrize("split", [False, True])
def test_actual_extractor_fields_match_after_reference_ocr_mask_parity(split):
    from engine_v2.extractors import nhis_acquisition_loss
    from engine_v2.tests.nhis_form_samples import coordinate_page

    page, source = coordinate_page()
    reference = deepcopy(source.words)
    identity = next(word for word in reference if word.text == "900101-1******")
    identity.text = "900101-1234567"
    if split:
        prefix, suffix = deepcopy(identity), deepcopy(identity)
        middle = (identity.bbox_px[0] + identity.bbox_px[2]) / 2
        prefix.text, suffix.text = "900101-", "1234567"
        prefix.bbox_px = (*identity.bbox_px[:2], middle, identity.bbox_px[3])
        suffix.bbox_px = (middle + 1, identity.bbox_px[1], identity.bbox_px[2] + 1, identity.bbox_px[3])
        reference = [word for word in reference if word is not identity] + [prefix, suffix]
    already_masked = fields.normalize_words(reference)
    left = nhis_acquisition_loss.extract(fields.prepare_pairs(page, reference, "text_layer"))
    right = nhis_acquisition_loss.extract(fields.prepare_pairs(page, already_masked, "own"))
    left_raw = {key: field.value for key, field in left.fields.items()}
    right_raw = {key: field.value for key, field in right.fields.items()}
    scored = fields.compare_fields("NHIS_ACQUISITION_LOSS", left_raw, right_raw, "NHIS_ACQUISITION_LOSS")
    assert scored["성명"]["match"] == scored["생년월일"]["match"] == 1
    assert all(value["match"] == value["eligible"] for value in scored.values())


def test_field_values_apply_same_semantic_normalization_and_final_masking():
    reference = {"성명": "가 짜 이 름", "생년월일": "１９９０.１.１.",
                 "사업장명칭": "９００１０１－１２３４５６７", "건강보험료": "100,000",
                 "월별고지금액": '{"2025.10":"100,000"}'}
    observed = {"성명": "가짜이름", "생년월일": "1990-01-01",
                "사업장명칭": "900101-1******", "건강보험료": "100000",
                "월별고지금액": '{"2025-10":"100000"}'}
    saved_reference, saved_observed = deepcopy(reference), deepcopy(observed)
    scored = fields.compare_fields("NHIS_PAYMENT", reference, observed, "NHIS_PAYMENT")
    for key in reference:
        assert scored[key]["eligible"] == scored[key]["match"] == 1
        assert sum(scored[key][name] for name in ("ocr_cause", "structure_cause", "unattributable")) == 0
    assert scored["발급일"]["eligible"] == 0
    assert scored["발급일"]["missing_reference"] == 1
    assert (reference, observed) == (saved_reference, saved_observed)


def test_fields_missing_reference_missing_ocr_and_different_kind_are_not_hidden():
    missing = fields.compare_fields("NHIS_PAYMENT", {"성명": "가짜이름"}, {}, "X", "가짜이름", "가짜이름")
    assert missing["성명"] == dict(eligible=1, match=0, missing_reference=0, ocr_cause=0,
                                 structure_cause=1, unattributable=0)
    wrong_type = fields.compare_fields("NHIS_PAYMENT", {"성명": "가짜이름"}, {"성명": "가짜이름"}, "INSURANCE_4", "가짜이름", "가짜이름")
    assert wrong_type["성명"]["match"] == 0
    assert wrong_type["성명"]["eligible"] == 1
    assert sum(item["eligible"] for item in missing.values()) == 1


@pytest.mark.parametrize("observed_text,expected_cause", [("가짜이름", "structure_cause"), ("가짜이름오류", "structure_cause"), ("가짜이르", "ocr_cause")])
def test_mismatch_cause_uses_literal_value_presence(observed_text, expected_cause):
    scored = fields.compare_fields("NHIS_PAYMENT", {"성명": "가짜이름"}, {}, "NHIS_PAYMENT", "성명 가짜이름", observed_text)
    assert scored["성명"][expected_cause] == 1


def test_derived_nonliteral_fields_and_unknown_keys_are_safe():
    secret = "UNREVIEWED_SYNTHETIC_KEY_79193"
    scored = fields.compare_fields("NHIS_PAYMENT", {secret: secret, "건강보험료": "100000"}, {}, "NHIS_PAYMENT", "50,000 150,000", "50,000 150,000")
    assert scored["건강보험료"]["unattributable"] == 1
    assert secret not in json.dumps(scored)
    assert all(set(value) == set(fields.FIELD_COUNTS) for value in scored.values())


def test_structured_field_semantics_retain_row_order_ignore_evidence():
    left = {"가입내역": [{"보험": "건강보험", "성명": "가짜이름", "confidence": .9}, {"보험": "국민연금", "성명": "가짜이름"}]}
    right = {"가입내역": [{"보험": "건강보험", "성명": "가 짜 이 름", "confidence": .1}, {"보험": "국민연금", "성명": "가짜이름"}]}
    assert fields.compare_fields("INSURANCE_4", left, right, "INSURANCE_4")["가입내역"]["match"] == 1
    right["가입내역"].reverse()
    assert fields.compare_fields("INSURANCE_4", left, right, "INSURANCE_4")["가입내역"]["match"] == 0


def test_payment_legacy_region_is_bounded_by_reference_headers_and_month_rows():
    page, result = _legacy()
    region = fields.table_region("NHIS_PAYMENT", page, result)
    assert region == (100, 300, 850, 490)
    assert result.words[0].text == "건강보험료 납부확인서"


def test_payment_government_region_uses_existing_structural_validations():
    page, result = _government()
    region = fields.table_region("NHIS_PAYMENT", page, result)
    assert region is not None
    assert 150 < region[0] < 200
    assert 750 <= region[1] <= 820
    assert 1850 < region[2] < 1925
    assert 1720 <= region[3] <= 1790


@pytest.mark.parametrize("factory", [_legacy, _government])
def test_payment_region_localizes_numeric_errors_and_missing_month_line(factory):
    from engine_v2.tools.ocr_baseline_metrics import measure

    page, reference = factory()
    region = fields.table_region("NHIS_PAYMENT", page, reference)
    assert region is not None
    observed = deepcopy(reference.words)
    altered = False
    for word in observed:
        cx = (word.bbox_px[0] + word.bbox_px[2]) / 2
        cy = (word.bbox_px[1] + word.bbox_px[3]) / 2
        if region[0] <= cx <= region[2] and region[1] <= cy <= region[3] and word.text == "100,000":
            word.text = "100,001"
            altered = True
            break
    assert altered
    numeric = measure(reference.words, observed, page.pixel_size, table_bounds=region)["table"]
    assert numeric["inside"]["cer"]["edits"] == 1
    assert numeric["inside"]["digit_cer"]["edits"] == 1
    assert numeric["outside"]["cer"]["edits"] == 0
    month = next(word for word in reference.words if word.text in {"2025.10", "1월"})
    row_center = (month.bbox_px[1] + month.bbox_px[3]) / 2
    observed = [word for word in reference.words if abs((word.bbox_px[1] + word.bbox_px[3]) / 2 - row_center) > 20]
    missing = measure(reference.words, observed, page.pixel_size, table_bounds=region)["table"]
    assert missing["inside"]["missed"] == 1
    assert missing["inside"]["miss_rate"] > 0
    assert missing["outside"]["missed"] == 0


@pytest.mark.parametrize("factory", [_legacy, _government])
def test_payment_unconfirmed_headers_or_months_are_unmeasured(factory):
    page, result = factory()
    result.words = [word for word in result.words if word.text not in {"고지금액"}]
    assert fields.table_region("NHIS_PAYMENT", page, result) is None
    page, result = factory()
    result.words = [word for word in result.words if not any(character.isdigit() for character in word.text)]
    assert fields.table_region("NHIS_PAYMENT", page, result) is None


def test_resident_reuses_existing_band_other_kinds_are_unmeasured():
    words = [_word("주민등록표 초본", 100, 10, 300), _word("번호 세대주 신고일", 100, 500, 500),
             _word("1 가짜이름 2025.10.01", 100, 550, 600), _word("이하여백", 100, 700, 200)]
    page, result = _page(words)
    assert fields.table_region("RESIDENT_ABSTRACT", page, result) is not None
    assert fields.table_region("NHIS_QUALIFICATION", page, result) is None
    assert fields.table_region("NHIS_PAYMENT", *_page([_word("건강보험료 납부확인서", 100, 50, 400)])) is None
