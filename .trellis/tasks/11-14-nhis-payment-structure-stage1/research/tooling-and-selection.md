# Research: reusable dump tooling and batch selection

- Date: 2026-11-14
- Scope: tracked local source and existing specifications only. No real documents, private input trees or prior result files were accessed.

## Existing structure tools

| Source | Confirmed behavior | Consequence |
| --- | --- | --- |
| `engine_v2/tools/layout_dump.py:1`, `:41`, `:45`, `:62` | Existing OCR layout CLI masks text, regroups word boxes into lines and prints position/confidence. It skips text-layer pages and accepts one OCR engine. | Extend this tool with an explicit structured `--out` mode rather than add a parallel layout CLI. Preserve its existing public `mask` and `group_lines` helpers and legacy invocation. |
| `engine_v2/tools/inspect_pdf.py:128` | PDF-only `dump_words` retains page/box/block/line, rounds coordinates and derives the output name from the input stem. It writes to a fixed directory. | Reuse the word-record concept, but not its destination/naming/rounding or console behavior. Those violate this task's explicit-output and original-geometry requirements. |
| `engine_v2/tools/extract_diag.py:98`, `:103`, `:128` | Diagnostic traces normalize/group boxes and replace a whole word with `[masked]`; they also run extraction. | A reference for schema only. The new mode must keep character shape and provider word order, and does not need to run extraction. |
| `engine_v2/tools/privacy.py:57`, `:77` | Existing masking maps Latin letters to lowercase `a`, keeps region names and label substrings, replaces identifier spans and changes some symbols. | Do not change this shared contract or call `mask_text` for the new projection. Exact whole-word membership and uppercase `A` require a separate local masking projection. |

## Safe components to reuse

- `demo/backend/tools/verify_cases.py:40`: `_private_location` resolves symlinks. Outside the checkout is permitted by runtime policy; inside must be ignored and untracked. Git checks suppress output and must occur outside the processing guard. This policy is not permission for this session to inspect outside/private documents.
- `engine_v2/tools/batch_assess.py:98`: `guarded` combines dependency/Python/native/log suppression, read-only assessment and a network prohibition. A swallowed prohibited attempt still fails.
- `engine_v2/tools/batch_assess.py:124`, `:188`: `_target` and `_atomic` add target type/hardlink checks and checked atomic sibling replacement; parent directories must already exist for the dump's explicit output. Protect the source file separately with equality/samefile checks.
- `engine_v2/tools/batch_assess.py:405`: `_inspect` rasterizes PDFs at 300 DPI into memory, creates `PageImage` objects and transforms text-layer `get_text('words', sort=True)` boxes by 300/72. It intentionally returns text references only with full-document text coverage. A structural dump must additionally retain the available words on partial-text PDFs, without changing batch reference eligibility.
- `engine_v2/tools/batch_assess.py:454`: `_recognize` calls the original explicit local engine and uses a scoped in-memory PIL bridge for Apple Vision. Reuse this invocation; do not introduce fallback, remote OCR, model downloads or temporary image files.
- `demo/backend/tools/verify_upload.py:78`: suppression/audit boundary is process-global; process sequentially and restore contexts on exceptions/interruption.

## Batch inventory and resume

- `batch_assess.py:213` visits entries in sorted order without following symlinks. It excludes hidden files and unsupported formats without opening their contents.
- `batch_assess.py:251` validates relative ID shape. Selection needs stricter canonical checks as well (no empty components, absolute paths, traversal, NUL or backslash separator ambiguity).
- `batch_assess.py:335` has a closed run-metadata schema. Preserve it: `--ids` is an invocation selection, not a new run identity or a new result field.
- `batch_assess.py:709` validates output/root overlap and locks; preserves group mappings; skips completed IDs including error rows; repairs only incomplete JSONL tails; fsyncs completed rows. Completion remains keyed by relative ID, even if source contents change.
- `batch_assess.py:850` / `:859` own CLI parsing and dispatch. Add optional `--ids` only for execution; reject it with `--summarize`.

Original planning proposal (superseded by the 2026-11-14 implementation approval refinements in design.md, which require count-only exclusion/deduplication): UTF-8 lines, one exact root-relative POSIX ID per nonempty line. Remove line endings only; retain spaces and case in IDs. Reject duplicate/noncanonical/unsupported/hidden/symlink/missing IDs with a fixed error and no path echo. Resolve entries against `--root`, not the list's directory. Validate the list location with `_private_location` because it contains source identifiers. Select from the existing metadata-only inventory; preserve inventory ordering and group assignment, then restrict processing. Thus unselected files can be inventoried but are never opened or OCRed. Exclusion metadata retains its existing inventory meaning. A changed selection can append to the same compatible run; previous rows, group numbers, full-run summary and accumulated error behavior remain unchanged.

## Synthetic-only verification precautions

`demo/backend/tests/__init__.py:8` uses existing sample PDFs if present. Do not run that initializer against a pre-existing sample tree. Follow the existing batch validation approach: make a fresh ignored in-checkout tracked-source copy, generate synthetic samples there, and copy the newly added test/tool changes. Link only known repository-contained dependency assets, never document trees. Keep TMPDIR and pytest basetemp inside the fresh sandbox. Run the 18 scenario modules sequentially without live/remote flags. P14 uses tracked blank templates with fictitious values and has no numeric assertion count; record its exit separately and do not invent a contribution to 1,885.

Historical `.trellis/tasks/archive/2026-11/11-13-batch-assess/validation.md` confirms engine 1,448/3 skipped and scenarios 18/1,885/0. Its backend count is older (1,252), so this task uses the user's 1,296 backend baseline and reports actual later results. Historical numbers are not a fresh test run.

## Limits

No new dump, native OCR run or full regression was executed during this planning research. No implementation files were edited. The forthcoming dump reflects adapter-returned words, including existing resident-number sanitization, not pre-sanitization text.
