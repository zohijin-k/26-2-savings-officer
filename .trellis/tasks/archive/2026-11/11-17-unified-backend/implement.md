# 실행 계획 — 신청자·담당자 연결 (백엔드 통합)

브랜치 `feat/unified-backend`(`main` f6d9827에서 분기). 명령은 저장소 루트에서 실행하고, Windows Git Bash에서는 앞에 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`을 붙인다. 이 세션에는 Trellis 하위 에이전트가 없어 인라인 흐름(`trellis-before-dev` → 구현 → `trellis-check` → `trellis-update-spec`)을 쓴다.

세 저장소가 같은 폴더에 나란히 있어야 한다: `../26-2-savings-applicant`(614dd7b), `../26-2-capstone`(태그 `archive/main-before-split`).

## 검토 관문

- **G0** 이 계획 승인 → `task.py start 11-17-unified-backend`. 그 전에는 제품 코드와 시험을 고치지 않는다.
- **G1** 바뀌는 기존 시험과 기대값은 `changed-test-expectations.md`에 적힌 것뿐이다. 그 밖의 기대값을 바꿔야 하면 먼저 그 파일에 적고 알린다.
- **G2** 시험에서 양쪽 정책이 어긋나는 곳이 나오면 고치지 않고 멈춰서 묻는다. 기대값을 맞추려고 판정이나 신청자 경계를 바꾸지 않는다.
- **G3** 커밋·push·PR은 팀장이 한다.

## 순서

### 0. 준비
- [x] `trellis-before-dev`: `.trellis/spec/backend/index.md`, `failure-filtering.md`, `document-form-contracts.md`, 신청자 저장소의 `applicant-submission.md`
- [x] 변경 전 기준은 `research/findings.md` 7절에 있다(같은 PC, 두 저장소)

### 1. 병합 적용 (R1, R2, R4, R5)
- [x] `python .trellis/tasks/11-17-unified-backend/apply_merge.py plan`으로 목록이 계획과 같은지 확인(가져올 42, 새로 들일 3, 병합 8, 정할 것 0)
- [x] `apply`로 한 번에 적용한다. 제품 코드 5개(교체 3, 병합 2), 시험 33개(교체 27, 추가 2, 병합 4), 시연 기대값 9개, 백엔드 규격 6개(교체 3, 추가 1, 병합 2)다
- [x] `check`로 대조하고, `git diff --stat`으로 `engine`, `engine_v2`, `demo/frontend`에 변경이 없는지 확인

### 2. 이 저장소 시험 고침 (R5)
- [x] `test_payment_paging.py`, `test_payment_paging_refinement.py`, `test_quality_assessment_parity.py`의 단언 6곳을 고친다. 업로드 응답 상태 4곳은 `assert_upload_status`로, 목록 응답 상태 2곳은 업로드 응답과 같은지 확인하도록 바꾼다(`changed-test-expectations.md`의 B 표)

### 3. 시험 (AC2, AC3, AC4)
- [x] 엔진 → 백엔드 → 시나리오(`--continue-on-collection-errors`), 실패 이름 목록을 두 기준과 비교
- [x] 설명되지 않는 새 실패는 원인을 찾는다. 병합이 만든 문제면 고치고, 정책이 어긋난 것이면 G2
- [x] `test_officer_frontend_integration.py`가 실제 저장소에서 통과하는지 확인(사본에서는 `node_modules`가 없어 확인하지 못했다)
- [x] 담당자 프런트: `cd demo/frontend && npx tsc -b && npx oxlint && npx vite build && npm test`

### 4. 규격과 문서 (R6, R8)
- [x] `trellis-update-spec`: 옮겨 온 백엔드 규격을 읽어 합친 동작과 맞는지 확인하고, 연결 실행 구성(백엔드 하나에 프런트 둘, 신청자 API가 이 저장소에도 있다는 점)을 기록
- [x] `README.md`, `docs/DEVELOPMENT.md`: 연결 실행 절(백엔드 8000, 신청자 프런트 5173, 담당자 프런트 5174)과 신청자 API를 고칠 때의 주의

### 5. 실제 화면 확인 (R7, AC5)
- [x] 임시 DB·임시 저장 폴더를 쓰는 격리 서버(저장소 밖 스크립트)에 두 프런트를 붙인다
- [x] 합성 서류(`demo/fixtures/samples`의 적합 묶음)로 본인인증 → 서식 작성 → 업로드 → 제출
- [x] 담당자 목록·상세에 그 신청이 보이는지, 담당자 결정이 신청자 마이페이지에 보이는지 확인
- [x] 신청자 응답에 내부 판정이 없는지 응답 본문으로 확인
- [x] 문서의 명령으로 실제 구성이 뜨는지 확인(자료는 쓰지 않음)

### 6. 마무리
- [x] `trellis-check`
- [x] `report.md`: 병합 결과, 시험 비교, 화면 확인, 이 PC에서 확인하지 못한 것
- [x] 커밋 단위와 PR 본문 정리(G3). 커밋은 팀장이 한다
- [ ] 신청자 저장소의 문서 안내는 이 PR이 병합된 뒤 별도 태스크로 한다(D3)

## 검증 명령

```bash
python .trellis/tasks/11-17-unified-backend/apply_merge.py check
python -m pytest engine_v2/tests -q --continue-on-collection-errors
python -m pytest demo/backend/tests -q --continue-on-collection-errors
for f in demo/backend/tests/run_p*_scenarios.py; do
  python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"
done
cd demo/frontend && npx tsc -b && npx oxlint && npx vite build && npm test
```

## 위험한 지점

- `api/review.py`의 `_run_review`: 신청자 저장소 것은 분리 전 `engine_adapter`에 맞춰 쓴 코드다. 이 저장소의 `engine_adapter`(화질 등급, 대체 서류 선택)와 함께 도는지는 `test_review_regressions.py`, `test_quality_failure_policy.py`, `test_quality_assessment_parity.py`로 본다. 저장소 밖 사본에서는 통과했다.
- `api/common.py`: 신청자 쪽 `applicant_findings`와 이 저장소의 `document_fact` 한 줄이 한 파일에 들어간다. `document_fact`의 `findings`는 내부용이고 신청자 응답에 실리지 않아야 한다.
- 금지어 검사(P4): 가져온 파일에 `download`, `attachment`가 허용 목록 밖에 있으면 실패한다. 사본에서는 통과했다.
- 서식 좌표 JSON(`demo/fixtures/form_coords`)은 손대지 않는다.
- 이 PC에서는 `fcntl`을 쓰는 13개 시험 모듈을 돌릴 수 없다. 백엔드 쪽은 `test_payment_stage2_routes.py` 하나다.
