"""11-26 Phase 1: an OCR-read 주민등록초본 is never an automatic PASS (SCAN_ABSTRACT_REVIEW_GUARD).

Synthetic only. Completeness (every history row up to the last one) cannot yet be established independently for
scans: rows missing from the image above a surviving 이하 여백 look complete. The guard sends such abstracts to
officer review with exactly one extra reason, SCAN_UNVERIFIED; text-layer abstracts and definite FAILs are unchanged
(see test_verify_upload case 4 for a scanned abstract that stays FAIL).
"""
from demo.backend import models
from demo.backend.tests.test_portal_uploads import assert_upload_status, client, new_app, upload
from demo.backend.tests.test_p2_resident_uploads import image_pdf, use_own_words
from demo.backend.tests.test_resident_slot_type_gate import TEXT_ABSTRACT, text_pdf
from engine_v2.tests import p2_resident_samples as sample
from .scan_guard import scan_guard_off  # noqa: F401 (fixture)


def _codes(response):
    with models.get_session() as session:
        return [finding["code"] for finding in session.get(models.Document, response["document_id"]).findings_json]


def _upload_scan(client, tmp_path, monkeypatch):
    use_own_words(monkeypatch, sample.resident())
    path = image_pdf(tmp_path / "FAKE-resident-scan.pdf", sample.resident())
    return upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "resident_abstract")


def _status(response, expected):
    assert_upload_status(response, expected)


def test_complete_scanned_abstract_is_reviewed_only_because_of_the_guard(client, tmp_path, monkeypatch):
    response, stored = _upload_scan(client, tmp_path, monkeypatch)
    _status(response, "NEEDS_REVIEW")
    assert _codes(response) == ["ADDRESS_HISTORY_INCOMPLETE"]
    assert stored["fields"]["주소이력불확실사유"] == "SCAN_UNVERIFIED"
    assert stored["fields"]["주소이력상태"] == "불확실"
    assert stored["fields"]["전입일"] == "불확실" and stored["fields"]["현주소시도"] == "불확실"
    assert stored["fields"]["주소이력끝근거"] == "이하 여백 (3쪽)"   # 끝 근거는 그대로 기록된다
    assert stored["fields"]["성명"] == sample.NAME and stored["fields"]["생년월일"] == sample.BIRTH


def test_the_same_scan_passes_when_the_guard_is_lifted(client, tmp_path, monkeypatch, scan_guard_off):
    # Phase 2에서 근거가 충분한 서식에 한해 재허용할 때의 기준선: 다른 검증은 모두 통과한다.
    response, stored = _upload_scan(client, tmp_path, monkeypatch)
    _status(response, "PASS")
    assert "주소이력상태" not in stored["fields"]
    assert stored["fields"]["전입일"] == "2023-08-30"


def test_text_layer_abstract_is_not_restricted(client, tmp_path):
    path = text_pdf(tmp_path / "FAKE-resident-text.pdf", TEXT_ABSTRACT)
    response, stored = upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "resident_abstract")
    _status(response, "PASS")
    assert "SCAN_UNVERIFIED" not in (stored["fields"].get("주소이력불확실사유") or "")
