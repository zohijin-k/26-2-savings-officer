# 설계 — 신청자·담당자 연결 (백엔드 통합)

요구사항은 `prd.md`, 근거는 `research/findings.md`에 있다. A는 신청자 저장소(`26-2-savings-applicant`), O는 이 저장소, B는 분리 전 코드(`26-2-capstone`)다.

## 1. 실행 구성

```
신청자 프런트 (A의 demo/frontend, 5173) ─┐
                                        ├─ /api → 이 저장소의 백엔드 (8000) → demo/demo.db, demo/storage
담당자 프런트 (O의 demo/frontend, 5174) ─┘
```

- 두 프런트의 개발 프록시 기본값이 `localhost:8000`이므로, 이 저장소의 백엔드를 8000번에 띄우면 프런트 코드를 고치지 않아도 된다. 담당자 프런트만 `npm run dev -- --port 5174`로 포트를 옮긴다.
- 신청자 저장소의 백엔드는 띄우지 않는다. 같은 포트를 쓰므로 둘을 함께 띄울 수도 없다.
- 브라우저의 요청은 각 개발 서버의 프록시를 거치므로 CORS 설정은 바꾸지 않는다.
- 신청은 이 저장소의 `demo/demo.db`와 `demo/storage`에 쌓인다. 제출된 신청은 `api/officer.py`의 목록 조건(`status != draft`)에 바로 걸린다. 담당자 결정은 같은 DB의 `Review`에 남아 신청자 마이페이지(`GET /api/applications/{id}/status`)에 보인다.

## 2. 경계

| 구분 | 파일 |
|---|---|
| A 것으로 교체 (제품 코드) | `demo/backend/api/applications.py`, `api/documents.py`, `api/review.py` |
| 3방향 병합 (제품 코드) | `demo/backend/api/common.py`, `demo/backend/tools/verify_upload.py` |
| A 것으로 교체·추가 (시험) | `demo/backend/tests`의 27개 교체, 2개 추가, 4개 병합, `demo/fixtures/expected`의 9개 교체 |
| 이 저장소 시험 고침 | `test_payment_paging.py`, `test_payment_paging_refinement.py`, `test_quality_assessment_parity.py`에서 신청자 응답의 상태를 확인하는 단언 6곳(6절) |
| 규격 | `.trellis/spec/backend/applicant-submission.md` 추가, `failure-filtering.md`·`index.md` 병합, A만 바꾼 `income-eligibility.md`·`seed-application.md`·`verify-cases.md` 교체 |
| 문서 | `README.md`, `docs/DEVELOPMENT.md`에 연결 실행 절 |
| 안 바뀜 | `engine`, `engine_v2`, `demo/frontend`, `demo/backend`의 나머지(`models.py`, `main.py`, `api/officer.py`, `api/forms.py`, `api/files.py`, `engine_adapter.py`, `ocr/`, `rules/`, `upload_assessment.py`), DB 구조, 프런트 규격 |

신청자 프런트의 규격(`frontend/applicant-ui-foundation.md` 등)은 가져오지 않는다. 이 저장소에는 신청자 프런트가 없다.

## 3. 병합 규칙

분리 전 코드 B를 기준으로 파일마다 한 가지 규칙을 쓴다.

| A | O | 결과 |
|---|---|---|
| 바꿈 | 그대로 | A의 파일 |
| 그대로 | 바꿈 | O의 파일 |
| 바꿈 | 바꿈 | `git merge-file A B O` |
| 추가 | 없음 | A의 파일 |
| 없음 | 추가 | O의 파일 |

- 대상 범위는 `demo/backend`, `demo/fixtures`, `.trellis/spec/backend`다.
- 규칙은 태스크 폴더의 `apply_merge.py`가 적용한다. 세 저장소의 내용을 작업 트리가 아니라 고정한 커밋(B `archive/main-before-split`, A 614dd7b, O f6d9827)에서 읽으므로 다시 돌려도 결과가 같다. `plan`은 목록만 출력하고, `apply`는 작업 트리에 쓰고, `check`는 적용 결과를 대조한다: 교체한 파일은 A의 파일과 같고, 병합한 파일은 `git merge-file` 출력과 같고, 범위 안에서 그 밖에 바뀐 파일이 없어야 한다.
- 지금 `plan`의 결과는 가져올 파일 42개, 새로 들일 파일 3개, 병합 8개, 사람이 정해야 하는 파일 0개다. 규칙에서 빼는 파일은 없다.
- 자동 병합이 깨끗해도 뜻이 어긋날 수 있다. 판단은 시험 결과로 한다(5절). 저장소 밖 사본에서 미리 돌려 본 결과는 `research/findings.md` 7절에 있다.

## 4. 계약

