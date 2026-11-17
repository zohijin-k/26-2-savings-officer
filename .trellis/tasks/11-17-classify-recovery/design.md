# 실서류 서식 분류 회복 진단 — 설계

운영 코드는 바꾸지 않는다. 새 도구 하나 `engine_v2/tools/classify_recovery_diag.py`와 시험 `engine_v2/tests/test_classify_recovery_diag.py`,
스펙 문서 `.trellis/spec/backend/classify-recovery-diag.md`를 더한다. 실행 틀(OUT_EXISTS, 외부 OCR 끄기, 네트워크 보호, 문서 키, 슬롯 고르기, 사유 코드 거르기)은
`doc_timing`·`batch_assess`의 함수를 그대로 불러 쓴다(`doc_timing.inspect`, `document_key`, `requirement`, `reason_codes`, `batch.guarded`, `batch.inventory`).

## 1. 하위 명령

| 명령 | 다시 판독 | 입력 | 출력 |
| --- | --- | --- | --- |
| `crosstab` | 없음 | `--timing <RUN_A>/rows.jsonl --scan <RUN_SCAN>/results.jsonl` | 화면에만 표 (숫자·코드) |
| `run` | 운영 판독을 한 번 다시 함 | `--root <HUB_ROOT> --out <OUT>` (선택: `--timing <RUN_A>/rows.jsonl`, `--forms`, `--limit`) | `<OUT>/run.json`, `<OUT>/rows.jsonl`(키+코드), `<OUT>/summary.txt` (화면에도) |

`--out`이 있으면 OUT_EXISTS로 멈춘다. 이어 하기 없음. 오류는 고정 코드 하나만 찍는다(doc_timing과 같은 ERROR 코드 집합).

## 2. crosstab (나-3, 다시 실행 없음)

- doc_timing 행은 `doc_timing.validate_row`, batch 행은 `batch_assess.load_rows`로 형식을 확인한다. 형식이 틀리면 INPUT_INVALID.
- doc_timing은 `phase == "measure"` 행 중 문서마다 반복 번호가 가장 작은 행 하나를 쓴다(건너뛴 행 `phase == "skipped"`는 따로 센다).
- 대응: batch `id`(루트 기준 상대경로)의 `doc_timing.document_key(id)`와 doc_timing `key`가 같으면 같은 문서. 두 실행의 루트가 같아야 맞는다.
  doc_timing은 PDF만 재므로 batch 쪽은 확장자 `.pdf` 행만 대응 후보로 센다(확장자 외 이름은 보지 않는다).
- 출력 줄:
  - `MATCH timing_docs scan_pdf_docs matched timing_only scan_only` — matched가 0이면 `WARNING ROOT_MISMATCH`.
  - `CROSS a_form scan_type n` (대응된 문서, 0이 아닌 칸만) + `CROSS_TOTAL`.
  - `TIER tier n` (A 전체), `XTIER tier text_layer later_text page_bin n` (A form X).
  - `XSCAN scan_type n`, `XSCAN_CODE engine_code n`, `XTEXTREF type n`(A-스캔 글자층 참조 판별, 없으면 NA) — A form X만.
  - `FALLBACK NOT_RECORDED` — 결과 행에 대체 사유가 없고, A 실행에서는 JBAI가 꺼져 대체 사유가 생기지도 않는다는 표시.

## 3. G1 후보 규칙 (승인 요청)

**넣는 자리:** `pdftext.classify_with_evidence(text)`의 결과가 None일 때만 추가로 본다. 기존 키워드가 하나라도 맞으면 결과는 그대로다.
그래서 이미 판별된 서식은 같은 입력에서 바뀌지 않는다. 다른 판별 함수(좌표 대체, 추출기 내부 인식)는 건드리지 않는다.

| 후보 | 규칙 (공백 제거한 판별 입력에서) | 쓰임 |
| --- | --- | --- |
| **N (권장)** | `4대사회보험확인용가입자가입내역확인서`를 포함 | 운영 반영 후보. 합성에서 확인한 끼어든 용도 표시 하나만 허용 |
| W (비교) | `4대사회보험` + 한글 2~3자 + `용` + `가입자가입내역확인서` | 다른 용도 표시(예: 제출용)가 실서류에 있는지 보는 비교용 |
| E (비교) | `4대사회보험`과 `가입자가입내역확인서`가 둘 다 있음 (순서·거리 무관) | 4대보험 추출기 자체 인식(insurance_4.py:106-107)과 같은 범위. 가장 넓음 |

