"""The fixture OCR tier is off unless a synthetic test or seed explicitly turns it on.

Invariant: in a normally started application no uploaded file receives a fixture
result (which skips identity, issue-date and quality checks), whatever its name or
content -- including a byte-identical copy of a generated demo sample. Every input
here is fictitious.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from demo.backend import models
from demo.backend import ocr as chain
from demo.backend.ocr import read_document
from demo.backend.ocr.base import OcrResult
from demo.backend.ocr.fixture import (FixtureOcr, enable_synthetic_fixture_ocr_for_tests,
                                      fixture_ocr_enabled, synthetic_fixture_ocr)
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_portal_uploads import client, new_app  # noqa: F401
from demo.fixtures.make_samples import make as make_sample

ROOT = Path(__file__).resolve().parents[3]
KEY = "S2_주민등록초본_적합"
SLOT = "resident_abstract"
ENROLLMENT = ["재 학 증 명 서", "성    명 : 가상신청", "학적상태 : 재학",
              "위 사람은 본 대학교에 재학 중임을 증명합니다.", "발급일자 : 2026.03.03"]


def enrollment_pdf(path):
    import pymupdf

    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        writer = pymupdf.TextWriter(page.rect)
        for index, line in enumerate(ENROLLMENT):
            writer.append((60, 80 + 22 * index), line, font=pymupdf.Font("cjk"), fontsize=11)
        writer.write_text(page)
        document.save(path)
    return path


def test_test_package_enables_fixtures_explicitly():
    # demo/backend/tests/__init__.py is the explicit opt-in for synthetic scenarios.
    assert fixture_ocr_enabled() is True


def test_a_normally_imported_app_never_selects_a_fixture(tmp_path):
    """A fresh process that loads the application (not the test package) has fixtures off,
    so even a byte-identical generated sample is read by the real tiers."""
    sample = make_sample(KEY, tmp_path)
    probe = (
        "import json, sys\n"
        "import demo.backend.main\n"
        "from demo.backend.ocr import read_document\n"
        "from demo.backend.ocr.fixture import FixtureOcr, fixture_ocr_enabled\n"
        "from demo.backend.rules.doc_types import DocType\n"
        "path = sys.argv[1]\n"
        "result = read_document(path, DocType.RESIDENT_ABSTRACT)\n"
        "print(json.dumps({'enabled': fixture_ocr_enabled(),\n"
        "                  'tests_loaded': 'demo.backend.tests' in sys.modules,\n"
        "                  'direct': FixtureOcr().read(path, None) is None,\n"
        "                  'tier': result.tier}))\n"
    )
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env.update({"JBAI_ENABLED": "0", "JBAI_ALLOW_REAL_DOCS": "false", "ENGINE_V2_OCR": "off"})
    output = subprocess.run([sys.executable, "-B", "-c", probe, str(sample)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=120, check=True).stdout
    seen = json.loads(output.strip().splitlines()[-1])
    assert seen == {"enabled": False, "tests_loaded": False, "direct": True, "tier": seen["tier"]}
    assert seen["tier"] != "fixture"


@pytest.mark.parametrize("kind", ["generated_sample", "fixture_named_enrollment"])
def test_uploads_get_no_fixture_result_when_disabled(client, tmp_path, kind):
    path = (make_sample(KEY, tmp_path) if kind == "generated_sample"
            else enrollment_pdf(tmp_path / f"{KEY}.pdf"))
    aid = new_app(client)
    with synthetic_fixture_ocr(False):
        response = client.post(f"/api/applications/{aid}/documents",
                               files={"file": (path.name, path.read_bytes(), "application/pdf")},
                               data={"slot_key": SLOT, "declared_issue_date": "2026-03-05"})
    assert response.status_code == 200
    with models.get_session() as session:
        row = session.get(models.Document, response.json()["document_id"])
        assert (row.ocr_json or {}).get("tier") != "fixture"
        if kind == "fixture_named_enrollment":
            assert row.stage1_status != "PASS"
            assert row.doc_type != str(DocType.RESIDENT_ABSTRACT)


class _ClaimsFixtureTier:
    name = "spoof"

    def read(self, file_path, expected):
        return OcrResult(detected_doc_type=DocType.RESIDENT_ABSTRACT, confidence=.99,
                         image_quality=.99, fields={"성명": "가상신청"}, tier="fixture")


def test_chain_discards_any_fixture_tier_result_while_disabled(tmp_path, monkeypatch):
    path = enrollment_pdf(tmp_path / "FAKE-any.pdf")
    monkeypatch.setattr(chain, "CHAIN", [_ClaimsFixtureTier()])
    with synthetic_fixture_ocr(False):
        result = read_document(str(path), DocType.RESIDENT_ABSTRACT)
        assert FixtureOcr().read(str(make_sample(KEY, tmp_path)), None) is None
    assert (result.tier, result.detected_doc_type, result.confidence) == ("none", None, 0.0)
    assert "FIXTURE_DISABLED" in result.fallback_reason
    # The same adapter is honored only under the explicit synthetic opt-in.
    assert read_document(str(path), DocType.RESIDENT_ABSTRACT).tier == "fixture"


def test_switch_restores_the_previous_state():
    with synthetic_fixture_ocr(False):
        assert fixture_ocr_enabled() is False
        with synthetic_fixture_ocr():
            assert fixture_ocr_enabled() is True
        assert fixture_ocr_enabled() is False
    assert fixture_ocr_enabled() is True
    enable_synthetic_fixture_ocr_for_tests()
    assert fixture_ocr_enabled() is True


def test_only_tests_and_the_synthetic_seed_can_turn_fixtures_on():
    """No server, API, verification tool or environment variable switches the tier on."""
    switch = re.compile(r"synthetic_fixture_ocr\(|enable_synthetic_fixture_ocr_for_tests\(|_enabled\s*=\s*True")
    allowed = {Path("demo/backend/ocr/fixture.py"), Path("demo/backend/tools/seed_officer_demo.py")}
    callers = set()
    for path in [*ROOT.joinpath("demo").rglob("*.py"), *ROOT.joinpath("engine_v2").rglob("*.py"),
                 *ROOT.joinpath("engine").rglob("*.py")]:
        relative = path.relative_to(ROOT)
        if "tests" in relative.parts or "node_modules" in relative.parts:
            continue
        if switch.search(path.read_text(encoding="utf-8", errors="ignore")):
            callers.add(relative)
    assert callers <= allowed
    source = ROOT.joinpath("demo/backend/ocr/fixture.py").read_text(encoding="utf-8")
    assert "environ" not in source and "getenv" not in source


def test_synthetic_seed_scopes_the_switch_to_its_own_sample_uploads():
    seed = ROOT / "demo/backend/tools/seed_officer_demo.py"
    if not seed.is_file():
        pytest.skip("this repository has no officer demo seed")
    source = seed.read_text(encoding="utf-8")
    assert source.count("with synthetic_fixture_ocr():") == 1
    block = source.split("with synthetic_fixture_ocr():", 1)[1].split("\n    _complete_work", 1)[0]
    assert "samples[filename]" in block and "upload_document" in block
