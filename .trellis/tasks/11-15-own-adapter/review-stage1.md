# Stage 1 independent review

Reviewed the new diagnostic CLI/evidence helper, both new test files, usage documentation, backend diagnostic spec/index and task contracts. Existing operating modules, tools, tests and fixture providers were not changed. Original documents, uploads, databases and the seven protected data folders were not accessed.

## Finding fixed

The LINE_MERGED counterfactual originally allowed literal month pieces in a box over a different row to be moved into reference month cells. Other uniquely aligned wrong observations could prevent the earlier absence branch, and the transplanted copy could then pass original extraction. A successful replay did not establish that the observed box actually merged those reference cells.

The helper now requires one uniquely aligned observed box to overlap every supported component cell before attempting the split replay. Identical duplicate merged candidates remain ambiguous. Visible literal components in composite boxes also prevent unsupported VALUE_NOT_FOUND/OCR_CHAR attribution elsewhere. Added three independent guards for another column, another row and duplicate merged boxes; they verify OTHER, no unsupported replay and unchanged observed words.

An in-memory authored probe removed only the new geometric guard: the unchanged original extraction path yielded LINE_MERGED before the guard and OTHER after it. No production code was modified for this probe.

## Verified contracts

- Extraction/observation/replay delegates to the original baseline runtime path; scoped wrappers restore on exceptions. Originals and confidence remain unchanged.
- Exact/normalized match opportunities and causal diagnosed denominators remain separate. Reference absence, empty/unavailable/error OCR, per-field failures and limit/selection counts stay explicit.
- The fixed field registry covers every existing registered field. Output rows/metadata/summaries use closed code/numeric/null projections; tests exercise Python/native/error sentinels and blocked writes/DB/network effects.
- Labels follow actual reference reader semantics. Unlabeled membership/closing dates, unrelated/duplicate labels, derived month components, ambiguous boxes and composite tokens are covered. Ordinary baseline normalization wins OK; the extra copy-only whitespace rule removes U+200B without rewriting date grammar.
- Names only select inputs; existing outputs and input/output/ID aliases are rejected. Rotated cases expose the existing extractor's missing references rather than claiming orientation repair.

## Checks

Final combined focused verification in the isolated tracked-source copy: **98 passed / 0 failed**, with five installed PyMuPDF deprecation warnings in pytest's warning summary. This is 52 CLI tests plus 46 evidence tests. `git diff --check` passed. No configured Python lint/type-check entry point was found among tracked project configuration files.

Full engine/backend/scenario/frontend regression gates and actual synthetic diagnostics are intentionally left to the parent session's sequential execution after this handoff. The exact five user-specified precommit patterns were not available to this review and were not invented; the parent requested them from the user. No staging, commit, push or production repair was performed.

## User-authorized selector delta review

Reviewed only the subsequent local selector and skipped-document changes in the new CLI/test files. No additional code fix was needed. The shared batch tool and evidence helper remain unchanged by this delta.

- An immediate nonhidden, nonsymlink child-folder ID expands only to PDF paths already present in the existing safe inventory. Exact root-relative PDF IDs select one inventoried file. Nested folder selectors are rejected; folder expansion may include safely inventoried nested PDFs.
- Blank and comment lines are ignored; an initial UTF-8 BOM and CRLF are handled. Invalid encoding/syntax, outside-root and missing selectors are counted per skipped line. Invalid/missing selector lines do not open their purported contents or perform a per-line existence traversal.
- Folder/file/empty-folder line counts, fully redundant/repeated valid-line counts and overlapping PDF candidate counts have separate definitions. Final PDF selection is deduplicated and retains stable safe-inventory ordering.
- Hidden entries and symlink targets do not reach document processing. The new synthetic guards cover hidden subtrees, file/folder symlinks, unsupported files and valid empty folders.
- TYPE_NOT_REQUESTED is an availability state, not a causal code. Other confidently classified types skip OCR under the default payment selection. Unknown/input/quality exclusions remain their own states. `skipped_documents` counts attempted documents with no requested-kind page; `classified_unrequested_documents` is the narrower all-pages-confidently-unrequested subset. `unrequested_pages` is explicit, separate from excluded pages.
- Output projections still contain only fixed codes/numbers/null and ordinal document identities. Selector strings remain selection-only data.

The primary selector source/tests matched the isolated copies byte-for-byte. AST parsing and `git diff --check` passed. Final combined focused verification after this delta: **105 passed / 0 failed** in 3.23 seconds, with five installed PyMuPDF deprecation warnings in pytest's warning summary (59 CLI tests + 46 evidence tests). No actual OCR/full regression was run by this review, and no private path or literal precommit pattern was read or transcribed.

## Main-session dispatch follow-up review

Reviewed the added distributions/cross-tabulation from extraction rows through closed summary validation and text rendering. Counts deduplicate fields per engine/page, reject inconsistent route observations, include missing-reference extraction paths, distinguish completed OTHER routes from unavailable null paths, and retain zero cells. ROUTE_MISMATCH follows OK and precedes classification/label/evidence causes. The existing normalized-success short circuit preserves OK fields when another field's evidence diagnosis fails.

The focused suite passes 127 tests, with 22 added cases covering route priority, missing-reference/OK precedence, classification collisions, page deduplication, incomplete/OTHER paths and fixed numeric output schemas. Full engine_v2 passes 1875 / 3 skipped / 3 xfailed, reconciling both the 22-test extension and 127-test total against the accepted baselines. The accepted native 70-page diagnosis preserves all 420 preceding comparison flags and dispatch observations. Its only causal-code changes are 20 government own billing-month and 10 government own issue-date records becoming ROUTE_MISMATCH. Initial sandbox Apple empty OCR is retained as a superseded environment result. Original recognition/extraction implementations and private documents receive zero edits/accesses.

Existing task/spec/usage files now describe the thirteen-cause priority and page-based route denominator. AST/source identity and diff hygiene pass. The five-pattern check and final stage inventory are owned by the final staging verification. Commit approval remains pending.