근거 문구는 운영 문구 형식을 따르되 그림자 평가에서는 저장·출력하지 않는다. 파일 이름은 보지 않는다.

**그림자 평가 방법(run):**
1. 운영 `read_document(path, None)`를 그대로 한 번 돌린다(기준). 이때 `classify_with_evidence` 호출의 입력과 결과를 문서 하나 동안만 메모리에 둔다(저장하지 않음).
2. 결과가 None이었던 입력에 후보가 걸린 문서만, `pdftext.classify_with_evidence`를 후보 판별로 바꿔 끼운 채 다시 `read_document`를 돌린다(OCR 결과는 문서 안 캐시로 재사용).
   판독은 결정적이므로, 기준 판독에서 None을 낸 판별 입력에 후보가 걸리지 않으면 바꿔 끼워도 첫 차이가 생기지 않는다 → 다시 돌리지 않고 기준과 같다고 센다.
3. 바뀐 문서는 후보 서식으로 슬롯을 골라 `assess_upload`까지 돌려 판정 분포를 센다(운영 판정 함수 그대로).
4. 출력: `G1 cand INS4_BASELINE INS4_CHANGED X_TO_INS4 OTHER_TO_INS4 FIRED_DOCS`, `G1_TRANSITION cand before after n`(바뀐 칸만), `G1_DECISION cand decision n`(바뀐 문서).

운영 반영(다-4)은 진의 결과를 본 뒤 별도 승인으로 하며, 이번 작업 커밋에는 넣지 않는다.

## 4. run의 판독 단계 기록 (나-3)

문서마다 doc_timing의 사전 검사(`inspect`: 암호·열기 오류·쪽 수·글자층 등급)를 먼저 한다. 그 뒤 위임 전용 감싸개(인자·결과·예외를 그대로 넘김)를 설치하고
운영 `read_document`를 부른다. 감싸개 대상: `LocalOcr.read`, `localocr._tier2_can_read`, `pdftext._read_pdf`, `engine._load_pages`, `preprocess.preprocess`,
`pipeline.ocr.ENGINES["own"]`(문서 안 OCR 캐시 겸용), `pdftext.classify_with_evidence`, `pdftext.classify_pages_with_evidence`, `file_evidence.independent_page_markers`, `localocr._generic`.
LocalOcr 안에서 일어난 사건 순서로 나간 자리를 정한다.

| 코드 | 뜻 (localocr.py 행) |
| --- | --- |
| L_RESULT | LocalOcr가 결과를 냄 |
| T_READ_NONE | 글자층 길, `_read_pdf` None (684-686) |
| T_TIER2_FORM | 글자층 길, 첫 쪽 판별이 PdfText 담당 서식 (688-690) |
| T_QUAL_NOT_NOTICE | 글자층 길, 통지형 아닌 자격확인서 (691-697) |
| T_LOAD_ERROR | 글자층 길, 쪽 읽기 오류 (720-721) |
| T_RECLASS_NONE | 글자층 길, 모든 쪽 다시 판별도 실패 (722-730) |
| T_RECLASS_DISCARD | 글자층 길, 모든 쪽 다시 판별로 서식을 찾았으나 일용·초본·등본이 아니라 버림 (729-730). 찾은 서식 코드를 함께 센다 |
| I_PREPROCESS_ERROR | 그림 길, 전처리 ValueError (762-765) |
| I_TEXT_PAGE | 그림 길, 글자 50자 이상 쪽 있음 (766-767) |
| I_OCR_ERROR | 그림 길, OCR 오류 (771-773) |
| I_UNCLASSIFIED | 그림 길, 판별 실패·쪽 표시 없음 (777-784) |
| I_UNCLASSIFIED_MARKERS | 그림 길, 판별 실패·쪽 표시 있음 → 서식 없는 결과 (785-791) |
| I_GENERIC_NONE | 그림 길, `_generic`이 None (841) |
| L_EXCEPTION_<종류> | LocalOcr 예외(ValueError/RuntimeError/MemoryError/OTHER). 예외 문장은 읽지 않는다 |

