# Stage 0 completion — 2026-11-15

Baseline source is current branch HEAD `2b4ab5949a2d7455a3da7da3ab0fd7c1f687e4d8`, identical to main. PR #7 is a comparison record, not the measured source. Existing tools, operating code, tests and fixtures were unchanged. All 782 recorded source-file hashes matched the isolated source after measurement.

The user removed two old data folders. The remaining seven folders were not accessed. All execution used a tracked-source isolation in `/tmp/own_adapter_work-67fp4sm5/`; only installed dependencies/models were linked. Results, prior numeric records/logs and reproduction materials are preserved under `/Users/zohijin/Desktop/own_adapter_runs/before/`.

## Regression gates

| Group | Required | Observed |
| --- | --- | --- |
| engine_v2 | 1748 passed / 3 skipped / 3 xfailed | Previous matching run reused; not rerun in this stage |
| backend | 1410 passed / 2 xfailed | Identical; exit 0 |
| scenarios | 18 modules / 1885 counted checks / 0 failures | Identical; all exits 0 |
| frontend | TypeScript / oxlint / Vite success | All exits 0 |

## Paired measurement

Existing generator/truth/metrics, samples 5, seed 20261113: 410 pairs / 820 paths / execution errors 0.

| Scope | Engine | False PASS | Confirmed false FAIL | REVIEW | PASS | FAIL |
| --- | --- | --- | --- | --- | --- | --- |
| Overall | own | 0/235 | 0/175 | 250 | 30 | 130 |
| Overall | reference | 15/235 | 0/175 | 250 | 60 | 100 |
| Payment | own | 0/50 | 0/35 | 60 | 0 | 25 |
| Payment | reference | 5/50 | 0/35 | 40 | 20 | 25 |

All three user-specified PR #7 checks match. Full rows, input/source fingerprints, stage/type/group/condition/field summaries and timing are retained in paired outputs.

## OCR baseline

The approved wrapper generated 111 PDFs / 114 pages without changing the existing generators. Both engines, clean/scan/phone: 106 eligible pages / 636 successful measurements, 0 execution errors, 0 empty OCR. Seven pages failed text-layer classification and one had a short text layer; these are explicit exclusions, not accuracy observations. All registered fields of measured types retain their original numerator/denominator and attribution populations. Unsupported generation paths and missing reference fields are not filled with invented values.

Thirteen actual classified types have measured groups. The authored INSURANCE_4 and ID_PHOTO_COPY inputs supplied no classified measurement groups; five types have no approved complete generator (ADMIN_INFO_CONSENT, LABOR_CONTRACT, FARM_BIZ_CERT, FISHERY_BIZ_CERT, BIZ_REG_CERT). The supplemental `ocr_field_coverage.json` explicitly includes all twenty registered types and every engine/variant/field, with zero attempts and null rates for unmeasured combinations. Generator labels are coverage metadata only and never force classification.

Legacy payment 50/50 has references for membership, billing months and issue date. Government payment 20/20 has billing-month and issue-date references; its extractor does not emit membership. The exact newly generated PDF bytes, relative selections, source hashes and generation/run commands are preserved as synthetic reproduction material.

## Disk measurements

The execution controller saved literal `df -h /` before/after each group, filesystem free bytes and workspace sizes. Peaks are five-second samples, not guaranteed instantaneous maxima. Free-space changes are not attributed exclusively to this run.

| Group | Seconds | Workspace before → after GiB | Sampled additional peak MiB |
| --- | ---: | ---: | ---: |
| backend | 81.688 | 0.011745 → 5.751595 | 5877.605 |
| scenarios | 68.006 | 5.751598 → 5.754185 | 311.496 |
| frontend | 2.470 | 5.754189 → 5.760700 | 6.668 |
| paired | 630.181 | 5.760700 → 5.760704 | 2.008 |
| OCR, including corpus generation | 572.543 | 0.121269 → 0.457378 | 344.176 |

Backend began above the required 15GiB free threshold. No ENOSPC occurred. After verified durable preservation, only this run's backend pytest directory (5.639GiB) was removed. Old workspaces and the seven protected data folders were untouched. Remaining current workspace cleanup is deferred until stage 1 artifacts are preserved.

Stage 0 gate passed; continue with the already authorized stage 1. No commit is authorized.
