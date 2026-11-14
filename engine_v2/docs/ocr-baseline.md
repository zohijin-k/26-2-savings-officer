# Text-layer OCR baseline

`engine_v2.tools.ocr_baseline` measures original text-layer pages against raster
OCR and reference-relative field agreement. It does not assess upload verdicts
or change any engine, classifier, extractor or service rule. A field agreement
rate measures loss relative to the existing extractor's text-layer result;
independent extractor accuracy remains the separate synthetic v2 reference
benchmark (`documentai_corpus_v2` / `documentai_staged_report`).

```sh
.venv/bin/python -B -m engine_v2.tools.ocr_baseline --root FAKE-input --out FAKE-output --engines own applevision --variants clean scan phone --limit 30
.venv/bin/python -B -m engine_v2.tools.ocr_baseline --root FAKE-input --out FAKE-output --engines own applevision --variants clean scan phone
.venv/bin/python -B -m engine_v2.tools.ocr_baseline --root FAKE-input --out FAKE-output --engines own applevision --variants clean scan phone --ids FAKE-selection.txt
.venv/bin/python -B -m engine_v2.tools.ocr_baseline --out FAKE-output --summarize
```

The example paths are fictitious. Actual output paths must pass the same private
location checks as `batch_assess`: inside the checkout they must be ignored and
untracked. Outside-checkout destinations are an operator option. Input/output
overlap, output symlinks/hardlinks and aliases to inputs or ID lists are rejected.
Existing assets must be installed beforehand; no downloads or remote engines.

## Selection and continuation

- PDFs only, case-insensitive suffixes. Hidden paths and symlinks are excluded
  without reading their contents. Other file types are inventory counts only.
- `--ids` reuses exact root-relative POSIX IDs from a private UTF-8 LF/CRLF list.
  It preserves spaces and case, deduplicates entries and reports only numeric
  selected/not-listed/duplicate/outside/missing/invalid counts. Unselected
  document contents are never opened.
- `--limit N` caps previously unfinished selected **documents attempted in this
  invocation**, including terminal exclusions/errors. It is not a page cap.
  Repeating a limited run advances to subsequent unfinished documents. Removing
  the limit processes the rest. Changing selection does not invalidate resume.
- A document completion record is appended and fsynced immediately. A stopped
  unfinished document reruns; complete documents, including errors/exclusions,
  are skipped. Only an incomplete final JSONL record may be repaired. Duplicate
  rows, interior corruption and complete invalid records are rejected.
- Resume binds resolved root location (opaque digest), schema version,
  engines, variants and all numeric settings. Source changes do not invalidate
  a completed ID; use a new output destination for a fresh measurement.
- Run one worker at a time; an advisory output lock rejects concurrent runs.

## Reference pages

Use the production `TEXT_LAYER_MIN_CHARS` rule (currently at least 50 characters
after production masking and strip). Separate no text from short/untrusted text.
Mixed PDFs are filtered page by page. Classification uses original page body
and existing geometry fallbacks, never a filename or an expected upload slot.

Broken text-layer heuristics use non-whitespace code points: replacement
characters >=1%, private-use Unicode characters >=5%, their combined count plus
invalid controls >=5%, or no usable word boxes. These thresholds exclude an
unreliable reference; they do not change production text-layer detection. All
thresholds and corruption counts are reported. Encrypted/corrupt/empty documents
are document-level populations; inaccessible page counts remain unknown.

## Memory-only variants and masking

All parameters are defined in `ocr_baseline_settings.SETTINGS` and copied into
run/summary metadata. Fixed seed is 20261115. A numeric page seed derives from
that seed, root-relative ID and original 1-based page index, independently of
selection, ordering, engine or continuation.

| Variant | Input |
| --- | --- |
| clean | 300 DPI RGB render |
| scan | 200 DPI grayscale, JPEG quality 70 |
| phone | 300 DPI; uniform rotation within ±1.5°; perspective corner offsets within ±1% of width/height; Gaussian sigma 1.0; JPEG quality 60 |

JPEG compression is applied in BytesIO and decoded before delivery through the
existing PNG-byte OCR interface. The phone forward/inverse transform is retained
only in memory. Both engines see identical variant bytes. OCR boxes are mapped
back to the original page for metrics; extraction sees the actual image geometry.
The source image is never geometrically corrected before OCR.

The normal engine masks some identifier digits before returning results. Scoped
delegating observers copy words **before** that original masking mutation for
raw CER only, then call the original masker unchanged. No masking is disabled.
Both extractor inputs independently pass through the same NFKC and production
word-masking boundary. Both extracted field projections then use the same
semantic projection, existing `documentai_staged.canonicalize` normalization,
final value masking and typed comparison. Complete, split and fullwidth
synthetic identifiers verify parity. All observers restore on exceptions too.

## Metrics

Reference and OCR words are independently ordered with production
`layout.normalize` / `layout.group_lines(tol=.6)`: ascending vertical centers,
group when the next word center is within .6 of its height (minimum .3% page
height), then ascending left position within each line. Geometry ties are
deterministic. No text similarity is used to choose reading order. Columns,
mixed font sizes and OCR line boxes can still affect this heuristic.

