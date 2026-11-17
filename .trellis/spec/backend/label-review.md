# Blind label review

Apply to `engine_v2.tools.label_review`, its static screen (`engine_v2/tools/label_review_static/`) and
`engine_v2/tests/test_label_review.py`. The tool records ground truth for B1-B3 and C1-C3 of
`.trellis/tasks/11-17-speed-baseline/measurement-definitions.md` with label criteria v0.1. It never
changes operating code; values are recomputed through the service path only for the screen.

## Signatures

```text
python -B -m engine_v2.tools.label_review serve --rows FAKE-rows.jsonl --root FAKE-input --out FAKE-labels [--sample 150] [--seed 20261117] [--port 8765]
python -B -m engine_v2.tools.label_review summary --out FAKE-labels [--round N]
```

## Contracts

- Bind address is the constant `HOST = '127.0.0.1'`; there is no host option. Middleware rejects any Host
  header other than `127.0.0.1:PORT`/`localhost:PORT`, any POST without the session token header, a foreign
  Origin or a non-JSON body, and every method other than GET/POST. Responses carry a strict CSP
  (`default-src 'none'`, self scripts/styles/images), `no-store` and `nosniff`. The screen loads only the
  three repository static files; no CDN, font or external script.
- Rows: doc_timing format 2+, validated by `doc_timing.validate_row`; a document's decision is its first
  measured repeat. Keys are only those in rows. The key → file map comes from `batch_assess.inventory` over
  `--root` (no symlinks, no hidden files); before each use the file is re-checked (not a symlink, resolved
  path equals root/relative, `O_NOFOLLOW`, regular file) and read into memory. Paths never leave the server.
- `--out` must resolve outside the repository (even ignored folders are refused) and must not overlap
  `--root`. One server per out folder (`serve.lock`).
- Samples (`plan.json`): B = every FAIL; C = PASS allocated by form with `doc_timing.allocate`, picking the
  smallest `sha256(seed:c:key)` per form (coordinated permanent random numbers). Same rows digest → same
  round, re-derived and compared (PLAN_MISMATCH); new rows → new round. Seed and size are fixed per out.
  Queue order uses a separate rank so position never reveals B vs C. Cross-check keys (20, `seed:cross`)
  are frozen in plan.json and only after the main queue is complete.
- Blind order: `GET /api/doc/{key}` returns ordinal, page count, form, issue-date bounds from
  `doc_timing.requirement(form)` and the own earlier label only. `GET /api/checks` returns, per form in the
  session, the "확인할 것" list (text, R codes, source file name) built by `checks(form)` from the same slot
  (`doc_timing.requirement`, double-savings default criteria) and the engine/file-evidence constants; it
  carries no key, decision or reason. Engine decision/reasons (`/engine`) and
  values (`/values`) return 409 BLIND_FIRST until a blind label exists. Cross-check documents show neither
  the earlier label nor the verdict.
- `labels.jsonl` is append-only, latest record per key+stage (values: per key+round) wins. Closed record:
  `v, key, stage, status, reasons, fields, round, revised, at, criteria`. New records use criteria `v0.2`; `v0.1`
  records and plans stay valid and unchanged (`CRITERIA_VERSIONS`), and the summary counts latest labels per
  stage and version (`LABEL_VERSION`). Item names are a fixed vocabulary
  (`batch_assess.FIELDS`, resident display keys, 서류종류, 발급일); O/X must cover exactly the items shown.
  No values, names, memos, paths or hashes of values. An incomplete final line is ignored by summary and
  truncated by serve; any other invalid line is LABELS_INVALID.
- Recomputed values: `demo.backend.ocr.read_document(path, None)` + `assess_upload` with the slot of the
  detected form, inside `batch_assess.guarded()`, JBAI/Upstage environment removed, kept in a small
  in-memory cache only. Screen shows recomputed decision/form/tier and whether they equal the measured row.
- Logs: uvicorn access log off, log level critical, no tracebacks (middleware turns exceptions into fixed
  codes). Console prints counts only.

## Summary

Numbers and fixed codes only. B: k = truth FAIL among labeled engine-FAIL documents; `EXCL_HOLD` and
`HOLD_AS_WRONG`; one-sided 95% Clopper-Pearson lower bound (`k = n` → `0.05^(1/n)`). C: wrong pass = truth
FAIL or any item X in that round's values; documents count only with blind and values; upper bound
(`k = 0` → `1 − 0.05^(1/n)`). Also truth NEEDS_REVIEW among PASS, per form, per R code, per engine FAIL
reason, per value item, revised counts and cross-check agreement (status, status+reasons). The bound is
computed by bisection on the exact binomial tail; no new dependency.

## Tests

Synthetic only: sample reproducibility and tamper detection, blind ordering, closed storage without
sentinel values/paths in labels, plan, console or logs, traversal/symlink refusal, out location, fixed
host and request checks, no external resources, Clopper-Pearson (0, 1, many; scipy cross-check when
installed), both HOLD treatments, round merge, cross-check agreement, and the real service path on a
synthetic text PDF.
