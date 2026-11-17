# 측정 정의 (숫자를 보기 전에 고정)

작성 2026-11-17, 기준 커밋 `345aa0f`. 이 문서의 정의는 개선 전(11/17)과 개선 후(11/22)에 **같은 그대로** 쓴다.
바꿀 때는 숫자를 보기 전에 바꾸고, 바꾼 날짜와 이유를 아래에 덧붙인다. 출력은 숫자·코드·O/X만 쓴다.

자리표시: `<REPO>` 저장소 위치, `<HUB_ROOT>` 실서류 PDF 폴더, `<RUN_DIR>` 실행 결과를 둘 폴더, `<WORK>` 합성 작업 공간.
상태 이름과 코드: **적합 = PASS**, **확인 필요 = NEEDS_REVIEW**, **재업로드 = FAIL**(확실한 미비, 신청자가 다시 올림), 미판정 = NOT_ASSESSED, 오류 = ERROR.

## A. 서류 단위 자동 판정 분포

A는 두 지표로 나눈다. 둘 다 PDF 파일 하나하나가 단위이며 신청 건 단위가 아니다.

- **A (주 지표)**: 실제 제출 그대로, 운영과 같은 판독 경로(`demo.backend.ocr.read_document` 체인, 글자층 쪽은 글자층 사용, 전북AI·Upstage 꺼짐)로
  서비스 `assess_upload`를 돌린 결과. 도구는 `engine_v2.tools.doc_timing`의 결과 행(`rows.jsonl`)이다. 반복 실행이면 문서마다 첫 측정 반복(`phase=measure`, `repeat=1`)의 판정을 쓴다.
  반복 사이 판정이 다르면 그 문서 수를 따로 적는다.
- **A-스캔 (보조 지표)**: `engine_v2.tools.batch_assess` 결과. 모든 쪽을 300dpi로 렌더링해 own OCR을 강제한다. **"모든 서류가 스캔본이라고 가정한 조건"**의 판정이며 운영 업로드 판정이 아니다.

두 지표의 조건 차이:

| 조건 | A (doc_timing) | A-스캔 (batch_assess) |
| --- | --- | --- |
| 판독 경로 | 운영 `read_document` 체인 그대로 (Fixture → JbaiOcr → LocalOcr → PdfText → Upstage) | 모든 쪽 렌더링·own OCR 뒤 운영 변환 함수와 `read_document` 마무리만 사용 (batch_assess.py:531-587) |
| 글자층 사용 | 운영과 같음: 쪽 글자 50자 이상이면 글자층, 첫 쪽만 읽는 PdfText 경로 포함 | 쓰지 않음: 글자층 쪽도 OCR (글자층은 비교 참조로만) |
| 예상 서류 종류 전달 | `read_document(path, None)`. 운영은 슬롯 종류를 넘기지만 own 경로에서 그 값을 쓰는 계층은 꺼진 JbaiOcr뿐 | 판독기에 넘기지 않음(미리 읽은 결과를 돌려줌) |
| 신청자 신원·신고 발급일 | 없음(None). 신원 대조·신고일 비교 사유는 나오지 않음 | 없음(None). 같음 |
| 판정 슬롯 | 판별 종류로 고른 두배적금 슬롯 (batch_assess `_requirement`와 같은 규칙) | 같음 |
| 슬롯이 없는 서류 | NOT_ASSESSED (미판별·일용근로·농어업·취업지원패키지 서류) | NOT_ASSESSED (코드 CLASSIFICATION_FAILED, WORK_CATEGORY_UNMAPPED, SLOT_UNAVAILABLE) |
| 대상 파일 | `.pdf`만 | PDF와 이미지(jpg·png·heic·gif·jfif). A-스캔도 PDF 행만 쓴다 |
| 제외 | 처리 전 점검에서 ENCRYPTED, OPEN_ERROR, EMPTY_DOCUMENT로 건너뜀(`phase=skipped`) | error_code ENCRYPTED, OPEN_ERROR, EMPTY_DOCUMENT (document_status ERROR) |
| 그 밖의 오류 | code PROCESSING_ERROR, GUARD_BLOCKED | error_code OCR_ERROR, EXTRACTION_ERROR, ASSESSMENT_ERROR, GUARD_BLOCKED, PROCESSING_ERROR, DECODE_ERROR 등 |
| 사유 코드 | 결과 행 `reasons`(형식 버전 2 이상)에 등록 코드·심각도 쌍 저장, 문서당 중복 없음 | 결과 행 `reasons`에 코드·심각도 저장 |

