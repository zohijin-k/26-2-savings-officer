# 실행 계획 — 구현 완료, 커밋 승인됨

## 순서와 승인 지점
- [x] 사용자 요청에 따라 Trellis planning 태스크 생성, 범위·조사 기록.
- [x] 제품 코드 변경 전 네 갈래 기준선 실행·일치 확인 (research/baseline.md).
- [x] PRD·설계·실행계획·시험 영향 목록 작성. PRD를 최종 구조로 재작성하고 중복/누락을 검토함.
- [x] 최신 계획, 새 시드 도구, phone.test.ts 삭제 승인 확인 (2026-11-13). 다른 기존 시험은 수정하지 않는다.
- [x] 승인 뒤 task.py start 실행 및 feat/savings-officer-only 브랜치 생성. 승인 전 start·제품 코드 편집·커밋 금지.
- [x] Phase 2의 trellis-before-dev로 관련 spec 읽기. 저장소의 dispatch 정책을 따르는 경우 implement/check에 태스크 경로와 curated manifests 전달. 현재 조사 단계에서는 하위 에이전트 미사용.
- [x] App.tsx/navigation-url.ts/문서 title을 담당자 전용으로 바꾸고 신청자 페이지·전용 코드·링크 제거. 글꼴·백엔드 자산 보존.
- [x] double_savings/province 고정 조회, 전체 신청 페이지 취합, 서류 단위 PASS/그 외 두 목록 구현. 역할/기준관리/타 사업 메뉴·필터·목업 분기 정리.
- [x] 상세 선택에 문서 ID를 연결하고 원본/기존 사유 2단 표시. 없는 원본/문서·다른 사업의 직접 URL·새로고침 확인.
- [x] 새 도구가 승인된 경우에만 research/demo-data.md의 최소 seed_officer_demo 구현. 기존 seed_application, 판정기, 모델, 기존 시험 기대값은 유지.
- [x] 루트 README 재작성, docs/DEVELOPMENT.md·demo/README.md 최소 갱신. 승인된 시연 명령을 실제 합성 데이터로 확인.
- [x] 프런트 분류/선택/URL과 승인된 시드의 데이터 소유권·재실행·정리 검증. 기존 시험은 research/test-impact.md 승인 내역대로만 변경.
- [x] 전체 spec/교차 계층 검토 및 필요한 새 지식을 spec에 영어로 최소 기록.
- [x] 네 갈래 검증 재실행, 변경 전후 표·기존 시험 변경/삭제 목록·git diff --stat main·커밋 파일/메시지 계획 제시.
- [x] 사용자 커밋 승인 확인 (2026-11-13: commit apply). 승인 전 git add/commit/push 하지 않음. 커밋 승인 후에도 push하지 않음.

## 검증 명령
저장소 루트의 기존 .venv를 사용한다. 환경 설치/모델 내려받기는 이번 기준선에 필요하지 않았다.

```sh
.venv/bin/python -m pytest engine_v2/tests -q
.venv/bin/python -m pytest demo/backend/tests -q
```

시나리오는 Python subprocess로 demo/backend/tests/run_p*_scenarios.py 18개를 각각 `-m demo.backend.tests.<stem>`으로 실행한다. 한 모듈 실패 뒤에도 계속 실행하고 종료코드와 마지막 통과/실패 수를 모은다. P14는 수치 합계 대신 완료 메시지와 종료코드로 검증한다. --live는 절대 붙이지 않는다.

```sh
cd demo/frontend
npm run lint
npm run build
```

화면 동작 검증: / 진입, 옛 /apply 진입, 뒤로/앞으로/새로고침, 신청자/취업지원 요소 제거, 같은 신청 안의 PASS와 FAIL/NEEDS_REVIEW 분리, null 및 미배정 페이지, 중복 슬롯의 정확한 ID 선택, 두 번째 API 페이지 누락 없음, 빈 목록/API 실패 구별, 원본 인라인 표시, 사유 원문 유지. 조회/화면 분류 전후 기존 Application/Document/Review 상태와 사유가 바뀌지 않는지도 확인한다.

프런트 기존 전화번호 시험 삭제 승인이 없으면 phone.ts와 phone.test.ts를 보존한다. 새 분류 모델에 의미 있는 합성 회귀 검증을 추가할 때 기존 네 갈래 수치와 별도로 보고한다. 시드 도구를 추가하면 관련 새 시험 수는 별도 가산해 설명한다. baseline 수치를 맞추기 위한 기존 시험 삭제·기대값 수정은 금지한다.

## 커밋 전 보고 형식
1. `git diff --stat main` 원문 및 `git status --short`의 untracked 파일 목록 (stat에 새 파일이 빠질 수 있음).
2. engine_v2 / backend / scenario / frontend의 before-after 표. 새 시험 증가와 승인된 삭제를 분리.
3. 파일·시험 이름·이유·승인 메시지로 시험 변경/삭제 원장. 화면 제거 묶음 별도 표시.
4. AI 변경 파일과 세션 전/사용자 변경 파일을 구분한 커밋 계획 후 승인 대기.

초기 기준: main e449c55, clean. 현재 planning 파일 외 소스 변경 없음. 태스크 생성은 작업 시작 승인이 아니다.

## 최종 상태
구현·spec 갱신·네 갈래 검증 완료. research/commit-review.md에 diff stat, 삭제 파일/라우트, 실제 CLI 결과 및 검수 제한을 기록했다. 사용자 커밋 승인 대기. 브라우저 시각 검수는 도구 호스트 불가로 수행하지 못했으며 실제 React 렌더 통합 시험으로 목록 분류를 확인했다.

## 커밋 승인
2026-11-13 사용자가 `commit apply`로 제안된 작업 커밋을 승인했다. 작업 커밋 후 Trellis archive/journal 기록을 진행하며 push는 하지 않는다.
