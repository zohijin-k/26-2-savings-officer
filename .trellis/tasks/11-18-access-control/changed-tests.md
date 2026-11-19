# 고친 기존 시험

R5에 따라 기존 시험에는 인증 단계만 더했다. 응답 기대값, 판정 기대값, 확인 문구는 하나도 바꾸지 않았고 지운 시험도 없다.

- 도우미는 `demo/backend/tests/security_support.py`(youth와 같은 파일)에 있다.
  - `authenticate_officer(client, monkeypatch)`: 시험 전용 합성 비밀번호로 실제 로그인 경로를 통과한다. pytest에서는 `monkeypatch`를 넘겨 환경변수를 시험 뒤에 되돌린다. 시나리오 모듈은 따로 도는 프로세스라 `monkeypatch` 없이 부른다.
  - `claim_synthetic_application(client, 신청 번호)`: DB에 직접 만든 합성 신청에 새 소유자 토큰을 주고 쿠키를 클라이언트에 넣는다.
- 고치기 전 실패 원인은 두 가지뿐이었다(2026-11-19, 이 PC).
  - DB에 직접 만든 신청(`make_application`, `ready`)을 HTTP로 불러 403. 응답에 `can_submit` 같은 키가 없어 `KeyError`로도 보였다.
  - 담당자 API를 로그인 없이 불러 503(시험 환경에 `OFFICER_PASSWORD`가 없음).

## pytest (11개 파일)

| 파일 | 시험 | 더한 것 | 원인 |
|---|---|---|---|
| `test_applicant_failure_findings.py` | `test_upload_list_final_and_officer_keep_reference_but_hide_only_review` | 담당자 상세 조회 직전 `authenticate_officer` | 503 |
| `test_applicant_submission_policy.py` | `test_direct_submit_rechecks_each_reupload_reason_after_clear_preparation`, `test_direct_submit_rechecks_all_input_guards_after_clear_preparation`, `test_negative_self_check_answers_remain_saved_without_applicant_verdict` | 신청 생성 직후 `claim_synthetic_application` | 403 |
| 〃 | `test_hidden_outcomes_submit_and_preserve_stored_and_officer_decisions` | `claim_synthetic_application`, 담당자 상세 조회 직전 `authenticate_officer`, 인자에 `monkeypatch` | 403, 503 |
| `test_applicant_supplement_projection.py` | `test_applicant_status_hides_empty_internal_deadline_but_keeps_stored_review` | `claim_synthetic_application` | 403 |
| `test_eligibility_blockers.py` | `test_confirmed_regional_excess_includes_numeric_evidence_without_scores`, `test_submit_rechecks_income_after_a_previously_clear_final_check`, `test_work_not_met_blocks_final_and_direct_submit`, `test_undetermined_income_remains_submittable_for_officer_review`, `test_unknown_work_remains_submittable_and_final_review_is_consistent`, `test_submit_rechecks_other_eligibility_after_clear_final_check` | `claim_synthetic_application` | 403 |
| `test_failure_cases_work_acceptance.py` | `test_source_shaped_work_failure_reaches_all_consumers` | `claim_synthetic_application` | 403 |
| `test_officer_frontend_integration.py` | `test_seeded_api_rows_render_in_the_actual_frontend_queue_tabs` | `authenticate_officer`, 인자에 `monkeypatch` | 503 |
| `test_officer_summary.py` | `test_summary_api` | `authenticate_officer` | 503 |
| `test_payment_paging.py` | `test_api_list_and_final_check_keep_paging_severity` | `claim_synthetic_application` | 403 |
| `test_quality_assessment_parity.py` | `test_actual_upload_final_check_submission_and_officer_quality_agree` | `claim_synthetic_application`, 담당자 상세 조회 직전 `authenticate_officer` | 403, 503 |
| `test_resident_number_privacy.py` | `test_officer_response_masks_legacy_review_payload_and_score` | `authenticate_officer`, 인자에 `monkeypatch` | 503 |
| `test_review_status_priority.py` | `test_overlap_preserves_both_reviews_and_reopens_officer_decision`, `test_new_review_list_detail_and_payload_agree` | `authenticate_officer`, 인자에 `monkeypatch` | 503 |

## 시나리오 모듈 (8개)

`run_p4_scenarios.py`, `run_p5_scenarios.py`, `run_p6_scenarios.py`, `run_p7_scenarios.py`, `run_p9_identity_scenarios.py`, `run_p11_criteria_scenarios.py`, `run_p12_subsidy_criteria_scenarios.py`, `run_p18_applicant_precheck_scenarios.py`

- `main()`에서 `TestClient`를 만든 바로 다음 줄에 `authenticate_officer(client)` 한 줄과 import 한 줄을 더했다. P6은 회차마다 새 클라이언트를 만들므로 그 안에 넣었다.
- 원인은 모두 담당자 API 503이었다. P18은 이 예외 때문에 임시 폴더의 `p4.db`를 닫지 못해 `WinError 32`로 끝났다.
- 고친 뒤 확인 항목 수가 기준선과 같다: P4 195, P5 161, P6 275, P7 255, P9 118, P11 38, P12 36, P18 183.
- P4의 기존 확인 "[7-1] 신청자 본인 서식 API는 담당자 역할 토큰으로 접근할 수 없다"는 로그인한 클라이언트에서도 그대로 403이다. 시험이 넣는 `Cookie` 머리글이 클라이언트 쿠키를 대신하고, 담당자 세션은 신청자 경로를 열지 않는다.

## 새로 더한 시험

- `test_access_control.py` (59개): 접근 제어 경계. `.trellis/spec/backend/access-control.md` 6절.
- 프런트 `tests/officer-session.test.ts` (3개): 로그인 화면 전환 이벤트와 세션·로그인 응답 구분.
