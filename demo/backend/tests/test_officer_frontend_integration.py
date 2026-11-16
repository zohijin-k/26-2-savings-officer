"""Seeded API rows traverse the actual frontend queue model and list table."""
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from demo.backend.main import app
from demo.backend.tests.test_seed_officer_demo import isolated_demo
from demo.backend.tools import seed_officer_demo as tool


class TableText(HTMLParser):
    """Collect visible text of the rendered list's table body."""

    def __init__(self):
        super().__init__()
        self.in_body = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag == "tbody":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            self.parts.append(data)


def test_seeded_api_rows_render_in_the_actual_frontend_queue_tabs(isolated_demo, capsys):
    assert tool.main([]) == 0
    seeded = json.loads(capsys.readouterr().out)
    before = tool._snapshot()
    with TestClient(app) as client:
        response = client.get("/api/officer/applications", params={
            "role": "province", "program": "double_savings", "page_size": 200,
        })
        assert response.status_code == 200
        body = response.json()
        rows = body["rows"]

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
  const resolve = (name) => name === './list-model.ts' ? load('src/pages/officer/list-model.ts') : localRequire(name);
  new Function('module', 'exports', 'require', js)(module, module.exports, resolve);
  return module.exports;
}
const {rows, role} = JSON.parse(fs.readFileSync(0, 'utf8'));
const model = load('src/pages/officer/list-model.ts');
const List = load('src/pages/officer/ApplicationList.tsx').default;
const {createElement} = localRequire('react');
const {renderToStaticMarkup} = localRequire('react-dom/server');
const html = {};
for (const queue of ['needs_review', 'pass', 'done', 'rejected']) {
  html[queue] = renderToStaticMarkup(createElement(List, {rows, role, initialQueue: queue, onOpen: () => {}}));
}
process.stdout.write(JSON.stringify({queues: rows.map(model.queueOf), counts: model.queueCounts(rows), html}));
"""
    completed = subprocess.run(["node", "-e", script], cwd=frontend,
                               input=json.dumps({"rows": rows, "role": body["role"]}),
                               text=True, capture_output=True, check=True)
    rendered = json.loads(completed.stdout)
    pass_id = seeded["applications"]["pass"]["application_id"]
    review_id = seeded["applications"]["needs-review"]["application_id"]
    queue_of = {row["application_id"]: queue for row, queue in zip(rows, rendered["queues"])}
    assert queue_of[pass_id] == "pass"
    assert queue_of[review_id] == "needs_review"
    assert rendered["counts"] == {"needs_review": 1, "pass": 1, "done": 0, "rejected": 0}

    text = {}
    for queue, html in rendered["html"].items():
        view = TableText()
        view.feed(html)
        text[queue] = "".join(view.parts)
    normal = next(row for row in rows if row["application_id"] == pass_id)
    review = next(row for row in rows if row["application_id"] == review_id)
    assert normal["application_no"] in text["pass"]
    assert normal["application_no"] not in text["needs_review"]
    assert review["application_no"] in text["needs_review"]
    assert review["application_no"] not in text["pass"]
    for queue in ("done", "rejected"):
        assert normal["application_no"] not in text[queue] and review["application_no"] not in text[queue]
    assert tool._snapshot() == before
