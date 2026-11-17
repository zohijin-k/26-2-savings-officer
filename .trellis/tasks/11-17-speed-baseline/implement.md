# 서류당 처리 시간 기준선 — 실행 계획

작업 공간 `<WORK>`는 `mktemp -d /tmp/speed_baseline_work-XXXXXXXX`로 만든다. 합성 자료와 실행 결과는 모두 여기에 두고 커밋하지 않는다.
`<RUN_DIR>`은 지난 작업의 보존 폴더 위치, `<HUB_ROOT>`는 실서류 위치다. 실서류와 실서류 결과는 열지 않는다.

## 0. 공통 회귀 (커밋마다, 다른 측정과 동시에 돌리지 않음)

```sh
df -g / | tail -1                     # 가용 15GiB 미만이면 중단
.venv/bin/python -m pytest engine_v2/tests
.venv/bin/python -m pytest demo/backend/tests --basetemp <WORK>/pytest/backend-<n>
for f in demo/backend/tests/run_p*_scenarios.py; do echo "== $f"; .venv/bin/python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
cd demo/frontend && npx tsc -b && npx oxlint && npx vite build --outDir <WORK>/frontend-<n>
.venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output <WORK>/paired-<n>.json
```

기준: engine_v2 2,338 passed / 3 skipped / 3 xfailed (+ 새 시험), backend 1,411 passed / 2 xfailed, 시나리오 검사 1,885 / 실패 0, 프런트 세 명령 종료 코드 0.
410쌍은 `<RUN_DIR>/before/paired.json`과 엔진별(own, reference) × 종류별로 비교한다: own 잘못된 통과 0/235, 참조 15/235, 납부 참조 5/50, 바뀐 행 수(case_id별 상태 차이).
비교 스크립트는 `<WORK>/paired_compare.py`에 두고 커밋하지 않는다. 잘못된 통과가 하나라도 늘면 중단한다. 기존 시험이 실패하면 고치지 않고 보고한다.

커밋 전 검사: 사용자가 작업 지시에서 준 다섯 패턴 각각을 `git diff --cached | grep -c`로 세고(패턴 문자열은 이 문서에 적지 않는다.
적으면 이 문서 자체가 걸린다), `git diff --cached --name-only`로 파일 목록을 본다.

하나라도 0이 아니면 커밋하지 않고 파일과 줄 번호만 보고한다. 커밋 뒤 `git log --oneline -3`.

## 1. 커밋 (1) — Trellis 작업 생성

1. `prd.md`, `design.md`, `implement.md`, `task.json`, `implement.jsonl`, `check.jsonl`을 쓴다. (`research/call-path.md`는 커밋 (2)에 넣는다.)
2. 공통 회귀 → 다섯 패턴 → 승인 요청 → `chore(task): create 11-17-speed-baseline`.

## 2. 커밋 (2) — `tools: add per-document timing tool`

1. `task.py start`로 작업을 in_progress로 바꾼다.
2. `engine_v2/tools/doc_timing.py` 작성 (design.md 1절).
3. `engine_v2/tests/test_doc_timing.py` 작성: 백분위, 반복 중앙값, 흔들림 비율, 예열 제외, OUT_EXISTS, 암호·열기 오류·0쪽 집계, 단계 배타 시간, 감싸개가 결과를 바꾸지 않음(합성 글자층 PDF로 감싼 것/안 감싼 것 비교), 층화 표본 고정 seed, 목표 O/X 경계(2.5초, 5초), 출력에 경로·파일 이름·문서 키가 없음, CLI 종단 실행(가짜 OCR 엔진).
4. 합성 측정 자료 만들기(`<WORK>/timing_pdfs`):
   - 지난 작업의 합성 글자층 111건을 `<RUN_DIR>/before/reproduction/generate_corpus.py`로 다시 만든다(출력 위치만 `<WORK>`로 바꾼 사본). `<RUN_DIR>/before/synthetic_corpus.json`의 sha256과 맞춘다.
   - 그 111건을 쪽마다 200dpi 이미지로 바꾼 이미지 PDF 111건, 글자층 쪽 + 이미지 쪽을 섞은 PDF 몇 건, 암호 PDF 1건, 깨진 PDF 1건을 더한다.
