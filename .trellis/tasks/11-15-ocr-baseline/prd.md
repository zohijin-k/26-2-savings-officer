# OCR baseline on text-layer PDF pages

## Approval and scope

- Task creation, planning and a new `work/ocr-baseline` branch from `main` were approved on 2026-11-15.
- Implementation approved on 2026-11-15 with mandatory payment-table attribution and symmetric masking/normalization.
- The latest instruction removes service verdict comparison from the original request. Do not measure upload status, reason-code agreement, false reupload candidates or false passes. Keep paired extractor field agreement.
- Do not open existing real documents. Author synthetic PDFs for every development run. The operator alone runs real inputs.
- Keep OCR engines, classifiers, extractors and service decisions unchanged. Existing tests must not be edited to conceal regression failures.

## Deliverable

Create `engine_v2/tools/ocr_baseline.py`, synthetic tests and tool documentation. Reuse batch assessment selection, durable continuation, output safety and summarize conventions without changing existing behavior.

```text
.venv/bin/python -B -m engine_v2.tools.ocr_baseline --root FAKE-input --out FAKE-output --engines own applevision --variants clean scan phone [--ids FAKE-selection.txt] [--limit N]
.venv/bin/python -B -m engine_v2.tools.ocr_baseline --out FAKE-output --summarize
```

`--limit` caps previously unfinished selected PDF documents attempted during this invocation, including terminally excluded documents. Page counts are separately reported. Removing the limit continues the same output set. Selection and limit are invocation controls, not run identity.

## Required behavior

1. Inspect PDFs only. Select pages using the existing trusted-text-layer threshold. Classify each eligible page from its body/geometry using existing production classification; never use filenames as type hints. Mixed PDFs remain eligible page by page.
2. Count no/insufficient text layer, broken text layer, encrypted PDF, unknown document type and processing errors separately. Separate file-level exclusions from page-level exclusions; never invent a page count when an encrypted/corrupt file hides it.
3. Render the same page into clean (300 DPI), scan (200 DPI, grayscale, JPEG 70) and phone (300 DPI, seeded rotation up to 1.5 degrees, mild perspective, Gaussian sigma 1.0, JPEG 60). Keep settings in one reviewed constant structure, persist its numeric settings and seed, and bind resume to them.
4. Report page CER after NFKC and whitespace removal with shared geometric reading order; order-independent multiset word precision/recall/F1; digits-only and Hangul-only CER. Expose edit counts and reference counts, including empty-denominator cases.
5. Call the same existing extractor route separately for the original text-layer reference and each OCR input. Compare reviewed semantic field values in memory. Missing reference fields are outside the agreement denominator and counted separately. Missing OCR fields and OCR-side misclassification count as mismatches for available reference fields. Extraction errors are separate failures, not successful samples.
6. Report OCR and whole input-processing seconds per page excluding rendering, transformations and benchmark metric computation. Split own detection/recognition where observable without algorithm changes; report unavailable splits explicitly. Record actual numeric thread settings and cold-start state.
7. Include NHIS payment table inside/outside CER, inside digit CER and detection miss rates, using existing header/month-row logic on reference geometry only; unconfirmed regions are unmeasured. Apply identical production masking and existing field normalization to both extraction sides before equality.
8. Attribute missing reference lines versus errors on geometrically covered lines; character-height bins; available existing table-region detectors; disagreement causes from normalized value presence in OCR text; and confidence-bin observed errors. Persist counts/metrics only.
8. Save page/document identifiers, page numbers, fixed type/engine/variant labels and numeric metrics. Never save original text, extracted values, coordinates, input-derived dictionary keys, exception messages or tracebacks, including temporary files and logs. Root-relative IDs are the explicitly allowed identifier exception; do not write absolute input paths.
9. Produce JSON and text tables grouped by type × engine × variant, including exclusions, missing-reference field counts, unavailable/error populations, timings and attribution coverage. No verdict columns or verdict dependencies.

## Acceptance

- Known synthetic strings/geometry prove exact metric results, normalization, denominators and geometric ordering.
- Synthetic multipage PDFs prove page eligibility and all exclusion reasons. Selection/resume tests prove no reads of unselected contents, unchanged completed rows, safe partial-tail recovery, stable random transforms and configuration rejection.
- Privacy tests place unique synthetic sentinels in source text, field values, unknown field keys, dependency stdout/stderr/native output and exception messages. No sentinel or coordinates reach any output/temporary artifact/log. Read-only/network guards block swallowed side effects too.
- Run one newly authored synthetic document through actual installed engines, record numeric metrics/timing, and clearly distinguish missing engines from failures. Do not download models or invoke remote engines.
- Run the requested engine tests, backend tests, all 18 scenario modules, and frontend TypeScript/lint/build. Compare actual counts to the supplied baselines; report existing failures before any attempt to alter tests.
- Before commit, review the full diff and staged sensitive-string scan, then request explicit approval. Do not commit, amend, push or add coauthor trailers without the specified authorization.
- Final delivery includes the two operator commands from the request with their supplied paths (chat only, never executed or committed) and a page-based runtime estimate using the synthetic run, including its limitations.
