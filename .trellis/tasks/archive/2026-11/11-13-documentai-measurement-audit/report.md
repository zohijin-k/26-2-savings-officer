# Measurement-method audit — implementation approval pending

Branch: `feat/documentai-measurement`, starting HEAD `965a634`. The existing result was reaggregated and 35 synthetic image cases replayed with observation-only wrappers. Every field result reproduced exactly. No real input, private dataset, production logic or benchmark implementation was changed. Only this planning/audit directory was added; no new commit or n=5 execution was made.

## 1. Original/no-degradation condition

Each type has one original page. CER here is **field-value CER after production routing**, not page OCR CER. A classifier miss currently prevents the extractor from being invoked and all expected fields then count as absent.

| Type | Exact fields | Accuracy | Field CER | Type accuracy | Verdict |
|---|---:|---:|---:|---:|---|
| Resident abstract | 7/7 | 100.00% | 0.0000 | 1/1 | NEEDS_REVIEW |
| NHIS payment | 9/13 | 69.23% | 0.7368 | 1/1 | NEEDS_REVIEW |
| NHIS qualification | 7/7 | 100.00% | 0.0000 | 1/1 | PASS |
| NHIS acquisition/loss | 6/6 | 100.00% | 0.0000 | 1/1 | PASS |
| Four-insurance enrollment | 0/5 | 0.00% | 1.0000 | 0/1 | NEEDS_REVIEW |
| Total | 29/38 | 76.32% | 0.6322 | 4/5 | 2 PASS / 3 review / 0 FAIL |

The original-only failures identify measurement/source-validity problems that must be resolved before using the old mixed-condition aggregate as evidence for OCR/extractor improvement. The user's prior real-document observations were not rerun or verified here.

### Confirmed insurance source/routing confound

- Both title lines are recognized by own, but the source places the purpose label immediately before the second title line on the same baseline. At 8pt, the three-character purpose occupies 24pt while the authored gap to the title is only 23.8pt, creating about 0.2pt overlap. Visual review shows the strings touching/merging.
- The actual OCR stream contains the first title, then the purpose, then the second title. The unchanged classifier expects the two title portions to concatenate without that inserted purpose. It therefore does not invoke the insurance extractor.
- This is reproducible **without OCR recognition error**: exact text-layer words with their geometry also fail independent classification, whereas PDF raw insertion-order text classifies correctly. The earlier raw-text source preflight could not detect this difference.
- A separate, explicitly truth-type-selected diagnostic invokes the existing insurance extractor on the same own words: 4/5 fields match, with the structured enrollment field still mismatching and source form validations failing. This is a diagnostic control only; it is not substituted for independent end-to-end accuracy.
- Accordingly, the reported 0/5 is not five independent field recognition failures. It is principally an uncalled-extractor/routing outcome on a problematic synthetic source.

### Payment source validity remains unresolved

The four missing original fields are `월별고지금액`, `월별장기요양보험료`, `건강보험료`, `장기요양보험료`. The existing extractor reports `payment_component_headers`, `payment_columns`, `paid_total_matches` failures and incomplete structure. Direct truth-type-selected extraction is still 9/13; this is not just a classification gate. The source header/column geometry and rendered-OCR correspondence need investigation **in the synthetic generator**, without weakening extraction or completeness rules. Equal overall character counts do not prove correct cells or amounts.

## 2. Actual fonts and image character coverage

The renderer explicitly calls `pymupdf.Font("cjk")`; the actual embedded body font is **Droid Sans Fallback Regular**, 3,556,308 bytes, SHA-256 `ee38813ea00c3e32add4268fff7fff9e39417b4913cb13be2415164a47807cc2`. Its name contains “Fallback”, but this is the selected bundled font's name, not evidence of macOS substituting a missing installed font. The embedded font bytes match that selected bundled font on all five pages. The separate evaluation-only English footer uses Helvetica.

The three optional downloaded font assets (Nanum Gothic, Nanum Myeongjo, Nanum Gothic Coding) are absent. **They were never selected by this generator**, so their absence did not trigger an operating-system fallback. No font was installed/downloaded during this audit.

| Type | Body font size | Missing source glyphs | Replacement characters | Authored page chars | OCR chars | OCR/authored |
|---|---:|---:|---:|---:|---:|---:|
| Resident abstract | 8–9pt | 0 | 0 | 246 | 241 | 97.97% |
| NHIS payment | 8–13.60pt | 0 | 0 | 454 | 454 | 100.00% |
| NHIS qualification | 8pt | 0 | 0 | 375 | 335 | 89.33% |
| NHIS acquisition/loss | 8pt | 0 | 0 | 304 | 274 | 90.13% |
| Four-insurance enrollment | 8pt | 0 | 0 | 485 | 484 | 99.79% |

Counts are full authored page streams, including the fictitious evaluation footer and printed separators, versus emitted own word text; both use NFC and Unicode-whitespace removal. These counts are coverage diagnostics, not CER or a claim that equal-length strings match. The differences can include ignored separators and character substitutions. Three original crops and the resident page were visually inspected; the insurance PDF was also independently rendered with Poppler. Hangul appears normally, with no missing-glyph boxes; the insurance title/purpose collision remains visible in both renderers. The font hypothesis is not supported; single-font/source-layout representativeness remains a limitation.

## 3. Normalization audit and format-only errors

| Feature | Exact comparison today | CER today |
|---|---|---|
| Date object | ISO conversion on both sides | Same value stream |
| Date string formats | No date parsing/canonicalization | No date-format canonicalization |
| Unicode composition | Raw string comparison | NFC on both sides |
| Whitespace | Preserved | All Unicode whitespace removed on both sides |
| Numeric commas | Preserved | Preserved |
| Hyphen/dash variants | Preserved | Preserved |
| Full-width characters | No NFKC | No NFKC |
| Structured fields | Same JSON parsing/semantic projection on both sides; list order retained | Fixed JSON labels/punctuation excluded; values retained |

