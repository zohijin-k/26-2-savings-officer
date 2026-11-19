# 설계: 두배적금 백엔드 접근 제어

youth에서 이미 쓰고 있는 방식(`officer_auth.py`, `generic_access.py`)을 이 저장소에 맞게 줄여 옮긴다. 판정·저장·응답 내용은 손대지 않고, 요청이 라우터에 닿기 전에 ASGI 미들웨어 두 개가 막는다.

## 1. 경계

| 경로 | 누가 쓸 수 있나 | 막힐 때 |
|---|---|---|
| `/api/health`, `/api/programs`, `/api/programs/{code}`, `/api/programs/{code}/criteria` | 누구나 | — |
| `POST /api/applications` (신청 만들기) | 누구나. 응답에 소유자 쿠키를 심는다 | — |
| `/api/applications/{id}/…` (32개) | 그 신청의 소유자 쿠키 | 403 |
| `GET /api/files/{문서번호}` | 그 서류가 속한 신청의 소유자, 또는 로그인한 담당자 | 403 |
| `/api/officer/…` (담당자 9개, 로그인·세션·로그아웃 3개) | 로그인한 담당자. `POST /api/officer/login`만 예외 | 401 (설정 없음은 503) |

- 경로 수는 2026-11-18 앱 등록 경로 47개 기준이다. 접근 제어 뒤에는 로그인·세션·로그아웃 3개가 더해져 50개가 된다.
- 신청 번호가 없거나 정수가 아닌 경로, 없는 신청·서류는 403이다. 존재 여부를 응답으로 구분하지 않는다.
- 담당자 세션은 원본 GET만 열어 준다. 담당자라도 신청자 경로의 읽기·쓰기는 할 수 없다(담당자 화면은 이 경로를 부르지 않는다).

## 2. 구성 요소

### 백엔드 (이 저장소)

- **`demo/backend/officer_auth.py` (새 파일)** — youth 파일을 그대로 옮긴다.
  - `POST /api/officer/login`: `OFFICER_PASSWORD`와 상수 시간 비교. 성공하면 서명 쿠키 `officer_session`(`발급.만료.난수.서명`, HMAC-SHA256, 8시간, `path=/api`, HttpOnly, SameSite=Lax, https면 Secure).
  - 같은 접속 주소에서 5회 실패하면 60초 동안 429.
  - `GET /api/officer/session`: 세션 만료 시각 또는 401. `POST /api/officer/logout`: 토큰을 폐기 목록에 넣고 쿠키를 지운다.
  - `OfficerAccess` 미들웨어: `/api/officer`와 그 아래 모든 경로(앞으로 생길 경로 포함)를 막는다. `OFFICER_PASSWORD`나 `OFFICER_SESSION_SECRET`이 비어 있으면 로그인을 포함한 전체가 503이다.
- **`demo/backend/applicant_access.py` (새 파일)** — youth `generic_access.py`에서 범용 사업, 공개 빈 서식, 이전 쿠키 넓히기, 쓰기 잠금을 뺀 것이다.
  - 경로의 신청 번호(또는 문서 번호 → 신청 번호)를 FastAPI와 같은 정수 규칙(`TypeAdapter(int)`)으로 읽는다. `+1`, `1.0` 같은 다른 표기도 같은 신청으로 보고 검사한다.
  - 쿠키 `applicant_access_{id}`의 SHA-256을 `Application.applicant_access_hash`와 `hmac.compare_digest`로 비교한다.
  - 막을 때 응답: 403, `{"detail": "신청자 본인만 접근할 수 있습니다."}`, `Cache-Control: private, no-store`.
- **`demo/backend/main.py`** — `officer_auth.router`를 등록하고, CORS 다음에 `ApplicantAccess`, 그다음 `OfficerAccess`를 붙인다(youth와 같은 순서. 담당자 검사가 가장 바깥).
- **`demo/backend/api/applications.py`** — 신청 만들기 응답의 쿠키 경로를 `/api/applications/{id}/forms/files`에서 `/api`로 바꾼다(한 줄). 신청자 저장소의 같은 파일도 같은 한 줄을 바꿔 두 파일을 같게 둔다(D1).
- `api/forms.py`의 작성 서식 PDF 소유자 검사(`_require_applicant_archive_access`)는 그대로 둔다. 미들웨어를 통과한 뒤 한 번 더 확인하는 셈이고, 두 저장소의 같은 파일을 건드리지 않는다.

### 담당자 프런트 (이 저장소)

- **`src/officer-session.ts` (새 파일)** — `/api/officer/…` 응답이 401·503이면 `officer-session-expired` 이벤트를 낸다(youth와 같은 함수).
- **`src/api.ts`** — 공통 `json()`이 오류를 던지기 전에 위 함수를 부른다.
- **`src/pages/officer/OfficerSession.tsx` (새 파일)** — 화면 진입 때 `GET /api/officer/session`으로 확인한다.
  - 로그인돼 있으면 담당자 화면을 그리고, 머리글 오른쪽에 "로그아웃" 버튼을 둔다.
  - 아니면 같은 주소에서 로그인 칸(비밀번호 한 칸)을 보여 준다. 따로 로그인 주소를 만들지 않아서, 로그인하면 보던 주소(목록, `/officer/review/{id}`)가 그대로 열린다.
  - 503이면 서버가 준 설정 안내를 보여 준다. 세션 만료 이벤트나 만료 시각이 오면 로그인 칸으로 돌아간다.
  - `?mock=1`이면 아무것도 확인하지 않고 지금 화면을 그린다.
