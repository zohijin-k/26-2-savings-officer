"""A 주민등록초본 slot never yields an automatic PASS without a positively read 초본.

Every input is fictitious. The checks cover the reader, the stored stage-1 verdict, the
applicant projection, submission readiness and the submitted review, for documents
that are not 초본 (or cannot be shown to be one) and for the demo fixture tier.
"""
import threading

import pymupdf
import pytest
from sqlmodel import select

from demo.backend import models
from demo.backend import ocr as chain
from demo.backend.ocr import read_document
from demo.backend.ocr.fixture import FIXTURES, FixtureOcr, is_generated_sample
from demo.backend.rules.doc_types import DocType
from demo.backend.tests import SAMPLES_DIR
from demo.backend.tests.security_support import claim_synthetic_application
from demo.backend.tests.test_eligibility_blockers import ready
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_p2_resident_uploads import image_pdf, use_own_words
from demo.backend.tests.test_portal_uploads import client, new_app  # noqa: F401
from demo.fixtures.make_samples import make as make_sample
from engine_v2.tests import p2_resident_samples as resident_sample
from engine_v2.tests.p2_form_samples import cell, page

SLOT = "resident_abstract"
ISSUE = "2026-03-03"
FIXTURE_ABSTRACT = "S2_주민등록초본_적합"

ENROLLMENT = ["재 학 증 명 서", "성    명 : 가상신청", "생년월일 : 1999.01.01",
              "소    속 : 가상대학교 공과대학", "학적상태 : 재학",
              "위 사람은 본 대학교에 재학 중임을 증명합니다.", "발급일자 : 2026.03.03", "가상대학교 총장"]
REGISTER = ["주민등록표 (등본)", "이 등본은 세대별 주민등록표의 원본내용과 틀림없음을 증명합니다.",
            "세대주 성명 : 가상신청", "세대주 및 관계 : 본인", "발급일 : 2026년 3월 3일"]
NHIS_PAYMENT = ["건강보험료 납부확인서", "성명 : 가상신청", "생년월일 : 1999-01-01",
                "고지금액 : 30,000", "발급일자 : 2026.03.03"]
UNRELATED = ["가상 동아리 회의록", "일시 : 2026.03.03", "안건 : 봄 행사 준비"]
# A resident-like heading without the 초본/등본 distinction is not evidence of a 초본.
UNCERTAIN = ["주민등록표", "성명 : 가상신청", "발급일 : 2026년 3월 3일"]


def text_pdf(path, *pages):
    with pymupdf.open() as document:
        font = pymupdf.Font("cjk")
        for lines in pages:
            sheet = document.new_page(width=595, height=842)
            writer = pymupdf.TextWriter(sheet.rect)
            for index, line in enumerate(lines):
                if line:
                    writer.append((60, 80 + 22 * index), line, font=font, fontsize=11)
            writer.write_text(sheet)
        document.save(path)
    return path


def blank_pdf(path):
    with pymupdf.open() as document:
        document.new_page(width=595, height=842)
        document.save(path)
    return path


def post(client, aid, path, filename=None):
    response = client.post(f"/api/applications/{aid}/documents",
                           files={"file": (filename or path.name, path.read_bytes(), "application/pdf")},
                           data={"slot_key": SLOT, "declared_issue_date": ISSUE})
    assert response.status_code == 200
    return response.json()


def stored(document_id):
    with models.get_session() as session:
        row = session.get(models.Document, document_id)
        return row.stage1_status, row.doc_type, [(f.get("code"), f.get("severity")) for f in row.findings_json or []]


def submitted(client, aid):
    readiness = client.get(f"/api/applications/{aid}/final-check").json()
    response = client.post(f"/api/applications/{aid}/submit")
    with models.get_session() as session:
        review = session.exec(select(models.Review).where(models.Review.application_id == aid)).one_or_none()
    return readiness, response.status_code, review


def enrollment_pdf(tmp_path, name="FAKE-enrollment.pdf"):
    return text_pdf(tmp_path / name, ENROLLMENT)