- **신청자 응답 경계**(A의 `applicant-submission.md`): 서류 상태는 `UPLOADED`·`REUPLOAD_REQUIRED`. 사유는 `REUPLOAD_CODES` 10개 가운데 FAIL만. 자격 사유, 자가진단 상세, 판독 신뢰도, 판정 기준 안내는 응답에 없다. 최종 확인과 제출은 같은 차단 함수를 쓴다.
- **판정**(O의 `failure-filtering.md`): 화질 등급 규칙과 납부확인서 구조 관찰값은 O의 것 그대로다. 저장되는 `Document.findings_json`, `stage1_status`, `Review`는 신청자 경계와 무관하게 온전하다.
- **맞물림**: 신청자 필터는 FAIL만 통과시킨다. O가 NEEDS_REVIEW로 낮춘 화질 사유는 신청자에게 `UPLOADED`로 보이고 담당자 확인으로 간다.
- **재업로드 허용 목록은 10개 그대로다.** O가 분리 뒤 새로 만든 사유 코드는 `NHIS_PAYMENT_PAGING_UNCERTAIN` 하나이고 담당자 확인용이라 목록에 넣지 않는다. 쪽수가 모자랄 때의 실패 코드 `PAGES_INCOMPLETE`는 이미 목록에 있어서, 납부확인서 쪽수 실패는 신청자에게 다시 올리라는 안내로 나간다. 신청자에게 무엇을 다시 올리라고 할지는 신청자 쪽 정책이고, 이 태스크는 그 정책을 바꾸지 않는다.
- **담당자 응답**: `api/officer.py`와 그것이 쓰는 `common`의 함수(`checklist_for`, `list_documents`, `list_documents_bulk`, `load_application`, `subsidy_estimate`)는 A가 바꾸지 않았다. 응답 모양이 바뀌지 않는다.

## 5. 검증

1. **파일 대조** — 3절의 대조.
2. **시험** — 엔진, 백엔드, 시나리오를 돌려 실패 목록을 변경 전 기준과 비교한다. 기준은 같은 PC에서 잰 두 가지다: 이 저장소의 변경 전(O 기준), 신청자 저장소(A 기준). 판정 규칙:
   - 가져오지 않은 시험: 실패 목록이 O 기준과 같아야 한다.
   - A에서 가져온 시험: 실패 목록이 A 기준과 같거나, 차이를 원인까지 설명할 수 있어야 한다.
   - 설명되지 않는 새 실패는 0이어야 한다.
3. **담당자 프런트** — `npx tsc -b && npx oxlint && npx vite build`, `npm test`. 프런트를 고치지 않으므로 변경 전과 같아야 한다.
4. **실제 화면** — 임시 DB와 임시 저장 폴더를 쓰는 격리 서버에 두 프런트를 붙여, 합성 서류로 제출 → 담당자 목록·상세 → 담당자 결정 → 마이페이지를 확인한다. 이 저장소의 `demo/demo.db`에는 시험 신청을 넣지 않는다.
5. **문서 절차 확인** — 문서에 적은 명령으로 백엔드와 두 프런트가 뜨고 기존 목록이 보이는지만 본다(자료를 쓰지 않는다).

이 PC는 Windows라 `fcntl`을 쓰는 13개 시험 모듈이 수집되지 않는다. 그 가운데 백엔드 모듈 `test_payment_stage2_routes.py`는 이 PC에서 확인할 수 없으므로 PR에 적어 리눅스·맥에서 한 번 돌려 달라고 요청한다.

## 6. 의도적으로 바뀌는 것

- 이 저장소 백엔드의 신청자 API 응답이 A와 같아진다(서류 상태 값, 사유 목록, 자격 사유 제거, 자가진단 결과 축소, 판정 기준 안내 제거). 이 저장소의 프런트는 담당자 전용이라 이 응답을 쓰지 않는다.
- 이 저장소의 기존 시험 31개 파일과 시연 기대값 9개 파일이 A의 것으로 바뀐다(교체 27, 병합 4). A에서 이미 검토를 거친 기대값이다.
- 이 저장소가 분리 뒤 추가한 시험 3개 파일에서 단언 6곳을 고친다. 신청자 API의 `status`가 내부 판정 값이기를 기대하던 곳이다. A의 시험이 쓰는 도우미 `assert_upload_status`로 바꿔, 저장된 판정(`Document.stage1_status`)은 전과 같은 값으로 확인하고 공개 상태도 함께 확인한다. 목록 응답의 상태는 업로드 응답의 상태와 같은지 확인한다. 판정 값에 대한 기대는 바뀌지 않는다.
- 파일 목록과 이유는 `changed-test-expectations.md`에 있다.

## 7. 선택과 이유

- **프런트를 고치지 않는다** — 두 프런트의 프록시 기본값이 같아서 포트만 맞추면 된다. `VITE_API_TARGET` 지원은 편의 기능이고 이 연결에 필요하지 않다.
- **신청자 저장소를 건드리지 않는다**(D3) — 연결에 필요한 변경은 모두 이 저장소에 있다.
- **화면 확인은 격리 서버로 한다** — 시연용 DB에 시험 신청이 섞이지 않게 한다. 연결의 근거는 같은 백엔드 코드가 한 DB를 쓴다는 점이라 임시 DB로도 같은 것을 확인한다.

## 8. 되돌리기

- 제품 코드, 시험·기대값, 규격·문서를 따로 커밋한다. 제품 코드와 시험 커밋을 되돌리면 분리된 상태로 돌아간다.
- DB 구조를 바꾸지 않으므로 자료 이전이나 복구는 없다.