**A0 오류 규칙 (A와 A-스캔 둘 다):** 실행 뒤 PDF 행의 오류 코드를 코드별로 센다. ENCRYPTED·OPEN_ERROR·EMPTY_DOCUMENT 밖의 오류 코드가
**1건이라도 있으면 그 실행의 A 숫자를 쓰지 않고 원인부터 본다.** batch_assess는 오류가 한 건이라도 있으면 종료 코드 1로 끝나므로(암호 파일만 있어도 1),
종료 코드가 아니라 오류 코드별 개수로 판단한다.

| 번호 | 정의 | 계산식 |
| --- | --- | --- |
| A0 | 전체 PDF 수 | A: doc_timing run.json `counts.inventory_pdf`(표본이 아닌 전체 실행). A-스캔: results.jsonl 행 중 확장자 .pdf인 행 수 |
| A1 | 제외 수 | ENCRYPTED, OPEN_ERROR, EMPTY_DOCUMENT 수를 코드별로 (지난 실서류 기준 예상: 암호 160, 열기 오류 5). 판정하지 않고 담당자가 직접 연다. A1% = A1 ÷ A0 |
| A2 | 판정 분모 | PASS + NEEDS_REVIEW + FAIL 문서 수. A0 − A1 − A6 과 같아야 한다 |
| A3 | 적합 | PASS 수, A3% = A3 ÷ A2 |
| A4 | 확인 필요 | NEEDS_REVIEW 수, A4% = A4 ÷ A2 |
| A5 | 재업로드 | FAIL 수, A5% = A5 ÷ A2 |
| A6 | 분모 밖 | NOT_ASSESSED 수와 A1 밖의 오류 수를 코드별로 |
| A7 | 확인 필요 사유 1위 | 도구: A는 doc_timing 결과 행의 `reasons`(형식 버전 2 이상), A-스캔은 batch_assess 결과 행의 `reasons`. NEEDS_REVIEW 문서에서 심각도 NEEDS_REVIEW 사유 코드를 문서당 한 번씩 셀 때 문서 수가 가장 많은 코드와 그 수, A7% = 그 수 ÷ A4. 동률이면 코드 이름순 |
| A8 | 1위 사유만 있는 건수 | 도구: A7과 같음. NEEDS_REVIEW 문서 중 심각도 NEEDS_REVIEW 사유 코드 집합이 정확히 {A7 코드}인 문서 수 |

사유 코드는 등록 코드(`verify_upload.SAFE_CODES`)만 그대로 쓰고 그 밖은 UNKNOWN_CODE로 센다. 사유 문장은 쓰지 않는다.

**현재 도구로 낼 수 있는 것:**
- A: doc_timing 결과 행에 판정 상태(`decision`)와, 형식 버전 2부터 사유 코드(`reasons`)가 저장된다. A0~A8 모두 결과 행에서 낸다.
  형식 버전 1 결과(사유 없음)로는 A7·A8을 내지 않는다. 개선 전·후 모두 형식 버전 2 이상으로 잰다.
- A-스캔: 결과 행에 필요한 값이 모두 있다. 지금 `--summarize`는 A1 구분·A2 분모 비율·A7·A8을 내지 않으므로 결과 행에서 계산식대로 센다.

```
cd <REPO> && caffeinate -i .venv/bin/python -B -m engine_v2.tools.doc_timing --root <HUB_ROOT> --out <RUN_DIR>/doc_timing/<이름> --engines own
cd <REPO> && caffeinate -i .venv/bin/python -B -m engine_v2.tools.batch_assess --root <HUB_ROOT> --out <RUN_DIR>/batch_assess/<이름> --engines own
```