A form X 문서에만 더 기록한다(값 없는 코드):
- `ocr_chars`: LocalOcr 안 OCR 글자 수 구간 (C0 / C1_99 / C100_499 / C500P / NA).
- `first_page_chars`: 첫 쪽 글자층 글자 수 구간 (C0 / C1_49 / C50P).
- 구조(첫 쪽 기준, 그리고 어느 쪽이든 해당하면 ANY): 가장 큰 덮는 그림 종류 MAIN_NONE/RGB/GRAY/CMYK/STENCIL/SMASK/OTHER, 덮는 그림 수 L0/L1/L2P,
  그림 DPI 구간 D_LT150/D150_199/D200_299/D300P/NA, 쪽 회전 R0/R90/R180/R270.
- `scan_type`: A-스캔과 같은 방식(`batch_assess._inspect` 300dpi 렌더링 + `batch_assess._engine` own)으로 판별한 서식. A-스캔 결과를 다시 만든 것이다.
- `text_all_type`: 모든 쪽 글자층을 이어 `classify_with_evidence`한 서식 (글자층이 없으면 NA).

**예외 종류(추가):** `LocalOcr.read`와 `PdfTextOcr.read`를 감싼 위임 감싸개가 예외를 그대로 다시 던지기 전에 예외 클래스 이름만 적는다
(`[A-Za-z_][A-Za-z0-9_]{0,63}`에 맞을 때만, 아니면 OTHER). 전처리 오류는 `preprocess` 감싸개에서 같은 방식으로 클래스 이름을 적는다. 예외 문장은 읽지 않는다.

**원인 코드(추가, A form X 문서마다 하나):**

| 원인 코드 | 조건 (위에서부터 처음 맞는 것) |
| --- | --- |
| EXCEPTION | LocalOcr 또는 PdfText에서 예외 (클래스 이름 함께 셈) |
| PREPROCESS_ERROR | I_PREPROCESS_ERROR (클래스 이름 함께 셈) |
| FIRST_IMAGE_LATER_TEXT | I_TEXT_PAGE |
| FEW_CHARS_DISCARD | T_RECLASS_DISCARD이고 첫 쪽 글자 1~49자 |
| TEXT_RECLASS_DISCARD | T_RECLASS_DISCARD이고 첫 쪽 글자 50자 이상 (첫 쪽 글자층 판별 실패, 뒤쪽에서 서식을 찾았지만 버림) |
| HIDDEN_TEXT_LAYER | 글자층 길로 끝났고(tier pdftext 또는 T_*), 첫 쪽 글자 50자 이상, 모든 쪽 글자층 판별 X, 첫 쪽에 쪽을 덮는 그림이 있음 |
| BACKGROUND_ONLY | 그림 길 판별 실패(I_UNCLASSIFIED*)이고 어느 쪽이든 덮는 그림 2개 이상 또는 가장 큰 그림에 SMask |
| OCR_ERROR | I_OCR_ERROR |
| OCR_EMPTY | 그림 길 판별 실패, OCR 글자 0, 위 구조 아님 |
| OCR_NO_KEYWORD | 그림 길 판별 실패, OCR 글자 있음 |
| TEXT_NO_KEYWORD | 글자층 길로 끝났고 위에 해당 없음 (글자층에 서식 단서 없음) |
| OTHER | 그 밖 |

출력 줄: `XCAUSE cause n`, `XCAUSE_SCAN cause scan_found n`(A-스캔 방식으로는 서식을 찾는지), `XEXC where class n`.

출력 줄: `COUNTS`, `BASELINE_VS_TIMING matched agree disagree`(`--timing`이 있을 때, 같은 운영 경로이므로 서식이 같아야 함), `FORM form n`, `TIER tier n`,
`XEXIT exit n`, `XRECLASS type n`, `XOCR bin n`, `XSTRUCT main layers dpi rot n`, `XSCAN exit scan_found n`, `XTEXT text_all_type n`.

## 5. 동의서 표시 단계 (라, 커밋 3)

기준 서식이 ADMIN_INFO_CONSENT인 문서만. 운영 `admin_consent_scan`과 같은 그림(원본 서식5 가로 1200px, 스캔 첫 쪽 가로 1200px → 원본 크기로 늘임)을 만든다.

