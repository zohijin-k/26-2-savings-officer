# 실서류 서식 분류 회복 진단 — 요구사항

브랜치 `work/classify-recovery`, 시작 main `574eb5f`. 작업 생성·계획·커밋마다 승인을 받는다.

## 배경 (진이 준 실서류 측정 숫자)

- A(운영 경로, doc_timing `hub_full_1`, 1,529건): PASS 545, NEEDS_REVIEW 662, FAIL 51, NOT_ASSESSED 271.
  서식 미분류(form X) 260 = 그림·판독기 없음(tier none) 168, 글자층·pdftext 88, 그 밖 4.
- A-스캔(batch_assess `hub_before_1117`, 1,528건): PASS 296, NEEDS_REVIEW 1,002, FAIL 146, NOT_ASSESSED 84. detected_type X 72.
- 같은 서류에서 A-스캔이 서식을 약 190건 더 알아본다 → 운영 경로가 그림 서류 일부를 읽지 못하고 넘기는 것으로 의심.
- 확인 필요 상위 사유: 자격확인서 REQUIRED_FIELD_UNREADABLE 131, 동의서 ADMIN_CONSENT_MARK_UNREADABLE 130(144건 중),
  납부확인서 NHIS_PAYMENT_PAGING_UNCERTAIN 113·MISSING_BILLING_MONTHS 88, 자격득실 REQUIRED_FIELD_UNREADABLE 103, 4대보험 REQUIRED_FIELD_UNREADABLE 85.
- 실서류 4대보험은 A에서 218건 분류됨(합성 0/5와 다름).

## 목표

운영 판별·추출 규칙을 바꾸기 전에, 진이 실서류에서 돌릴 **값 없는 진단**과 **후보 규칙의 그림자 평가**를 준비한다.
이번 작업의 커밋은 운영 동작을 바꾸지 않는다. 운영 반영은 진의 실서류 결과를 본 뒤 별도 승인으로 한다.

## 요구사항

