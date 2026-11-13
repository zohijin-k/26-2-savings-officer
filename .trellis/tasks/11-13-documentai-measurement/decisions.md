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
