# DocumentAI measurement

This documents the historical v1 measurement. For the current approved paired-stage method, use [measurement v2](documentai-staged-measurement.md). V1 results are retained for reproducibility; their mixed-condition/uncalled-field percentages are not interchangeable with v2 metrics.

This tool observes **own OCR → existing engine_v2 extractors → existing demo upload assessment**. It does not change any OCR, extractor, policy, confidence threshold or verdict logic. Run it sequentially: dependency suppression, read-only auditing and observation wrappers are process-global.

## Synthetic execution

From the repository root:

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_bench synthetic \
  --samples 1 --seed 20261113 --output /tmp/documentai-measurement.json
```

The parent output directory must already exist. The tool writes numeric/identifier-only JSON and a sibling Markdown report, prints fixed-vocabulary progress plus a numeric completion summary, and exits 0 on complete execution, 1 when a measurement fails, or 2 on invalid arguments/output errors. It never enumerates an existing input directory. Synthetic source files live in an automatically cleaned temporary directory. Model assets must already be installed; there is no download or network OCR.

Five document types are covered: `resident_abstract`, `nhis_payment`, `nhis_qualification`, `nhis_acquisition_loss`, `insurance_4`. Seven conditions are original 300dpi, thresholded monochrome, expanded-canvas rotations +5° and -5°, 90° counterclockwise, 24% resolution (about 72dpi), and the existing strong phone simulation (perspective, desk background, shadows, optical blur and JPEG loss). Source content uses existing fictitious fixture providers; images, not injected OCR words, are measured. Names cycle over four invented strings when increasing repetitions. The fixture family remains fixed, so additional repetitions are not independent template coverage.

Truth is authored separately from extraction. A dedicated test validates all 38 source fields against their generated text layers before OCR evaluation. The source PDF uses CJK text and an explicit fictitious mark. Existing synthetic phone rendering and NFC/whitespace CER primitives are reused; the older mixed-title three-type synthetic suite is not classification ground truth.

Defects are separate from normal-content image transformations: early/future issuance, a deliberately mismatching applicant identity, a printed missing-page claim, wrong upload slot, severe resolution loss, severe blur, invalid file bytes, missing resident address dates and a missing payment month. Identity mismatch changes the reference applicant; wrong type changes the requested slot. The source text/bitmap is otherwise changed before OCR, never an extracted fact or verdict. All five types receive each common defect. The last two defects apply only to their relevant types.

## Metric contracts

- Field accuracy is exact typed equality of the authored semantic field with the extracted field. Date objects use ISO values. JSON fields are compared as parsed structures; list order matters. Evidence boxes/confidence in insurance rows are excluded, while all eight reviewed semantic columns are retained. No substring/contains matching is used.
- CER uses the existing NFC plus Unicode-whitespace normalization and Levenshtein distance. Scalar values and ordered structured values form the character stream; fixed JSON keys/punctuation cannot inflate accuracy. Variable month keys are included. It may exceed 1. An empty-reference field uses denominator 1 for insertion errors; absence of an expected empty field is an exact mismatch even when CER is 0. Aggregates use total edits / max(total reference characters, 1), not a mean of per-field ratios.
- Classification is observed from the existing content classifier independently of the requested slot. A missing/wrong classification cannot receive fields through a ground-truth-selected extractor. The full normal-content denominator remains in classification and field accuracy.
- False rejection counts a normal-content case once only when final document status is `FAIL` and at least one requested reupload code has severity `FAIL`. Code counts are deduplicated within each document and can sum above the document count. The report lists all ten requested codes, including zeros, and nonzero type/condition breakdowns.
- False acceptance is the count of authored defective cases ending `PASS` divided by all defective attempts. `NEEDS_REVIEW` is neither an accepted defect nor a confirmed rejection. The report includes that distribution to avoid treating extensive manual review as automatic defect detection.
- **Normal content is not a guarantee of acceptable image quality.** Low-resolution transformations deliberately test the quality boundary; resulting reuploads can be correct policy behavior. Interpret the requested false-rejection number as an operational reupload rate on content-valid papers. Original-only and condition-level results are also available.
- Processing timing includes original reading/rasterization, own OCR, extraction, file evidence and shared upload assessment. It excludes source generation and metric comparison. The first measured case includes cold model initialization. Headline/type/condition timing uses normal-content pages; JSON also stores all-attempt and defect timing. Invalid bytes do not have physical pages and are excluded from normal timing.
- Execution failures stay in attempted/normal/defect denominators, with missing expected fields counted as errors. They are reported separately; no success-only score is presented. Missing metrics use `null` only for groups with no applicable samples.

The complete report includes all 35 type/condition cells, per-cell field metrics, codes, defective-case outcomes and weakest document/field/condition rankings. Improvement suggestions are candidates only. The committed example report is in the Trellis task's `measurement-report.md`; its regression comparison is in `validation.md`.

## Private text-layer agreement mode

Do **not** use synthetic output as authorization to execute private cases. This task did not run real documents. A future authorized invocation is:

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_bench private \
  --cases /tmp/FAKE-cases.json --output /tmp/FAKE-metrics.json
```

A fabricated schema example (not an actual case):

```json
{"schema_version":1,"cases":[{"file":"FAKE-document.pdf","doc":"nhis_payment"}]}
```

The manifest must be outside the checkout or ignored **and untracked**, after resolving symlinks. The output and atomic temporary sibling independently obey the same `verify_cases` policy; no bypass flag or new ignore rule exists. Output cannot alias the manifest or an original source, including hardlinks. Relative sources resolve from the resolved manifest directory. Unknown/duplicate keys and unsupported types are rejected. The tool does not create parent directories.

Every source PDF page needs a usable text layer. Existing extraction on that layer produces an in-memory **silver reference**, not independently verified truth. The same PDF is rendered at 300dpi and read with own in memory; no private image/temp source is written. Both sides use existing form/attachment scoping. Only fields actually extracted on the reference side are compared; `reference_missing_fields` explicitly reports the remainder of the reviewed field contract. Thus a high agreement score does not prove either extraction correct or complete.

Output contains only numeric case positions, fixed document/field names, fixed status/reason codes, numbers and O/X. Manifest identifiers, paths, filenames, values, raw text, exception messages, confidence/evidence objects and OCR debug output are not recorded. Python/native/log output is suppressed on success and failure, and assessment auditing prevents source mutation, subprocesses and DB writes. Private reference/measurement failures use a fixed generic code; metrics are never serialized from complete extraction/assessment objects.
