# 서류당 처리 시간 기준선 — 요구사항

브랜치 `work/speed-baseline`, 시작 main `f6d9827`. 작업 생성·계획·커밋마다 승인을 받는다.

## 목표와 배경

서류당 처리 시간 목표는 own 엔진, 맥북, OCR부터 판정까지 서류 하나 전체 기준 **평균 2.5초 이하, p95 5초 이하**다.
이번 작업은 이 목표를 잴 기준선 도구를 만든다. 운영 동작(판별, 추출, 판정, 엔진 선택 순서)은 바꾸지 않는다.

- 작업 A: 업로드 → 판별 → 추출 → 판정의 운영 호출 경로를 파일:행으로 기록한다 (코드 변경 없음). 결과: `research/call-path.md`.
- 작업 B: 운영 경로와 같은 함수를 불러 PDF 한 건 전체 시간을 재는 CLI `engine_v2/tools/doc_timing.py`.
- 작업 C: `ocr_baseline` 필드 기록에 값 유무(`actual_present`)를 저장하고, 비교 도구에 결과 분포와 전→후 교차표를 더한다.

## 지난 작업에서 이어받을 메모

11-15-own-adapter 감소 2건(월별 보수외소득 건강보험료 own clean 1/10→0/10, 납부확인서 생년월일 AV phone 113/120→112/120)은 둘 다 MATCH→UNATTRIBUTABLE 1건. 빈칸/틀린 값 구분은 작업 C 반영 후 실서류 재측정에서 확인.

## 요구사항

| ID | 요구사항 |
| --- | --- |
| R01 | 실서류 PDF, 실서류 결과 폴더(`<HUB_ROOT>`, `<HUB_RESULTS>`, `<OPERATOR_DIAG>`), 실서류 기준선 요약 파일은 열지 않는다. 검색에서 `engine_v2/data`와 `<OPERATOR_DIAG>`를 뺀다. 개발과 시험은 합성 자료로만 한다. 실서류 실행은 진이 한다. |
| R02 | 화면 출력과 요약 파일에는 숫자, O/X, 코드 이름만 쓴다. 값, 이름, 파일 경로, 문서 ID는 출력하지 않는다. 결과 행 파일 안의 내부 ID는 허용하되 화면에 찍지 않는다. |
| R03 | 커밋 파일에는 실서류 경로나 결과 폴더 절대경로 대신 `<HUB_ROOT>`, `<RUN_DIR>` 같은 자리표시를 쓴다. |
| R04 | 운영 코드(demo/backend, engine, engine_v2의 판별·추출·판정·OCR·엔진 선택)를 바꾸지 않는다. 바뀌는 곳은 `engine_v2/tools/` 새 도구와 ocr_baseline 도구 둘, 새 시험, 문서뿐이다. |
| R05 | doc_timing은 작업 A에서 확인한 운영 함수(`demo.backend.ocr.read_document`, `demo.backend.upload_assessment.assess_upload`)를 그대로 불러 PDF 한 건을 처음부터 끝까지 잰다. 글자층 쪽에 OCR을 강제로 돌리지 않는다. 운영과 다르게 하는 부분은 `research/call-path.md` 5절과 보고에 적는다. |
| R06 | 단계별 시간: 열기, 글자층 읽기, 렌더링, OCR, 판별, 추출, 파일 증거, 서류 단위 판정, 그 밖, 전체. 모델 불러오기 시간은 따로 기록하고 서류 시간에서 뺀다. 예열 N건(기본 3)은 통계에서 빼고 따로 기록한다. |
| R07 | 옵션: `--root`, `--out`(이미 있으면 OUT_EXISTS로 멈춤), `--engines`(기본 own), `--repeat`(기본 1), `--sample N`(서식별 층화 표본, 고정 seed), `--limit`. 암호 PDF와 열기 오류는 처리하지 않고 사유 코드로 센다. |
| R08 | run.json에 기계 모델, CPU 코어 수, 전원, 시작·끝 부하 평균, 파이썬·주요 라이브러리 버전, own 스레드 설정, 시작·끝 시각, git 커밋을 기록한다. 시작 부하 평균이 코어 수의 절반을 넘거나 배터리 전원이면 경고만 출력한다. |
| R09 | summary_brief.txt: 전체 통계(건수, 평균, 중앙값, p90, p95, 최대), 목표 판정 줄(MEAN_LE_2_5S, P95_LE_5S), 서식별·글자층 유무별(TEXT/NONE/MIXED)·쪽수 구간별(1/2/3+) 통계, 단계별 합계와 비중, 반복 2회 이상이면 서류별 중앙값 통계와 반복 간 흔들림(서류별 최대/최소 비율의 중앙값·p90), 느린 서식 상위 5개(코드, 건수, 평균, p95, 전체 시간 중 비중). |
| R10 | doc_timing 시험: 백분위 계산, 반복 중앙값, 예열 제외, OUT_EXISTS, 출력에 경로·이름·ID가 나오지 않음, 암호·열기 오류 집계, 단계 시간 중첩 처리, 측정 도구가 운영 결과를 바꾸지 않음. 합성 자료로 실제 실행해 요약이 나오는지 확인한다. |
| R11 | ocr_baseline 필드 기록에 `actual_present`(0/1)를 더한다. 이미 계산하는 값을 저장만 한다. 판정 방식과 기존 숫자 6개는 바꾸지 않는다. 기존 시험 기대값을 바꾸지 않는다. |
| R12 | ocr_baseline_compare에 필드별 MATCH / BLANK / WRONG / OTHER 분포와 전→후 교차표를 더한다. `actual_present`가 없는 예전 결과는 NA로 처리하고 오류를 내지 않는다. |
| R13 | 합성 ocr_baseline 전후 비교에서 기존 지표(필드 일치, 인식 지표, 행 수)가 모두 같아야 한다. 하나라도 바뀌면 멈추고 보고한다. |
| R14 | 커밋 순서: (1) Trellis 작업 생성 (2) `tools: add per-document timing tool` (작업 B, 작업 A 문서 포함) (3) `ocr baseline: record field value presence` (작업 C). 커밋마다 승인을 받는다. |
| R15 | 각 커밋 전 회귀(engine_v2, backend, 시나리오, 프런트, 합성 410쌍)와 다섯 패턴 검사를 한다. 회귀와 시간 측정은 동시에 돌리지 않는다. `git add`는 파일을 하나씩 지정한다. amend, push, 커밋 메시지의 Co-Authored-By 줄은 금지한다. |

