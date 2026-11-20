"""D10 (11-19): pages that read one shared embedded image are reviewed, not rejected (synthetic only).

A PDF may draw two different pages over one embedded main image (same xref). The reader takes the
embedded image as the page, so both pages give the same OCR input and the page marker repeats while
the rendered pages differ. That repeat is PAGE_IMAGE_SHARED (NEEDS_REVIEW). A repeat across different
images, or the same page shown twice (same image, same render), stays PAGES_DUPLICATED (FAIL).
"""
import json
import os
from unittest.mock import patch

import pymupdf
import pytest

from demo.backend.ocr.localocr import ENGINE_ENV, LocalOcr
from demo.backend.rules.doc_check import _repeats_from_shared_image, check_document

from .run_p8_localocr_scenarios import abstract_slot
from .run_p18_applicant_precheck_scenarios import IDENTITY, resident_words


def _pixmap(level):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2066, 2923), False)
    pix.clear_with(level)
    return pix


def _pdf(path, images, overlays=()):
    """One page per image level; pages with the same level share one image xref (PyMuPDF stores it once).

    ``overlays``: page indices that get a drawn rectangle over the image, so their render differs.
    """
    with pymupdf.open() as document:
        pixmaps = {}
        for index, level in enumerate(images):
            page = document.new_page(width=595, height=842)
            page.insert_image(page.rect, pixmap=pixmaps.setdefault(level, _pixmap(level)))
            if index in overlays:
                page.draw_rect(pymupdf.Rect(100, 100 + 40 * index, 300, 130 + 40 * index), color=(0, 0, 0),
                               fill=(0, 0, 0))
        document.save(path)
    with pymupdf.open(path) as document:
        return [page.get_image_info(xrefs=True)[0]["xref"] for page in document]


def _read(tmp_path, images, words, overlays=()):
    from engine_v2.pipeline import ocr as v2ocr

    path = tmp_path / "synthetic-abstract.pdf"
    xrefs = _pdf(path, images, overlays)
    pending = iter(words)
    with patch.dict(os.environ, {ENGINE_ENV: "d10-synthetic"}), \
            patch.dict(v2ocr.ENGINES, {"d10-synthetic": lambda png, size: next(pending)}):
        ocr = LocalOcr().read(str(path), None)
    assert ocr is not None
    return xrefs, ocr, check_document(abstract_slot(), ocr, identity=IDENTITY)


def test_pages_sharing_one_image_with_different_renders_are_reviewed(tmp_path):
    # The observed shape: pages 1 and 2 draw different content over one image and read the same
    # marker; page 3 has its own image.
    xrefs, ocr, result = _read(tmp_path, [245, 245, 240],
                               [resident_words("1/2"), resident_words("1/2"), resident_words("2/2", index=1)],
                               overlays=(1,))
    assert xrefs[0] == xrefs[1] != xrefs[2]
    data = json.loads(ocr.fields["쪽표기자료"])
    assert data["markers"] == [[1, 2], [1, 2], [2, 2]]
    assert data["image_groups"] == [[0, 0], [0, 1], None]  # numbers only, never the xref
    assert result.status == "NEEDS_REVIEW"
    assert "PAGE_IMAGE_SHARED" in result.codes and "PAGES_DUPLICATED" not in result.codes
    assert all(f.severity != "FAIL" for f in result.findings)


def test_repeated_marker_on_different_images_still_fails(tmp_path):
    xrefs, ocr, result = _read(tmp_path, [245, 240], [resident_words(), resident_words(index=1)])
    assert xrefs[0] != xrefs[1]
    assert "image_groups" not in json.loads(ocr.fields["쪽표기자료"])
    assert result.status == "FAIL" and "PAGES_DUPLICATED" in result.codes
    assert "PAGE_IMAGE_SHARED" not in result.codes


def test_same_page_shown_twice_still_fails(tmp_path):
    # Same image and same render: the PDF really shows one page twice.
    xrefs, ocr, result = _read(tmp_path, [245, 245], [resident_words(), resident_words()])
    assert xrefs[0] == xrefs[1]
    assert json.loads(ocr.fields["쪽표기자료"])["image_groups"] == [[0, 0], [0, 0]]
    assert result.status == "FAIL" and "PAGES_DUPLICATED" in result.codes


def test_repeat_partly_outside_the_shared_image_still_fails(tmp_path):
    # Marker 1/1 on pages 1, 2 (shared image, different renders) and on page 3 (own image).
    xrefs, _, result = _read(tmp_path, [245, 245, 240], [resident_words(), resident_words(), resident_words()],
                             overlays=(1,))
    assert xrefs[0] == xrefs[1] != xrefs[2]
    assert result.status == "FAIL" and "PAGES_DUPLICATED" in result.codes


@pytest.mark.parametrize("groups", [None, "x", [[0, 0]], [[0, 0], [0]], [[0, 0], [0, True]], [[0, 0], 1],
                                    [[0, 0], None], [[0, 0], [1, 1]]])
def test_missing_or_malformed_groups_keep_the_duplicate(groups):
    data = {} if groups is None else {"image_groups": groups}
    assert _repeats_from_shared_image(data, [[1, 1], [1, 1]], None) is False


def test_two_up_sheets_use_one_group_per_sheet():
    sheets = [[[1, 2], [2, 2]], [[1, 2], [2, 2]]]
    assert _repeats_from_shared_image({"image_groups": [[0, 0], [0, 1]]}, None, sheets) is True
    assert _repeats_from_shared_image({"image_groups": [[0, 0], [0, 0]]}, None, sheets) is False
