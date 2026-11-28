"""열지 못한 파일의 판독 실패 사유에 서버 저장 경로가 들어가지 않는다 (11-28).

PDF·그림 라이브러리의 예외 문장에는 연 파일의 전체 경로가 들어 있다(저장소 위치, 신청번호, 서버 계정 이름). 전에는 그
문장을 그대로 `판독실패` 값으로 저장해 담당자 응답과 DB에 남겼다. 지금은 예외 종류 이름만 남긴다.
"""
from __future__ import annotations

import pytest

from demo.backend.ocr import pdftext
from demo.backend.ocr import read_document
from demo.backend.rules.doc_types import DocType

FILES = {
    "FAKE-empty.pdf": b"",
    "FAKE-garbage.pdf": b"SYNTHETIC not a pdf " * 40,
    "FAKE-garbage.png": b"SYNTHETIC not an image " * 40,
    "FAKE-garbage.jpg": b"SYNTHETIC not an image " * 40,
}


@pytest.fixture
def stored(tmp_path):
    folder = tmp_path / "storage-SECRET-LOCATION" / "DS-2026-999999"
    folder.mkdir(parents=True)
    paths = {}
    for name, body in FILES.items():
        paths[name] = folder / name
        paths[name].write_bytes(body)
    return paths


def _leaks(value, path) -> bool:
    text = str(value)
    return any(part in text for part in (str(path), str(path.parent), "storage-SECRET-LOCATION", "DS-2026-999999", path.name))


@pytest.mark.parametrize("name", sorted(FILES))
def test_reader_reason_names_the_error_kind_but_not_the_path(stored, name):
    path = stored[name]
    result = pdftext.PdfTextOcr().read(str(path), DocType.RESIDENT_ABSTRACT)
    assert result is not None and result.is_encrypted            # 열지 못한 파일로 처리된다(판정은 전과 같다)
    reason = result.fields["판독실패"]
    assert reason.startswith("파일을 열 수 없습니다" if name.endswith(".pdf") else "이미지를 열 수 없습니다")
    assert not _leaks(reason, path)


@pytest.mark.parametrize("name", sorted(FILES))
def test_stored_read_result_never_contains_the_storage_path(stored, name):
    path = stored[name]
    result = read_document(str(path), DocType.RESIDENT_ABSTRACT)
    carried = [result.fields, result.fallback_reason, result.quality_note, result.classification_evidence]
    assert not any(_leaks(value, path) for value in carried)
