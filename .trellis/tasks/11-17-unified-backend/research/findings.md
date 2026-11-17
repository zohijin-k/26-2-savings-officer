# 조사 기록 — 신청자·담당자 연결 (2026-11-17)

비교 대상: 이 저장소 `main` f6d9827(O), `26-2-savings-applicant` `main` 614dd7b(A), 분리 전 코드인 허브 `26-2-capstone` 13d8752(B). 세 저장소를 같은 PC에 나란히 받아 놓고 파일 단위로 비교했다.

## 1. 지금 이어지지 않는 이유

- 두 백엔드 모두 DB와 저장 폴더를 자기 저장소 안의 고정 경로로 쓴다: `demo/backend/models.py:17` `DB_PATH = …/demo/demo.db`, `demo/backend/api/common.py:26` `STORAGE = …/demo/storage`. 환경 변수로 바꾸는 길은 없다.
- 서류 경로는 `storage/documents/…` 형태의 상대 경로로 저장된다(`api/documents.py:237`).

## 2. 두 백엔드가 같은 것

- `main.py`, `models.py`, `api/officer.py`, `api/forms.py`, `api/files.py`가 A, O, B에서 모두 같다. DB 표 구조도 같다(두 저장소의 `demo.db`를 `pragma table_info`로 비교).
- API 경로 42개가 같다(`@router` 데코레이터 목록 비교).
- 담당자 목록은 초안이 아닌 신청을 모두 읽는다: `api/officer.py:215` `select(Application).where(Application.status != STATUS_DRAFT)`. `Review`는 제출 때 만든다(`api/review.py`의 `submit` → `_run_review`).
- `api/officer.py`가 다른 모듈에서 가져다 쓰는 것은 `common.checklist_for`, `list_documents`, `list_documents_bulk`, `load_application`, `subsidy_estimate`, `forms.form_links`다. 신청자 쪽이 바꾼 `document_dict`, `applicant_findings`, `review.py`의 함수는 쓰지 않는다.

## 3. 프런트

- 신청자 프런트(`26-2-savings-applicant/demo/frontend/src`)가 부르는 주소: `/api/applications…`, `/api/programs`. 화면 폴더는 `pages/applicant`뿐이다.
- 담당자 프런트(이 저장소)가 부르는 주소: `/api/officer…`, `/api/files/`. 화면 폴더는 `pages/officer`뿐이다.
- 두 프런트 모두 `vite.config.ts`의 `/api` 프록시 기본값이 `http://localhost:8000`이다. 이 PC의 담당자 저장소에는 `VITE_API_TARGET`을 읽는 미커밋 로컬 수정이 있다(이 태스크와 무관, 커밋 대상 아님).
- `main.py`의 CORS 허용 출처는 5173번뿐이지만, 개발 서버 프록시를 거치는 요청은 브라우저 기준으로 같은 출처라 CORS 대상이 아니다.

## 4. 허브 기준 3방향 비교

`demo/backend`(시험 제외)

| 파일 | A | O | 처리 |
|---|---|---|---|
| `api/applications.py`, `api/documents.py`, `api/review.py` | 바꿈 | 그대로 | A 것을 가져온다 |
| `engine_adapter.py`, `ocr/localocr.py`, `rules/doc_check.py`, `upload_assessment.py` | 그대로 | 바꿈 | O 것을 둔다 |
| `tools/seed_officer_demo.py` | 없음 | 새 파일 | O 것을 둔다 |
| `api/common.py`, `tools/verify_upload.py` | 바꿈 | 바꿈 | `git merge-file` 충돌 0 |

`demo/backend/tests`: A만 바꿈 27, A가 추가 2(`test_applicant_submission_policy.py`, `test_applicant_supplement_projection.py`), 양쪽이 바꿈 4(`run_p18_applicant_precheck_scenarios.py`, `test_nhis_recent_history.py`, `test_quality_failure_policy.py`, `test_review_regressions.py`, 모두 충돌 0), O가 추가 6, 같음 34.

`demo/fixtures`(samples 제외): A만 바꿈 9(`expected/S1`~`S8`, `S10`), 나머지 같음.

