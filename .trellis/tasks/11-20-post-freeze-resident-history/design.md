# Conservative continuation-table recovery

## Boundaries

Existing flow: `preprocess` -> `engine._load_pages` -> local OCR/text words -> `layout.normalize/group_lines` -> `resident_abstract.extract/_parse_rows` -> `localocr._from_resident` -> `doc_check`. The direct engine also consumes fields, warnings and validations through `evaluate_document`.

Preserve the legacy same-line table path and its bounds. Do not change shared line grouping, preprocessing, OCR dispatch/models, classifiers, rulepacks, attachment partitioning or page-count policy. Add synthetic tests in new engine/backend modules.

## Planned functions

| File / function | Change |
|---|---|
| `engine_v2/extractors/resident_abstract.py::_table_bounds` | Preserve default callable contract used by diagnostics; delegate to a bounded split-header candidate path where appropriate. |
| Same file: small private header/row-evidence helper(s) | Locate header categories and independent row candidates; distinguish extraction evidence from weaker omission-risk evidence. |
| Same file: `_parse_rows`, optional private date-cell helper | Join only uniquely justified same-cell date fragments; expose sufficient observations to verify candidate coverage, preserving notes/continuations. |
| Same file: `ResidentAbstractResult`, `extract` | Carry default-empty fixed-vocabulary table issues; verify per-page coverage; scope uncertainty to history-derived evidence. |
| `demo/backend/ocr/localocr.py::_from_resident` | Map new issues to existing history uncertainty fields and suppress unsafe residence-derived values. |
| `demo/backend/rules/doc_check.py::_check_document` | If needed, extend the existing reason description; reuse the review finding and FAIL precedence without generic verdict overrides. |

New private helper names are provisional. Existing result defaults and public signatures remain compatible.

## Structural recovery

1. Use the legacy same-line path first. Failure alone does not prove missing history.
2. For continuation recovery, bound a header band around an observed number label using normalized coordinates and median glyph height. Initial ceiling: total span <= 3.5 page-height percentage points and <= three median glyph heights; adjacent relevant lines <= 1.5 median heights apart. Pin inclusive boundaries with synthetic tests, never by tuning against real documents.
3. Require number, address and date/holder categories in supported horizontal order. Spaced address characters and vertically split date-label characters may combine only inside their own column/header band. No unrestricted whole-page concatenation.
4. Require aligned ordinal/address/report-date body evidence below the header and before existing end markers. Recovery needs at least two supported candidate rows, or one complete row corroborated by the preceding proven table and compatible continuation markers. Prior-page structure never supplies missing values; compare column structure rather than equal header y positions.
5. Derive the recovered body start from the proven header bottom; preserve footer/blank/military-table stops. Test first-row proximity so no row is skipped.
6. Parse the new recovery path into temporary page-local state. Merge only after all independently observed candidates are accounted for. On ambiguous or partial parsing, discard speculative changes and flag review; an unread new row must not be appended to the previous page's final address. Legacy proven-table continuation semantics remain covered by unchanged tests.

## Incompleteness evidence

Use weaker evidence for review only, never for invented rows:

- A correctly located number label plus nearby address/date/holder fragments and an aligned ordinal/address/date-like candidate, but failed complete table validation; or
- At least two aligned ordinal/address/report-date candidate groups on a compatible continuation of a proven table, even with insufficient header evidence; or
- A proven table contains row/ordinal/date candidates not accounted for after parsing, including a partially read page rather than only zero entries.

Require local geometry and bounded body area. Page count alone, one date, matching prose terms or a prior table alone are insufficient. Malformed date-like tokens may support unreadability but never become dates. Without any surviving OCR structure, omission cannot be reliably distinguished from an attachment.

Both recovery and omission-risk evidence stop at the existing military-section, blank-space or footer boundary through the shared private `_table_end` helper. Synthetic other-section rows with otherwise matching geometry must neither be recovered nor add a history-review signal.

Add default-empty issue metadata, proposed reasons `TABLE_NOT_FOUND` and `ROWS_UNREADABLE`. Preserve exact existing `history_numbers`, `history_empty_page` and legacy reason semantics. Apply existing kept/blank-page rules; suspicious content cannot become blank merely because detection failed.

Include new evidence in the local history-completeness decision, with a value-free warning and a validation excluded from the legacy broad `history*` confidence cap (`history_tables_readable`). For new table uncertainty, cap only history/count/current-address confidence; keep legacy number/date confidence policy distinguishable and unchanged. Engine warnings require review and low history-field confidence prevents confirmed eligibility rejection from partial history.

The adapter maps new reasons into existing `주소이력상태`/`주소이력불확실사유` and uncertain transfer date/count. Withhold any other residence-derived field that could establish eligibility. Do not reduce global OCR confidence solely for this new issue: independent issue-date/identity confidence and existing confirmed FAIL must survive. `doc_check` adds its existing review finding; final FAIL still wins.

## Date fragments

Try the current complete-token parse first. No date-value concatenation is introduced in this implementation. Fragmented, competing, invalid or cross-row dates require review. This keeps the change focused on header recovery and omission detection without guessing value components.

## Risks and limits

| Risk | Control |
|---|---|
| Nearby prose/other tables falsely merge | Require bounded categories, column order and independent row evidence; negative fixtures. |
| Header boundary swallows the first row | Pin boundary and header-to-row gap tests. |
| Failed row changes a previous address | Stage new-path state and reject ambiguous candidate mapping before merge. |
| Global confidence cap weakens independent FAIL | Scope new uncertainty and test combined identity/date/page failures in both paths. |
| Strict gates miss unusual forms | Review supported uncertainty; do not broaden layout inference. |
| Attachment already triggers independent page review | Preserve page policy; assert no additional history signal. |

Synthetic recovery verifies the mechanism, not the true cause or accuracy on case 81. Roll back only this task's explicit source/test changes, without resetting original branches/tag or touching holdout artifacts.

## Authorized diagnostic compatibility follow-up

The old temporary PDF observer accepts only `lines`, while the extractor now passes the optional `allow_split` keyword. Synthetic reproduction proves a `TypeError`; the unwrapped extractor reads ten entries. The old observer marks invocation only after its wrapped call returns, explaining why this failure can leave both invocation flags false. A keyword-compatible shim alone is insufficient: the new extractor performs multiple bounds/probe calls, and attempted parse counts are not committed history counts.

Preserve both originals. Versioned temporary tools observe only the public extractor with `*args, **kwargs`, mark invocation before calling, re-raise engine errors, distinguish completion and telemetry stages, and count final `HistoryEntry.page` values. The numbered wrapper retains its metadata/source guards and pins the new PDF tool hash. Their tests use generated bytes and fake metadata; real source access is blocked. These auxiliary files remain outside Git, with hashes recorded in the validation report.