## B. 재업로드 안내 정확도 (B1~B3)

- 대상: A에서 FAIL로 판정된 문서 중 진이 원본을 보고 라벨을 단 표본. 라벨 = "그 재업로드 사유가 원본에 실제로 있다(맞음)/없다(틀림)".
- B1 = 안내가 맞은 건수 k, B2 = 라벨 건수 n.
- B3 = 정확도의 95% 단측 하한(Clopper–Pearson): k < n이면 Beta(0.05; k, n − k + 1)의 값, **k = n(오판 0)이면 0.05^(1/n)**.
- 표본 뽑기: A의 FAIL 문서에서 사유 코드별 층화, 고정 seed. 표본 수와 seed는 라벨 전에 적는다.

## C. 잘못된 통과 (C1~C3)

- 대상: A에서 PASS로 판정된 문서 중 진이 라벨을 단 표본. 라벨 = "실제로 미비가 있는데 통과했다(잘못된 통과)/아니다".
- C1 = 잘못된 통과 건수 k, C2 = 라벨 건수 n.
- C3 = 잘못된 통과 비율의 95% 단측 상한: k > 0이면 Beta(0.95; k + 1, n − k)의 값, **k = 0이면 1 − 0.05^(1/n)**.
- 합성 410쌍의 잘못된 통과(own 0/235)는 C와 다른 지표다. 둘을 섞지 않는다.

**C 라벨 핵심 항목 (2026-11-18 고정, 라벨 결과를 보기 전).** 라벨은 "PASS가 맞는가"를 아래 항목만으로 판단한다.
판정(서류 단위 `check_document`·`assess_upload`), 재업로드(FAIL), 확인 필요(NEEDS_REVIEW) 규칙이나 신청 건 소득·자격 판정(`facts.build_facts` → `scoring`·`eligibility_blockers`)이
실제로 읽는 필드만 넣었다. 추출만 되고 어떤 규칙도 읽지 않는 필드(예: 납부확인서 `고지월`, 초본 `과거주소미포함의심`)는 넣지 않는다.
기준 커밋 `bafa2f9`. 함수 이름으로 적고, 행 번호는 바뀔 수 있다.

| 서식 | 핵심 항목 (OCR 필드) | 읽는 규칙 (파일 · 함수) | 잘못 읽으면 바뀌는 것 |
| --- | --- | --- | --- |
| 공통 | 서식 종류(`detected_doc_type`), 발급일, 원본 화질(`image_quality`·원본이미지크기) | doc_check.py `_check_document`·`finalize_image_quality`, file_evidence.py `resolution_defect`, engine stage1 | 다른 서식 통과, 발급일 기간 밖 통과, 저화질 통과 |
| 주민등록초본 | 주소변동내역 (미포함·없음 → FAIL), **주소이력건수 (1건 → PAST_ADDRESS_OMISSION_SUSPECTED, 확인 필요)**, 주소날짜검증자료, 쪽표기자료(쪽 누락·중복), 초본신청인성명·생년월일, 전입일(거주 점수) | doc_check.py `_check_document`(주소이력건수·주소변동내역), `_check_resident_pages`, facts.py `build_facts`(전입일) → scoring.py `score_residence` | 과거 주소 빠진 초본 통과, 쪽 빠진 초본 통과, 본인 아닌 초본 통과, 거주 점수 |
| 건강보험료 납부확인서 | **월별고지금액 (판정 대상 석 달)**, 고지월검증자료(조회기간·금액 없는 달), 납부쪽표기자료, 납부표완전성자료, **가입구분**, 사업장명칭, 성명·가입자성명 | doc_check.py `_check_billing_months`·`_check_payment_paging`, facts.py `_monthly_premium`(월별고지금액만 사용, 건강보험료 평균은 쓰지 않음)·`_insurance_facts`(가입구분) → scoring.py `score_income` | 소득 140% 상한 판정(보험료·가입구분 상한 행), 소득 점수, 고지월 누락 통과 |
| 건강보험 자격확인서 | 가구원목록·가구원수, 가입구분, 사업장관리번호(·상태), 성명·생년월일, 양식판독상태 | doc_check.py `_check_document`(양식판독상태·필수 항목), facts.py `build_facts`(가구원수)·`_insurance_facts` | 가구원 수(소득 상한 행), 가입구분 |
| 자격득실확인서 | 자격이력자료(조회기간·취득·상실 행), 발급일, 성명·생년월일 | doc_check.py 자격이력 확인, work_continuity.py | 근로 지속 요건, 이력 기간 누락 통과 |
| 4대보험 가입내역확인서 | 가입내역 행(보험·상태·자격취득일), 성명·생년월일, 양식판독상태 | doc_check.py `_insurance_identity_unreadable`, work_continuity.py | 근로 지속 요건, 본인 아닌 서류 통과 |
| 행정정보 공동이용 동의서 | 동의여부, 서명잉크확인, 성명·생년월일 | upload_assessment.py `assess_upload`(종이 동의서) | 동의 없음·서명 없음 통과 |
| 사업자등록증명 | 개업일, 사업자상태, 사업자등록번호, 성명·생년월일, 양식판독상태 | doc_check.py `_check_document`, work_continuity.py | 휴·폐업 또는 기준일 뒤 개업 통과 |

