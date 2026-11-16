# 저장소 코드 조사 — 실행 없는 근거

2026-11-15 추적 소스와 추적된 작업 보고만 읽었다. 원본 서류·결과 폴더·기존 비추적 합성 입력·가림 덤프는 열지 않았다. 시험·생성기·OCR은 실행하지 않았다.

## 1단계 읽기 지도

| 경로 | 함수/구간 | 확인 항목 |
| --- | --- | --- |
| `engine_v2/pipeline/ocr/own.py` | `recognize` 114~136, `polygon_bbox`, `ctc_decode` | 검출 crop당 OcrWord 하나, bbox/confidence와 최종 정렬. 검출·인식·가중치 변경 금지. |
| `engine_v2/pipeline/ocr/__init__.py` | `OcrWord`, `OcrResult.__post_init__`, `.text`, `_run_own`, `_run_applevision`, `run_ocr` | 마스킹, 15px 전체 text 정렬, AV 좌하단 정규화 → 좌상단 픽셀 좌표, 예외. |
| `engine_v2/pipeline/layout.py` | `normalize`, `group_lines`, `line_text`, `squash` | 페이지 %, 중심 y 묶음 tol=.6 / 최소 높이 .3%, x 순서와 공백. |
| `engine_v2/pipeline/preprocess.py` | `PageImage`, `TEXT_LAYER_MIN_CHARS`, PDF 처리 | 텍스트 선택, DPI, 회전 계약. |
| `engine_v2/pipeline/privacy.py` | `mask_words`, `mask_rrn`, `mask_data` | 변이 여부와 관찰 경계. 마스킹 유지. |
| `engine_v2/tools/ocr_baseline_runtime.py` | `reference_page` 50, `variant_image` 69, `recognize` 122, `extract` 195 | 참조 회전행렬, 300dpi, clean, 엔진/추출기 호출. |
| `engine_v2/tools/ocr_baseline_fields.py` | `normalize_words` 19, `prepare_pairs` 34, `compare_fields` 69 | 양쪽 NFKC+마스킹, 대칭 의미 비교. |
| `engine_v2/tools/ocr_baseline_settings.py` | SETTINGS | clean/scan/phone 설정·seed 재사용. |
| `engine_v2/tools/batch_assess.py` | FIELDS, `guarded`, `_memory_bridge`, `_read_pages` 531 이후 | 안전 선택·AV 메모리 브리지·실제 dispatch/후처리. |
| `demo/backend/ocr/pdftext.py` | `classify_pages_with_evidence` 118 | 본문 우선·좌표 fallback, expected 종류 oracle 금지. |
| `demo/backend/ocr/localocr.py` | `LocalOcr.read`, `_from_nhis` 363, `_from_resident`, `_identity_source_confidence` 292 | 운영 경로와 신뢰도 전달. |
| `engine_v2/extractors/nhis_payment.py` | `extract` 346, 가입구분 387~394, `_extract_monthly` 168, 고지월 430~437 | 본문/사업장 기반 가입구분, 머리글·월 행·기간·연도. |
| 같은 파일 | `_body_issue_date` 324~343, consensus 365~378 | 무라벨 날짜 fallback·머리글 일치. |
| `engine_v2/extractors/nhis_payment_gov.py` | `recognizes`, `_value_cells`, `_monthly_table`, `extract` 343 | 정부 여덟 열 분기; 발급일 432~435, 고지월 458, 가입구분 지원 여부 대조. |
| `engine_v2/extractors/nhis_common.py` | DATE_RE, COMPACT_DATE_RE, `page_lines`, `label_hits`, `header_for_page`, `_closing_issue_date`, `consensus` | 라벨 결합, 오른쪽/아래 후보, 날짜 문법. |
| `engine_v2/extractors/nhis_forms.py` | `confirmation_issue_date`, `label_hits`, `table_columns`, `column_cells` | 정부 날짜·칸 구조. |
| `engine_v2/extractors/format_text.py` | `normalize_format_text`, `normalize_numeric_text` | dash 변환과 숫자 칸 한정 보정. |
| `engine_v2/extractors/nhis_acquisition_loss.py`, `nhis_qualification.py`, `resident_abstract.py` | extract와 줄/날짜 helper | 보호 필드 및 다른 fields의 계약. |

실행 단계의 비교표는 단위, 좌표/정규화, 줄 묶음과 문턱, 줄·단어 순서, 한글 공백, Unicode/전각 문자, confidence, 회전의 8항목을 own/AV/공유 추출기별로 작성한다. 코드만으로 실서류 원인을 확정하지 않는다.

## 합성 생성 경로