## 수용 기준과 중단 지점

| 기준 | 확인할 결과 |
| --- | --- |
| AC01 → R15 | engine_v2 2,338 passed / 3 skipped / 3 xfailed (+ 새 시험 수), backend 1,411 passed / 2 xfailed, 시나리오 1,885 검사 실패 0, 프런트 세 명령 성공. 기존 시험이 실패하면 고치지 않고 이유부터 보고한다. |
| AC02 → R15 | 410쌍 전(`<RUN_DIR>/before`)·후(HEAD): own 잘못된 통과 0/235, 글자층 참조 15/235, 납부 5/50 유지, 바뀐 행 수 보고. 잘못된 통과가 늘면 중단한다. |
| AC03 → R05~R10 | doc_timing 합성 실행에서 run.json, rows.jsonl, summary_brief.txt가 생기고, 요약에 숫자·코드만 있다. 새 시험이 모두 통과한다. |
| AC04 → R11~R13 | 합성 ocr_baseline 전후에서 기존 compare 출력(COHORT, EXCLUSION, FIELD, RECOGNITION)과 summary 숫자(시간 제외)가 같고, 결과 행에서 `actual_present`와 시간을 뺀 나머지가 같다. 기존 시험 기대값 변경 0. |
| AC05 → R14 | 커밋마다 `git diff --cached` 다섯 패턴이 모두 0이고 파일 목록을 보고한 뒤 승인을 받는다. 커밋 뒤 `git log --oneline -3`로 확인한다. |
| AC06 | 진이 실행할 명령 3개를 채팅 보고에만 적는다(커밋 파일에는 자리표시). 보고 후 멈춘다. |

설계는 `design.md`, 실행 순서와 명령은 `implement.md`, 운영 경로 근거는 `research/call-path.md`에 둔다.