확인한 후보: 주소이력건수(1건이면 확인 필요)는 핵심 항목이다. 납부확인서 가입구분은 서류 판정은 바꾸지 않지만 신청 건 소득 상한 행을 정하므로 핵심 항목이다
(직장 상한이 모든 가구원 수에서 지역 상한보다 높아, 지역을 직장으로 잘못 읽으면 소득 요건을 잘못 충족시키는 방향이다).

## J. 전북AI OCR 비교 (J1~J4)

**이번 주 측정하지 않음** — 도구 없음(ocr_baseline 엔진은 own·applevision뿐), 대상 120쪽이 실서류라 외부 전송이 필요함, 운영에서 쓰지 않는 엔진.
정의만 남긴다: 같은 납부확인서 120쪽 × 3상태(clean, scan, phone), ocr_baseline과 같은 채점. J1 가입구분, J2 고지월, J3 발급일 일치율, J4 쪽당 초.

## T. 서류당 처리 시간 (T1~T3)

- 도구: `engine_v2.tools.doc_timing` (서비스 업로드 경로, own 고정). 서류당 시간 = 판독부터 서류 단위 판정까지, 모델 불러오기 제외.
- 조건: 예열 3건 뒤, `--repeat 3`(서류별 3회 중앙값), **전원 연결**(run.json power = AC), 시작 부하 경고 없음. 조건이 어긋나면 그 실행은 T로 쓰지 않고 다시 잰다.
  ```
  cd <REPO> && caffeinate -i .venv/bin/python -B -m engine_v2.tools.doc_timing --root <HUB_ROOT> --out <RUN_DIR>/doc_timing/<이름> --engines own --repeat 3
  ```
- T1 = 서류당 시간 중앙값(초), T2 = p95(초), T3 = 측정 장비(run.json의 기계 모델·CPU·코어·전원·라이브러리 버전·own 스레드).
- 목표 판정 줄(평균 ≤ 2.5초, p95 ≤ 5초)도 함께 적는다. 전체 1회 실행(`--repeat 1`)은 예비 값이며 T로 쓰지 않는다.
  시간을 줄이려면 표본 200건 × 3회(`--sample 200 --repeat 3 --strata-from <전체 1회 결과>`)로 T를 재고, 그 사실을 적는다.

## E. 담당자 처리 시간 실험 (E1~E4)

- 담당자 화면이 보여 주는 것: **확인 필요 사유(코드·문구·안내)와 판독 항목별 "원본 위치" 버튼.** 사유와 위치는 직접 연결되어 있지 않다
  (관련 항목을 하나로 정할 수 있는 사유는 서류 판정 사유 40개 중 14개, research/d1-findings.md e절; 화면 근거는 research/verdict-reasons.md 2절).
