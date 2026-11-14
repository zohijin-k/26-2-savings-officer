# NHIS payment structure dump

Use the existing layout tool's structured mode with one explicit input and output:

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.layout_dump \
  FAKE-input.pdf --out engine_v2/data/FAKE-structure.json
```

All example paths are fictitious. The output parent must already exist. The output and its temporary sibling follow `verify_cases` policy: outside the checkout, or ignored and untracked inside it. Source/output aliases and unsafe targets are rejected. Console output contains fixed statuses and counts, never paths. No original image, OCR cache or dependency log is written. This feature was developed and verified with synthetic inputs only.

Structured mode always captures `text_layer`, `own` and `applevision`; do not combine it with `--engine`. Both OCR engines read the same in-memory 300 DPI PDF rendering. Available text words are preserved per page even for mixed PDFs. Images have no text-layer words. Missing Apple capability is a skip, distinct from a recognition failure. Dependencies/models must already be installed locally; there are no downloads, remote calls or fallback engines. The older console mode without `--out` remains compatible and has its previous masking behavior.

The JSON retains zero-based page and word indices, page/pixel sizes, unrounded top-left pixel boxes, derived word width/height and confidence. Word order is the adapter-returned order, without regrouping. Existing upstream resident-number stars remain stars. This is a structural comparison, not a pre-redaction text export or ground-truth accuracy report.

Only an entire word exactly matching the union of the existing payment extractor's fixed label constants stays literal. No trimming, case/whitespace normalization or substring exceptions are used. The 28-item list and source constants are fully enumerated in the task design and tested against the code-owned vocabulary. Metadata labels existing only as function-local strings, region names, prose, purpose values and fixture-derived fragments do not qualify. Other text is mapped character by character: digits to `9`, Hangul/Jamo to `가`, Latin letters to `A`; punctuation, symbols and whitespace retain their shape, and other alphabets are masked to `?`.

Each engine also has value-free payment diagnostics: canonical recognized heading names from that same vocabulary, observed header clusters and matched headings against nine expected component groups, recognized month count, and allowlisted failed validation names. Scope markers distinguish recognition observations, government/legacy table parsing and unavailable diagnostics. These counts do not expose dates, month values or amounts.

The billing diagnostic calls the existing LocalOcr conversion and billing checker with the canonical default savings payment requirement. It is a scoped payment probe, not a full upload verdict. `billing_cause` distinguishes independent period conflict/uncertainty, missing required query range, confirmed amount absence, uncertain amount absence, malformed amount-absence evidence, monthly-map missing/unreadable/incomplete evidence (including historical maps and the fallback after a readable period) and no finding. A missing table row and `MISSING_BILLING_MONTHS` are separate observations; one does not prove the other. Periods, fields, finding messages and source text stay in memory only.

Exit codes are 0 for a completed report without processing errors (optional capability/text absence allowed), 1 for safe recorded engine/diagnostic errors, 2 for argument/location/input/output failures, and 130 for interruption. Infrastructure failure preserves an existing output. Inspect explicit engine/page states before interpreting an empty list or null diagnostic count as an observed zero.