# (input, expected stored stage-1 status, expected codes, applicant status)
TEXT_CASES = {
    "enrollment": (lambda p: text_pdf(p / "FAKE-a.pdf", ENROLLMENT), "NEEDS_REVIEW",
                   [("UNKNOWN_DOCUMENT_TYPE", "NEEDS_REVIEW")], "UPLOADED"),
    "register": (lambda p: text_pdf(p / "FAKE-b.pdf", REGISTER), "FAIL",
                 [("WRONG_DOCUMENT_TYPE", "FAIL")], "REUPLOAD_REQUIRED"),
    "nhis_payment": (lambda p: text_pdf(p / "FAKE-c.pdf", NHIS_PAYMENT), "FAIL",
                     [("WRONG_DOCUMENT_TYPE", "FAIL")], "REUPLOAD_REQUIRED"),
    "unrelated": (lambda p: text_pdf(p / "FAKE-d.pdf", UNRELATED), "NEEDS_REVIEW",
                  [("UNKNOWN_DOCUMENT_TYPE", "NEEDS_REVIEW")], "UPLOADED"),
    "blank": (lambda p: blank_pdf(p / "FAKE-e.pdf"), "NEEDS_REVIEW",
              [("UNKNOWN_DOCUMENT_TYPE", "NEEDS_REVIEW")], "UPLOADED"),
    "uncertain_title": (lambda p: text_pdf(p / "FAKE-f.pdf", UNCERTAIN), "NEEDS_REVIEW",
                        [("UNKNOWN_DOCUMENT_TYPE", "NEEDS_REVIEW")], "UPLOADED"),
    "enrollment_then_register": (lambda p: text_pdf(p / "FAKE-g.pdf", ENROLLMENT, REGISTER), "FAIL",
                                 [("WRONG_DOCUMENT_TYPE", "FAIL")], "REUPLOAD_REQUIRED"),
}


@pytest.mark.parametrize("kind", TEXT_CASES)
def test_non_abstract_inputs_never_pass_through_upload_or_submission(client, tmp_path, kind):
    build, status, codes, applicant = TEXT_CASES[kind]
    path = build(tmp_path)
    direct = read_document(str(path), DocType.RESIDENT_ABSTRACT)
    assert direct.detected_doc_type is not DocType.RESIDENT_ABSTRACT
    app = ready(make_application(premium=1))
    claim_synthetic_application(client, app.id)
    body = post(client, app.id, path)
    stage1, detected, found = stored(body["document_id"])
    assert stage1 == status
    assert all(code in found for code in codes)
    assert ("UNKNOWN_DOCUMENT_TYPE", "NEEDS_REVIEW") in found or ("WRONG_DOCUMENT_TYPE", "FAIL") in found
    assert detected != str(DocType.RESIDENT_ABSTRACT)
    assert body["status"] == applicant
    readiness, code, review = submitted(client, app.id)
    if applicant == "REUPLOAD_REQUIRED":
        assert readiness["can_submit"] is False
        assert code != 200 and review is None
    else:
        # Unknown type stays submittable for officer review (applicant-submission contract).
        assert readiness["can_submit"] is True and code == 200
        assert review.stage1_status != "PASS" and review.final_status != "PASS"
        assert review.review_payload_json.get("recommended_action") != "자동 승인"


@pytest.mark.parametrize("ocr_engine", ["off", "applevision"])
def test_image_only_enrollment_or_unreadable_scan_is_not_a_pass(client, tmp_path, monkeypatch, ocr_engine):
    if ocr_engine == "applevision":
        pytest.importorskip("ocrmac")
    source = text_pdf(tmp_path / "src.pdf", ENROLLMENT)
    with pymupdf.open(source) as document:
        png = document[0].get_pixmap(dpi=200).tobytes("png")
    scan = tmp_path / "FAKE-scan.pdf"
    with pymupdf.open() as document:
        document.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=png)
        document.save(scan)
    aid = new_app(client)
    monkeypatch.setenv("ENGINE_V2_OCR", ocr_engine)
    body = post(client, aid, scan)
    status, detected, _ = stored(body["document_id"])
    assert detected != str(DocType.RESIDENT_ABSTRACT)
    assert status != "PASS"


