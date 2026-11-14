"""Synthetic-only selective inventory, private-list and durable-resume contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from engine_v2.tools import batch_assess as batch


SECRET = "SYNTHETIC-DOCUMENT-VALUE-483761"


@pytest.fixture
def corpus(tmp_path):
    root, out, ids = tmp_path / "FAKE-input", tmp_path / "FAKE-output", tmp_path / "FAKE-ids.txt"
    root.mkdir()
    return root, out, ids


def add(root, name):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SECRET, encoding="utf-8")
    return path


def results(out):
    target = out / "results.jsonl"
    return [json.loads(line) for line in target.read_text().splitlines()] if target.exists() else []


def fake_processor(monkeypatch, *, fail=()):
    observed = []

    def process(path, identifier, group, engines):
        assert path.read_text(encoding="utf-8") == SECRET
        observed.append(identifier)
        row = batch._blank(identifier, group)
        if identifier in fail:
            row.update(error_code="DECODE_ERROR", document_status="ERROR", exception="ValueError")
        return row

    monkeypatch.setattr(batch, "process_file", process)
    return observed


def invoke(root, out, ids=None, *extra):
    args = ["--root", str(root), "--out", str(out), *extra]
    if ids is not None:
        args += ["--ids", str(ids)]
    return batch.main(args)


def count_line(captured):
    assert captured.err == ""
    line = captured.out.splitlines()[0].split()
    assert line[0] == "ids"
    return {line[index]: int(line[index + 1]) for index in range(1, len(line), 2)}


def test_selects_exact_ids_in_inventory_order_without_opening_other_content(corpus, monkeypatch, capfd):
    root, out, ids = corpus
    for name in ("a/first.pdf", "b/second.PDF", "root.pdf", "b/한 글.pdf"):
        add(root, name)
    ids.write_text("b/한 글.pdf\nb/second.PDF\n", encoding="utf-8")
    original_open = Path.open
    forbidden = {root / "a/first.pdf", root / "root.pdf"}

    def checked_open(path, *args, **kwargs):
        assert path not in forbidden, "unselected source opened"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == ["b/second.PDF", "b/한 글.pdf"]
    assert [(row["id"], row["group"]) for row in results(out)] == [("b/second.PDF", 2), ("b/한 글.pdf", 2)]
    assert json.loads((out / "run.json").read_text())["groups"] == {"a": 1, "b": 2}
    captured = capfd.readouterr()
    assert count_line(captured) == dict(selected=2, not_listed=2, duplicates=0, outside_root=0, missing=0, invalid=0)
    assert all(value not in captured.out for value in (str(root), str(ids), str(out), "first.pdf", "second.PDF", "한 글.pdf", SECRET))
    for target in out.iterdir():
        if target.is_file():
            assert SECRET not in target.read_text()


def test_count_only_duplicates_outside_missing_and_invalid_entries(corpus, monkeypatch, capfd):
    root, out, ids = corpus
    add(root, "keep.pdf")
    add(root, "omit.pdf")
    ids.write_text("keep.pdf\nkeep.pdf\n../PRIVATE-OUTSIDE.pdf\n/PRIVATE-ABSOLUTE.pdf\n"
                   "missing.pdf\nmissing.pdf\n./keep.pdf\na//b.pdf\n.hidden.pdf\nwrong.txt\na\\b.pdf\n", encoding="utf-8")
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == ["keep.pdf"]
    captured = capfd.readouterr()
    assert count_line(captured) == dict(selected=1, not_listed=1, duplicates=2, outside_root=2, missing=1, invalid=5)
    assert "PRIVATE" not in captured.out and ".pdf" not in captured.out and SECRET not in captured.out


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_line_delimiters_preserve_spaces_case_and_unicode(corpus, monkeypatch, capfd, ending):
    root, out, ids = corpus
    names = [" leading space.pdf", "A.PDF", "한 글.pdf", "z\tpart.pdf", "z\u2028part.pdf"]
    for name in names:
        add(root, name)
    ids.write_bytes(("\r\n".join(reversed(names)) + ending).encode("utf-8"))
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == sorted(names)
    assert count_line(capfd.readouterr())["selected"] == len(names)


def test_empty_or_unusable_list_never_processes_documents(corpus, monkeypatch, capfd):
    root, out, ids = corpus
    add(root, "private.pdf")
    ids.write_text("\n\r\nmissing.pdf\n../outside.pdf\n", encoding="utf-8")
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == [] and results(out) == []
    assert count_line(capfd.readouterr()) == dict(selected=0, not_listed=1, duplicates=0, outside_root=1, missing=1, invalid=0)


@pytest.mark.parametrize("entry", ["a/../keep.pdf", "../../outside.pdf", "/outside.pdf"])
def test_traversal_absolute_entries_count_as_outside_without_opening(corpus, monkeypatch, capfd, entry):
    root, out, ids = corpus
    add(root, "keep.pdf")
    ids.write_text(entry + "\n", encoding="utf-8")
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == []
    counts = count_line(capfd.readouterr())
    assert counts["outside_root"] == 1 and counts["selected"] == 0


@pytest.mark.parametrize("entry", ["a//b.pdf", "./keep.pdf", "bad\x00.pdf", "a\\b.pdf", ".hidden.pdf", "wrong.txt", "a/.hidden/x.pdf"])
def test_noncanonical_hidden_or_unsupported_entries_are_counted(corpus, monkeypatch, capfd, entry):
    root, out, ids = corpus
    add(root, "keep.pdf")
    ids.write_text(entry + "\n", encoding="utf-8")
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == []
    counts = count_line(capfd.readouterr())
    assert counts["invalid"] == 1 and counts["selected"] == 0


def test_symlink_entries_are_not_followed_and_count_as_missing(corpus, monkeypatch, capfd):
    root, out, ids = corpus
    add(root, "keep.pdf")
    external = ids.parent / "FAKE-other.pdf"
    external.write_text(SECRET)
    (root / "linked.pdf").symlink_to(external)
    (root / "linked-dir").symlink_to(ids.parent, target_is_directory=True)
    ids.write_text("linked.pdf\nlinked-dir/FAKE-other.pdf\nkeep.pdf\n")
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == ["keep.pdf"]
    assert count_line(capfd.readouterr())["missing"] == 2


def test_list_paths_resolve_from_root_not_list_parent(corpus, monkeypatch):
    root, out, ids = corpus
    add(root, "folder/sample.pdf")
    ids.parent.joinpath("lists").mkdir()
    ids = ids.parent / "lists" / "ids.txt"
    ids.write_text("folder/sample.pdf\n")
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    assert observed == ["folder/sample.pdf"]


def test_completed_success_and_error_ids_skip_with_expanding_selection(corpus, monkeypatch, capfd):
    root, out, ids = corpus
    for name in ("a/skip.pdf", "b/error.pdf", "b/new.pdf"):
        add(root, name)
    ids.write_text("b/error.pdf\na/skip.pdf\n")
    observed = fake_processor(monkeypatch, fail={"b/error.pdf"})
    assert invoke(root, out, ids) == 1
    first = (out / "results.jsonl").read_bytes()
    assert observed == ["a/skip.pdf", "b/error.pdf"]
    observed.clear()
    ids.write_text("b/new.pdf\nb/error.pdf\na/skip.pdf\n")
    assert invoke(root, out, ids) == 1  # errors in completed rows remain run-wide
    assert observed == ["b/new.pdf"]
    expanded = (out / "results.jsonl").read_bytes()
    assert expanded.startswith(first)
    observed.clear()
    ids.write_text("a/skip.pdf\n")
    assert invoke(root, out, ids) == 1
    assert observed == [] and (out / "results.jsonl").read_bytes() == expanded
    assert [(row["id"], row["group"]) for row in results(out)] == [("a/skip.pdf", 1), ("b/error.pdf", 2), ("b/new.pdf", 2)]
    output = capfd.readouterr().out
    assert output.splitlines()[-1].split()[:3] == ["0", "1", "1"]


def test_subset_resume_repairs_only_incomplete_tail_and_keeps_schema(corpus, monkeypatch):
    root, out, ids = corpus
    for name in ("one.pdf", "two.pdf"):
        add(root, name)
    ids.write_text("one.pdf\n")
    fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    target = out / "results.jsonl"
    before = target.read_bytes()
    target.write_bytes(before + b'{"id":')
    assert invoke(root, out, ids) == 0
    assert target.read_bytes() == before
    assert set(json.loads((out / "run.json").read_text())) == {"schema_version", "policy", "root", "engines", "groups", "excluded"}
    assert set(results(out)[0]) == set(batch._blank("fake.pdf", 0))


def test_switching_between_filtered_and_unfiltered_run_preserves_compatibility(corpus, monkeypatch, capfd):
    root, out, ids = corpus
    for name in ("a/one.pdf", "b/two.pdf"):
        add(root, name)
    ids.write_text("b/two.pdf\n")
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 0
    first = (out / "results.jsonl").read_bytes()
    capfd.readouterr()
    observed.clear()
    assert invoke(root, out) == 0
    assert observed == ["a/one.pdf"]
    assert (out / "results.jsonl").read_bytes().startswith(first)
    assert "ids" not in capfd.readouterr().out
    assert invoke(root, out, ids, "--engines", "own", "applevision") == 2


@pytest.mark.parametrize("data", [b'\xff\xfe', b'\x80'])
def test_invalid_utf8_does_not_create_output_or_echo(corpus, monkeypatch, capfd, data):
    root, out, ids = corpus
    ids.write_bytes(data)
    fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 2
    assert not out.exists()
    assert capfd.readouterr() == ("", "")


def test_missing_list_does_not_create_output_or_echo(corpus, monkeypatch, capfd):
    root, out, ids = corpus
    fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 2
    assert not out.exists()
    assert capfd.readouterr() == ("", "")


@pytest.mark.parametrize("name", [".lock", "run.json", "results.jsonl", "run.json.fixed.tmp", "nested/ids.txt"])
def test_list_inside_output_is_never_overwritten_or_repaired(corpus, monkeypatch, capfd, name):
    root, out, ids = corpus
    add(root, "one.pdf")
    ids = out / name
    ids.parent.mkdir(parents=True)
    ids.write_text("one.pdf\n")
    before = ids.read_bytes()
    fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 2
    assert ids.read_bytes() == before
    assert capfd.readouterr() == ("", "")


@pytest.mark.parametrize("name", [".lock", "run.json", "results.jsonl"])
def test_external_list_hardlink_to_output_is_rejected_before_mutation(corpus, monkeypatch, capfd, name):
    root, out, ids = corpus
    out.mkdir()
    ids.write_text("one.pdf\n")
    os.link(ids, out / name)
    before = ids.read_bytes()
    fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 2
    assert ids.read_bytes() == before
    assert capfd.readouterr() == ("", "")


def test_symlinked_private_list_uses_resolved_location(corpus, monkeypatch):
    root, out, ids = corpus
    add(root, "one.pdf")
    ids.write_text("one.pdf\n")
    link = ids.parent / "list-link.txt"
    link.symlink_to(ids)
    observed = fake_processor(monkeypatch)
    assert invoke(root, out, link) == 0
    assert observed == ["one.pdf"]


@pytest.mark.parametrize("tracked", [False, True])
def test_list_requires_ignored_and_untracked_inside_fake_checkout(corpus, monkeypatch, capfd, tracked):
    from demo.backend.tools import verify_cases

    root, out, ids = corpus
    repo = ids.parent / "FAKE-git"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("ignored/\n")
    (repo / "ignored").mkdir()
    ids = repo / ("ignored/ids.txt" if tracked else "unignored.txt")
    ids.write_text("one.pdf\n")
    if tracked:
        subprocess.run(["git", "add", "-f", "--", "ignored/ids.txt"], cwd=repo, check=True)
    monkeypatch.setattr(verify_cases, "REPOSITORY_ROOT", repo)
    fake_processor(monkeypatch)
    assert invoke(root, out, ids) == 2
    assert not out.exists()
    assert capfd.readouterr() == ("", "")


def test_summary_cannot_accept_selection_or_touch_outputs(corpus, monkeypatch, capfd):
    _, out, ids = corpus
    ids.write_text("never-open.pdf\n")
    monkeypatch.setattr(batch, "summarize", lambda *args: pytest.fail("summary called"))
    assert batch.main(["--out", str(out), "--summarize", "--ids", str(ids)]) == 2
    assert not out.exists()
    assert capfd.readouterr() == ("", "")
