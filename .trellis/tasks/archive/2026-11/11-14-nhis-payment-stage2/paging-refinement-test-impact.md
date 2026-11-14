# 쪽수 보완 후 시험 영향 — 승인 전 목록

기존 시험·헬퍼·공용 픽스처·단언은 수정하지 않았다. 이 문서는 사용자 조건 9에 따른 전후 값과 이유의 사전 검토 목록이며, 시험 변경 승인을 받은 기록이 아니다. 1/1 추가는 제안하지 않는다. 숫자 예시는 저장소의 가상 합성 입력에만 해당하며 가린 덤프 값이 아니다.

환경 문제를 제외한 영향은 **28개 매개변수 사례: engine 3개, backend 25개**다. main에 있던 시험은 `test_review_regressions.py`의 1개뿐이고, 나머지 27개는 이 작업의 이전 미커밋 stage2/쪽수 시험이다. 아래 ‘기존 기대’는 해당 시험의 기존 단언을 뜻하며, 모두 main 기준선에 포함된다는 뜻이 아니다.

| 원인 | 사례 수 | 현재 동작 / 검토할 조치 |
| --- | ---: | --- |
| C2 머리글 경계 잘림 계속 보류 | 5 | 긍정 재현의 구조 완전성이 거짓. C2를 복원하지 않고 해당 긍정 사례만 보류 대상으로 표시하는 방안 검토 |
| 제출 파일 합산 불가 | 9 | 기존 FAIL 기대 → NEEDS_REVIEW. 조건 3의 명시적 fallback. 확정 재업로드 blocker가 없음을 함께 검토 |
| 완전한 표의 쪽수 불확실 사유 면제 | 12 | 10개는 문서 REVIEW 그대로이고 쪽수 코드만 없어짐; 1개 업로드는 PASS; 1개는 확인된 월 보험료 사용 가능 |
| 확장된 여백 경계 | 1 | 기존 단어가 새 범위 안에 완전히 들어옴. 기대값을 바꾸기보다 새 실제 경계를 가로지르는 로컬 합성 입력으로 목적 보존 |
| 조회기간 확정 필수 — main 기존 시험 | 1 | 기간 없는 구형 표는 합계가 맞아도 PASS → REVIEW; 소득 근거·pipeline 결과도 함께 변경 |

구체적 검토 범위는 **기대값 변경 22개 + C2 보류 표시 5개 + 경계 안전성 재현 입력 보완 1개**다. C2 긍정 5개는 원래 단언을 보존한 `xfail(strict=True)`로 보류하여 복구 시 XPASS도 실패하게 한다. 경계 입력은 표시 값은 그대로 두고 현재 경계를 실제로 가로지르도록 그 시험의 로컬 합성 상자만 옮긴다. 모든 조치는 승인 전이며, 공용 원본 fixture·410쌍 입력/정답/지표 변경이나 1/1 추가는 포함하지 않는다.

## 각 사례의 기존 단언과 현재 관찰

