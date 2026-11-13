# DocumentAI synthetic measurement

Seed: 20261113; repetitions per cell: 1; own OCR only.

NFC and Unicode-whitespace removal apply to CER only; field accuracy uses exact semantic values. Structured lists retain order. Insurance geometry/confidence metadata are excluded. Missing fields count as errors. Rates include failed attempts; NEEDS_REVIEW is neither PASS nor confirmed FAIL.

Normal means correct document content before image transformations. Low-resolution/phone rejection can be a valid quality-policy action. This small synthetic corpus is diagnostic, not a population accuracy estimate. Reference source preflight is separate from OCR measurement.

Timing includes image/PDF read, own OCR, extraction, file evidence and upload assessment; excludes generation and metrics. First measured case includes model initialization (cold start). Headline/type/condition timing uses normal-content pages only; all-attempt and defect times are stored separately in JSON. Rejected unreadable bytes are excluded from normal timing.

## Overall and document types

| Type | Normal n | Defect n | Field exact | CER | Type accuracy | False reject | False accept | Failed | Normal s/page |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 35 | 42 | 36.84% | 0.7122 | 65.71% | 14.29% (5/35) | 0.00% (0/42) | 0 | 1.3413 |
| resident_abstract | 7 | 9 | 55.10% | 0.4680 | 85.71% | 14.29% (1/7) | 0.00% (0/9) | 0 | 1.0444 |
| nhis_payment | 7 | 9 | 39.56% | 0.5691 | 85.71% | 14.29% (1/7) | 0.00% (0/9) | 0 | 2.1491 |
| nhis_qualification | 7 | 8 | 40.82% | 0.6231 | 85.71% | 14.29% (1/7) | 0.00% (0/8) | 0 | 1.0905 |
| nhis_acquisition_loss | 7 | 8 | 35.71% | 0.5918 | 71.43% | 14.29% (1/7) | 0.00% (0/8) | 0 | 1.0010 |
| insurance_4 | 7 | 8 | 0.00% | 1.0000 | 0.00% | 14.29% (1/7) | 0.00% (0/8) | 0 | 1.4214 |

## Complete type × condition matrix

