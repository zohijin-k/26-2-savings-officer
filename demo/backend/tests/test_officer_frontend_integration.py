"""Seeded API rows traverse the actual frontend grouping and list renderer."""
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from demo.backend.main import app
from demo.backend.tests.test_seed_officer_demo import isolated_demo
from demo.backend.tools import seed_officer_demo as tool


class ListText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.current = dict(attrs).get("aria-label")
            self.sections[self.current] = []

    def handle_endtag(self, tag):
        if tag == "section":
            self.current = None

    def handle_data(self, data):
        if self.current:
            self.sections[self.current].append(data)


def test_seeded_api_documents_render_in_the_two_actual_frontend_lists(isolated_demo, capsys):
    assert tool.main([]) == 0
    seeded = json.loads(capsys.readouterr().out)
    before = tool._snapshot()
    with TestClient(app) as client:
        response = client.get("/api/officer/applications", params={
            "role": "province", "program": "double_savings", "page_size": 200,
        })
        assert response.status_code == 200
        rows = response.json()["rows"]

    # TypeScript and React are the app's existing installed build dependencies.
    # Compile its actual modules in memory; do not duplicate classification here.
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    script = r"""
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const localRequire = createRequire(path.join(process.cwd(), 'package.json'));
const ts = localRequire('typescript');
function load(relative) {
  const source = fs.readFileSync(path.join(process.cwd(), relative), 'utf8');
  const js = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const module = {exports: {}};
  new Function('module', 'exports', 'require', js)(module, module.exports, localRequire);
  return module.exports;
}
const rows = JSON.parse(fs.readFileSync(0, 'utf8'));
const groups = load('src/pages/officer/document-groups.ts').groupOfficerDocuments(rows);
const List = load('src/pages/officer/ApplicationList.tsx').default;
const html = localRequire('react-dom/server').renderToStaticMarkup(
  localRequire('react').createElement(List, {groups, onOpen: () => {}}));
process.stdout.write(JSON.stringify({groups, html}));
"""
    completed = subprocess.run(["node", "-e", script], cwd=frontend,
                               input=json.dumps(rows), text=True, capture_output=True, check=True)
    rendered = json.loads(completed.stdout)
    groups = rendered["groups"]
    pass_id = seeded["applications"]["pass"]["application_id"]
    review_id = seeded["applications"]["needs-review"]["application_id"]
    assert len(groups["pass"]) == 9 and len(groups["needsReview"]) == 1
    assert sum(item["applicationId"] == pass_id for item in groups["pass"]) == 5
    assert all(item["applicationId"] == review_id for item in groups["needsReview"])
    assert all(item["status"] == "PASS" for item in groups["pass"])
    assert all(item["status"] != "PASS" for item in groups["needsReview"])

    view = ListText()
    view.feed(rendered["html"])
    assert set(view.sections) == {"적합 서류", "확인 필요 서류"}
    text = {key: "".join(parts) for key, parts in view.sections.items()}
    normal = next(row for row in rows if row["application_id"] == pass_id)
    review = next(row for row in rows if row["application_id"] == review_id)
    assert normal["application_no"] in text["적합 서류"]
    assert normal["application_no"] not in text["확인 필요 서류"]
    assert review["application_no"] in text["확인 필요 서류"]
    assert groups["needsReview"][0]["label"] in text["확인 필요 서류"]
    assert tool._snapshot() == before
