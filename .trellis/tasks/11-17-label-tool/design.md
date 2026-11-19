# Design

## Commands

```
python -B -m engine_v2.tools.label_review serve --rows ROWS --root ROOT --out OUT [--sample 150] [--seed 20261117] [--port 8765]
python -B -m engine_v2.tools.label_review summary --out OUT [--round N]
```

## Rows and keys

- Rows are validated with `doc_timing.validate_row`; format 2+ only. A document's decision is the first
  measure repeat (`phase=measure`, `repeat=1`, `code=NONE`), as in measurement definition A.
- Keys are 16-hex hashes of root-relative paths. The key → file map is built by walking `--root` with
  `batch_assess.inventory` (no symlinks, no hidden files) and hashing relative paths. Only keys present in
  rows are mapped; unknown keys are 404, non-hex keys 400. Before every open: not a symlink, resolved path
  inside root, `O_NOFOLLOW` open, regular file.

## Samples (plan.json)

- B = all FAIL keys of the round.
- C = PASS keys, `doc_timing.allocate` per form, then inside each form the keys with the smallest
  permanent random rank `sha256("seed:key")`. Each round is a simple random sample per stratum; a later
  round with mostly the same PASS documents reuses most earlier picks (coordinated sampling) without
  selecting on label state.
- A round is identified by the sha256 of the rows file. Same rows → same round, sample re-derived and
  compared with the stored one (PLAN_MISMATCH otherwise). New rows → new round appended. Seed and C size
  are fixed per out folder.
- Queue order is a separate rank (`seed:order:key`) over B ∪ C so position never reveals B vs C.
- Cross-check: 20 keys with the smallest `seed:cross:key` rank among documents of the latest round that
  have a blind label, frozen in plan.json when started (only after the main queue is complete).
- plan.json also keeps per-round form, decision and engine reason codes for sampled keys (value-free) so
  the summary needs only `--out`.

## Labels (labels.jsonl, append-only, latest record per key+stage wins)

Closed record: `v, key, stage (blind|cross|values), status (PASS|NEEDS_REVIEW|FAIL|HOLD|null),
reasons ([R1..R6,R9], only for FAIL), fields ([[item, O|X]], values only), round (values only),
revealed (O|X: engine verdict for this key was shown before this blind record), at, criteria (v0.1)`.
Item names come from a fixed per-form vocabulary (batch_assess.FIELDS plus resident display keys and
서류종류). Values stage O/X is per round because the engine's reading can change between runs.

## Server

FastAPI + uvicorn on 127.0.0.1 only (constant, no option), access log off, fixed error codes, Host header
check, per-session token header on POST, strict CSP, no-store. One lock serializes OCR recompute (inside
`batch_assess.guarded()`), page rendering and label writes. Recomputed values live only in memory. The
screen shows the recomputed decision, form and reader tier code next to the measured row: the first chain
tier (FixtureOcr) answers when a file stem equals a demo fixture key, which the labeler should notice.
Cross-check keys stay usable after a later round drops them (row data from the round that sampled them).

## Summary

B (HOLD excluded / HOLD as wrong): k = truth FAIL among labeled FAIL docs; lower bound Clopper-Pearson
(k = n → 0.05^(1/n)). C: wrong pass = truth FAIL or any value X for that round; upper bound
(k = 0 → 1 − 0.05^(1/n)); C docs count only when blind + values for the round exist. Also NEEDS_REVIEW
count, per form, per R code, per engine FAIL reason, revealed-then-edited count, cross-check agreement
(status and status+reasons).