- **`src/App.tsx`** — `OfficerConsole`을 `OfficerSession`으로 감싸고, 머리글에 로그아웃 자리를 둔다.
- 화면 글자는 "담당자 로그인", "담당자 비밀번호", "로그인", "로그아웃"으로 youth와 맞춘다. 색과 글꼴은 이 저장소 토큰(`app-shell.css`, `index.css`)을 쓴다.

### 신청자 프런트 (신청자 저장소)

- 바꾸지 않는다. 신청을 만들 때 받은 쿠키가 `path=/api`라서 이후 모든 요청(업로드 미리보기와 마이페이지의 `/api/files/{문서번호}` 포함)에 자동으로 붙는다.

## 3. 데이터 흐름

1. 신청자 화면 → `POST /api/applications` → 응답 `Set-Cookie: applicant_access_{id}=<토큰>; Path=/api; HttpOnly; SameSite=Lax` (5년).
2. 신청자 화면의 이후 요청 → Vite 프록시(5173 → 8000) → `OfficerAccess`(해당 없음) → `ApplicantAccess`(쿠키 해시 비교) → 라우터.
3. 담당자 화면 → `POST /api/officer/login` → `Set-Cookie: officer_session=…; Path=/api` → 이후 `/api/officer/…`, `/api/files/{문서번호}` 요청에 자동으로 붙는다.
4. 브라우저 쿠키는 포트를 가리지 않는다. 같은 브라우저에서 5173과 5174를 함께 쓰면 두 쿠키가 양쪽에 모두 붙지만, 각 검사는 자기 쿠키만 본다.

## 4. 호환성과 이전

- **이 변경 전에 만든 작성 중 신청 (D3)** — 브라우저에 좁은 경로의 쿠키만 있어 새 검사에 막힌다. 이전 쿠키는 서식 파일 경로 요청에만 실려 오는데, 신청자 화면이 이어 쓰기 때 먼저 부르는 신청·상태 조회에는 실리지 않는다. 그래서 youth처럼 서식 파일 요청 때 쿠키를 넓혀 주는 방식으로는 이어 쓰기를 보장할 수 없다. 새 탭에서 신청을 다시 시작한다. 시연 데이터는 `seed_officer_demo`, `seed_application`으로 다시 만든다.
- **실행 방법** — 이 저장소 백엔드는 `.env`에 `OFFICER_PASSWORD`, `OFFICER_SESSION_SECRET`이 있어야 담당자 화면을 쓸 수 있다(D2). 실행 명령은 `python -m uvicorn demo.backend.main:app --env-file .env --reload --port 8000`으로 바꾼다. 신청자 화면과 `?mock=1`은 설정 없이도 지금처럼 동작한다.
- **DB** — 모델과 표는 바뀌지 않는다. `applicant_access_hash`는 이미 있는 칸이다.
- **되돌리기** — 미들웨어 두 줄과 라우터 한 줄을 빼면 지금 동작으로 돌아간다. 쿠키 경로 `/api`는 되돌리지 않아도 기존 동작에 영향이 없다.

## 5. 시험

- **`demo/backend/tests/security_support.py` (새 파일)** — youth 도우미를 그대로 옮긴다.
  - `authenticate_officer(client, monkeypatch)`: 시험 전용 합성 비밀번호로 실제 로그인 경로를 통과한다.
  - `claim_synthetic_application(client, id)`: DB에 직접 만든 합성 신청에 시험용 소유자 쿠키를 준다.
- **`demo/backend/tests/test_access_control.py` (새 파일)** — youth `test_security_access.py`에서 이 저장소 경로에 맞는 시험을 옮긴다.
  - 신청자 경로 32개 각각이 쿠키 없음과 남의 쿠키를 403으로 막는다.
  - 원본은 소유자와 담당자에게만 열린다.
  - 정수 다른 표기와 토큰 없는 옛 신청이 막힌다.
  - 담당자 경로 전부가 세션을 요구한다.
  - 만료·위조·로그아웃 뒤 재사용이 막히고, 5회 실패하면 잠긴다.
  - 비밀번호가 없으면 담당자 경로 전체가 503이다.
  - 서명값이 없을 때와 https일 때 쿠키 속성이 맞다.
  - 공개 경로는 쿠키 없이 열린다.
- **기존 시험·시나리오** — 401·403에 걸리는 곳에 위 두 도우미 호출만 더한다. 응답 기대값은 바꾸지 않는다. 고친 파일 목록은 `changed-tests.md`에 남긴다.
- **프런트** — `tests/officer-session.test.ts`로 이벤트 함수를 확인한다(로그인 경로 제외, 401·503만, 담당자 경로만).

## 6. 문서와 규격

- 이 저장소
  - `README.md`, `docs/DEVELOPMENT.md`: `.env` 설정, 실행 명령, 연결 실행 안내의 로그인 단계를 고친다.
  - `.env.example`: `OFFICER_PASSWORD`, `OFFICER_SESSION_SECRET`을 추가한다.
  - `.trellis/spec/backend/access-control.md`: 새 규격(7절)을 만들고 색인에 넣는다.
  - `unified-backend.md`: 연결 실행에 `.env`와 로그인이 필요하다는 점, 소유자 쿠키 경로를 반영한다.
  - `.trellis/spec/frontend/officer-documents.md`: 로그인 화면을 한 절 추가한다.
- 신청자 저장소: `api/applications.py` 한 줄, `docs/DEVELOPMENT.md`와 `README.md`의 연결 실행 안내, `.trellis/spec/backend/applicant-submission.md`의 "Second copy" 절.
- 작업 폴더(저장소 밖): `.claude/launch.json`의 `savings-link-backend`에 `--env-file`을 추가한다. 이 PC용 `26-2-savings-officer/.env`에 합성 개발 비밀번호를 넣는다(gitignore 대상, 커밋하지 않음).
