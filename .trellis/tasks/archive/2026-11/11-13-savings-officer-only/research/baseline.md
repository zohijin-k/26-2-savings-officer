# 작업 전 기준선 (2026-11-13)

## 실행 상태
- git main e449c55 (`chore(task): archive 11-13-verify-cases`), 세션 시작 시 작업 트리 clean.
- Python 3.14.6 (.venv), pytest 9.2.0, Node v26.13.1. 기존 설치 사용; 의존성/엔진/시험 파일 변경 없음.
- 합성 fixture/임시 DB/storage만 사용. 실제 서류를 열지 않았고 금지된 데이터 디렉터리의 파일 조회·시험 입력을 수행하지 않음. 시나리오 --live와 실제 DB reset 미실행.
- JBAI 설정은 시나리오 subprocess에서 제외했다. 네트워크 OCR이나 모델 내려받기 없이 시험 완료.

## 네 갈래 비교
| 구분 | 사용자 기준 | 실제 결과 | 일치 |
| --- | --- | --- | --- |
| engine_v2/tests | 1,264 통과·3 skip | 1,264 통과·3 skip, 92.39초 | 예 |
| demo/backend/tests | 1,227 통과 | 1,227 통과, 89.12초 | 예 |
| 시나리오 | 18개 모듈·1,885 통과·실패 0 | 18개 전부 종료 0·1,885 통과·실패 0 | 예 |
| frontend | lint 경고 1·build 통과 | lint 종료 0/경고 1, build 종료 0 | 예 |

엔진 deprecation warnings 7건, backend warnings 9건. lint 경고는 src/components/StatusBadge.tsx:5의 react(only-export-components)다. build에는 기존 500kB 이상 chunk 크기 안내도 있으며 실패가 아니다. 경고 수를 맞추기 위해 코드나 설정을 바꾸지 않았다.

## 명령
```sh
.venv/bin/python -m pytest engine_v2/tests -q
.venv/bin/python -m pytest demo/backend/tests -q
# 각 run_p*_scenarios.py를 순서대로 아래처럼 별도 subprocess 실행 (18개)
.venv/bin/python -m demo.backend.tests.run_p11_criteria_scenarios
# --live 없음, 모든 모듈 종료코드 수집
cd demo/frontend
npm run lint
npm run build
```

## 시나리오 개별 결과
통과/실패는 각 모듈이 마지막에 출력한 수치다. P14는 숫자 통과 카운터가 없어 모듈 성공으로 별도 확인하며 1,885 합계에 임의로 더하지 않는다.

| 모듈 | 통과 / 실패 | 종료코드 |
| --- | --- | --- |
| run_p11_criteria_scenarios | 38 / 0 | 0 |
| run_p12_subsidy_criteria_scenarios | 29 / 0 | 0 |
| run_p13_household_scenarios | 26 / 0 | 0 |
| run_p14_pdf_forms_scenarios | 수치 합계 미출력; 8개 서식 검증 완료 | 0 |
| run_p15_jbai_scenarios | 129 / 0 | 0 |
| run_p16_job_docs_scenarios | 96 / 0 | 0 |
| run_p17_own_scenarios | 75 / 0 | 0 |
| run_p18_applicant_precheck_scenarios | 180 / 0 | 0 |
| run_p19_nhis_history_scenarios | 24 / 0 | 0 |
| run_p20_nhis_continuation_scenarios | 7 / 0 | 0 |
| run_p2_scenarios | 53 / 0 | 0 |
| run_p3_scenarios | 186 / 0 | 0 |
| run_p4_scenarios | 189 / 0 | 0 |
| run_p5_scenarios | 152 / 0 | 0 |
| run_p6_scenarios | 261 / 0 | 0 |
| run_p7_scenarios | 253 / 0 | 0 |
| run_p8_localocr_scenarios | 89 / 0 | 0 |
| run_p9_identity_scenarios | 98 / 0 | 0 |

## 실행 원본 로그
검증 원본은 /tmp/savings-officer-baseline-engine.log, -backend.log, -lint.log, -build.log 및 -run_p*_scenarios.log에 있다. 머신 임시 파일이라 커밋하지 않는다. 시나리오 종료코드/로그 위치 JSON은 baseline-scenarios.json에 함께 기록했다.

## 이번 턴 변경
제품·시험·README 변경 없음. planning 태스크 및 Codex workspace 초기화 파일만 생성. git diff --stat main은 추적 중 파일 변경이 없어 출력이 없다 (신규 planning 파일은 git status --short로 별도 확인). 이것은 커밋 승인 요청이 아니며 구현 후 동일 비교와 stat을 다시 제시한다.
