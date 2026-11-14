# OCR baseline measurement

Apply to `engine_v2.tools.ocr_baseline` and its tool-only helpers/tests. Measure
OCR and page-local extractor agreement on trusted text-layer PDF pages. Service
verdict/status/reason comparison is outside this tool's scope. Do not modify
operating engines, classifiers, extractors, verdicts or old tests.

## Reference and masking

- Reuse `TEXT_LAYER_MIN_CHARS` and content/geometry classification. Filter mixed
  PDFs page by page. No filename/type hints or expected-type oracle.
- Corruption thresholds, transforms, overlap and bins live in one resume-bound
  numeric `SETTINGS` structure. Separate document and page exclusions.
- Observe words before production masking for raw CER: clone, then delegate to
  the original masker unchanged. Restore observers on failures. Never disable
  masking to improve benchmark metrics.
- Both extractor word inputs use identical NFKC + production masking. Both raw
  field projections use identical semantic projection, existing canonicalization,
  final value masking and typed equality. Test complete, split and fullwidth
  synthetic identifiers through the actual extractor. Missing references have
  no agreement denominator.
- Keep original reference geometry/fields fixed across variants. Agreement
  includes OCR geometry sensitivity; it is neither independent extractor accuracy
  nor multipage/application accuracy.

## Geometry and metrics

- Keep edits/reference counts, null empty denominators and CER above one. Page
  mean/median/p90 and pooled CER differ. Word F1 uses token multisets, not sets.
- Reuse documented production line grouping independently on each side, with
  geometry-only ties. Apply PDF page rotation to unrotated text boxes. Raster
  dimensions round outward; DPI determines scale, not rounded canvas ratios.
- Inverse-map phone boxes for metrics only; extraction uses distorted geometry.
- Payment tables are mandatory: use reference-only legacy header/month helpers
  or government header/month/column structural checks. Report inside/outside CER,
  inside digit CER and detection misses. Unconfirmed regions are unmeasured.
- Residents reuse the full-width history-table band; other types are unmeasured.
  Report measured/unmeasured/unavailable table counts. Box overlap is observed
  coverage, not hidden detector recall. Confidence bins are not calibrated.

## Privacy, continuation and reporting

- Reuse batch selection/location/alias/quiet/read-only/no-network primitives.
  Never persist text, values, coordinates, arbitrary source keys, exception
  messages or tracebacks, including temporary files. Root-relative IDs are the
  explicit identifier exception. No absolute input paths are persisted.
- One fsynced document completion record owns page measurements. Completed
  errors/exclusions are terminal. Limit counts unfinished document attempts
  per invocation; report completed skips and remaining limits separately.
- Validate closed numeric schemas and count/rate consistency on append, resume
  and summary. Validate identity before tail repair. Reject duplicate rows,
  interior corruption and complete invalid records.
- Summarize is read-only, root-independent and backend-free. Processing runs
  atomically refresh summary JSON/text. Provide compact comparison tables and
  detailed denominator/attribution tables.
- Retain valid OCR timings when extraction later fails; expose all-attempt time
  separately. Exclude rendering, transforms, reference extraction and metric
  computation. Report actual threads, cold calls and empty-output populations.

## Synthetic verification environment

Use tracked-source isolation and new synthetic samples, never ignored input,
upload or database trees. Dependency/model/font links are allowed. Put temporary
data outside the isolated checkout so external-path tests keep their premise.
Give the isolation its own Git boundary so lint does not inherit an ignored
parent. Report these environmental failures before correcting their setup;
do not change old tests.

Apple Vision can return empty outputs inside the execution sandbox without an
adapter exception. Verify the same authored synthetic input in normal native
execution before interpreting it as document quality. Preserve the original
engine behavior and explicit empty-result counts. Actual documents are run by
the operator independently.