| Type | Condition | n | Exact | CER | Type | Reupload FAIL | Status (PASS/review/FAIL) | Failed | s/page |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| resident_abstract | original | 1 | 100.00% | 0.0000 | 100.00% | 0 | 0/1/0 | 0 | 1.1984 |
| resident_abstract | monochrome | 1 | 100.00% | 0.0000 | 100.00% | 0 | 0/1/0 | 0 | 1.0101 |
| resident_abstract | rotate_plus5 | 1 | 57.14% | 0.4138 | 100.00% | 0 | 0/1/0 | 0 | 1.0843 |
| resident_abstract | rotate_minus5 | 1 | 28.57% | 0.7586 | 100.00% | 0 | 0/1/0 | 0 | 1.2455 |
| resident_abstract | rotate90 | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.0127 |
| resident_abstract | low_resolution | 1 | 71.43% | 0.3448 | 100.00% | 1 | 0/0/1 | 0 | 0.5394 |
| resident_abstract | phone | 1 | 28.57% | 0.7586 | 100.00% | 0 | 0/1/0 | 0 | 1.2208 |
| nhis_payment | original | 1 | 69.23% | 0.7368 | 100.00% | 0 | 0/1/0 | 0 | 2.1602 |
| nhis_payment | monochrome | 1 | 100.00% | 0.0000 | 100.00% | 0 | 1/0/0 | 0 | 2.1346 |
| nhis_payment | rotate_plus5 | 1 | 7.69% | 0.4901 | 100.00% | 0 | 0/1/0 | 0 | 2.2735 |
| nhis_payment | rotate_minus5 | 1 | 23.08% | 0.5099 | 100.00% | 0 | 0/1/0 | 0 | 2.2695 |
| nhis_payment | rotate90 | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 2.0117 |
| nhis_payment | low_resolution | 1 | 69.23% | 0.7368 | 100.00% | 1 | 0/0/1 | 0 | 1.6810 |
| nhis_payment | phone | 1 | 7.69% | 0.5099 | 100.00% | 0 | 0/1/0 | 0 | 2.5133 |
| nhis_qualification | original | 1 | 100.00% | 0.0000 | 100.00% | 0 | 1/0/0 | 0 | 1.0995 |
| nhis_qualification | monochrome | 1 | 100.00% | 0.0000 | 100.00% | 0 | 1/0/0 | 0 | 1.0879 |
| nhis_qualification | rotate_plus5 | 1 | 14.29% | 0.8936 | 100.00% | 0 | 0/1/0 | 0 | 1.1629 |
| nhis_qualification | rotate_minus5 | 1 | 28.57% | 0.7872 | 100.00% | 0 | 0/1/0 | 0 | 1.1475 |
| nhis_qualification | rotate90 | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.1438 |
| nhis_qualification | low_resolution | 1 | 28.57% | 0.7872 | 100.00% | 1 | 0/0/1 | 0 | 0.6487 |
| nhis_qualification | phone | 1 | 14.29% | 0.8936 | 100.00% | 0 | 0/1/0 | 0 | 1.3433 |
| nhis_acquisition_loss | original | 1 | 100.00% | 0.0000 | 100.00% | 0 | 1/0/0 | 0 | 0.9952 |
| nhis_acquisition_loss | monochrome | 1 | 100.00% | 0.0000 | 100.00% | 0 | 1/0/0 | 0 | 0.9934 |
| nhis_acquisition_loss | rotate_plus5 | 1 | 16.67% | 0.7143 | 100.00% | 0 | 0/1/0 | 0 | 1.0795 |
| nhis_acquisition_loss | rotate_minus5 | 1 | 16.67% | 0.7143 | 100.00% | 0 | 0/1/0 | 0 | 1.0832 |
| nhis_acquisition_loss | rotate90 | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.0113 |
| nhis_acquisition_loss | low_resolution | 1 | 0.00% | 1.0000 | 0.00% | 1 | 0/0/1 | 0 | 0.5671 |
| nhis_acquisition_loss | phone | 1 | 16.67% | 0.7143 | 100.00% | 0 | 0/1/0 | 0 | 1.2773 |
| insurance_4 | original | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.4135 |
| insurance_4 | monochrome | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.4176 |
| insurance_4 | rotate_plus5 | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.4946 |
| insurance_4 | rotate_minus5 | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.4898 |
| insurance_4 | rotate90 | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.4723 |
| insurance_4 | low_resolution | 1 | 0.00% | 1.0000 | 0.00% | 1 | 0/0/1 | 0 | 0.9508 |
| insurance_4 | phone | 1 | 0.00% | 1.0000 | 0.00% | 0 | 0/1/0 | 0 | 1.7110 |

## Fields by document

| Type | Field | Correct/n | Exact | CER |
|---|---|---:|---:|---:|
| resident_abstract | name | 3/7 | 42.86% | 0.5714 |
| resident_abstract | birth_date | 4/7 | 57.14% | 0.4286 |
| resident_abstract | issue_date | 4/7 | 57.14% | 0.4286 |
| resident_abstract | applicant_name | 6/7 | 85.71% | 0.1429 |
| resident_abstract | applicant_birth_date | 6/7 | 85.71% | 0.1429 |
| resident_abstract | current_address | 2/7 | 28.57% | 0.7143 |
| resident_abstract | address_history_count | 2/7 | 28.57% | 0.7143 |
| nhis_payment | 성명 | 3/7 | 42.86% | 0.5714 |
| nhis_payment | 생년월일 | 3/7 | 42.86% | 0.4571 |
| nhis_payment | 발급일 | 6/7 | 85.71% | 0.1429 |
| nhis_payment | 사업장명칭 | 3/7 | 42.86% | 0.0000 |
| nhis_payment | 납부자번호 | 3/7 | 42.86% | 0.5714 |
| nhis_payment | 문서확인번호 | 3/7 | 42.86% | 0.5714 |
| nhis_payment | 용도구분 | 3/7 | 42.86% | 0.5714 |
| nhis_payment | 조회기간 | 3/7 | 42.86% | 0.5714 |
| nhis_payment | 월별고지금액 | 1/7 | 14.29% | 0.5937 |
| nhis_payment | 월별장기요양보험료 | 1/7 | 14.29% | 0.5889 |
| nhis_payment | 건강보험료 | 2/7 | 28.57% | 0.7143 |
| nhis_payment | 장기요양보험료 | 2/7 | 28.57% | 0.5000 |
| nhis_payment | 납부총액 | 3/7 | 42.86% | 0.5714 |
| nhis_qualification | 성명 | 2/7 | 28.57% | 0.7143 |
| nhis_qualification | 생년월일 | 2/7 | 28.57% | 0.7143 |
| nhis_qualification | 발급일 | 6/7 | 85.71% | 0.1429 |
| nhis_qualification | 가구원수 | 2/7 | 28.57% | 0.7143 |
| nhis_qualification | 가구원목록 | 2/7 | 28.57% | 0.7143 |
| nhis_qualification | 자격확인요청일 | 4/7 | 57.14% | 0.4286 |
| nhis_qualification | 사업장관리번호 | 2/7 | 28.57% | 0.7143 |
| nhis_acquisition_loss | 성명 | 2/7 | 28.57% | 0.7143 |
| nhis_acquisition_loss | 생년월일 | 2/7 | 28.57% | 0.7143 |
| nhis_acquisition_loss | 발급일 | 5/7 | 71.43% | 0.2857 |
| nhis_acquisition_loss | 가입구분 | 2/7 | 28.57% | 0.7143 |
| nhis_acquisition_loss | 취득일 | 2/7 | 28.57% | 0.7143 |
| nhis_acquisition_loss | 변동내역 | 2/7 | 28.57% | 0.5714 |
| insurance_4 | 성명 | 0/7 | 0.00% | 1.0000 |
| insurance_4 | 생년월일 | 0/7 | 0.00% | 1.0000 |
| insurance_4 | 발급일 | 0/7 | 0.00% | 1.0000 |
| insurance_4 | 발급번호 | 0/7 | 0.00% | 1.0000 |
| insurance_4 | 가입내역 | 0/7 | 0.00% | 1.0000 |

