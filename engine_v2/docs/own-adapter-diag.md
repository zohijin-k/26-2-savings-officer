# Own/Apple adapter diagnostics

`engine_v2.tools.own_adapter_diag` measures page-local field agreement and reports conservative structural observations through the existing OCR baseline extraction path. It does not repair OCR output, change confidence, change service decisions, or establish the cause of a private document's failure.

Run from the repository root with installed local dependencies. Inputs/outputs must satisfy the existing external-or-ignored location policy. Use a new output directory for each invocation; existing output directories are rejected.

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.own_adapter_diag --root /tmp/FAKE-pdfs --out /tmp/FAKE-diag --engines own applevision
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.own_adapter_diag --root /tmp/FAKE-pdfs --ids /tmp/FAKE-payment.ids --out /tmp/FAKE-payment-diag --engines own applevision --fields NHIS_PAYMENT:MEMBERSHIP NHIS_PAYMENT:BILLING_MONTH NHIS_PAYMENT:ISSUE_DATE
```

`--limit N` limits attempted PDFs, including encrypted/open-error documents. PDF pages are evaluated separately. `--ids` accepts an immediate person-folder ID (select all inventoried PDFs below it) or a root-relative PDF path (select only that file). Blank lines and lines starting with `#` are ignored. Invalid/missing entries are skipped with numeric-only accounting; overlapping selections never process a PDF twice. Names select inputs only; they never hint document classification. With the default payment fields, nonpayment documents are skipped and counted, not relabeled as payment. Do not run an unknown input tree when preparing synthetic development evidence.

The default fields are the three payment fields above. `REGISTRY` in the tool provides the fixed ASCII code for every registered type/field pair. Other fields retain exact and normalized agreement measurements; unsupported causal evidence stays explicitly unattributable. Clean rendering and both actual local OCR callables are reused unchanged. A missing engine, OCR error, empty OCR, missing reference and classification failure have separate populations.

The extraction call is `ocr_baseline_runtime.extract → batch_assess._read_pages → localocr._from_supported_form → nhis_payment.extract`, with government forms delegated to `nhis_payment_gov.extract`. Observation wrappers always delegate to the original call and restore it on exit. The actual reference and observed branch are recorded as LEGACY/GOVERNMENT/OTHER, with null for unavailable paths; filenames and generator metadata do not choose a branch.

## Outputs and denominators

The four output files are `run.json`, `results.jsonl`, `summary.json`, and `summary.txt`. Their closed schemas permit only fixed codes, integer document/page ordinals, finite numeric measurements and null. Text, values, input IDs/paths, coordinates, hashes, exception details and tracebacks are not diagnostic output. Dependencies execute under the existing quiet, read-only, no-network boundary.

- **Eligible** counts a present reference field. Reference absence is not a failed recognition.
- **Match opportunities** count completed comparisons with defined exact/normalized flags. Unsupported causal attribution does not erase a completed comparison. Execution failures and unavailable/empty OCR remain explicit without manufactured agreement rates.
- **Diagnosed** is the denominator for the thirteen mutually exclusive causal-code rates. Missing/unattributable evidence and availability/error states do not enter that denominator.
- Exact comparison uses typed raw field equality. Normalized comparison uses the existing symmetric semantic projection/canonicalization/masking. A normalized success is OK even when raw exact equality differs.
- A zero denominator produces null, including unmeasured form/field/engine cells.

Selection counters count valid folder/file lines, empty folders, invalid/missing/outside lines, duplicate selectors and overlapping PDF occurrences. Invalid/missing counts are per skipped line. A valid repeated selector, or a valid line adding no new PDFs because all its candidates were already selected, increments `duplicate_ids`; `overlapping_pdf_ids` counts the already-selected candidates on each valid line. An existing safe folder without PDFs is an empty-folder line, not a missing path.

`TYPE_NOT_REQUESTED` is a counted-zero page availability status. `skipped_documents` counts attempted documents with no requested-kind page, including input/quality/unknown exclusions. `classified_unrequested_documents` is the subset whose every page was confidently classified as another kind. `unrequested_pages` counts explicit TYPE_NOT_REQUESTED pages; unknown/quality exclusions remain separate. These are processing populations, not document verdicts.

The first supported causal condition wins:

| Code | Observation |
| --- | --- |
| OK | Existing normalized field comparison succeeds |
| ROUTE_MISMATCH | The measured field mismatches and the completed observed dispatch differs from the text-layer dispatch |
| LABEL_NOT_FOUND | A required reference-supported anchor is absent, including its permitted spacing/split/Unicode checks |
| LABEL_SPACED | Internal whitespace separates an otherwise supported anchor |
| LABEL_SPLIT | Spatially adjacent observations split the supported anchor |
| VALUE_NOT_FOUND | No matching, format-related or uniquely aligned candidate exists |
| VALUE_OTHER_LINE | The actual field requires one line/cell and a supported value falls on another line |
| LINE_MERGED | One uniquely aligned observed box corroborates the separate reference cells; a bounded copy split resolves the original extraction |
| ORDER | Equal token/geometry populations differ only in order and an original-path replay resolves the failure |
| NORMALIZE | A permitted normalization of a copy resolves the original-path extraction |
| PATTERN_MISMATCH | Unique, aligned literal components violate the existing format grammar |
| OCR_CHAR | A unique spatially supported candidate contains character errors |
| OTHER | Available evidence does not justify a more specific diagnosis |

Membership need not have a literal membership label. Billing-month lists require component evidence. Issue dates may be unlabeled and use a closing/issuing block; an unrelated print date is not their label. Counterfactuals operate only on copies and never replace measured extraction results or original confidence. The additional whitespace normalization removes U+200B ZERO WIDTH SPACE from a copy; it does not rewrite parentheses into date grammar or insert digits/separators.

Availability codes include separate input exclusions, reference absence/unattributability, classification failure, engine availability, OCR/extraction/empty-output states, and limit accounting. REFERENCE_ERROR, RENDER_ERROR and PROCESSING_ERROR describe execution failures with causal `counted=0`; they do not extend the thirteen-cause vocabulary.

Exit 0 means processing completed, including expected exclusions; 1 means execution-error records exist; 2 means argument/location/output/schema rejection; 130 means interruption. These are processing statuses, not document verdicts.

## Synthetic scope

Development uses newly authored inputs and tracked-source isolation. Preserve exact synthetic input bytes, settings, source identity and numeric results for later comparisons; put temporary PDFs, pytest files, DBs and uploads in a separately owned workspace. Retain long-lived results outside `/tmp` when comparisons may happen days later.

Legacy and government payment forms use different existing readers. Government membership is not emitted. Field-by-field reference availability must be reported, even for valid generated inputs. Synthetic/private form equivalence has not been verified: **합성·실서류 서식 차이 가능**. Do not infer private-document causes from synthetic distributions.

## Dispatch counts

`summary.json.routes.distributions` contains page counts for text_layer and each selected engine by LEGACY/GOVERNMENT/OTHER. `routes.cross` contains each engine's reference-form by observed-form cross-tabulation. `summary.txt` renders both as ROUTE and ROUTE_CROSS lines containing only fixed names and counts, including zero cells. Each completed path counts once per document/page across fields. A completed extraction counts even when its reference fields are absent. Reference counts include successful reference extraction on unrequested or classification-failed pages. OCR engines run only for requested types. An unavailable or failed path has a null form and contributes no dispatch count.

On a present-reference mismatch, ROUTE_MISMATCH precedes classification/label/value/evidence diagnoses. OK retains first priority. Reference absence and execution/availability errors retain their status. Dispatch agreement and field agreement therefore have separate denominators.