- E1 설계: 팀원 2~3명, 합성 "확인 필요" 서류 20건. 조건 두 가지 — (가) 원본만 보고 판단, (나) **지금 담당자 화면 그대로**의 사유 표시와 항목별 원본 위치 버튼.
  순서 교차: 참가자마다 (가)→(나) 또는 (나)→(가)를 번갈아 배정하고, 두 조건에 서로 다른 10건씩을 쓰되 참가자 사이에서 세트를 바꾼다. 실서류는 쓰지 않는다.
- E2 = 조건 (나)에서 확인 필요 서류 1건 처리 시간의 중앙값. 조건 (가)의 중앙값도 함께 적는다.
- s = 제외 서류(A1, 암호·열기 오류) 1건을 담당자가 직접 여는 시간. E1 실험에서 따로 재거나, 재지 않았으면 가정값과 근거를 적는다.
- **E3 = 6 × (A4% × E2 + A1% × s)** — 신청 1건당 담당자 시간. A4%, A1%는 0~1 비율.
- **E4 = 12,821 × E3 ÷ 60** — 전체 신청 12,821건의 담당자 시간.
- **진 확인 대기:** E3의 "6"(신청 1건당 서류 수)과 단위(E2·s를 분으로 두면 E3은 분/신청, E4는 시간). 확인 전에는 E3·E4를 계산하지 않는다.
- 가정(명시): 재업로드(A5)는 신청자 단계에서 해결되어 담당자 시간에 넣지 않는다. 적합(A3) 서류의 담당자 시간은 0으로 둔다.

## G. 서류 분류(G1)와 핵심 항목 추출(G2)

- 도구: `engine_v2.tools.documentai_staged`, `normal_baseline` 그룹(조건 original), own 단계(B).
  G1 = 종류를 맞힌 서류 수 ÷ 서류 수. G2 = 맞힌 핵심 항목 수 ÷ 추출기가 불린 핵심 항목 수(판별 실패 항목은 분모 밖, 전체 작성 항목 기준 값도 함께 적음).
- 발표용 세트: 11/13과 같은 합성 원본 25건 / 165항목 = `--samples 5 --seed 20261113`의 sample 1~5.
- 검증 세트: 같은 생성기의 다른 원본 25건 = `--samples 10 --seed 20261117`의 sample 6~10 (research/validation-set.md). 배치는 같고 가상 값만 다르다는 한계가 있다.
- **두 세트를 항상 나란히 보고한다. 검증 세트에서 오르지 않으면 "달성"이라고 쓰지 않는다.** 발표용 세트만 오른 개선은 "발표용 세트에서만 상승"이라고 쓴다.
- 기준값(11/17, 수정 전): research/validation-set.md 표.

## OCR 관련 표현 규칙

- own은 **공개 사전학습 모델(PP-OCRv5 mobile 검출·한국어 인식, RapidOCR v3.10.0 ONNX)을 그대로 쓰는 자체 운영 엔진**이다. 미세조정하지 않았다.
- 이번 개선은 OCR 인식 개선이 아니라 **Document AI(판별·추출·판정) 개선**이라고 쓴다. "학습시킨 OCR", "OCR 인식률 향상"이라고 쓰지 않는다.
- G2가 오르면 "핵심 항목 추출 개선"이라고 쓰고 "OCR 정확도 향상"이라고 쓰지 않는다.

## 바뀐 기록

- 2026-11-17 (숫자를 보기 전, 작업 E): A7·A8 도구를 doc_timing 결과 행의 `reasons`(형식 버전 2 이상)로 고정.
- 2026-11-17 (숫자를 보기 전): A를 A(주 지표, 운영 판독 경로·doc_timing)와 A-스캔(보조 지표, batch_assess)으로 나눔. J를 이번 주 측정 제외로 바꿈. E3의 6과 단위를 진 확인 대기로 표시. 사유 표시 문구를 화면 그대로로 고정.
- 2026-11-18 (라벨 결과를 보기 전): C절에 라벨 핵심 항목 표를 고정. 판정·재업로드·확인 필요·소득 판정 규칙이 실제로 읽는 필드만 넣음.
