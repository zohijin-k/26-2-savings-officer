# Design: payment structure evidence, stage 1

Status: implementation approved 2026-11-14, including the five user refinements. Branch: `work/nhis-payment-structure-stage1`.

## Boundaries and task shape

Keep one task because the deliverables share one input-evidence contract, unchanged operating-code boundary and final approval gate. Research is already a planning deliverable; the two small tooling changes are verified together. No extractor fixes are included. Source-backed findings live in `research/input-granularity.md` and `research/tooling-and-selection.md`.

Only tooling under `engine_v2/tools/`, new test files and relevant documentation/specs may change in implementation. Preserve all existing tests and OCR/classification/extraction/assessment/verdict implementations. The user supplies real structure dumps only in a later stage; this task's development and validation use authored synthetic inputs.

## Reuse and CLI

Extend `engine_v2.tools.layout_dump` with an explicit `--out` JSON mode; keep its closed projection/diagnostics in the local helper `engine_v2.tools.structure_dump` to avoid mixing legacy and structured masking contracts. Retain the existing single-engine console mode and imported `mask`/`group_lines` helpers unchanged for compatibility. The new mode is documented and tested through this command shape (all placeholders fictitious):

```text
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.layout_dump FAKE-input.pdf --out FAKE-output.json
```

`--out` mode always measures `text_layer`, `own` and `applevision`. Reject a simultaneous single-engine override rather than silently ignore it. It has no unmasked mode, automatic input discovery or source-derived output filename. Require an existing output parent. Legacy helpers are not reused for masking or grouping because their contracts differ; extending their module reuses the established layout-tool entry point.

Use the existing batch inspection/explicit engine invocation, quiet/read-only/network guard and target/atomic helpers rather than a second OCR stack. Keep Git location validation outside that guard and all backend/OCR imports and execution inside it where supported by the existing boundaries. Disable bytecode before backend imports and invoke with `-B`. Do not write raster pages, OCR caches, raw logs or model downloads.

## Input and word projection

Decode a single supported PDF/image through the existing batch page contract. PDFs are rasterized at 300 DPI in memory for both OCR engines even if they have a text layer. Text-layer words use sorted PyMuPDF word order and the same point-to-pixel transform as batch assessment. Preserve per-page available text even on mixed PDFs; leave batch's full-coverage reference rule unchanged. For this partial-text case, add a small dump-local text-word collector using the same conversion rather than changing the batch reference contract.

Capture each provider's adapter-returned `OcrResult.words` without sorting, merging, splitting or filtering it further. Do not group before serialization. The provider's returned order is the evidence; any diagnostic reading-order view is outside this stage. Page indices follow production's zero-based numbering.

The closed JSON projection contains:

- `schema_version`, a fixed masking-policy version and fixed engine names;
- per engine/page: fixed status/code, page index, point size where available, pixel size and coordinate units;
- per word: zero-based `word_index`, masked `text`, unrounded `bbox_px`, derived `width_px` / `height_px` and numeric confidence.

Do not include source path/name/stem, file metadata, raw page text, fields, full extraction/assessment results, exception messages, value hashes or dynamic object dumps. Confidence is retained as numeric word evidence, including the context needed for confidence-sensitive billing diagnostics. Validate geometry/confidence as finite numeric data before serialization; report malformed engine output with a fixed status rather than serialize arbitrary objects.

Existing resident-number redaction may already have changed trailing digits to `*` in the adapter words. Retain those stars and all geometry/order; do not bypass that operating boundary. The dump does not claim access to original pre-redaction character content.

## Exact-label masking

Keep one finite NHIS_PAYMENT label vocabulary in the new tool mode, backed exclusively by existing extractor module constants listed below. Include observed fixed metadata/table item names and extractor-recognized fragments only; do not import broad region/prose/value allowlists. Reuse existing extractor constant tuples where appropriate without editing them, without adding remaining function-local item names.

The complete approved literal vocabulary is derived only from `nhis_payment.CARE`, `HEALTH`, `OUTSIDE_HEALTH`, `MONTH_LABELS`, `TABLE_LABELS`, `TABLE_LABEL_FRAGMENTS`, and `nhis_payment_gov.COMPONENTS`, `HEADERS`, `GROUPS`. No function-body literals, fixtures, substring-derived fragments or independently authored label additions are permitted. The current deduplicated set is exactly **28** items:

```text
건강
건강보험
건강보험료
고지
고지금액
고지보험료
금액
납부
납부금액
납부년월
납부보험료
납부월
년
년월
노인장기요양
보수외건강
보수외소득월액(건강)
보수외소득월액(요양)
보수외소득월액건강
보험료
보험료연월
보험료월
실납부
월
월별
장기요양
장기요양보험료
청구월
```

Metadata labels that exist only as function-body literals, split fragments absent from these constants, titles, confirmation/issuer prose, region names, membership and purpose values are excluded. All recognized-heading diagnostic strings are projected through the same vocabulary.

For each original whole word, first perform exact case/whitespace-sensitive membership against that vocabulary. Only an exact match is emitted literally. Do not normalize, trim, search for substrings or reconstruct labels to decide this exception. Otherwise replace each digit with `9`, Hangul syllable/Jamo with `가`, and Latin letters with uppercase `A`, preserving whitespace, punctuation and symbols. Other alphabetic scripts are masked to `?` rather than retained as values. Character substitutions retain shape length and do not alter boxes. Fixed item names embedded in a value-bearing word are fully masked as ordinary characters.

Examples below are a proposed contract, not an executed tool result:

| Synthetic input word | Output |
| --- | --- |
| `고지금액` | `고지금액` |
| `고지금액:123,450` | `가가가가:999,999` |
| `가상시험 ABC 2026.11` | `가가가가 AAA 9999.99` |
| `12월` | `99가` |

The per-engine words can differ. No accuracy or label-semantic conclusion is inferred from masked prose. Unreconstructable fixed-label context is explicitly deferred to stage 2 rather than obtained by revealing value-bearing words.

## Per-engine value-free diagnostic probe

Run existing payment extraction against the unmodified in-memory provider words under the guard; expose only a closed diagnostic projection, never source text, field values, messages or evidence payloads. Observe production helper calls through scoped wrappers to capture actual header bands/clusters rather than invent another table parser. Store recognized names from the 28-item vocabulary only, observed component cluster count and matched expected-heading count against nine, month count and allowlisted failed validation names. Distinguish an uncalled/unavailable diagnostic from a real zero count.

Reuse production `payment_period.collect`, LocalOcr conversion and `_check_billing_months` with the existing canonical NHIS_PAYMENT requirement. This is a scoped payment diagnostic, not a full upload verdict or newly inferred eligibility. Only fixed cause enums may leave memory: independent period conflict or uncertainty/missing evidence; required-month range omission; confirmed billed-amount absence; uncertain billed-amount absence; malformed amount-absence evidence; monthly-map missing/unreadable/missing-required-key uncertainty (also reached after a readable period and covering historical evidence); and NONE/NOT_RUN/error states as appropriate. Derive causes from existing structured branches, never message parsing. Table-month loss is reported separately from the MISSING_BILLING_MONTHS cause; a failed monthly-row check alone cannot establish why that code occurred. Persist no period, month, amount or finding detail values. Preserve all scoped wrappers after failures. The actual fixed billing causes are `NONE`, `PERIOD_CONFLICT`, `PERIOD_UNCERTAIN_OR_MISSING`, `QUERY_RANGE_MISSING_REQUIRED_MONTHS`, `CONFIRMED_AMOUNT_MONTHS_MISSING`, `AMOUNT_ABSENCE_UNCERTAIN`, `AMOUNT_EVIDENCE_INVALID`, `MONTHLY_MAP_MISSING_OR_UNREADABLE`, and `NOT_RUN`; historical-map cases share the monthly-map cause rather than inventing an additional enum.

## Locations, output and failures

Apply `verify_cases._private_location` to the resolved requested output and atomic sibling. Inside the checkout both must be ignored and untracked; outside locations are an operator-runtime option. Do not add an ignore-rule bypass. Reject source/output aliases, hardlinks and unsafe output targets using the existing target policy plus explicit source equality/samefile checks. Recheck before replacement and preserve the old output on infrastructure/serialization failure.

Only the explicit JSON destination is written after guarded processing. Console output consists of fixed status/codes and counts; no paths, argument echoes, input words or dependency output. Do not expose exception messages or tracebacks. Text-layer absence is `NOT_APPLICABLE` per page. Optional unavailable Apple Vision is `SKIPPED/ENGINE_UNAVAILABLE`; recognition failures are distinct fixed errors. Successful pages and safe failure states can coexist in a dump. Exit 0 for a completed dump without processing errors (optional absence allowed), 1 for recorded engine/page processing errors, 2 for arguments/location/input/output contract failures, and 130 for interruption. A run-level failure does not replace a prior dump.

## batch_assess --ids

Add optional `--ids <file>` to batch execution; absence preserves current behavior. The list is UTF-8, one exact `--root`-relative POSIX path per nonempty line. Preserve case and spaces; strip line endings only. Count and deduplicate repeated entries; count and exclude absolute/outside-root/traversal entries and missing, hidden, unsupported, symlink or noncanonical members without echoing them. Process the valid unique subset. A list with no usable entries performs no document processing. Report inventory not-listed, duplicate, outside-root and missing/invalid counts using fixed labels only. A final newline is optional. Validate the list's actual location using the existing private-location policy and keep it protected from output aliases.

Use the existing sorted inventory and group assignment, then filter the processing list. Metadata-only traversal of unselected entries remains permitted, but no unselected document is opened, rasterized, OCRed, extracted or assessed. The list order does not change processing order. Validate selection before creating or mutating outputs. `--summarize --ids` is an argument error.

Keep VERSION/POLICY, the closed metadata schema and result schema unchanged. Root and engine compatibility checks, lock/fsync, partial-tail repair, completed-ID skipping (including terminal errors), persistent group numbers and summary of all stored rows remain unchanged. Selection may vary across invocations against the same compatible output; it is not a new resume identity. Previous unselected rows stay in place. Existing accumulated processing-error exit behavior stays run-wide.

## Compatibility, risks and follow-up

- User refinement authorizes read-only production extractor/billing-check calls for diagnostics. Never feed masked words into those calls or change their operating behavior.
- Existing lowercase/substr-based masking helpers remain unchanged. Only the new structured mode implements this task's stronger projection.
- A text layer is not ground truth; a structural difference alone does not prove the cause of real extraction loss.
- Provider box boundaries, heights, order and confidence can affect regrouping/header/body checks as well as OCR character recognition. Preserve them for stage-2 comparison.
- Native Apple/model availability must be reported from synthetic execution after approval; never substitute another engine or install/download automatically.
- New tool tests are separate files. New expected counts are explained as additions to the supplied baseline, not changes to old assertions.
- If implementation requires an operating-code change or exposes a material new contract decision, return to planning.
- Commit only after presenting actual checks, `git diff --stat main`, a real synthetic dump example and a proposed commit plan, then receiving separate approval.