| 파일::시험[매개변수] | 기존 기대 → 현재 실제 | 원인 |
| --- | --- | --- |
| `engine_v2/tests/test_payment_stage2_structure.py::test_clipped_upper_fragments_require_complete_unique_heading_evidence[0.7]` | `structure_complete`: True → False | C2 계속 보류 |
| `engine_v2/tests/test_payment_stage2_structure.py::test_clipped_upper_fragments_require_complete_unique_heading_evidence[1]` | `structure_complete`: True → False | C2 계속 보류 |
| `engine_v2/tests/test_payment_stage2_structure.py::test_clipped_upper_fragments_require_complete_unique_heading_evidence[1.7]` | `structure_complete`: True → False | C2 계속 보류 |
| `demo/backend/tests/test_payment_paging.py::test_certain_missing_folio_fails_independently_of_table_and_document_confidence[False-False]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_certain_missing_folio_fails_independently_of_table_and_document_confidence[False-True]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_certain_missing_folio_fails_independently_of_table_and_document_confidence[True-False]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_certain_missing_folio_fails_independently_of_table_and_document_confidence[True-True]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[False-None-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[False-1/-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[False-l/2-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[False-1/2-0.2]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[False-0/2-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[True-None-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[True-1/-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[True-l/2-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[True-1/2-0.2]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_uncertain_marker_is_review_without_reupload_or_quality_failure[True-0/2-1]` | 쪽수 코드 있음 → 없음; 상태 REVIEW 유지 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_actual_text_pdf_upload_route_checks_printed_total[1/2]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_crossing_marker_cannot_be_cropped_into_count_proof` | `payment_paging.assess(collect(input))`: UNCERTAIN → INCOMPLETE | 확장 후 실제 경계가 달라짐 |
| `demo/backend/tests/test_payment_paging.py::test_exact_v2_s1_pages_incomplete_is_fail_in_both_paths[own]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_exact_v2_s1_pages_incomplete_is_fail_in_both_paths[reference]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_actual_image_upload_persists_independent_paging[1/2-FAIL]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_paging.py::test_actual_image_upload_persists_independent_paging[None-NEEDS_REVIEW]` | `response.status`: NEEDS_REVIEW → PASS | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_paging_review_or_failure_cannot_establish_income[None]` | `_field(record, health premium)`: None → 50000 | 완전한 표 fallback |
| `demo/backend/tests/test_payment_paging.py::test_api_list_and_final_check_keep_paging_severity[1/2-FAIL]` | `verdict.status`: FAIL → NEEDS_REVIEW | 전체 제출 쪽 합산 보장 불가 |
| `demo/backend/tests/test_payment_stage2_routes.py::test_repaired_shapes_traverse_actual_image_upload_without_changing_average[clipped]` | `response.status`: PASS → NEEDS_REVIEW | C2 계속 보류 |
| `demo/backend/tests/test_payment_stage2_routes.py::test_repaired_complete_table_cannot_override_independent_period_conflict[clipped]` | `structure_complete`: True → False | C2 계속 보류 |
| `demo/backend/tests/test_review_regressions.py::test_legacy_payment_sum_failure_controls_direct_verdict_and_financial_trust[False-legacy]` | `verdict.status`: PASS → NEEDS_REVIEW | 확정 조회기간 없음 |

## main 기존 시험 1개 — 함께 검토할 후속 단언

`demo/backend/tests/test_review_regressions.py::test_legacy_payment_sum_failure_controls_direct_verdict_and_financial_trust[False-legacy]`는 연·월이 적힌 행과 인쇄 합계는 있으나 확정된 인쇄 조회기간이 없다. 새 조건 1은 `premium_months`가 비어 있어도 `period_status=READABLE`을 요구하므로 행에서 기간을 추측하지 않고 검토 처리한다.

| 검증 | 기존 기대 | 현재 결과 |
| --- | --- | --- |
| `verdict.status` | PASS | NEEDS_REVIEW |
| `facts.monthly_premium` | 110000 | None |
| `pipeline.status.value` | PASS | NEEDS_REVIEW |

전체 시험 로그는 첫 status 단언에서 멈춘다. 후속 두 값은 부모 작업에서 별도 확인한 결과이며, 실패한 whole-suite 시험이 그 단언까지 실행했다는 뜻은 아니다. 월별 금액 원본을 지우는 변경이 아니라, REVIEW 서류의 금액을 확정 소득 근거로 사용하지 않는 결과다. 이 세 단언을 함께 검토해야 하며, financial-trust 단언을 삭제하거나 공용 헬퍼에 기간/쪽수를 추가해 숨기지 않는다. `month-only` 및 `incorrect=True` 사례는 이 목록에 포함되지 않는다.

## 이전 미커밋 쪽수 시험의 목적 보존