## Confirmed normal reupload FAIL codes

| Code | Documents |
|---|---:|
| DOCUMENT_ISSUED_AFTER_APPLICATION | 0 |
| DOCUMENT_ISSUED_TOO_EARLY | 0 |
| IDENTITY_MISMATCH | 0 |
| IMAGE_RESOLUTION_TOO_LOW | 0 |
| LOW_IMAGE_QUALITY | 5 |
| MISSING_ADDRESS_DATES | 0 |
| MISSING_BILLING_MONTHS | 0 |
| PAGES_INCOMPLETE | 0 |
| UNREADABLE_FILE | 0 |
| WRONG_DOCUMENT_TYPE | 0 |

Code totals may exceed document totals. Only code severity FAIL with final document FAIL counts.

## Defects

| Defect | n | PASS (false accept) | NEEDS_REVIEW | FAIL | Execution errors |
|---|---:|---:|---:|---:|---:|
| identity_mismatch | 5 | 0 | 4 | 1 | 0 |
| issued_after_application | 5 | 0 | 3 | 2 | 0 |
| issued_too_early | 5 | 0 | 2 | 3 | 0 |
| low_image_quality | 5 | 0 | 5 | 0 | 0 |
| low_resolution | 5 | 0 | 0 | 5 | 0 |
| missing_address_dates | 1 | 0 | 1 | 0 | 0 |
| missing_billing_months | 1 | 0 | 1 | 0 | 0 |
| pages_incomplete | 5 | 0 | 4 | 1 | 0 |
| unreadable_file | 5 | 0 | 0 | 5 | 0 |
| wrong_document_type | 5 | 0 | 1 | 4 | 0 |

A zero false-accept rate can reflect extensive manual review. It does not establish successful automatic defect recognition.

## Reupload codes by normal type × condition

| Type | Condition | Code | Documents |
|---|---|---|---:|
| resident_abstract | low_resolution | LOW_IMAGE_QUALITY | 1 |
| nhis_payment | low_resolution | LOW_IMAGE_QUALITY | 1 |
| nhis_qualification | low_resolution | LOW_IMAGE_QUALITY | 1 |
| nhis_acquisition_loss | low_resolution | LOW_IMAGE_QUALITY | 1 |
| insurance_4 | low_resolution | LOW_IMAGE_QUALITY | 1 |

Unlisted type/condition/code combinations have zero occurrences.

## Fields by type × condition