5. 합성 실행(회귀와 겹치지 않게):
   ```sh
   .venv/bin/python -B -m engine_v2.tools.doc_timing --root <WORK>/timing_pdfs --out <WORK>/timing_r1 --engines own
   .venv/bin/python -B -m engine_v2.tools.doc_timing --root <WORK>/timing_pdfs --out <WORK>/timing_s40_r3 --sample 40 --repeat 3 --strata-from <WORK>/timing_r1
   .venv/bin/python -B -m engine_v2.tools.doc_timing --root <WORK>/timing_pdfs --out <WORK>/timing_r1 --engines own   # OUT_EXISTS 확인
   ```
   요약에 경로·이름·키가 없는지 grep으로 확인한다. 합성 글자층/이미지 서류 평균으로 실서류 실행 시간을 범위로 추정한다.
6. 문서: `.trellis/spec/backend/doc-timing.md` 추가와 색인 한 줄, `research/call-path.md`.
7. 공통 회귀 → 다섯 패턴 → 승인 요청 → 커밋.

## 3. 커밋 (3) — `ocr baseline: record field value presence`

1. 합성 ocr_baseline **전** 결과: main `f6d9827`을 `git archive`로 `<WORK>/src_before`에 풀고 `.venv`, `engine_v2/models/own` 링크만 건다.
   ```sh
   cd <WORK>/src_before && PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.ocr_baseline --root <WORK>/pdfs --out <WORK>/ocr_before --engines own applevision --variants clean scan phone
   ```
   (`<WORK>/pdfs`는 2-4의 글자층 111건과 같은 파일이다.) Apple Vision이 샌드박스에서 빈 결과를 내면 일반 실행으로 다시 돌리고 그 사실을 보고한다.
2. 코드 변경: `ocr_baseline_fields.compare_fields(presence=False)`, `ocr_baseline.process_file`(presence=True), `validate_row`(6개 또는 7개 키), `ocr_baseline_compare`(OUTCOME, TRANSITION).
3. 새 시험 `engine_v2/tests/test_ocr_baseline_presence.py`: 값 유무 기록, 예전 6키 행 읽기, 잘못된 actual_present 거부, 분류 규칙, NA 처리, 교차표, 출력에 ID 없음. 기존 시험 파일은 고치지 않는다.
4. 합성 ocr_baseline **후** 결과: 같은 명령을 저장소 작업 트리에서 `--out <WORK>/ocr_after`로 돌린다.
5. 전후 확인: 새 compare 출력의 STATUS·COHORT·EXCLUSION·FIELD·RECOGNITION 줄에서 delta가 모두 0 또는 NA이고, summary.json에서 시간 항목을 뺀 나머지가 같고, results.jsonl 행에서 `actual_present`와 seconds를 뺀 나머지가 같다. 하나라도 다르면 멈추고 보고한다.
6. 문서: `.trellis/spec/backend/ocr-baseline.md`에 값 유무와 분포 규칙 추가.
7. 공통 회귀 → 다섯 패턴 → 승인 요청 → 커밋.

## 4. 마무리 보고

작업 A 표, doc_timing 옵션과 운영과 다르게 한 부분, 합성 요약 숫자와 실서류 예상 시간, 작업 C 형식과 전후 0 변화,
커밋 해시·시각·파일·다섯 패턴, 회귀 비교, 진이 실행할 명령 3개(채팅에만 실경로)를 표로 보고하고 멈춘다.

## 되돌리기

각 커밋은 새 파일 추가나 도구 둘의 작은 변경이다. 되돌릴 때는 `git revert <hash>`를 쓴다(amend 금지).
