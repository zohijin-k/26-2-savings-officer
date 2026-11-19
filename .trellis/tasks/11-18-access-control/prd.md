# 두배적금 백엔드 접근 제어

Source: 팀장 요청 2026-11-18 — 프로젝트 점검에서 찾은 "두배적금 백엔드에 접근 제어가 없음"을 먼저 고치기로 함("접근 제어부터").

## Goal

두배적금 통합 백엔드(이 저장소 `demo/backend`)에서 신청자는 자기 신청만 읽고 바꿀 수 있고, 담당자는 로그인한 뒤에만 신청 목록·심사 상세·원본 서류를 볼 수 있게 한다. 신청자·담당자 화면의 흐름과 판정 결과는 그대로 둔다.

## Background

- 2026-11-18 로컬 서버(이 저장소 백엔드, 합성 데이터)에 쿠키 없이 보낸 요청의 결과다. youth 백엔드는 같은 종류의 요청에 401(담당자)·403(신청)을 낸다.
  - `GET /api/officer/applications` → 200, 전체 3건
  - `GET /api/applications/1` → 200, `identity_json`에 성명·생년월일
  - `GET /api/files/{문서번호}` → 200, 원본 PDF
- 신청을 만들 때 소유자 토큰의 해시를 `Application.applicant_access_hash`에 저장하고 쿠키 `applicant_access_{id}`를 `path=/api/applications/{id}/forms/files`로 발급한다(`demo/backend/api/applications.py:205`). 이 쿠키를 검사하는 곳은 작성 서식 PDF 한 곳뿐이다(`demo/backend/api/forms.py:571`).
- 신청 번호(`Application.id`)와 문서 번호는 1부터 매기는 순번이다.
- 신청자 프런트(`26-2-savings-applicant/demo/frontend`)는 `/api/applications…`, `/api/programs…`를 부르고, 업로드 미리보기와 마이페이지에서 `file_url`(`/api/files/{문서번호}`)을 연다(`DocumentUpload.tsx:449`, `MyPage.tsx:191`).
- 담당자 프런트(이 저장소 `demo/frontend`)는 `/api/officer…`와 `/api/files/{문서번호}`만 부르고 로그인 화면이 없다. `?mock=1`이면 백엔드를 부르지 않는다(`demo/frontend/src/api.ts:188`).
- youth가 같은 문제를 이미 풀었다. 옮겨 올 출처는 다음과 같다.
  - `demo/backend/officer_auth.py`, `demo/backend/generic_access.py`
  - `demo/backend/tests/security_support.py`, `demo/backend/tests/test_security_access.py`
  - `demo/frontend/src/officer-session.ts`, `demo/frontend/src/pages/officer/OfficerSession.tsx`
- 이 저장소에서 HTTP로 담당자·원본 API를 부르는 시험·시나리오 파일은 16개다.
- 신청자 API 파일(`api/applications.py`, `api/forms.py`, `api/files.py` 등)은 신청자 저장소와 내용이 같고, 한쪽을 고치면 다른 쪽에도 반영하는 것이 규칙이다(`.trellis/spec/backend/unified-backend.md`).

## Decisions

- **D1 저장소 범위 (사용자 결정)**
  - 접근 제어는 전부 이 저장소에 넣는다.
  - 신청자 저장소는 `api/applications.py`의 소유자 쿠키 경로 한 줄과 연결 실행 안내만 같이 고쳐, 두 저장소의 신청자 API 파일을 같게 유지한다.
  - 신청자 저장소 백엔드를 따로 띄우면 검사는 없다.
- **D2 설정이 없을 때 (사용자 결정)** — youth처럼 막는다. `OFFICER_PASSWORD`나 `OFFICER_SESSION_SECRET`이 비어 있으면 로그인을 포함한 담당자 경로 전체가 503이고 설정 안내를 낸다. 신청자 화면과 `?mock=1`은 영향이 없다.
- **D3 이전에 만든 작성 중 신청 (계획 승인 때 확인)** — 이전 쿠키를 넓혀 주는 이전 기능을 만들지 않는다. 이 변경 전에 만든 작성 중 신청은 403이 나므로 새 탭에서 다시 시작한다. 근거는 `design.md` 4절에 있다.

