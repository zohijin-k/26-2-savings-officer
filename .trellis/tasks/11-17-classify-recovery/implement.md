# 실서류 서식 분류 회복 진단 — 실행 계획

작업 공간 `<WORK>`는 `mktemp -d /tmp/classify_recovery_work-XXXXXXXX`로 만든다. 합성 자료, 재현 스크립트, 실행 결과는 모두 여기에 두고 커밋하지 않는다.
`<HUB_ROOT>`는 실서류 위치, `<RUN_A>`는 doc_timing `hub_full_1` 결과 폴더, `<RUN_SCAN>`은 batch_assess `hub_before_1117` 결과 폴더다. 열지 않는다.

## 0. 공통 회귀 (커밋마다, 다른 측정과 동시에 돌리지 않음)

```sh
df -g / | tail -1                     # 가용 15GiB 미만이면 중단
.venv/bin/python -m pytest engine_v2/tests -q -p no:cacheprovider
.venv/bin/python -m pytest demo/backend/tests -q -p no:cacheprovider --basetemp <WORK>/pytest/backend-<n>
for f in demo/backend/tests/run_p*_scenarios.py; do echo "== $f"; .venv/bin/python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
cd demo/frontend && npx tsc -b && npx oxlint && npx vite build --outDir <WORK>/frontend-<n>
.venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output <WORK>/paired-<n>.json
rm -rf <WORK>/pytest/backend-<n>        # 끝나면 이번 작업의 임시 폴더 정리
```

스크립트는 `<WORK>/regress.sh <n>`(커밋하지 않음). 기준: 커밋 1의 회귀 결과(= main `574eb5f`). 410쌍은 `<WORK>/paired-1.json`과 case_id·엔진별로 비교한다:
own 잘못된 통과 0/235, 참조 15/235, 납부 참조 5/50, 바뀐 행 수. 잘못된 통과가 하나라도 늘면 중단한다. 기존 시험이 실패하면 고치지 않고 보고한다.

커밋 전 검사: 사용자가 작업 지시에서 준 다섯 패턴 각각을 `git diff --cached | grep -c`로 세고(패턴 문자열은 이 문서에 적지 않는다), `git diff --cached --name-only`를 본다.
하나라도 0이 아니면 커밋하지 않고 파일과 줄 번호만 보고한다. 커밋 뒤 `git log --oneline -3`.

## 1. 커밋 (1) — `chore(task): create 11-17-classify-recovery`

1. `prd.md`, `design.md`, `implement.md`, `research/findings.md`, `task.json`, `implement.jsonl`, `check.jsonl`.
2. 공통 회귀(n=1) → 다섯 패턴 → 승인(진 승인 완료) → 커밋. 이후 커밋은 prd R20 규칙(조건 충족 시 묻지 않고 커밋).

## 2. 커밋 (2) — `tools: add classification recovery diagnostics with G1 shadow` (나·다)

1. `task.py start`.
2. `engine_v2/tools/classify_recovery_diag.py`: `crosstab`, `run`(판독 단계 기록, A form X 구조·스캔 비교, G1 후보 N/W/E 그림자 평가). design.md 1~4, 7절.
3. `engine_v2/tests/test_classify_recovery_diag.py`: design.md 9절(커밋 3 항목 제외).
4. 합성 확인(회귀와 겹치지 않게):
   - 나-2 재현 PDF(`<WORK>/repro`, `<WORK>/repro2`)를 루트로 `run`을 실제 own으로 돌려 조건별 코드가 research/findings.md 나-2 표와 맞는지 본다.
   - 합성 doc_timing 실행(`<WORK>/timing_synth`)과 합성 batch_assess 실행(`<WORK>/scan_synth`)을 같은 루트로 만들어 `crosstab`을 돌린다.
   - 합성 G1·G2 전후: `<WORK>/scratch/g1g2.py`(design.md 8절). 전 값이 20/25·145/165가 아니면 멈추고 보고.
   - 화면·summary.txt에 경로·파일 이름·키가 없는지 grep.
5. 문서: `.trellis/spec/backend/classify-recovery-diag.md`, 색인 한 줄.
6. 공통 회귀(n=2) → 다섯 패턴 → R20 조건 충족 시 커밋.

## 3. 커밋 (3) — `tools: add consent mark and payment table stage diagnostics` (라·마)

1. 도구에 동의서 단계(design.md 5절)와 납부 단계(6절)를 더한다. 결과 행 schema는 그대로 두고 `consent`·`payment` 키를 해당 문서에만 둔다(형식 판 2).
2. 그림자 후보 P1(여유 0.1·0.2·0.3), C1, 위치 맞춤을 더한다(design.md 6-1절).
3. 시험 추가: 서식5 합성 스캔(제자리·8pt 이동·표시 없음·둘 다), 표시 없음 변형에서 위치 맞춤이 표시를 만들지 않음, 합성 납부확인서 단어의 HEADER_BAND_CUT와 P1 적용 시 통과, C1 끼움이 운영 집합을 바꾸지 않음.
4. 합성 확인: 합성 납부확인서 5건(발표용)과 5건(검증)의 own 단계 코드가 모두 HEADER/HEADER_BAND_CUT인지. P1 여유별 G2 전후와 410쌍(`<WORK>/scratch/p1_paired.py`, 그림자 끼운 documentai_staged). 위치 맞춤 오판독 합성(`<WORK>/scratch/consent_align.py`).
5. 스펙 문서 갱신.
6. 공통 회귀(n=3) → 다섯 패턴 → R20 조건 충족 시 커밋.

## 4. 진이 실행할 명령 (채팅 보고에만 실경로, 여기에는 자리표시)

```sh
cd <REPO> && T=<RUN_A> && S=<RUN_SCAN> && caffeinate -i .venv/bin/python -B -m engine_v2.tools.classify_recovery_diag crosstab --timing "$T/rows.jsonl" --scan "$S/results.jsonl" ; caffeinate -i .venv/bin/python -B -m engine_v2.tools.classify_recovery_diag run --root <HUB_ROOT> --out <OUT> --timing "$T/rows.jsonl"
```

`run` 한 번으로 서식 미분류 다섯 원인(XCAUSE5), G1 N/W/E, P1 0.1·0.2·0.3, C1, 동의서 변형(ALIGNED·INNER·INNER_STRONG) 그림자 결과가 모두 나온다.
모든 PDF를 운영 경로로 한 번 다시 판독한다(doc_timing 한 번과 비슷한 시간 + A form X 문서의 300dpi OCR + 납부확인서마다 OCR 재사용 재판독 3회). 회귀·다른 측정과 동시에 돌리지 않는다.

## 5. 마무리 보고 후 멈춤

가~마 답(파일:행), 커밋 목록(해시·시각·파일·다섯 패턴)과 회귀 결과, 진의 명령, 나·라·마 결과에 따른 수정 제안(구현은 승인 후)을 표로 보고한다.

## 되돌리기

각 커밋은 새 파일 추가다. 되돌릴 때는 `git revert <hash>` (amend 금지).
