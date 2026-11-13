# Decisions

| ID | Decision | Reason |
|---|---|---|
| D01 | Proceed without interactive Trellis gates and commit prompts | Explicit user authorization for unattended completion and local commits takes precedence. |
| D02 | Branch feat/documentai-measurement; no main/remote mutations | Requested isolation; initial checkout was clean. Git ref creation required sandbox escalation and succeeded. |
| D03 | Initial n=1 per type/condition, seven conditions = 35 normal-content cases | Complete matrix before increasing repetitions; benchmark is diagnostic, not a population estimate. |
| D04 | Keep low resolution among normal-content transformations; separately explain quality rejection | Correct content can still violate upload quality policy; this is an operational reupload rate, not proof of a rule bug. |
| D05 | Private text layer is a silver reference; do not execute any real case | Text-layer extraction can itself be wrong. Only fabricated temporary PDFs may test the mode. |
| D06 | Missing outputs and execution failures remain visible in denominators | Avoid success-only accuracy and silent loss of difficult cases. |
| D07 | No existing test or production OCR/extraction/rule edits | Measurement-only requirement. |
| D08 | Reuse fictitious fixture providers for five sources; independently author all 38 field values and validate generated text-layer extraction | Existing complete synthetic forms avoid fabricated truth from OCR outputs. Resident date is rendered without internal spaces so text-layer word tokenization preserves the fixture's supported date token. |
| D09 | Use 35 normal-content plus 42 defective cases, n=1 per type/condition | All requested cells completed quickly with one layout/font per type; do not imply population accuracy or independent repeated samples. No sample reduction was needed. |
| D10 | Keep scalar/structured exact equality strict, exclude insurance evidence geometry/confidence only | Bounding boxes and confidence jitter are not field semantics. Retain all eight semantic insurance columns. |
| D11 | Use normal-only timing in headline/type/condition tables | Defects include invalid bytes and immediate rejections, which would understate OCR time. Preserve all-attempt/defect timing separately in temporary numeric results. |
| D12 | Mirror production attachment scoping and text-PDF routing for the private silver reference | Independent review found whole-PDF versus scoped-form comparison bias. Added synthetic attachment/type-mismatch tests. A first full engine run exposed a new benchmark preflight failure from geometric-versus-raw-text classification; fix only benchmark routing, then repeat full engine verification. |
| D13 | Commit value-free synthetic report tables; keep source images, raw JSON and execution logs in temporary paths | Explicit user request requires a reviewable report; no source values or real-document outputs are included. |
| D14 | Keep confirmed FAIL reupload counts independent from review and all other statuses | Final status FAIL plus requested code severity FAIL is required. Five normal-content quality reuploads are operational outcomes, not evidence of erroneous policy. |
| D15 | Repeat identical 77 synthetic cases once after regressions finish; retain only the second run | Avoid concurrent-test timing bias. All non-timing case results matched exactly; do not pool correlated repeats or double sample denominators. |
