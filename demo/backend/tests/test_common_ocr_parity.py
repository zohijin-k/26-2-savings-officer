"""11-27: the common OCR technology matches the shared manifest (savings-officer == youth, model-free).

engine_v2/common_ocr_manifest.json is byte-identical in both repositories. A change to common OCR code
(engine_v2/pipeline, the resident-abstract extractor and its completeness signals, the backend OCR
tiers, the resident page-integrity check) must be made in both repositories and the manifest
regenerated in both (python -m engine_v2.tools.common_ocr_parity --write). Business Document AI
blocks are listed as excluded and never hashed.
"""
import json

from engine_v2.tools import common_ocr_parity as parity


def _manifest():
    return json.loads(parity.MANIFEST.read_text(encoding="utf-8"))


def test_common_ocr_matches_the_shared_manifest():
    assert parity.differences(_manifest(), parity.compute()) == []


def test_manifest_is_canonical_and_pins_the_pp_ocrv5_models():
    manifest = _manifest()
    assert parity.MANIFEST.read_text(encoding="utf-8") == parity.dump(manifest)
    assert manifest["models"] == {
        "det.onnx": "4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae",
        "korean_dict.txt": "a88071c68c01707489baa79ebe0405b7beb5cca229f4fc94cc3ef992328802d7",
        "rec.onnx": "cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b",
    }
    for rel in ("engine_v2/pipeline/ocr/own.py", "engine_v2/pipeline/ocr/__init__.py", "engine_v2/pipeline/preprocess.py",
                "engine_v2/extractors/resident_abstract.py", "engine_v2/tools/fetch_own_models.py"):
        assert rel in manifest["files"]
    resident = manifest["mixed"]["demo/backend/ocr/localocr.py"]["blocks"]
    for name in ("_from_resident", "_number_column_ordinals", "_shared_image_groups", "preload_own",
                 "render_pages", "LocalOcr", "SCAN_ABSTRACT_REVIEW_GUARD"):
        assert resident[name]


def test_business_document_ai_blocks_are_excluded_not_hashed():
    manifest = _manifest()
    localocr = manifest["mixed"]["demo/backend/ocr/localocr.py"]
    assert "_business_resident_marks" in localocr["excluded"] and "_business_resident_marks" not in localocr["blocks"]
    doc_check = manifest["mixed"]["demo/backend/rules/doc_check.py"]["blocks"]
    assert set(doc_check) == {"CODE_PAGE_IMAGE_SHARED", "RESIDENT_HISTORY_REASON_LEGEND",
                              "_repeats_from_shared_image", "_check_resident_pages"}


def test_a_changed_common_block_is_reported():
    expected = _manifest()
    altered = json.loads(json.dumps(expected))
    altered["files"]["engine_v2/pipeline/ocr/own.py"] = "0" * 64
    altered["mixed"]["demo/backend/ocr/localocr.py"]["blocks"]["_from_resident"] = "0" * 64
    assert parity.differences(altered, parity.compute()) == [
        "files: engine_v2/pipeline/ocr/own.py", "mixed: demo/backend/ocr/localocr.py::_from_resident"]
