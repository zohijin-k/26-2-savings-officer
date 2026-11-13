# Independent measurement review

Scope: new benchmark core, synthetic corpus/aggregation and new tests. No private source data was inspected or executed. No production code or existing test was edited during review.

## Validation

- Independent focused run: `python -B -m pytest engine_v2/tests/test_documentai_bench.py engine_v2/tests/test_documentai_synth.py -q`.
- Result at review time: **47 passed**, five existing PyMuPDF import warnings, 3.90 seconds.
- Own selection is explicit; fixture and remote adapters are excluded and restored after each case.
- Classification comes from production LocalOcr/PdfText routing, independently of expected document type. A wrong declared type cannot supply its own fields.
- Missing fields and execution failures remain visible; exact typed equality is separate from NFC/whitespace-normalized CER. Insurance evidence metadata is excluded using a fixed semantic projection.
- Synthetic truth is authored from source constants and checked against fabricated text PDFs. The measurement reads rendered images, not those text references.
- Private manifests and outputs reuse resolved external-or-ignored/untracked policy; source/manifest aliases, including symlinks and hardlinks, are rejected. Numeric/O/X/code-only projection, native/Python/log suppression and read-only audit guards have focused tests.

## Findings sent to implementers

| ID | Finding | Required resolution |
|---|---|---|
| R01 | Private `_text_reference` directly extracts all text pages while measured LocalOcr scopes supported forms with `attached_pages.extract_form`. A legitimate attachment could create a baseline/measurement scope difference. | Reuse unchanged `extract_form` for text reference; cover a fabricated form-plus-attachment PDF. Core implementer notified. |
| R02 | Readable Markdown initially reports field metrics per type across all conditions, while requested field × type × condition granularity exists only in JSON. | Add a per-cell field table/CSV artifact or an explicit link to the committed numeric breakdown. Root notified. |
| R03 | Overall/type timing includes defects and immediate invalid-file rejections, while cell/condition timing includes only normal-content transformations. | Label the timing scopes or use normal-only timing for the headline comparison. Root notified. |

## Interpretation limits

- One authored layout/font per document and n=1 per matrix cell are diagnostic, not a population estimate. Repeated image conditions are correlated.
- Normal-content low-resolution images can validly receive quality-policy FAIL; the operational reupload metric must carry this qualification.
- A low defective-document PASS rate may reflect manual review rather than successful automatic defect recognition; NEEDS_REVIEW must be shown separately.
- Invalid bytes have no natural page count. Overall attempted-input timing should not be presented as pure successful OCR throughput.
- Private text layers are silver references and can themselves omit or misextract fields. Reference coverage is explicitly reported.

## Follow-up review

R01 was implemented using the production attachment-scoping helper and a fabricated two-page regression. Targeted rerun passed both attachment and wrong-declared-type tests. It also exposed a new reference-only routing difference: the insurance source is recognized from raw PDF text, but coordinate word ordering loses the title phrase. Production text-PDF reading uses raw PDF text first. The core implementer was asked to mirror that order, retaining the independent-classification safeguard and the full synthetic preflight test.

Independent arithmetic check of the completed synthetic numeric artifact: 77 attempts = 35 normal matrix cases + 42 defects; all 35 type/condition pairs present; 98/266 exact field matches; five normal-content confirmed reupload failures; zero defective-document PASS results; zero execution errors. Recomputed numerator/denominator totals match the saved summary. Normal statuses are 25 NEEDS_REVIEW, five FAIL and five PASS; defect statuses are 21 FAIL and 21 NEEDS_REVIEW. These counts support the explicit review-versus-detection caveat.

## Resolution and artifact verification

- R01: supported text-reference forms now use existing `extract_form`; resident history retains all pages. A separate review caught raw-text versus geometric-classification routing of a valid synthetic insurance source; final verification must cover all source preflights after matching production text-PDF routing.
- R02: full per-field/type/condition Markdown table added, plus nonzero reupload-code combinations and explicit zeros.
- R03: headline timing now uses normal-content pages only; numeric summary keeps normal, defect and all-attempt timing separately.
- Saved synthetic result independently recomputed: all 35 pairs present; 77 attempts (35 normal + 42 defective), 98/266 exact fields, 5 normal confirmed reupload failures, zero defective PASS, zero execution failures. Normal statuses are 25 review/5 FAIL/5 PASS; defects are 21 FAIL/21 review. All aggregate numerators and denominators match.

## Final resolution

- R01 resolved: supported-form reference extraction now shares `extract_form`; reference classification mirrors production raw-text-first routing, with geometry only as fallback. Fabricated two-page attachment and insurance word-order regressions pass.
- R02 resolved: generated Markdown includes all 266 type/condition/field rows with exact counts and CER.
- R03 resolved: headline/type timing uses `normal_seconds_per_page`; normal/defect/all-attempt numeric timings remain distinct and documented.
- Final independent focused run: **50 passed**, six existing dependency warnings, 3.36 seconds. All 38 authored source fields pass preflight; no original OCR/extractor/verdict/test changes were needed.
- No remaining blocking finding from this scoped review. Root owns full regressions, final artifact retention and local commit verification.
