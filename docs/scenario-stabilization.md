# Standalone scenario stabilization (2026-11-23)

PRODUCTION_NOT_READY. Tests use synthetic temporary databases and files. No production migration or deployment.

P4/P6/P16/P18 failed on both officer main `b54e66a183791031c38c05483c4d1b5827e1f1f0` and README PR #42 HEAD `195bccb0db02cf3ce0072e7f17e3ef9160e8cb75`. All four scenario blobs were identical between those refs. These were existing main failures, not README regressions.

| Module | Existing failure | Corrected verification |
|---|---|---|
| P4 | Missing CAS token returned 428, then missing response label; youth also had a forbidden token only in an upload comment | Read authorized detail revision; send single `expected_revision` and bulk `expected_revisions`; retain strict source/role scan, assert missing428/type422/stale409 and full Review/Application invariance |
| P6 | Same legacy CAS request; S6/S8 expected public null for a diagnostic that reads private stored OCR | Send observed revision, assert +1; compare stored 0.0/0.6 while preserving public non-exposure checks |
| P16 | Receipt/interview event aliases were expected to establish an absent issue-date label | Require NEEDS_REVIEW / REQUIRED_FIELD_UNREADABLE; add explicit issue-label PASS controls |
| P18 | Low-confidence dates were expected to carry definite out-of-range codes | Require LOW_OCR_CONFIDENCE review and absence of definite date violations; confident boundary cases still FAIL |

All 18 modules passed: **1980 checks plus P14's eight form sets**. P4 205, P6 279, P16 110, P18 185. No skipped scenarios, removed checks, relaxed runtime guards or policy changes.

Run from the repository root:

```bash
python -m demo.backend.tests.run_p4_scenarios
python -m demo.backend.tests.run_p6_scenarios
python -m demo.backend.tests.run_p16_job_docs_scenarios
python -m demo.backend.tests.run_p18_applicant_precheck_scenarios
```

P16 exercises the retained low-level reader/rule interfaces with synthetic OCR. Youth's canonical receipt upload bypass is independently covered by `test_receipt_manual_review.py`; low-level extraction tests do not authorize automatic receipt decisions at upload.
