"""11-18: a printed '열람용' (viewing copy) mark sends the document to officer review (synthetic only)."""
from engine_v2.tests.test_resident_abstract import wd

from ..api.common import applicant_findings
from ..api.officer import _document_view
from ..models import Document
from ..ocr.pdftext import VIEWING_COPY_FIELD, read_page_text
from .test_resident_blank_pages import _read, _two_pages


def _with_bottom_mark(pages):
    return pages[:-1] + [pages[-1] + [wd(40.0, 96.0, "열람용", 1.0, 8)]]


def test_viewing_copy_with_an_otherwise_normal_abstract_is_reviewed(tmp_path):
    ocr, result = _read(tmp_path, _with_bottom_mark(_two_pages()))
    assert ocr.fields[VIEWING_COPY_FIELD] == "있음"
    assert result.status == "NEEDS_REVIEW" and result.codes == ["VIEW_ONLY_DOCUMENT"]
    # The reason is for the officer screen only.
    assert applicant_findings([f.as_dict() for f in result.findings]) == []


def test_normal_abstract_without_the_mark_is_unchanged(tmp_path):
    ocr, result = _read(tmp_path, _two_pages())
    assert VIEWING_COPY_FIELD not in ocr.fields
    assert result.status == "PASS" and "VIEW_ONLY_DOCUMENT" not in result.codes


def test_text_layer_mark_sets_the_flag_only_when_printed():
    text = '자격득실확인서\n성명 가상시험\n발급일 2026-03-10\n※ 이 문서는 열람용입니다.'
    assert read_page_text(text, None, 0).fields[VIEWING_COPY_FIELD] == "있음"
    assert VIEWING_COPY_FIELD not in read_page_text(text.replace('열람용', '안내용'), None, 0).fields


def test_applicant_view_keeps_other_findings():
    findings = [{"code": "VIEW_ONLY_DOCUMENT", "message": "담당자용", "severity": "NEEDS_REVIEW"},
                {"code": "ISSUE_DATE_MISSING", "message": "발급일", "severity": "NEEDS_REVIEW"}]
    assert applicant_findings(findings) == []
    document = Document(slot_key="resident_abstract", file_path="synthetic.pdf", findings_json=findings)
    officer_findings = _document_view(document, {})["findings"]
    assert [f["code"] for f in officer_findings] == ["VIEW_ONLY_DOCUMENT", "ISSUE_DATE_MISSING"]