## Requirements

- **R1 담당자 로그인**
  - `/api/officer`로 시작하는 모든 경로(앞으로 생길 경로 포함)는 로그인한 담당자만 쓸 수 있다. `POST /api/officer/login`만 예외다.
  - 비밀번호와 세션 서명값은 `.env`의 `OFFICER_PASSWORD`, `OFFICER_SESSION_SECRET`으로 정한다(D2).
  - 세션은 8시간이고, 로그인 5회 실패 시 60초 잠금, 로그아웃 시 토큰 폐기를 youth와 같게 둔다.
- **R2 신청자 소유자 확인**
  - `/api/applications/{id}/…`의 모든 경로(32개)는 그 신청의 소유자 쿠키가 있어야 한다.
  - 신청 만들기 응답은 쿠키를 `path=/api`로 발급한다(D1).
  - `POST /api/applications`, `/api/programs…`, `/api/health`는 지금처럼 공개다.
- **R3 원본 서류** — `GET /api/files/{문서번호}`는 그 서류가 속한 신청의 소유자나 로그인한 담당자만 열 수 있다. 담당자 세션은 신청자 경로를 열어 주지 않는다.
- **R4 담당자 화면 로그인**
  - 담당자 프런트에 로그인 화면(비밀번호 한 칸)과 로그아웃 버튼이 있다.
  - 로그인하면 보던 주소가 그대로 열리고, 세션이 끝나면 로그인 화면으로 돌아간다.
  - 서버 설정이 없으면 설정 안내를 보여 준다. `?mock=1`은 로그인 없이 그대로다.
- **R5 판정·응답 불변** — 판정, 저장 값, 응답 내용은 바뀌지 않는다. 기존 시험에는 인증 단계만 더하고 기대값은 고치지 않는다. 고친 시험 파일은 `changed-tests.md`에 남긴다.
- **R6 막힘 확인 시험** — 다음 경우가 막히는 것을 새 시험으로 남긴다.
  - 쿠키 없음, 다른 신청의 쿠키, 정수 다른 표기
  - 로그인 안 한 담당자, 만료·위조·폐기된 세션, 설정 없음
- **R7 문서** — 다음을 고친다(목록은 `design.md` 6절).
  - 이 저장소의 실행 명령(`--env-file .env`), `.env.example`, 연결 실행 안내, 백엔드·프런트 규격
  - 신청자 저장소의 연결 실행 안내와 규격

## Acceptance Criteria

- **AC1 (R1–R3)** 쿠키 없이 보낸 `GET /api/officer/applications`, `GET /api/applications/{id}`, `GET /api/files/{문서번호}`가 각각 401, 403, 403이다. 비밀번호 설정이 없으면 첫 번째가 503이다.
- **AC2 (R2, R3, R6)** 다른 신청의 소유자 쿠키로 읽기·쓰기 요청을 보내면 403이다. 신청자 경로 32개와 담당자 경로 전부를 새 시험이 하나씩 확인한다.
- **AC3 (R4)** 연결 실행(8000, 5173, 5174)의 실제 화면에서 다음이 지금처럼 동작한다. 로그아웃 뒤에는 담당자 화면이 다시 로그인을 요구한다.
  - 신청자: 본인인증부터 제출과 마이페이지까지
  - 담당자: 로그인, 목록, 상세, 원본 열람, 결정
- **AC4 (R5)** 백엔드 시험과 시나리오 18개가 이 PC의 바꾸기 전 기준선 대비 새 실패 없이 통과한다. 담당자 프런트의 `tsc`·`oxlint`·`vite build`·단위 시험이 통과한다. 신청자 저장소 백엔드 시험도 11-17 기준선 대비 새 실패가 없다.

## Out of Scope

- 담당자 개인 계정과 역할별 권한. 역할·지역 선택은 지금처럼 로그인 뒤 화면 범위를 고르는 것이다.
- HTTPS 배포, CSRF 토큰 등 운영 환경 보안 전반.
- 이전에 만든 작성 중 신청을 이어 쓰게 하는 쿠키 이전(D3).
- 신청자 저장소 백엔드의 접근 제어(D1), youth 저장소 변경.
