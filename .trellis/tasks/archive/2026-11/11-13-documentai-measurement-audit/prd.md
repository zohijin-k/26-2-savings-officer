# Audit measurement validity before implementation

## Authorized scope
Investigate the existing synthetic measurement on feat/documentai-measurement, present findings and a concrete correction plan, then wait for user approval. Implementation and n=5 rerun were explicitly approved by the user with seven constraints; final results must be reported for another approval. Use synthetic data only; do not access real inputs or private datasets. Preserve OCR, extraction, classification and verdict logic and existing tests.

## Requirements
1. Isolate original/no-degradation metrics per document type: exact fields, CER and independent type classification.
2. Verify actual rendering fonts, embedded glyph coverage, representative image appearance and authored-versus-OCR character counts.
3. Audit symmetric normalization, count format-only mismatches and separate missing fields from wrong values.
4. Recompute an analytical view with deliberately low-resolution images classified as quality defects, preserving the original recorded result.
5. Estimate n=5 per type/condition runtime and inspect whether existing repetitions are independent/unique.
6. Implement paired text-layer/own stages, raw and normalized accuracy, explicit unextracted classification outcomes, three case groups and five distinct samples per condition. Preserve old reports. Show attribution tables, weak rankings, diff versus main and all four regression branches, then wait for final approval. Do not push, merge or modify main.

## Acceptance
- Five original document rows, five OCR-count rows and evidence-backed font conclusion.
- Reproduced original field scores; counts for all 266 synthetic field comparisons.
- Quality-reclassified denominators and rates, with no deletion of samples.
- Measured-runtime-based estimate plus independent-sample limitation.
- Findings and plan reported to user; task stays planning until approval.

## Approved constraints (2026-11-13)

- Change synthetic originals only for proven generator bugs impossible as document content; cite specification/fixture/code evidence for every change. Preserve ambiguous layouts and purpose markings, especially in stress cases. No real-document reads.
- Compare identical case geometry with reference text-layer words versus actual own words. Classification remains independent; uncalled fields are a separate outcome, never counted as field errors.
- Report raw and normalized accuracy together and distinguish baseline classification/extraction errors from OCR-introduced losses and recoveries.
- Five unique samples for every condition, same table includes per-page times. Normal baseline, stress and quality defects have separate verdict rate denominators.
- No production OCR/classifier/extractor/adapter/rule or existing test edits. Existing report remains immutable.