def test_fixture_name_alone_does_not_select_a_canned_abstract(client, tmp_path):
    """The P0 reproduction: a 재학증명서 renamed to a fixture key was auto-approved."""
    path = enrollment_pdf(tmp_path, f"{FIXTURE_ABSTRACT}.pdf")
    assert FIXTURES[FIXTURE_ABSTRACT].detected_doc_type is DocType.RESIDENT_ABSTRACT
    assert FixtureOcr().read(str(path), DocType.RESIDENT_ABSTRACT) is None
    assert read_document(str(path), DocType.RESIDENT_ABSTRACT).tier != "fixture"
    app = ready(make_application(premium=1))
    claim_synthetic_application(client, app.id)
    body = post(client, app.id, path)
    assert stored(body["document_id"])[:2] == ("NEEDS_REVIEW", None)
    _, code, review = submitted(client, app.id)
    assert code == 200
    assert review.stage1_status != "PASS" and review.final_status != "PASS"
    assert review.review_payload_json.get("recommended_action") != "자동 승인"


@pytest.mark.parametrize("variant", ["register_text", "extra_page", "image", "other_key_body"])
def test_fixture_requires_the_generated_sample_body(tmp_path, variant):
    target = tmp_path / f"{FIXTURE_ABSTRACT}.png" if variant == "image" else tmp_path / f"{FIXTURE_ABSTRACT}.pdf"
    if variant == "register_text":
        text_pdf(target, REGISTER)
    elif variant == "extra_page":
        (tmp_path / "gen").mkdir()
        generated = make_sample(FIXTURE_ABSTRACT, tmp_path / "gen")
        with pymupdf.open(generated) as document:
            document.new_page()
            document.save(target)
    elif variant == "image":
        target.write_bytes(b"\x89PNG\r\n\x1a\n")
    else:
        other = make_sample("S3_주민등록등본_오제출", tmp_path)  # a different key's generated body
        target.write_bytes(other.read_bytes())
    assert not is_generated_sample(target, FIXTURE_ABSTRACT)
    assert FixtureOcr().read(str(target), None) is None


@pytest.mark.parametrize("key", sorted(FIXTURES))
def test_every_generated_demo_sample_still_selects_its_fixture(tmp_path, key):
    path = make_sample(key, tmp_path)
    hit = FixtureOcr().read(str(path), None)
    assert hit is not None and hit.tier == "fixture"
    assert hit.detected_doc_type == FIXTURES[key].detected_doc_type
    shipped = SAMPLES_DIR / f"{key}.pdf"
    if shipped.is_file():
        assert FixtureOcr().read(str(shipped), None) is not None


def enrollment_page():
    size = resident_sample.resident()[0][0].pixel_size
    return page([cell(300, 200 + 90 * index, 1800, 260 + 90 * index, line)
                 for index, line in enumerate(ENROLLMENT)], size=size)


@pytest.mark.parametrize("order", ["enrollment_first", "enrollment_last", "enrollment_only"])
def test_mixed_enrollment_and_resident_pages(client, tmp_path, monkeypatch, order):
    def pages():
        resident = resident_sample.resident()
        return {"enrollment_first": [enrollment_page(), *resident],
                "enrollment_last": [*resident, enrollment_page()],
                "enrollment_only": [enrollment_page()]}[order]
    path = image_pdf(tmp_path / "FAKE-mixed.pdf", pages())
    use_own_words(monkeypatch, pages())
    aid = new_app(client, name=resident_sample.NAME, birth=resident_sample.BIRTH)
    body = post(client, aid, path)
    status, detected, codes = stored(body["document_id"])
    assert status == "NEEDS_REVIEW"
    if order == "enrollment_only":
        assert (detected, codes) == (None, [("UNKNOWN_DOCUMENT_TYPE", "NEEDS_REVIEW")])
    else:
        # The 초본 keyword on other pages selects the resident reader, whose page-structure
        # validation then refuses to treat the foreign page as part of a complete 초본.
        assert ("PAGES_UNREADABLE", "NEEDS_REVIEW") in codes
    assert body["status"] == "UPLOADED"