- 제출 합산 불가 9건: NEEDS_REVIEW로 변경 검토 시에도 PASS 아님, 쪽수 근거 저장, 신원/표 판독과 독립적인 검토 유지, API/list/final-check의 확정 FAIL blocker 없음 등을 함께 검증한다. 운영 집계가 불가능한 상태에서 기존 FAIL 기대를 맞추려고 파일 단위 수를 전체 제출 수로 취급하지 않는다.
- 완전한 표 fallback 10건: 입력은 이미 기간·대상 월·인쇄 합계·발급 정보 조건을 충족한다. `image_quality=.55`가 별도로 `LOW_IMAGE_QUALITY NEEDS_REVIEW`를 남기므로 문서 상태는 REVIEW다. 사라진 쪽수 코드를 다시 만들거나 독립 화질 규칙을 바꾸지 않는다. 코드 없음/비FAIL과 별도의 불완전 표 검토 재현을 함께 유지하는 방안이 적합하다.
- marker 없는 완전 표 업로드 1건과 소득 근거 1건: 각각 PASS와 기존 합성 월 보험료 50000 사용을 검토한다. 값을 추측해 채운 것이 아니며, 표시된 전체 쪽수가 파일 쪽수보다 큰 입력의 REVIEW/소득 근거 차단은 유지해야 한다.
- 경계 횡단 1건: `test_crossing_marker_cannot_be_cropped_into_count_proof`의 기존 authored 단어는 이전 좁은 가로 경계를 넘었지만 새 여백 범위에는 통째로 포함된다. raw collector의 UNCERTAIN→INCOMPLETE는 운영 FAIL을 뜻하지 않는다. **INCOMPLETE로 단언만 바꾸지 말고**, 이 시험의 로컬 단어를 실제 새 경계를 가로지르게 옮겨 `UNCERTAIN`과 전체 토큰 보존 목적을 유지하는 입력 보완을 권고한다. 원본 공용 fixture와 덤프 좌표는 사용하지 않는다. 이 보완도 승인 전이다.
- C2 긍정 5건: 사용자가 복원을 계속 보류하였으므로 다시 켜서 통과시키지 않는다. 원래 월별 평균과 기간 충돌 검증 목적은 보존하고, C2에 종속된 긍정 사례만 명시적 보류 대상으로 다루는 방안을 검토한다.

## 실행 근거 및 제외

초기 로그: `engine_v2/data/stage2_paging_refinement_20261114/engine.log`는 3 failed / 1626 passed / 3 skipped. `backend.log`는 26 failed / 1366 passed이며, 이 중 1건은 격리 프런트 의존성이 없었던 환경 실패다. 해당 `test_officer_frontend_integration.py::test_seeded_api_documents_render_in_the_two_actual_frontend_lists`는 위 28개에서 제외했다. 환경 의존성 설치 후의 최종 backend 재실행으로 실제 해소 여부를 확인한다.

- `final-engine.log`: 3 failed, 1627 passed, 3 skipped, 7 warnings in 82.75s (0:01:22). 실패 node 집합은 초기 영향 목록과 동일.
- `final-backend.log`: 25 failed, 1373 passed, 9 warnings in 145.34s (0:02:25). 실패 node 집합은 환경 1건을 제외한 초기 영향 목록 25개와 동일. 프런트 의존성 환경 실패는 재실행에서 해소됨.

시험 변경·커밋 승인 요청을 대신하지 않는다. 해당 파일의 JSON에는 28개 node별 사유·전후·권고와 승인 전 상태를 보존했다.


## Subsequent user decision and implementation

This inventory describes the earlier REVIEW-policy candidate. The user subsequently approved19 changes and retained nine FAIL expectations conditionally. Read-only inspection confirmed both explicit-slot paths are one-file replacement, so those nine FAIL expectations were NOT changed and now pass. Approved19 and the required ten new incomplete-table controls are implemented. C2 positives retain original assertions with strict xfail reason C2 header-edge recovery held. See paging-single-file-upload-audit.md. No 1/1 or common-fixture/corpus input edit.
