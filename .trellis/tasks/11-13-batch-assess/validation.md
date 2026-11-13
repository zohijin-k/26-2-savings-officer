# Batch assessment validation

## Isolation and unchanged-code evidence

The user approved implementation after planning, with six refinements reflected in PRD/design. All document inputs for this task are newly generated synthetic data. No existing ignored document/sample trees or outside-repository inputs were inspected. The regression harness uses a tracked-source copy inside a fresh ignored repository-local sandbox, so backend test initialization generates fresh samples instead of reading any existing local samples. Only repository-contained model/font dependency directories are linked; no document inputs are linked. Protected tracked test/OCR/extractor/assessment files were hashed before implementation.

`validation-location.json` points to the fresh synthetic-only sandbox for this session. It contains no actual source-document location. TMPDIR and pytest basetemp are contained there. Old scenarios run without `--live`; external OCR tests use their authored fake transports, never remote services. Scenario output is captured in memory and only module IDs, exit codes and numeric counts are retained.

## Final regression results

| Verification branch | Result | Evidence |
| --- | --- | --- |
| engine_v2 full suite | **1,448 passed / 3 skipped / 0 failed**, 7 existing warnings | Exit 0; 28.59 seconds; prior 1,375 + 73 new tests |
| demo/backend full suite | 1,252 passed, 0 failed; 9 existing warnings | Exit 0; 78.93 seconds, isolated tracked-source snapshot |
| Scenario modules | All 18 exits 0; counting modules 1,885 passed, 0 failed | Numeric-only scenarios-summary.json in sandbox; P14 has no numerical pass count |
| Frontend | `npm run lint` and `npm run build` both exit 0 | Primary checkout; existing large-chunk build advisory |

Frontend lint was first tried in the ignored mirror, where oxlint correctly found no files because the mirror's parent is ignored. It was then run in the primary frontend directory and passed. No source/configuration was changed for this check. The primary build also passed; a successful mirror build is redundant supporting evidence, not a separate branch count.

## Focused review and actual synthetic run

- Independent Trellis review completed; **73 new tests passed**, 0 failed. See `review.md` for fixed tail-corruption, unknown-verdict, history-field, known-page and zero-policy-table cases.
- Final own/Apple source was run on **8 newly generated synthetic files**, including one deliberately undecodable HEIC. Both actual local engines completed 7 readable files; the HEIC produced fixed DECODE_ERROR/UnidentifiedImageError and execution continued through all files. Batch exit 1 correctly reflects that intentional per-file error, not a regression failure or a document verdict.
- Generated-corpus outcome: PASS 2, NEEDS_REVIEW 3, NOT_ASSESSED 2, ERROR 1. Classification failure is 2/8 (successful own runs with no classified kind); opening/decode failure is a separate 1/8. All identity fields are `미검사`. Date-policy reasons are both 0/8 and still appear in their separate numerical table.
- Rerunning the exact same command skipped all 8 IDs, performed no new OCR and preserved results.jsonl bytes exactly. Summary exited 0 with empty stderr. Output and console scans found none of the generated name/date/workplace/OCR/decoder-message sentinels. Checked outputs contain only allowed value-free metadata and paths.
- Source SHA256 comparison confirms the final tool matches the actual native-engine run; code hashes here identify source, never document values. Earlier synthetic output was kept separate after the semantic registry expanded; the final output used a new directory rather than silently mixing schemas.
- The full actual summary is `synthetic-summary.txt` (238 lines). It includes all type/status/reason/field/agreement tables, mapping rules and page-time distributions. All ratios show numerator/denominator; unavailable comparisons remain explicit. These synthetic measurements do not establish accuracy on real documents.

Fictitious-path command shape for the observed execution:

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.batch_assess --root FAKE-input --out engine_v2/data/FAKE-output --engines own applevision
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.batch_assess --summarize --out engine_v2/data/FAKE-output
```

## Final integrity and review gate

- All **186 protected existing test/OCR/extractor/assessment source hashes are unchanged**. Existing tests, frontend and operating OCR/classification/extraction/assessment/verdict code have no diff. Only the new tool/tests/docs/task artifacts and backend spec index entry are changed.
- Both new Python files pass AST syntax parsing; `git diff --check` passes; Trellis implement/check contexts each validate with 8 entries. No configured Python lint/typecheck command was found; syntax checks are not claimed as type checking.
- All original test branches executed with unchanged assertions. New test counts explain the engine-only count increase; there are no new skips.
- HEIC support remains decoder-dependent. The deliberate invalid synthetic HEIC proves fixed-code continuation, not successful decoding of every HEIC variant. Real own and Apple execution, unlike the codec-failure fixture, was observed natively.
- Run-level usage/location/config/resume/output failures are intentionally exit-only 2; interruption is 130. There is no catch-wide errors file that could write after failed validation or lock acquisition. Per-file errors retain fixed code/class in JSONL.
- Proposed single work commit: `feat(tools): add value-free resumable batch assessment`, covering the new tool/tests/user docs/backend contract/index and this task's planning/research/review/numeric evidence. No unrecognized dirty files are included.
- Present the final `git diff --stat main`, all four branches and actual synthetic summary to the user, then wait for separate commit approval. **No commit, archive, push or merge has been performed.**