Thus semantic preparation is symmetric, but the requested string-format canonicalization is incomplete. A temporary audit comparator applied the **same** NFKC, whitespace removal, reviewed dash-equivalence mapping, validated date parsing and numeric-only grouped-comma removal to expected and observed values, recursively. It did not invent missing fields, remove meaningful address punctuation or change stored outputs.

| Scope | Comparisons | Raw exact matches | Mismatches | Format-only | Missing fields | Other value/structure differences |
|---|---:|---:|---:|---:|---:|---:|
| Five originals | 38 | 29 | 9 | **0** | 9 | 0 |
| All 35 matrix images | 266 | 98 | 168 | **0** | 151 | 17 |

| Type across seven conditions | Format-only | Missing | Other differences |
|---|---:|---:|---:|
| Resident abstract | 0 | 19 | 3 |
| NHIS payment | 0 | 44 | 11 |
| NHIS qualification | 0 | 29 | 0 |
| NHIS acquisition/loss | 0 | 24 | 3 |
| Four-insurance enrollment | 0 | 35 | 0 |

Normalization needs an explicit contract and tests, but adding it alone would recover **zero** of the currently recorded errors under the audited rules. No global punctuation-stripping score was substituted, since it could collapse genuinely distinct identifiers/addresses.

## 4. Quality-defect reclassification

The deliberately 24%-resolution condition produces a short side of about 595px. Existing policy assigns poor original-resolution quality and FAIL, so these five cases must be authored as **quality defects**, not normal-document false rejections. The report's previous caveat did not make the category correct; decision D04 in the original task should be superseded after approval.

The following is a new analytical view only. The old report and JSON have not been overwritten.

| Measure | Previous classification | Low-resolution moved to quality defects |
|---|---:|---:|
| Total attempts | 77 | 77 |
| Normal/content-valid matrix cases | 35 | 30 |
| Defect cases | 42 | 47 |
| Normal confirmed reupload FAIL | 5/35 = 14.29% | **0/30 = 0%** |
| Deliberate low-resolution FAIL | In normal numerator | **5/5 quality defects** |
| Defective PASS | 0/42 | 0/47 |
| Remaining normal exact fields | 98/266 = 36.84% | 82/228 = 35.96% |
| Remaining normal type matches | 23/35 = 65.71% | 20/30 = 66.67% |

The remaining 30 cases include stress transformations: their 25 review/5 PASS outcomes do not mean all 30 are an acceptable-image normal baseline. Original-only must remain its own baseline. Phone/rotation expectations need to be declared before scoring; do not relabel cases by observing their verdict. The five moved cases were known quality violations from their input design, not selected because they happened to fail.

## 5. n=5 runtime estimate

The requested minimum is interpreted as **five cases per document type × condition**, or 175 transformed images, not merely five images total per condition across all types. After taxonomy correction this is 150 remaining condition cases plus 25 explicit low-resolution quality defects. Keeping the existing separate defects at five repetitions adds 210, giving 385 attempts total.

Measured evidence: the retained 77-case run spent 90.11 seconds inside processing; this audit replayed 35 images in 61.24 seconds wall time (50.36 seconds processing). The five original image calls totalled 7.71 seconds wall time, including cold initialization on the first case.

| Future run | Cases | Estimated wall time on this Mac |
|---|---:|---:|
| Originals only, n=5 per type | 25 | 40–60 seconds |
| Complete type × condition matrix, n=5 | 175 | 5–7 minutes |
| Matrix plus existing separate defect suite, n=5 | 385 | 10–15 minutes |

These are extrapolations with overhead/headroom, not completed measurements. Source/layout corrections, tests and visual acceptance are excluded. Source changes can alter OCR runtime.

There is also a corpus bug: `sources(sample)` selects names with `sample % 4`, so source definitions for samples 0 and 4 are exactly equal. `--samples 5` currently creates only four unique source parameter sets per type (with some randomized photo changes). Five samples must first become five unique authored cases, and shared layout/font correlation must still be disclosed.

## Proposed approval scope

1. Correct benchmark source validity and synthetic layout only; include rendered/perfect-word-geometry checks so raw PDF insertion order cannot hide an invalid baseline.
2. Separate page OCR, classification, extractor-invoked field metrics and end-to-end field metrics. Keep missed classification visible; do not use oracle classification to inflate the main score.
3. Implement field-aware symmetric normalization and retain raw exact figures, with regression tests for missing fields, real value differences, identifier zeros and meaningful punctuation.
4. Author expected content/image validity in case metadata; move low-resolution inputs to quality defects and keep original baseline separate from stress conditions.
5. Generate at least five unique cases per cell, run n=5 only after base-source acceptance, and issue a superseding report plus required regressions.

Only benchmark tooling, new tests and documentation would change. OCR, extractor, classifier, adapter and verdict logic remain untouched. Implementation and n=5 execution are **waiting for the user's requested approval**.

## Evidence retention

Audit-only scripts/results and synthetic PNGs are under `/tmp/documentai-audit/`: `analyze.py`, `analysis.json`, `controls.py`, `controls.json`, `payment_probe.py`, `payment-control.json`, `extractor_control.py`, `extractor-control.json` and synthetic previews. They contain no real input. The original benchmark numeric artifact remains `/tmp/documentai-measurement.json`; prior committed report remains unchanged. Repository diff is limited to this new planning directory.