def test_replacing_a_passed_abstract_drops_the_previous_pass(client, tmp_path, monkeypatch):
    original_chain = list(chain.CHAIN)
    use_own_words(monkeypatch, resident_sample.resident())
    good = image_pdf(tmp_path / "FAKE-resident.pdf", resident_sample.resident())
    aid = new_app(client, name=resident_sample.NAME, birth=resident_sample.BIRTH)
    first = post(client, aid, good)
    assert stored(first["document_id"])[0] == "PASS"
    monkeypatch.setattr(chain, "CHAIN", original_chain)
    second = post(client, aid, enrollment_pdf(tmp_path))
    listed = client.get(f"/api/applications/{aid}/documents").json()
    slot_docs = [doc for doc in listed if doc["slot_key"] == SLOT]
    assert [doc["document_id"] for doc in slot_docs] == [second["document_id"]]
    with models.get_session() as session:
        rows = session.exec(select(models.Document).where(models.Document.application_id == aid,
                                                           models.Document.slot_key == SLOT)).all()
    assert [(row.id, row.stage1_status) for row in rows] == [(second["document_id"], "NEEDS_REVIEW")]
    checklist = client.get(f"/api/applications/{aid}/required-documents").json()
    item = next(row for row in checklist["items"] if row["slot_key"] == SLOT)
    assert [doc["document_id"] for doc in item["documents"]] == [second["document_id"]]


def test_concurrent_uploads_leave_one_self_consistent_slot_verdict(client, tmp_path):
    """Two in-flight uploads to the slot: whichever is stored last keeps its own verdict."""
    aid = new_app(client)
    files = {"register": text_pdf(tmp_path / "FAKE-r.pdf", REGISTER),
             "enrollment": enrollment_pdf(tmp_path)}
    responses = {}

    def send(kind):
        responses[kind] = post(client, aid, files[kind])

    threads = [threading.Thread(target=send, args=(kind,)) for kind in files]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with models.get_session() as session:
        rows = session.exec(select(models.Document).where(models.Document.application_id == aid,
                                                           models.Document.slot_key == SLOT)).all()
    assert len(rows) == 1
    # Replacement may reuse the deleted row id, so identify the stored upload by its file.
    survivor = next(kind for kind, path in files.items() if rows[0].file_path.endswith(path.name))
    expected = {"register": ("FAIL", "REUPLOAD_REQUIRED"), "enrollment": ("NEEDS_REVIEW", "UPLOADED")}[survivor]
    assert (rows[0].stage1_status, responses[survivor]["status"]) == expected


@pytest.mark.parametrize("stored_status", ["PASS", "NEEDS_REVIEW"])
def test_review_never_lets_the_slot_type_stand_in_for_an_unread_type(stored_status):
    """Engine conversion keeps an unread type in the slot but cannot make it a confident 초본."""
    from demo.backend.engine_adapter import to_engine_documents

    row = {"doc_type": None, "expected_doc_type": str(DocType.RESIDENT_ABSTRACT), "slot_key": SLOT,
           "confidence": .95, "image_quality": .95, "status": stored_status, "fields": {"성명": "가상신청"}}
    [document] = to_engine_documents([row])
    assert document.doc_type == str(DocType.RESIDENT_ABSTRACT)
    assert document.ocr_confidence <= .4
    read = to_engine_documents([{**row, "doc_type": str(DocType.RESIDENT_ABSTRACT), "status": "PASS"}])[0]
    assert read.ocr_confidence == .95