- CER is exact unit-cost Levenshtein edits / reference characters after NFKC
  and Unicode whitespace removal. Values may exceed 1. Page mean/median/p90
  and pooled edits/reference characters are separate statistics.
- Digit CER keeps ASCII 0–9 after NFKC; Hangul CER keeps syllables and Jamo
  ranges. Empty reference denominators are N/A/null; insertion counts survive.
- Word precision/recall/F1 use exact NFKC whitespace-token multisets in
  reconstructed lines, independent of word order. Repetitions count. Spacing
  and tokenization differences are intentionally visible.
- Field `eligible=1` only when the original page extractor produced that
  reviewed field. Otherwise `missing_reference=1`, outside the match denominator.
  Missing OCR fields and different OCR-side document types are mismatches.
  Processing errors and unavailable engines are separate populations.
- The reference field values are extracted once from original page geometry
  and fixed across variants. Phone field losses therefore include geometry and
  structure sensitivity. This is page-local measurement; continuation pages
  needing preceding-page context are not complete-document field accuracy.

## Error attribution

Reference lines and OCR boxes overlap when intersection area / smaller area is
at least .1. Missing reference lines have no qualifying box. Covered-line CER
is reported separately. Each OCR box's text is assigned once to the line with
highest overlap; ambiguous boxes, unmatched boxes and covered lines with no
assigned text have separate counts. This observes returned text boxes, so an
engine-filtered empty recognition can also look like detection loss.

Height bins (<12, 12–<20, 20–<32, >=32 pixels) use median reference word-box height
scaled to variant DPI, a proxy rather than true font glyph height. Each bin
reports character edits/counts and missed/covered reference lines.

Table regions come from **reference words only**:

- NHIS payment: reuse existing legacy month headers/header blocks/month rows,
  or government eight-column header/month/column structural checks. A confirmed
  bounded rectangle includes identified headers, monthly rows and an available
  total. Report inside/outside CER, inside digit CER and inside/outside detection
  misses. A region cannot be inferred from the OCR side. Unconfirmed regions
  are unmeasured, never zero error.
- Resident forms: reuse the existing history-table vertical band, treated as a
  full-width band estimate rather than precise cell segmentation.
- Other types: unmeasured. Measured coverage accompanies every aggregate.

Field mismatches with every normalized scalar reference leaf literally present
in normalized OCR text are counted as structure/extractor issues; otherwise as
OCR issues. Keys and JSON punctuation are excluded. Derived values absent even
from reference text are separately unattributable. This is a diagnostic heuristic,
not a causal proof. No values, substrings or their hashes are output.

Confidence bins [0,.5), [.5,.8), [.8,.9), [.9,1] use character-weighted mean
confidence on assigned OCR text for each covered reference line. They report
actual CER and incorrect-line rate with counts. Invalid scores are unavailable;
missed lines have no confidence and stay in the detection population. Engine
confidence scores are not comparable calibrated probabilities.

## Speed and outputs

Whole processing time is OCR + page classification/extraction/finalization.
Rendering, image transformations, reference extraction and metric computation
are excluded; reference extraction is separately timed. Own detection wrapper
includes its image preprocessing/postprocessing, while recognition split is
session inference only. Initialization and residual time are separate. Apple
has only whole-call timing. Observer copy overhead is reported and subtracted
from OCR wall time. Thread counts are read from actual ONNX sessions (normally
intra=2/inter=1); opaque native Apple settings stay null. Cold calls are explicit.

- `run.json`: closed run identity/settings; no absolute source paths.
- `results.jsonl`: document completion records containing page exclusions and
  page × engine × variant numeric metrics, fixed labels and reviewed field names.
  Root-relative IDs are the allowed identifying exception.
- `summary.json`, `summary.txt`: atomically refreshed aggregate tables after a
  run, grouped by document type × engine × variant.
- `--summarize`: recomputes and prints text plus JSON from persisted records;
  it reads no input directory, imports no OCR/model backend and writes nothing.
  To export this read-only display, redirect stdout to a separate safe location.

No document text, field values, coordinates, dependency messages or tracebacks
are saved to outputs, logs or temporary files. Quiet Python/native output,
read-only filesystem/DB guards and a network prohibition surround all content
processing. Schema validation occurs before persistence and during summary.
Progress contains only fixed labels, counts and elapsed seconds.

Exit 0 means measurement completed, including expected reference exclusions or
unavailable engines. Exit 1 means a document/page/engine processing error was
recorded. Exit 2 means invalid arguments, location, configuration, persisted
records or output failure. Interruption exits 130; earlier fsynced rows survive.

Estimate an operator run from eligible pages × the sum of all requested
engine/variant per-page processing times, plus rendering/transform overhead.
Keep cold-start overhead separate. One synthetic document provides only an
initial estimate; the operator's limited pilot supplies a better median/p90.

Timing populations retain completed OCR measurements even when extraction
subsequently fails; `attempt_seconds` additionally covers all attempts. Summary
counts expose `empty_ocr_pages`, `table_unmeasured` and `table_unavailable`.
On this development host Apple Vision returned empty outputs inside the execution
sandbox, but recognized the same authored synthetic page in normal native
execution. Check the empty-output population before drawing document conclusions.
