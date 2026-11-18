"""11-18: ADMIN_CONSENT_NOT_GIVEN (FAIL) only for a confident refusal mark on a good-quality image.

Synthetic only: the 서식5 template with a drawn X mark, saved as a vector PDF or a raster scan.
"""
from pathlib import Path

import pytest

from .. import upload_assessment
from ..ocr import admin_consent_scan as consent
from ..ocr.base import OcrResult
from ..rules.doc_types import DocType
from ..rules.required_docs import DocRequirement
from .test_admin_consent_inner_strong import _pdf

REQ = DocRequirement("admin_info_consent", DocType.ADMIN_INFO_CONSENT, "합성 동의서")


def _assess(path, quality):
    read = OcrResult(DocType.ADMIN_INFO_CONSENT, .95, image_quality=quality,
                     fields={"성명": "가상신청", "생년월일": "1999-01-01"})
    ocr, result = upload_assessment.assess_upload(Path(path), REQ, paper_admin_consent=True, reader=lambda *_: read)
    return ocr, result


def test_blurry_scan_read_as_refusal_is_reviewed(tmp_path):
    path = _pdf(tmp_path / "blurry-disagree.pdf", mark="agree.동의하지 않음", raster_dpi=100)
    ocr, result = _assess(path, .5)  # Q05: the labelled false refusal was a 0.5 quality scan
    assert "ADMIN_CONSENT_NOT_GIVEN" not in result.codes
    assert "ADMIN_CONSENT_MARK_UNCERTAIN" in result.codes and result.status == "NEEDS_REVIEW"
    assert ocr.fields["동의여부"] == "확인필요"


def test_clear_refusal_still_fails(tmp_path):
    path = _pdf(tmp_path / "clear-disagree.pdf", mark="agree.동의하지 않음")
    ocr, result = _assess(path, 1.0)
    assert ocr.fields["동의표시판독"] == "확실"
    assert result.status == "FAIL" and "ADMIN_CONSENT_NOT_GIVEN" in result.codes
    assert "ADMIN_CONSENT_MARK_UNCERTAIN" not in result.codes


def test_clear_agreement_is_unchanged(tmp_path):
    path = _pdf(tmp_path / "clear-agree.pdf", mark="agree.동의함")
    ocr, result = _assess(path, 1.0)
    assert ocr.fields["동의여부"] == "동의함"
    assert not {"ADMIN_CONSENT_NOT_GIVEN", "ADMIN_CONSENT_MARK_UNCERTAIN", "ADMIN_CONSENT_MARK_UNREADABLE"} & set(result.codes)


@pytest.mark.parametrize("observations", [
    {"동의여부": "동의하지 않음", "서명잉크확인": "있음", "동의표시판독": "불확실"},
    {"동의여부": "동의하지 않음", "서명잉크확인": "있음"},  # older observations without the confidence word
])
def test_uncertain_refusal_mark_on_a_good_image_is_reviewed(tmp_path, monkeypatch, observations):
    monkeypatch.setattr(consent, "inspect_admin_consent_scan", lambda _: dict(observations))
    _, result = _assess(tmp_path / "FAKE-consent.png", 1.0)
    assert result.status == "NEEDS_REVIEW" and "ADMIN_CONSENT_MARK_UNCERTAIN" in result.codes
    assert "ADMIN_CONSENT_NOT_GIVEN" not in result.codes


@pytest.mark.parametrize("ratios, aligned, expected", [
    ({"동의함": 0.0, "동의하지 않음": 0.55}, True, "확실"),
    ({"동의함": 0.0, "동의하지 않음": 0.55}, False, "불확실"),   # weak alignment
    ({"동의함": 0.03, "동의하지 않음": 0.55}, True, "불확실"),   # the other box is not clearly empty
    ({"동의함": 0.0, "동의하지 않음": 0.08}, True, "불확실"),    # faint mark
    ({"동의함": 0.5, "동의하지 않음": 0.55}, True, "불확실"),    # both boxes
])
def test_mark_confidence_needs_one_clear_mark_and_one_empty_box(ratios, aligned, expected):
    assert consent.mark_confidence(ratios, aligned) == expected