| Type | Condition | Field | Correct/n | Exact | CER |
|---|---|---|---:|---:|---:|
| resident_abstract | original | name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | original | birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | original | issue_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | original | applicant_name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | original | applicant_birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | original | current_address | 1/1 | 100.00% | 0.0000 |
| resident_abstract | original | address_history_count | 1/1 | 100.00% | 0.0000 |
| resident_abstract | monochrome | name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | monochrome | birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | monochrome | issue_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | monochrome | applicant_name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | monochrome | applicant_birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | monochrome | current_address | 1/1 | 100.00% | 0.0000 |
| resident_abstract | monochrome | address_history_count | 1/1 | 100.00% | 0.0000 |
| resident_abstract | rotate_plus5 | name | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate_plus5 | birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | rotate_plus5 | issue_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | rotate_plus5 | applicant_name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | rotate_plus5 | applicant_birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | rotate_plus5 | current_address | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate_plus5 | address_history_count | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate_minus5 | name | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate_minus5 | birth_date | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate_minus5 | issue_date | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate_minus5 | applicant_name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | rotate_minus5 | applicant_birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | rotate_minus5 | current_address | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate_minus5 | address_history_count | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate90 | name | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate90 | birth_date | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate90 | issue_date | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate90 | applicant_name | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate90 | applicant_birth_date | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate90 | current_address | 0/1 | 0.00% | 1.0000 |
| resident_abstract | rotate90 | address_history_count | 0/1 | 0.00% | 1.0000 |
| resident_abstract | low_resolution | name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | low_resolution | birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | low_resolution | issue_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | low_resolution | applicant_name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | low_resolution | applicant_birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | low_resolution | current_address | 0/1 | 0.00% | 1.0000 |
| resident_abstract | low_resolution | address_history_count | 0/1 | 0.00% | 1.0000 |
| resident_abstract | phone | name | 0/1 | 0.00% | 1.0000 |
| resident_abstract | phone | birth_date | 0/1 | 0.00% | 1.0000 |
| resident_abstract | phone | issue_date | 0/1 | 0.00% | 1.0000 |
| resident_abstract | phone | applicant_name | 1/1 | 100.00% | 0.0000 |
| resident_abstract | phone | applicant_birth_date | 1/1 | 100.00% | 0.0000 |
| resident_abstract | phone | current_address | 0/1 | 0.00% | 1.0000 |
| resident_abstract | phone | address_history_count | 0/1 | 0.00% | 1.0000 |
| nhis_payment | original | 성명 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 생년월일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 사업장명칭 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 납부자번호 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 문서확인번호 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 용도구분 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 조회기간 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | original | 월별고지금액 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | original | 월별장기요양보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | original | 건강보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | original | 장기요양보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | original | 납부총액 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 성명 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 생년월일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 사업장명칭 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 납부자번호 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 문서확인번호 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 용도구분 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 조회기간 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 월별고지금액 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 월별장기요양보험료 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 건강보험료 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 장기요양보험료 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | monochrome | 납부총액 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | rotate_plus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_plus5 | 생년월일 | 0/1 | 0.00% | 0.6000 |
| nhis_payment | rotate_plus5 | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | rotate_plus5 | 사업장명칭 | 0/1 | 0.00% | 0.0000 |
| nhis_payment | rotate_plus5 | 납부자번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_plus5 | 문서확인번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_plus5 | 용도구분 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_plus5 | 조회기간 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_plus5 | 월별고지금액 | 0/1 | 0.00% | 0.3486 |
| nhis_payment | rotate_plus5 | 월별장기요양보험료 | 0/1 | 0.00% | 0.3679 |
| nhis_payment | rotate_plus5 | 건강보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_plus5 | 장기요양보험료 | 0/1 | 0.00% | 0.2500 |
| nhis_payment | rotate_plus5 | 납부총액 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_minus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_minus5 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_minus5 | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | rotate_minus5 | 사업장명칭 | 0/1 | 0.00% | 0.0000 |
| nhis_payment | rotate_minus5 | 납부자번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_minus5 | 문서확인번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_minus5 | 용도구분 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_minus5 | 조회기간 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate_minus5 | 월별고지금액 | 0/1 | 0.00% | 0.4128 |
| nhis_payment | rotate_minus5 | 월별장기요양보험료 | 0/1 | 0.00% | 0.3774 |
| nhis_payment | rotate_minus5 | 건강보험료 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | rotate_minus5 | 장기요양보험료 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | rotate_minus5 | 납부총액 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 발급일 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 사업장명칭 | 0/1 | 0.00% | 0.0000 |
| nhis_payment | rotate90 | 납부자번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 문서확인번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 용도구분 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 조회기간 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 월별고지금액 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 월별장기요양보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 건강보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 장기요양보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | rotate90 | 납부총액 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | low_resolution | 성명 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 생년월일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 사업장명칭 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 납부자번호 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 문서확인번호 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 용도구분 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 조회기간 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | low_resolution | 월별고지금액 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | low_resolution | 월별장기요양보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | low_resolution | 건강보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | low_resolution | 장기요양보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | low_resolution | 납부총액 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | phone | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | phone | 생년월일 | 0/1 | 0.00% | 0.6000 |
| nhis_payment | phone | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_payment | phone | 사업장명칭 | 0/1 | 0.00% | 0.0000 |
| nhis_payment | phone | 납부자번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | phone | 문서확인번호 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | phone | 용도구분 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | phone | 조회기간 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | phone | 월별고지금액 | 0/1 | 0.00% | 0.3945 |
| nhis_payment | phone | 월별장기요양보험료 | 0/1 | 0.00% | 0.3774 |
| nhis_payment | phone | 건강보험료 | 0/1 | 0.00% | 1.0000 |
| nhis_payment | phone | 장기요양보험료 | 0/1 | 0.00% | 0.2500 |
| nhis_payment | phone | 납부총액 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | original | 성명 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | original | 생년월일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | original | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | original | 가구원수 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | original | 가구원목록 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | original | 자격확인요청일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | original | 사업장관리번호 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | monochrome | 성명 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | monochrome | 생년월일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | monochrome | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | monochrome | 가구원수 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | monochrome | 가구원목록 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | monochrome | 자격확인요청일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | monochrome | 사업장관리번호 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | rotate_plus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_plus5 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_plus5 | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | rotate_plus5 | 가구원수 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_plus5 | 가구원목록 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_plus5 | 자격확인요청일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_plus5 | 사업장관리번호 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_minus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_minus5 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_minus5 | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | rotate_minus5 | 가구원수 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_minus5 | 가구원목록 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate_minus5 | 자격확인요청일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | rotate_minus5 | 사업장관리번호 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate90 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate90 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate90 | 발급일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate90 | 가구원수 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate90 | 가구원목록 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate90 | 자격확인요청일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | rotate90 | 사업장관리번호 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | low_resolution | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | low_resolution | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | low_resolution | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | low_resolution | 가구원수 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | low_resolution | 가구원목록 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | low_resolution | 자격확인요청일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | low_resolution | 사업장관리번호 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | phone | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | phone | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | phone | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_qualification | phone | 가구원수 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | phone | 가구원목록 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | phone | 자격확인요청일 | 0/1 | 0.00% | 1.0000 |
| nhis_qualification | phone | 사업장관리번호 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | original | 성명 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | original | 생년월일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | original | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | original | 가입구분 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | original | 취득일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | original | 변동내역 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | monochrome | 성명 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | monochrome | 생년월일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | monochrome | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | monochrome | 가입구분 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | monochrome | 취득일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | monochrome | 변동내역 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | rotate_plus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_plus5 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_plus5 | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | rotate_plus5 | 가입구분 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_plus5 | 취득일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_plus5 | 변동내역 | 0/1 | 0.00% | 0.6667 |
| nhis_acquisition_loss | rotate_minus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_minus5 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_minus5 | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | rotate_minus5 | 가입구분 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_minus5 | 취득일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate_minus5 | 변동내역 | 0/1 | 0.00% | 0.6667 |
| nhis_acquisition_loss | rotate90 | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate90 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate90 | 발급일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate90 | 가입구분 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate90 | 취득일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | rotate90 | 변동내역 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | low_resolution | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | low_resolution | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | low_resolution | 발급일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | low_resolution | 가입구분 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | low_resolution | 취득일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | low_resolution | 변동내역 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | phone | 성명 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | phone | 생년월일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | phone | 발급일 | 1/1 | 100.00% | 0.0000 |
| nhis_acquisition_loss | phone | 가입구분 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | phone | 취득일 | 0/1 | 0.00% | 1.0000 |
| nhis_acquisition_loss | phone | 변동내역 | 0/1 | 0.00% | 0.6667 |
| insurance_4 | original | 성명 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | original | 생년월일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | original | 발급일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | original | 발급번호 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | original | 가입내역 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | monochrome | 성명 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | monochrome | 생년월일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | monochrome | 발급일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | monochrome | 발급번호 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | monochrome | 가입내역 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_plus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_plus5 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_plus5 | 발급일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_plus5 | 발급번호 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_plus5 | 가입내역 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_minus5 | 성명 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_minus5 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_minus5 | 발급일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_minus5 | 발급번호 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate_minus5 | 가입내역 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate90 | 성명 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate90 | 생년월일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate90 | 발급일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate90 | 발급번호 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | rotate90 | 가입내역 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | low_resolution | 성명 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | low_resolution | 생년월일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | low_resolution | 발급일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | low_resolution | 발급번호 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | low_resolution | 가입내역 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | phone | 성명 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | phone | 생년월일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | phone | 발급일 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | phone | 발급번호 | 0/1 | 0.00% | 1.0000 |
| insurance_4 | phone | 가입내역 | 0/1 | 0.00% | 1.0000 |

