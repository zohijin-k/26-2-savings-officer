# 의도적으로 바뀌는 기존 시험과 기대값 (2026-11-17)

신청자 응답 경계를 이 저장소 백엔드에 들이는 일(prd R2, R5)의 직접 결과다. 아래 외의 기존 기대값은 건드리지 않는다. 판정 값(`PASS`·`FAIL`·`NEEDS_REVIEW`)에 대한 기대는 어느 시험에서도 바꾸지 않는다.

## A. 신청자 저장소의 것으로 바뀌는 파일

출처는 신청자 저장소(`26-2-savings-applicant`)의 커밋 c4179bd, a5c59d7이다. 시험별로 무엇을 왜 바꿨는지는 그 저장소의 `.trellis/tasks/archive/2026-11/11-13-savings-applicant-submit/`에 있는 `test-impact.md`, `backend-test-impact.md`, `scenario-test-impact.md`에 적혀 있다. "교체"로 적은 파일은 이 저장소가 분리 전 내용 그대로 갖고 있던 것이라 신청자 저장소의 파일로 바꾼다. "3방향 병합"으로 적은 파일은 이 저장소도 바꾼 것이라 두 변경을 합친다.

| 구분 | 파일 |
|---|---|
| 시나리오 12개 (교체) | `run_p3`, `run_p4`, `run_p5`, `run_p6`, `run_p7`, `run_p9_identity`, `run_p12_subsidy_criteria`, `run_p13_household`, `run_p15_jbai`, `run_p16_job_docs`, `run_p17_own`, `run_p19_nhis_history` (`…_scenarios.py`) |
| 시험 15개 (교체) | `test_address_resolution_failures.py`, `test_applicant_failure_findings.py`, `test_daily_work_uploads.py`, `test_eligibility_blockers.py`, `test_failure_cases_work_acceptance.py`, `test_followup_failure_acceptance.py`, `test_mixed_attachments.py`, `test_p2_business_uploads.py`, `test_p2_nhis_uploads.py`, `test_p2_payment_uploads.py`, `test_p2_resident_uploads.py`, `test_portal_uploads.py`, `test_resident_number_privacy.py`, `test_verify_cases.py`, `test_verify_upload.py` |
| 시험 4개 (3방향 병합, 충돌 0) | `run_p18_applicant_precheck_scenarios.py`, `test_nhis_recent_history.py`, `test_quality_failure_policy.py`, `test_review_regressions.py` |
| 시연 기대값 9개 (교체) | `demo/fixtures/expected/S1.json` ~ `S8.json`, `S10.json` |
| 새 시험 2개 (추가) | `test_applicant_submission_policy.py`, `test_applicant_supplement_projection.py` |

바뀌는 기대의 종류: 신청자 API의 서류 상태가 내부 판정 값에서 `UPLOADED`·`REUPLOAD_REQUIRED`로, 신청자에게 보이는 사유가 허용 목록 10개의 FAIL로, 자격 사유와 자가진단 상세가 응답에서 빠짐, 제출을 막는 조건이 필수 입력·동의·업로드와 허용 목록의 서류 실패로. 저장된 판정을 확인하던 단언은 `assert_upload_status` 등으로 저장된 값을 직접 읽어 그대로 유지한다.

## B. 이 저장소가 분리 뒤 추가한 시험에서 고치는 단언 6곳

세 파일 모두 신청자 API의 `status`가 내부 판정 값이기를 기대한다. 합친 백엔드는 공개 상태를 돌려주므로, 판정은 저장된 값으로 확인하고 공개 상태는 따로 확인한다. `assert_upload_status(data, expected)`는 `Document.stage1_status == expected`와 공개 상태·공개 사유를 함께 확인하는 신청자 저장소의 도우미다(`test_portal_uploads.py`).

| # | 시험 | 바꾸기 전 | 바꾼 뒤 |
|---|---|---|---|
| 1 | `test_payment_paging.py::test_actual_image_upload_persists_independent_paging` | `assert response["status"] == status` | `assert_upload_status(response, status)` |
| 2 | `test_payment_paging.py::test_api_list_and_final_check_keep_paging_severity` | `assert body["status"] == expected` | `assert_upload_status(body, expected)` |
| 3 | 같은 시험 | 목록 응답의 `status == expected` | 목록 응답의 `status == body["status"]` |
| 4 | `test_payment_paging_refinement.py::test_second_upload_replaces_first_and_remaining_file_controls_paging` | `assert response['status']=='FAIL'` | `assert_upload_status(response,'FAIL')` |
| 5 | `test_quality_assessment_parity.py::test_actual_upload_final_check_submission_and_officer_quality_agree` | `assert body["status"] == expected` | `assert_upload_status(body, expected)` |
| 6 | 같은 시험 | 목록 응답의 `status == expected` | 목록 응답의 `status == body["status"]` |

이 시험들의 나머지 단언(최종 확인의 서류 차단, 제출 응답 코드, 저장된 사유의 심각도, 담당자 상세의 판정과 사유)은 고치지 않는다. 저장소 밖 사본에서 위 6곳만 바꿔 돌렸을 때 세 파일의 결과가 변경 전 기준과 같았다(`research/findings.md` 7절).