`engine_v2`: O에만 있는 파이썬 파일 42개, O만 바꿈 2, A는 B와 같다. `engine`: O만 바꿈 2.

`.trellis/spec`: A에만 있음 3(`backend/applicant-submission.md`, `frontend/applicant-ui-foundation.md`, `frontend/upload-queue.md`), A만 바꿈 5, O만 바꿈 1, 양쪽이 바꿈 3(`backend/failure-filtering.md`, `backend/index.md`, `frontend/index.md`), O에만 있음 7.

A 쪽에서 지운 파일, 한쪽이 지우고 다른 쪽이 바꾼 파일은 없다.

같은 비교를 작업 트리 대신 git에 저장된 내용(파일 식별값)으로 다시 해도 결과가 같다: 가져올 파일 42개(제품 코드 3, 시험 27, 시연 기대값 9, 규격 3), 새로 들일 파일 3개(시험 2, 규격 1), 병합할 파일 8개(제품 코드 2, 시험 4, 규격 2), 사람이 정해야 하는 파일 0개.

출처가 되는 커밋. 세 저장소는 분리 직전 커밋 e449c55까지 이력이 같다.

- A가 분리 뒤 `demo/backend`·`demo/fixtures`를 바꾼 커밋은 둘이다: c4179bd `feat(applicant): enforce public reupload policy and server submission guards`, a5c59d7 `test(applicant): preserve review outcomes across three-step submission scenarios`. 기대값을 바꾼 이유는 A의 `.trellis/tasks/archive/2026-11/11-13-savings-applicant-submit/`의 `test-impact.md`, `backend-test-impact.md`, `scenario-test-impact.md`에 시험별로 적혀 있다.
- O가 분리 뒤 같은 범위를 바꾼 커밋: 53c8954, 5c058eb(화질 등급), 500e69d(납부확인서 쪽수), 54dbfe4(시연 신청번호), 96b8e41, dc21a8d.

## 5. 양쪽 변경의 뜻

- A(신청자 응답 경계, `26-2-savings-applicant/.trellis/spec/backend/applicant-submission.md`): 신청자 서류 상태는 `UPLOADED` 또는 `REUPLOAD_REQUIRED`뿐이다. 신청자에게 보이는 사유는 `REUPLOAD_CODES` 10개 가운데 심각도 FAIL인 것뿐이다. 자격 사유, 자가진단 결과 상세, 판독 신뢰도, 판정 기준 안내는 응답에 없다. 최종 확인과 제출은 필수 입력·동의·업로드와 허용 목록의 서류 실패만 막는다. 저장된 판정과 담당자 응답은 그대로다.
- O(화질 등급과 납부확인서 구조): 화질이 기준 미만이어도 종류를 알아봤고 필수 칸을 읽었으면 `LOW_IMAGE_QUALITY`가 NEEDS_REVIEW다(분리 전에는 FAIL). `document_fact`가 저장된 사유를 내부용으로 싣는다(`api/common.py`의 한 줄 추가). 납부확인서 쪽수·완결성 관찰값을 판독 결과에 더한다(`ocr/localocr.py`).
- 맞물림: A의 신청자 필터는 FAIL만 통과시키므로, O가 NEEDS_REVIEW로 낮춘 화질 사유는 신청자에게 보이지 않고 담당자 확인으로 간다. 두 규칙은 글로는 서로 어긋나지 않는다. 실제로 그런지는 합친 사본의 시험으로 확인한다(7절).
- O가 분리 뒤 새로 만든 사유 코드는 `NHIS_PAYMENT_PAGING_UNCERTAIN` 하나다. 안내 문구가 "담당자가 원본과 전체 쪽수를 확인합니다"인 담당자 확인용 코드다(`rules/doc_check.py:59`, `:81`). `doc_check.py`가 새로 참조하는 `ADMIN_CONSENT_MARK_UNREADABLE`, `ADMIN_CONSENT_SIGNATURE_UNREADABLE`, `RECEIPT_OCR_UNAVAILABLE`는 분리 전부터 양쪽에 있던 코드다. 넷 다 A의 허용 목록 10개 밖이라 신청자에게는 보이지 않는다. 쪽수가 모자랄 때의 실패 코드 `PAGES_INCOMPLETE`는 허용 목록에 있다.