| ID | 요구사항 |
| --- | --- |
| R01 | 실서류 PDF와 실서류 결과 폴더(`<HUB_ROOT>`, `<HUB_RESULTS>`, `<OPERATOR_DIAG>` 아래 실서류 실행 폴더)는 열지 않는다. 검색에서 `engine_v2/data`와 `<OPERATOR_DIAG>`를 뺀다. 개발과 시험은 합성으로만 한다. 실서류 실행은 진이 한다. |
| R02 | 진단 출력(화면, 요약 파일)은 숫자, O/X, 고정 코드 이름만 쓴다. 값, 이름, 파일 경로, 문서 ID, 자유 문장, 예외 문장은 쓰지 않는다. 결과 행에는 16자리 문서 키만 둔다. |
| R03 | 운영 코드(demo/backend, engine, engine_v2의 판별·추출·판정·OCR)를 바꾸지 않는다. 바뀌는 곳은 `engine_v2/tools/` 새 진단 도구, 새 시험, 스펙 문서, 작업 문서뿐이다. |
| R04 | 파일 이름이나 폴더 이름을 판정·판별·진단 코드에 쓰지 않는다(확장자로 PDF만 고르는 것은 doc_timing과 같다). |
| R05 | 가: batch_assess 결과의 slot, group, work_category 출처와 판정·detected_type 영향 여부를 파일:행으로 답한다 (`research/findings.md` 가절). |
| R06 | 나: (1) LocalOcr가 None을 돌려주거나 OcrFallback을 내는 조건, PdfText가 X로 끝나는 조건, A와 A-스캔 차이를 파일:행 표로 낸다. (2) 합성으로 재현한다. (3) 진이 돌릴 진단: 기존 두 결과 파일을 문서 키로 맞춘 교차표(다시 실행 없음)와, A form X 문서의 판독 단계 코드(다시 실행). |
| R07 | 다: 4대보험 "확인용" 판별 후보 규칙(design.md 3절)을 승인받은 뒤, 운영은 그대로 두고 후보 규칙의 결과를 세는 그림자 평가를 진단 도구에 넣어 먼저 커밋한다. 실서류 출력: 기존 INSURANCE_4 중 판별이 바뀌는 수, X에서 INSURANCE_4로 새로 잡히는 수, 다른 서식에서 INSURANCE_4로 바뀌는 수. |
| R08 | 다: 합성 발표용 세트(seed 20261113, sample 1~5)와 검증 세트(seed 20261117, sample 6~10)의 G1·G2를 그림자 규칙 적용 전후로 보고한다. 두 세트를 항상 나란히 쓴다. |
| R09 | 라: ADMIN_CONSENT_MARK_UNREADABLE 조건, 표시 판독 방식, LOW_IMAGE_QUALITY 기준을 파일:행으로 보고하고, 실패 단계를 코드로 나누는 진단과 실서류 실행 명령을 준비한다(단계별 개수만 출력). |
| R10 | 마: 합성에서 놓친 납부확인서 4항목 × 5건의 실패 단계(머리글, 열 경계, 행 묶음, 값 형식)를 단계 코드로 보고하고, 실서류 NHIS_PAYMENT_PAGING_UNCERTAIN·MISSING_BILLING_MONTHS와 같은 원인인지 확인할 진단과 실행 명령을 준비한다. |
| R11 | 진단 도구 시험은 합성 자료만 쓴다. 감싸개가 운영 판독 결과를 바꾸지 않음(감싼 것/안 감싼 것 비교), 출력에 경로·이름·키가 없음, OUT_EXISTS, 후보 규칙이 기존 키워드 판별을 바꾸지 않음을 확인한다. |
| R12 | 기존 시험이 실패하면 고치지 않고 이유부터 보고한다. 기대값 변경은 목록과 이유를 보고하고 승인을 받는다. 합성 410쌍에서 own 잘못된 통과가 0/235에서 늘면 중단한다. |
| R13 | 커밋 파일에 절대경로를 쓰지 않는다(`<HUB_ROOT>`, `<RUN_DIR>` 같은 자리표시). `git add`는 파일 하나씩. amend·push 금지. 커밋 메시지에 Co-Authored-By 줄 없음. |
| R14 | 커밋마다: 회귀(engine_v2 pytest, demo/backend pytest, 시나리오 반복문, 프런트 세 명령, 합성 410쌍)와 다섯 패턴 검사, 파일 목록 보고, 승인. 회귀와 다른 측정을 동시에 돌리지 않는다. |
| R15 | 커밋 순서: (1) `chore(task): create 11-17-classify-recovery` (2) `tools: add classification recovery diagnostics with G1 shadow` (나·다) (3) `tools: add consent mark and payment table stage diagnostics` (라·마, P1·C1·위치 맞춤 그림자). 보고 후 멈춘다. |
| R16 | (추가) 커밋 2의 run: LocalOcr에서 사라지던 예외의 종류(예외 클래스 이름만)와, 다섯 원인(숨은 글자층, 첫 쪽 1~49자 후 버림, 첫 쪽 그림+뒤쪽 글자층, 전처리 오류, 큰 배경 그림만 추출) 중 어디에 해당하는지를 문서마다 하나의 원인 코드로 남기고 원인별 건수를 낸다. |
| R17 | (추가) 커밋 3: 후보 P1(납부 머리글 띠 여유, 쪽 높이 대비 여유 0.1·0.2·0.3%p 비교) 그림자 평가. 합성 발표용·검증 세트 G2(165항목) 전후, 410쌍 영향, 실서류에서 NHIS_PAYMENT_PAGING_UNCERTAIN·MISSING_BILLING_MONTHS가 사라지는 문서 수와 새로 생기는 문서 수. |
| R18 | (추가) 커밋 3: 후보 C1(동의서 "원본 150dpi 미만 그리고 표시·서명 못 읽음" FAIL → NEEDS_REVIEW) 그림자 평가. 실서류 FAIL→NEEDS_REVIEW 수. 사람이 봐도 못 읽는 원본을 자동으로 가려낼 방법은 제안만. |
| R19 | (추가) 커밋 3: 동의서 위치 맞춤 후보 그림자 평가. 표시가 없는 서식을 표시 있음으로 읽는 경우(잘못된 통과 방향)를 합성으로 따로 시험하고 수를 보고한다. |
| R20 | (승인 규칙 변경) 회귀 전체 통과, 410쌍 own 잘못된 통과 0/235, 기존 시험 기대값 변경 0·실패 0, 다섯 패턴 0, Co-Authored-By 없음, amend·push 없음, 파일 하나씩 add를 모두 만족하면 묻지 않고 커밋하고 `git log --oneline -3`을 보고한다. 기존 시험 실패·기대값 변경, 잘못된 통과 증가, 운영 동작을 바꾸는 커밋, 진의 실서류 실행이 필요할 때, 지시 범위 밖이면 멈춘다. |

