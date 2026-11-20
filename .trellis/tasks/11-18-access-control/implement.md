# 실행 계획: 두배적금 백엔드 접근 제어

## 순서

1. [ ] **기준선** — 바꾸기 전 이 저장소 `main`(7f39c36)의 백엔드 시험과 시나리오 18개 결과를 이 PC에서 저장한다(엔진은 바꾸지 않으므로 제외). 신청자 저장소는 11-17 기준선(614dd7b, 이후 문서만 바뀜)을 쓴다.
2. [ ] **백엔드** — `officer_auth.py`, `applicant_access.py`를 추가하고 `main.py`에 등록한다. `api/applications.py`의 쿠키 경로를 `/api`로 바꾼다.
3. [ ] **새 시험** — `tests/security_support.py`, `tests/test_access_control.py`.
4. [ ] **기존 시험 정리** — 전체를 돌려 401·403으로 새로 실패한 곳에 도우미 호출만 더한다. 기대값은 바꾸지 않고, 고친 파일은 `changed-tests.md`에 남긴다.
5. [ ] **담당자 프런트** — `officer-session.ts`, `OfficerSession.tsx`, `api.ts`, `App.tsx`, 로그인 화면 스타일, `tests/officer-session.test.ts`.
6. [ ] **신청자 저장소** — `api/applications.py` 한 줄을 같게 바꾸고, 쿠키 관련 시험(`run_p4`, `run_p7`, 작성 서식 PDF 시험)과 백엔드 전체를 11-17 기준선과 비교한다.
7. [ ] **문서와 규격** — 설계 6절의 목록.
8. [ ] **작업 폴더 설정** — `launch.json`의 `--env-file`, 이 PC용 `.env`(합성 값).
9. [ ] **실제 화면 확인** — 연결 실행(8000, 5173, 5174).
   - 신청자: 본인인증부터 서류 업로드·제출, 마이페이지까지.
   - 담당자: 로그인, 목록, 상세, 원본 열람, 결정, 로그아웃.
   - 쿠키 없는 요청이 401·403인지 확인한다.
10. [ ] **점검** — `trellis-check`. 금지어(`download`, `attachment`)와 보호 원칙을 확인한다.

## 확인 명령 (저장소 루트)

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -B -m pytest demo/backend/tests -q -p no:cacheprovider --continue-on-collection-errors
for f in demo/backend/tests/run_p*_scenarios.py; do python -B -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
cd demo/frontend && npx tsc -b && npx oxlint && npx vite build && npm test
```

- 결과는 기준선과 실패 이름으로 비교한다. 이 PC에는 원래 실패하는 시험이 있다(Windows의 `fcntl`, 심볼릭 링크 권한, 출력 차단 함수).
- 판정 기준은 두 가지다. 새 실패가 0이어야 하고, 기준선에서 통과하던 시험이 모두 통과해야 한다.

## 위험한 곳

- **기존 시험 수** — 401·403에 걸리는 시험이 많을 수 있다. 도우미 호출만 더하고, 기대값을 고치고 싶어지면 멈추고 보고한다.
- **`test_officer_frontend_integration.py`** — 실제 프런트 빌드를 쓰므로, 로그인 칸이 목록보다 먼저 그려지는지 확인한다(`?mock=1` 경로).
- **P4 시나리오** — `demo/` 아래 새 코드와 주석에 금지어를 쓰지 않는다.
- **같은 브라우저의 두 화면** — 쿠키가 포트를 가리지 않으므로 담당자 세션이 신청자 탭에도 붙는다. 신청자 경로는 담당자 세션을 인정하지 않으니 문제는 없지만, 화면 확인 때 따로 본다.

## 되돌리기

- 백엔드: `main.py`의 미들웨어 두 줄과 라우터 한 줄을 빼면 이전 동작이다.
- 프런트: `App.tsx`에서 `OfficerSession` 감싸기를 빼면 이전 화면이다.