| 단계 | 코드 |
| --- | --- |
| 서식 좌표 | SPEC_OK / SPEC_UNAVAILABLE |
| 스캔 열기 | LOAD_OK / LOAD_ERROR |
| 쪽 수 | P1 / P2P |
| 제목 쪽 | TITLE_FIRST / TITLE_LATER / TITLE_NONE (판독 중 잡은 쪽별 글자에서 `행정정보공동이용`이 처음 나온 쪽) |
| 비율 | A_LE_2 / A_2_5 / A_GT_5 (스캔과 원본의 세로/가로 비율 차이 %) |
| 위치 어긋남 | S_LE_3 / S_3_10 / S_GT_10 (pt, 위상 상관으로 구한 평행 이동 크기), 상관 세기 PEAK_STRONG / PEAK_WEAK |
| 표시(운영 그대로) | MARK_NONE / MARK_AGREE / MARK_DISAGREE / MARK_BOTH, 칸별 비율 구간 R_LT1 / R1_3_5 / R_GE3_5 (%) |
| 표시(위치 맞춤 그림자) | ALIGNED_NONE / ALIGNED_AGREE / ALIGNED_DISAGREE / ALIGNED_BOTH (같은 칸을 구한 이동만큼 옮겨 다시 셈) |
| 서명 | SIGN_O / SIGN_X, ALIGNED_SIGN_O / ALIGNED_SIGN_X |
| 운영과 같은가 | PROD_MATCH_O / PROD_MATCH_X (운영 결과 `동의여부`와 다시 센 표시가 같은지) |
| 화질 | Q10 / Q09 / Q07 / Q05 / Q_OTHER (`objective_image_quality`), 판정과 LOW_IMAGE_QUALITY 심각도 |

출력 줄: `CONSENT stage code n` 단계별, `CONSENT_MARK prod aligned n`, `CONSENT_DECISION mark quality decision n`.

## 6. 납부확인서 월별 표 단계 (마, 커밋 3)

기준 서식이 NHIS_PAYMENT인 문서만. 판독 중 `nhis_payment.extract`에 들어간 쪽(위임 감싸개로 잡음, 문서 하나 동안만 메모리)과 결과 검증 이름을 쓴다.

| 항목 | 코드 |
| --- | --- |
| 판독기 | GOV(8열 정부 서식) / LEGACY |
| 첫 실패 단계 | HEADER / COLUMN / ROW / FORMAT / ARITH / TABLE_OK — 검증 이름 묶음: HEADER = payment_group_headers·payment_component_headers(GOV) 또는 월 머리글·고지금액 머리글 없음(LEGACY), COLUMN = payment_columns, ROW = monthly_rows_found·months_continuous·payment_sum_row, FORMAT = monthly_amounts_numeric, ARITH = monthly_total_matches·paid_total_matches |
| 머리글 세부(GOV) | HEADER_BAND_CUT (운영 띠 기준 `y0 > 묶음 아래`로는 열 제목이 안 맞고, 글자 중심 기준 `cy > 묶음 아래`로는 맞음) / HEADER_CLUSTERS_LT9 / HEADER_CLUSTERS_GT9 / HEADER_LABEL_MISMATCH |
| 운영 사유 | PAGING_UNCERTAIN O/X, MISSING_BILLING_MONTHS 심각도(FAIL/NEEDS_REVIEW/X), PAGES_INCOMPLETE O/X |
| 쪽수 표시 | `payment_paging.assess` 상태 COMPLETE/INCOMPLETE/NOT_REQUIRED/UNCERTAIN/ABSENT, fallback_allowed O/X |
| 완결성 | period_status, printed_total_observed, arithmetic_complete, issue_information_read 각 O/X/NA, 조회기간 상태 READABLE/OTHER/ABSENT, amounts_certain O/X/NA |

출력 줄: `PAYMENT route stage detail n`, `PAYMENT_REASON reason stage n`, `PAYMENT_PAGING state fallback n`, `PAYMENT_COMPLETE key value n`.
값(금액·월·이름)은 읽어도 메모리에서만 쓰고, 출력과 행에는 코드만 남긴다.

## 6-1. 커밋 3 그림자 후보 (운영 불변)