## 수용 기준과 중단 지점

| 기준 | 확인할 결과 |
| --- | --- |
| AC01 → R14 | engine_v2 2,379 passed / 3 skipped / 3 xfailed (+ 새 시험 수), backend 1,411 passed / 2 xfailed, 시나리오 18개 실패 0, 프런트 세 명령 종료 코드 0 (커밋 1 회귀 = main `574eb5f` 기준값). |
| AC02 → R12 | 410쌍: own 잘못된 통과 0/235, 글자층 참조 15/235, 납부 참조 5/50 유지. 커밋 1 결과 대비 바뀐 행 0. |
| AC03 → R06 | crosstab이 합성 rows.jsonl·results.jsonl로 교차표를 내고, run이 합성 재현 PDF(나-2 표의 조건들)에서 각 조건의 단계 코드를 기대대로 낸다. |
| AC04 → R07, R11 | 그림자 평가가 합성 4대보험 5건을 X→INSURANCE_4로 세고, 다른 합성 서식(초본·납부·자격·자격득실 각 5건)은 바뀌지 않는다. 운영 `pdftext.classify_with_evidence`는 바뀌지 않는다(시험). |
| AC05 → R08 | 발표용·검증 세트 G1·G2 전후 표. 기준값(전)은 research/validation-set(11-17-speed-baseline)과 같아야 한다(20/25, 145/165). 다르면 멈추고 보고. |
| AC06 → R09, R10 | 동의서·납부 단계 코드가 합성 시험 자료(위치를 옮긴 서식5 표시, 합성 납부확인서)에서 기대 코드를 낸다. 합성 납부 5건은 HEADER_BAND_CUT로 나온다. |
| AC07 → R13, R14 | 커밋마다 다섯 패턴 0, 파일 목록 보고, 승인 후 커밋, `git log --oneline -3` 확인. |
| AC09 → R16 | 나-2 재현 PDF에서 원인 코드가 조건마다 HIDDEN_TEXT_LAYER / FEW_CHARS_DISCARD / FIRST_IMAGE_LATER_TEXT / PREPROCESS_ERROR / BACKGROUND_ONLY로 나오고, 전처리 오류에는 예외 클래스 이름이 붙는다. |
| AC10 → R17~R19 | P1 여유별 합성 G2 전후·410쌍 바뀐 행·잘못된 통과, C1 합성 전후, 위치 맞춤 합성 오판독 수를 표로 보고한다. 410쌍 측정에서 그림자 적용 시 잘못된 통과가 늘면 그 후보는 "운영 반영 불가"로 적는다(운영은 바꾸지 않음). |
| AC08 | 진이 실행할 실서류 명령을 채팅 보고에만 적는다(커밋 파일에는 자리표시). 보고 후 멈춘다. |

설계는 `design.md`, 실행 순서와 명령은 `implement.md`, 사실 확인은 `research/findings.md`에 둔다.