## 6. 시험이 프런트 파일을 읽는 곳

`run_p4_scenarios.py`(금지어 허용 목록, 담당자 화면 폴더 검사)와 `run_p7_scenarios.py`가 `demo/frontend` 아래 파일을 읽는다. A의 P4는 신청자 프런트 파일 이름을 허용 목록에 갖고 있다. 합친 사본에서 A의 P4·P7이 이 저장소의 프런트를 상대로 그대로 통과했다(7절). 따로 처리할 것이 없다.

## 7. 이 PC에서의 시험 (2026-11-17)

이 PC는 Windows다. `engine_v2/tools/batch_assess.py:17`의 `import fcntl`(리눅스·맥 전용) 때문에 이 저장소의 엔진 시험 12개 모듈과 백엔드 시험 1개 모듈(`test_payment_stage2_routes.py`)이 수집 단계에서 오류가 난다. 그래서 `--continue-on-collection-errors`로 나머지를 돌렸다. 아래의 실패는 이 작업과 무관한 이 PC의 기존 실패다.

| 대상 | 엔진 | 백엔드 | 시나리오 18개 |
|---|---|---|---|
| 이 저장소 변경 전 (f6d9827) | 103 실패, 1,467 통과, 3 건너뜀, 3 xfail, 오류 12 | 139 실패, 1,256 통과, 오류 1 | 17개 정상, `run_p17` 종료 코드 1 |
| 신청자 저장소 (614dd7b) | 10 실패, 1,254 통과, 3 건너뜀 | 132 실패, 1,207 통과 | 17개 정상, `run_p17` 종료 코드 1 |
| 합친 사본 (저장소 밖, 4절 규칙) | 돌리지 않음(엔진은 이 저장소와 같은 코드) | 150 실패, 1,357 통과, 오류 1 | 17개 정상, `run_p17` 종료 코드 1 |

합친 사본의 백엔드 실패를 시험 파일의 출처에 맞는 기준과 비교했다(A에서 가져온 파일은 A 기준, 나머지는 O 기준).

- 기준에 없던 실패는 11개이고 모두 O가 분리 뒤 추가한 시험이다. A에서 가져온 시험과 병합한 시험에서는 0개다.
- 그 가운데 10개(`test_payment_paging.py` 5, `test_payment_paging_refinement.py` 1, `test_quality_assessment_parity.py` 4)는 신청자 API의 `status`가 내부 판정 값(`PASS`·`FAIL`·`NEEDS_REVIEW`)이기를 기대한다. 합친 백엔드는 공개 상태(`UPLOADED`·`REUPLOAD_REQUIRED`)를 돌려준다. 대응은 FAIL → `REUPLOAD_REQUIRED`, PASS·NEEDS_REVIEW → `UPLOADED`로 일관됐다.
- 사본에서 이 시험들의 그 단언만 A의 도우미 `test_portal_uploads.assert_upload_status`(저장된 판정과 공개 상태를 함께 확인, A의 시험 12개 파일이 쓰는 방식)로 바꾸니 세 파일이 O 기준과 같은 결과가 됐다(2 실패 140 통과, 그 2개는 O 기준에도 있는 실패). 바꾼 단언은 6개다(업로드 응답 상태 4, 목록 응답 상태 2). 최종 확인 차단, 제출 가능 여부, 저장된 사유, 담당자 응답을 확인하는 나머지 단언은 그대로 통과했다. 양쪽 정책이 동작으로도 어긋나지 않는다는 근거다.
- 나머지 1개(`test_officer_frontend_integration.py`)는 사본에 `node_modules`가 없어서 난 오류다(`Cannot find module 'typescript'`). 병합과 무관하고, 실제 저장소에서 다시 확인한다.
- 기준에서 실패하다가 합친 사본에서 통과하게 된 시험은 0개다.