| 후보 | 끼우는 방법 | 실서류 출력 | 합성 출력 |
| --- | --- | --- | --- |
| **P1** 납부 머리글 띠 여유 m ∈ {0.1, 0.2, 0.3} (쪽 높이 %p) | `nhis_payment_gov._header_columns`를 위임 감싸개로 감싸, `expected == GROUPS`로 불려 결과가 있을 때만 묶음 머리글 단어의 사본을 `y1 - m`으로 돌려준다. 그러면 `group_bottom`이 m만큼 올라가 열 머리글 띠 조건이 `y0 > 묶음 아래 - m`이 된다. 묶음 머리글 단어의 x·신뢰도는 같아 다른 검사는 그대로다 | 기준 NHIS_PAYMENT 문서마다 OCR 캐시로 다시 판독·판정: `P1 m PAGING_GONE PAGING_NEW BILLING_GONE BILLING_NEW`, `P1_DECISION m before after n` | 발표용·검증 세트 G2 전후, 410쌍(own·참조 잘못된 통과, 바뀐 행) |
| **C1** 동의서 화질 재업로드 완화 | 판정 때 `doc_check.ESSENTIAL_FIELD_UNREADABLE_CODES`에서 ADMIN_CONSENT_MARK_UNREADABLE·ADMIN_CONSENT_SIGNATURE_UNREADABLE을 뺀 집합으로 `patch.object`. 그러면 "150dpi 미만 + 표시·서명 못 읽음"만으로는 FAIL이 되지 않고 NEEDS_REVIEW. 두 코드는 동의서에서만 나온다 | 기준 ADMIN_INFO_CONSENT 문서: `C1 before after n`, `C1 FAIL_TO_REVIEW n` | 합성 저해상도 동의서 전후 |
| **위치 맞춤** (5절 ALIGNED) | 도구 안에서만 계산 | 5절 | 합성 서식5: 표시 없음(이동·확대·흐림·잡음) 변형에서 표시 있음으로 읽은 수(잘못된 통과 방향), 표시 있음 변형에서 맞게 읽은 수 |

P1·C1·위치 맞춤은 진의 실서류 결과를 본 뒤 별도 승인 없이는 운영에 넣지 않는다.

## 7. 결과 행 형식 (`<OUT>/rows.jsonl`, schema 1)

`key`(16자리), `code`(NONE / ENCRYPTED / OPEN_ERROR / EMPTY_DOCUMENT / PROCESSING_ERROR / GUARD_BLOCKED), `form`, `tier`, `decision`, `reasons`(doc_timing 규칙),
`exit`, `trace`(코드 사전), `g1`(후보별 서식), `consent`·`payment`(커밋 3, 해당 문서만). 모든 값은 고정 코드 집합에서만 오며 `validate_row`로 확인한다.
화면·summary.txt에는 키도 찍지 않는다.

## 8. 합성 G1·G2 전후 (다-3)

`documentai_staged.measure_stage`를 발표용(`sources(0..4)`, seed 20261113)·검증(`sources(5..9)`, seed 20261117) 세트의 original 조건 25건씩에 own으로 돌린다.
original 그림은 seed와 무관하다(11-17-speed-baseline research/validation-set.md). 전: 운영 그대로. 후: 도구의 후보 N 판별을 `patch.object`로 끼운 채 같은 함수.
G1 = 종류 맞힌 수 ÷ 25, G2 = 맞힌 핵심 항목 ÷ 추출기가 불린 핵심 항목 (+ 전체 작성 항목 기준). 실행 스크립트는 작업 공간에 두고 커밋하지 않는다.

## 9. 시험 (합성만, 빠른 가짜 OCR)

- 가짜 OCR: `ENGINES["own"]`을 그림과 무관하게 고정 단어(서식 제목 포함)를 돌려주는 함수로 바꿔 빠르게 돌린다. 실제 own으로 한 재현은 작업 보고(research)에 둔다.
- 감싼 것/안 감싼 것의 `read_document` 결과(서식, tier, 필드, 신뢰도) 같음.
- 나-2 조건 PDF(숨은 글자층, 첫 쪽 1~49자, 첫 쪽 그림+뒤쪽 글자층, 흑백 마스크, 투명 배경)마다 기대한 나간 자리 코드.
- 후보 N/W/E: 기존 키워드가 맞는 입력에서 결과 불변, 합성 4대보험 제목 입력에서 INSURANCE_4, 무관한 입력에서 None. 운영 `pdftext.classify_with_evidence`는 실행 뒤에도 원래 함수.
- crosstab: 합성 rows/results로 대응·교차표, 루트 불일치 경고, 형식 오류 거부.
- 출력에 경로·파일 이름·키가 없음, OUT_EXISTS.
- (커밋 3) 서식5 원본에 표시를 그린 합성 스캔(제자리 / 8pt 이동 / 표시 없음 / 둘 다)에서 단계 코드, 합성 납부확인서 단어에서 HEADER_BAND_CUT.

## 10. 되돌리기

모든 커밋은 새 파일 추가다. 되돌릴 때는 `git revert <hash>` (amend 금지).