## Weakest diagnostic groups

### by_document

| Group | Field exact | CER | Type accuracy | n |
|---|---:|---:|---:|---:|
| insurance_4 | 0.00% | 1.0000 | 0.00% | 7 |
| nhis_acquisition_loss | 35.71% | 0.5918 | 71.43% | 7 |
| nhis_payment | 39.56% | 0.5691 | 85.71% | 7 |
| nhis_qualification | 40.82% | 0.6231 | 85.71% | 7 |
| resident_abstract | 55.10% | 0.4680 | 85.71% | 7 |

### by_condition

| Group | Field exact | CER | Type accuracy | n |
|---|---:|---:|---:|---:|
| rotate90 | 0.00% | 1.0000 | 0.00% | 5 |
| phone | 13.16% | 0.7517 | 80.00% | 5 |
| rotate_plus5 | 18.42% | 0.7168 | 80.00% | 5 |
| rotate_minus5 | 21.05% | 0.7383 | 80.00% | 5 |
| low_resolution | 42.11% | 0.8148 | 60.00% | 5 |

### Fields

| Type | Field | Correct/n | CER |
|---|---|---:|---:|
| insurance_4 | 가입내역 | 0/7 | 1.0000 |
| insurance_4 | 발급번호 | 0/7 | 1.0000 |
| insurance_4 | 발급일 | 0/7 | 1.0000 |
| insurance_4 | 생년월일 | 0/7 | 1.0000 |
| insurance_4 | 성명 | 0/7 | 1.0000 |
| nhis_payment | 월별고지금액 | 1/7 | 0.5937 |
| nhis_payment | 월별장기요양보험료 | 1/7 | 0.5889 |
| nhis_acquisition_loss | 가입구분 | 2/7 | 0.7143 |
| nhis_acquisition_loss | 생년월일 | 2/7 | 0.7143 |
| nhis_acquisition_loss | 성명 | 2/7 | 0.7143 |
| nhis_acquisition_loss | 취득일 | 2/7 | 0.7143 |
| nhis_payment | 건강보험료 | 2/7 | 0.7143 |
| nhis_qualification | 가구원목록 | 2/7 | 0.7143 |
| nhis_qualification | 가구원수 | 2/7 | 0.7143 |
| nhis_qualification | 사업장관리번호 | 2/7 | 0.7143 |

## Improvement candidates (not implemented)

- Investigate the lowest-ranked type/condition cells using further independent synthetic templates and fonts before drawing production conclusions.
- Separate orientation, title recognition and coordinate/table-layout losses through the reported classification and field metrics.
- Inspect semantic table fields with high CER and missing-field rates; test row/column completeness with additional authored layouts.
- Calibrate quality-policy reuploads separately from text-content mistakes, especially for intentionally small originals and phone photographs.
- Increase independent templates and sample diversity; report warm/cold timing and confidence intervals in a future evaluation.

No OCR, extractor or verdict logic was changed. Private-document mode was not executed on real documents.

## Run environment and repeat check

Final retained run: 2026-11-13, Darwin arm64, Python 3.14.6, ONNX Runtime 1.31.1, PyMuPDF 2.1, Pillow 13.0.0, NumPy 2.5.4 and OpenCV headless 4.14.0.94. Existing CPU sessions use two intra-op and one inter-op thread. The final run started after regression checks finished; the initial diagnostic run is excluded from every sample denominator. All 77 non-timing case results matched exactly between the two runs.
