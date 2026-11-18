# Blind label review

Apply to `engine_v2.tools.label_review`, its static screen (`engine_v2/tools/label_review_static/`) and
`engine_v2/tests/test_label_review.py`. The tool records ground truth for B1-B3 and C1-C3 of
`.trellis/tasks/11-17-speed-baseline/measurement-definitions.md` with label criteria v0.1. It never
changes operating code; values are recomputed through the service path only for the screen.

## Signatures

```text
python -B -m engine_v2.tools.label_review serve --rows FAKE-rows.jsonl --root FAKE-input --out FAKE-labels [--sample 150] [--seed 20261117] [--port 8765] [--revalue-forms NHIS_PAYMENT,...] [--base-rows FAKE-round1-rows.jsonl]
python -B -m engine_v2.tools.label_review summary --out FAKE-labels [--round N]
python -B -m engine_v2.tools.label_review mismatch --out FAKE-labels [--round N]
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
- Later rounds (sets): B = every FAIL of the round. C = round-1 C keys that are PASS again (the round-1 sample is
  never drawn again; `c_alloc` then holds C form counts). N = every PASS key of the round that was not PASS in
  round-1 rows (new-PASS stratum, census; stage one + O/X). Every round stores `pass_keys` (all PASS keys of its
  rows) and `n`. A plan written before N lacks round-1 `pass_keys`: a new round then fails with
  `BASE_ROWS_REQUIRED`, and `--base-rows` (round-1 rows, matched by sha256, else PLAN_MISMATCH) fills them once.
- Later rounds (carry-over): stage-one labels are per key across rounds, so a new round asks stage one only for
  B ∪ C ∪ N members without one. Each new round stores `label_base` (label records existing when it opened; earlier
  records are "carried"), `carried` ({key: new decision or `ABSENT`} for every key sampled in an earlier round)
  and `revalue` (sorted form codes from `--revalue-forms`, or null). C/N values O/X carry over from the previous
  round only when `revalue` is a list, the key's form is not in it, and the key was a C or N member of the previous
  round with the same form (`values_record`); otherwise that round's own O/X is required. No option → null →
  every C document of the new round needs O/X again. Given again for the same rows the list replaces the stored
  one; omitted it keeps it. Plans and rounds without these fields stay valid. Value hashes are never stored:
  the labeler chooses the forms whose extraction changed.
- Screen: a carried stage-one label shows "N회차 정답 이어받음" (`label.inherited`), carried O/X shows
  "N회차 이어받음" (`values.inherited`); saving again records a label of the current round.
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
reason, per value item, revised counts and cross-check agreement (status, status+reasons). Round carry-over:
`REVALUE` (ALL, NONE or form codes), `INHERITED` per set (carried blind and values),
`C_DETAIL VALUES_INHERITED`, and `TRANSITION before_set before after after_set documents` with truth counts per
state for every carried key (sets B, C, N or OUT), plus `TRANSITION_CHANGED`. Values in C, N and in the mismatch
listing use `values_record`, so carried O/X count.

N (census, no sampling bound): `N_TOTAL` (documents, blind, values, pending), `N` per HOLD treatment
(wrong, labeled, rate) with wrong = truth not PASS or any item X, `N_DETAIL` (truth per state, VALUE_X,
FAIL_OR_VALUE_X = the C1 definition for comparison, VALUES_INHERITED), and N rows in `BY_FORM`, `R_CODE`, `VALUE_ITEM_N`, `INHERITED`,
`SAMPLE` and the mismatch listing (set `N`, same rule as C).

`PASS_COMBINED` (per HOLD treatment) uses the strict wrong-pass definition in both strata: truth not PASS
(FAIL or NEEDS_REVIEW) or any item X. An engine PASS is not looked at by staff, so a truth NEEDS_REVIEW is
missed as well. C1-C3 keep their definition (truth FAIL or any item X); `C_DETAIL PASS_NOT_TRUTH_OR_VALUE_X`
counts the C stratum (HOLD excluded) by the strict definition, i.e. k_old of EXCL_HOLD.

```text
N_old = |PASS keys of this round ∩ PASS keys of round 1|   (round 1: all PASS)   C sample: k_old wrong of n_old
N_new = |N|                                               N census:  k_new wrong of n_new
W_old = N_old / (N_old + N_new), W_new = N_new / (N_old + N_new)
estimate = W_old · k_old / n_old + W_new · k_new / n_new
upper    = W_old · CP_upper(k_old, n_old) + W_new · k_new / n_new     (one-sided 95%)
```

The new stratum is a census, so only the old stratum carries sampling error; EXCL_HOLD treats HOLD documents of
both strata as missing at random. Both are NA until every N document has stage one and O/X, or when a stratum with
N_h > 0 has no usable label. With N_new = 0 the line equals the C bound. The bound is
computed by bisection on the exact binomial tail; no new dependency.

## Mismatch listing

Read-only. One line per labeled disagreement of a round: B with truth not FAIL; C with truth not PASS or
any item X (C values not yet saved print `VALUES_PENDING`; truth PASS without values is not listed). Columns
are round, screen ordinal (seeded order over B ∪ C; equals the screen when no document is missing), set,
form code, engine decision, engine reason codes, truth state, R codes and X item names from the fixed
vocabulary. Never keys, paths, file names, values or dates.

## Tests

Synthetic only: sample reproducibility and tamper detection, blind ordering, closed storage without
sentinel values/paths in labels, plan, console or logs, traversal/symlink refusal, out location, fixed
host and request checks, no external resources, Clopper-Pearson (0, 1, many; scipy cross-check when
installed), both HOLD treatments, round merge, cross-check agreement, round-two carry-over (only new documents and revalued forms are asked; transition
table; output free of paths, names, values and dates), the N set (fixed C sample, N = new PASS only,
`--base-rows` fill, PASS_COMBINED), and the real service path on a
synthetic text PDF.