| 종류 코드 | 기존 생성 경로 | 계획/한계 |
| --- | --- | --- |
| RESIDENT_ABSTRACT | `documentai_corpus_v2.sources` → `documentai_synth.pdf_bytes` | 5건. |
| NHIS_PAYMENT | 같은 경로; `p2_payment_samples.payment` + `p2_business_samples.text_pdf`; `make_synth_eval.documents` | v2 5건 + 정부형 20건 + legacy 50건. legacy는 이름 5 × 직장/지역 2 × 날짜/월 형식 5를 기존 Source 셀 입력으로 작성한다. 전문 생성기의 형식 옵션은 없고 범용 셀 렌더러를 사용한다. 정부형은 가입구분을 출력하지 않으므로 이 분모를 보충하지 못한다. |
| NHIS_QUALIFICATION | v2/`nhis_form_samples.qualification_cells` | 5건. |
| NHIS_ACQUISITION_LOSS | v2/`nhis_form_samples.acquisition_cells` | 5건. |
| INSURANCE_4 | v2/`nhis_form_samples.insurance_portal_cells` | 5건. 가입내역 개선은 하지 않음. |
| PAYMENT_RECEIPT | `make_job_docs.LAYOUTS`의 receipt 레이아웃 | 접수 전용을 뺀 6건, 취소/묶음 원래 결함 유지. |
| EXAM_CONFIRMATION | `make_job_docs.exam_admission` | 1건. |
| EXAM_TRANSCRIPT | `make_job_docs.exam_score` | 1건. |
| REGISTRATION_CONFIRMATION | `make_job_docs.registration_only` | 1건, receipt_registration_only. 생성 메타데이터를 분류 oracle로 쓰지 않음. |
| ADMISSION_TICKET | `make_job_docs.admission_ticket` | 1건. |
| INTERVIEW_CONFIRMATION | `make_job_docs.interview_official`, `interview_company` | 각 1건. 추적된 빈 서식·좌표·설치된 글꼴만 사용. |
| BIZ_REG_PROOF | `p2_business_samples.business` + 같은 모듈 text_pdf | 1건. |
| DAILY_WORK_RECORD | `fail_case_samples.daily` + 기존 `test_daily_work_record`/`test_daily_work_uploads`의 TextWriter 렌더 방식 | 1문서 4쪽. 순수 렌더만 사용, backend 시험 모듈 import 금지. 부록 참조 부재 분리. |
| RESIDENT_CERTIFICATE | `demo.fixtures.make_samples.make`의 등본 본문 | 간이 본문 1건. 완전한 양식 평가가 아님. |
| ID_PHOTO_COPY | 같은 모듈의 사진사본 본문 | 간이 본문 1건. 실제 사진 평가가 아니며 참조 부재를 노출. |

계획상 15종, 111 PDF / 114쪽이다. 실제 페이지 수가 다르면 생성 집계에서 보고한다. 종류를 파일명·생성기 메타데이터로 강제하지 않고 실제 분류 실패도 보인다.

다음 5종은 기존의 완성된 합성 글자층 서류 생성 경로를 확인하지 못하여 제외한다: `ADMIN_INFO_CONSENT`, `LABOR_CONTRACT`, `FARM_BIZ_CERT`, `FISHERY_BIZ_CERT`, `BIZ_REG_CERT`. 빈 서식·좌표·토큰 단위 시험만으로 채워진 합성 생성기가 있다고 보지 않는다. 새 생성기 개발은 범위에 넣지 않는다.

## 기존 보고와 시간 근거

- `.trellis/tasks/archive/2026-11/11-15-ocr-baseline/validation.md`: engine 1,748/3/3, backend 1,410/2, 시나리오 18개/1,885/0. 단일 합성 납부 PDF의 두 엔진 × 3변형 wall 16.69초, 처리 합계 15.15초. 초기 견적 약 17초/쪽.
- 114쪽 baseline은 약 1,938초(32분), 서류별 밀도·초기화·환경을 감안한 일정 예상 30~60분. legacy 50쪽 clean 두 엔진 진단은 약 5~10분부터 예상하고 실제 합성 pilot 후 갱신한다. 이번 측정값이 아니다.
- `.trellis/tasks/archive/2026-11/11-14-nhis-payment-stage2/paging-final-validation.md`: 410쌍/820경로/실행 오류 0. own 전체 오통과 0/235·오FAIL 0/175·REVIEW 250, 참조 전체 15/235·0/175·REVIEW 250; 납부 참조 오통과 5/50. PASS 수는 새 기준값 status_counts로 저장하며 잔여 건수로 추산하지 않는다.
- `demo/backend/tests/__init__.py`는 import 시 기존 samples 폴더를 탐색한다. 원 작업공간에서 backend 시험을 실행하지 않고 추적 소스 격리와 새 합성 파일로 실행한다.
