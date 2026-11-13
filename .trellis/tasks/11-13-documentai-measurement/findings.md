# Measurement findings and candidates

The completed run uses own only, five authored fictitious source layouts, one CJK font, seed 20261113 and one sample per type/condition. It measures 35 normal-content cases and 42 deliberately defective cases. No real input was opened and no production OCR/extractor/verdict logic was changed. The full tables are in [measurement-report.md](measurement-report.md).

| Metric | Result |
|---|---:|
| Execution | 77/77 completed, 0 errors |
| Exact fields | 98/266 = 36.84% |
| Micro CER | 0.7122 |
| Correct document type | 23/35 = 65.71% |
| Normal confirmed reupload FAIL | 5/35 = 14.29% |
| Defective PASS | 0/42 = 0% |
| Normal processing | 1.3413 seconds/page |

The five normal reuploads are all `LOW_IMAGE_QUALITY` on intentionally low-resolution images. Original/monochrome/rotation/phone groups have no confirmed reupload FAIL in this sample. Thus the requested rate is an operational quality-policy outcome on correct-content documents; it does not demonstrate an erroneous rejection rule. Normal verdicts were 5 PASS, 25 NEEDS_REVIEW and 5 FAIL. Defective cases were 21 FAIL and 21 NEEDS_REVIEW. Zero defective PASS therefore does not establish automatic defect detection.

| Weak document rank | Exact fields | Classification |
|---|---:|---:|
| 4-insurance enrollment | 0/35 = 0% | 0/7 |
| NHIS acquisition/loss | 15/42 = 35.71% | 5/7 |
| NHIS payment | 36/91 = 39.56% | 6/7 |
| NHIS qualification | 20/49 = 40.82% | 6/7 |
| Resident abstract | 27/49 = 55.10% | 6/7 |

| Weak condition rank | Exact fields | Classification |
|---|---:|---:|
| 90° counterclockwise | 0/38 = 0% | 0/5 |
| Strong phone degradation | 5/38 = 13.16% | 4/5 |
| +5° | 7/38 = 18.42% | 4/5 |
| -5° | 8/38 = 21.05% | 4/5 |
| Low resolution | 16/38 = 42.11% | 3/5 |

All five insurance fields (`성명`, `생년월일`, `발급일`, `발급번호`, `가입내역`) were missing through the measured routing in all seven image conditions. Treat that as one shared classification/routing failure rather than five independent field-reader defects. Additional weakest field rankings, including CER tie breaks, are in the full report. Original alone achieves 29/38 exact fields and 4/5 correct types; monochrome achieves 33/38 and 4/5. These are highly correlated transformations of five layouts, not population estimates.

| Improvement candidate only | Evidence and next diagnostic |
|---|---|
| Investigate insurance title recognition and content routing | 0/7 image classifications despite independently verified source fields. Inspect recognized title tokens/order and separate overlap/template artifacts from classifier behavior on additional authored layouts. |
| Evaluate orientation handling | 90° loses every type and field. Compare orientation detection/correction on independent synthetic pages before proposing production changes. |
| Investigate table/coordinate stability under mild rotation and perspective | Most ±5° and phone types remain identifiable, while field accuracy drops sharply. Trace table header, column and bounded-value losses without changing rule thresholds. |
| Expand synthetic layouts, font and identity variants | A single source family cannot establish generalization. Include independent layouts, differing row counts and multi-page histories before comparing future improvements. |
| Separate operational quality and recognition calibration | Every normal confirmed reupload is the quality code at low resolution. Keep that policy outcome separate from low OCR confidence/manual review. |
| Measure stable deployment throughput | This local CPU run includes cold initialization on its first page; the retained final run started after all regression checks ended. Repeat under an isolated, pinned environment with warm/cold timing before capacity planning. |

None of these candidates was implemented. Real text-layer agreement mode was implemented and tested only with fabricated temporary PDFs; no real-document benchmark was run.
