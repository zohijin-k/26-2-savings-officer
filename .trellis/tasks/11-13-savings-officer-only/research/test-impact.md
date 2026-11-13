# 기존 시험 변경/삭제 승인 목록

2026-11-13 사용자가 phone.test.ts 삭제와 새 시드 CLI·새 시험을 승인했다. 다른 기존 시험 파일은 수정·삭제하지 않는다. 아래는 승인 원장이다.

## A. 신청자·취업지원 화면 제거에 따른 시험 삭제 (별도 승인 묶음)
| 파일 | 시험/검증 이름 | 제안 | 이유 |
| --- | --- | --- | --- |
| demo/frontend/src/forms/phone.test.ts | formatPhone의 cases 반복문 9개 검증 | 삭제 | 신청자 전용 전화번호 입력 도우미 phone.ts를 UI와 함께 제거하므로 그 구현 전용 검증도 제거 |
| demo/frontend/src/forms/phone.test.ts | isValidPhone의 validCases 반복문 4개 검증 | 삭제 | 같은 신청자 전용 입력 검증 제거 |

이 파일에는 이름 있는 test() 함수가 없으며 최상위 반복문 검증 13개가 전부다. package.json의 lint/build는 이를 독립 시험으로 실행하지 않는다. 네 갈래 기준선의 pytest/시나리오 통과 수에는 포함되지 않는다. 승인하지 않으면 phone.ts와 이 시험을 함께 보존하고 UI 연결만 제거한다.

취업지원 프런트 전용 시험 파일은 현재 조사에서 발견하지 못했다. 취업지원 API·엔진·시나리오 시험은 화면 제거를 이유로 삭제하지 않는다.

## B. 기존 기대값 변경/기타 시험 삭제
계획된 변경: 없음. engine_v2/tests 전체, demo/backend/tests의 pytest 전체, 18개 시나리오, fixtures/expected/S*.json 모두 보존한다. 수치 맞추기용 삭제/skip/기대값 완화는 하지 않는다.

## C. 화면 제거에 따른 시험 보조 정보 정리 (기대값은 유지)
파일: `demo/backend/tests/run_p4_scenarios.py`
시험: `test_no_download_in_source` (내부 `_scan`, `_download_feature_imports`).

최종 사용자 조건에 맞춰 `APPLICANT_FORM_FILE_ALLOWLIST`의 예외 경로도 편집하지 않고 그대로 둔다. 삭제된 프런트 경로의 예외는 동작에 영향을 주지 않는다. backend/api/forms.py 예외는 API를 보존하므로 유지한다. 기대값 두 개는 계속 []이며 저장 경로/잘못된 import 금지 검사는 유지한다. 시험 이름·개수·의미를 변경하지 않는다.

P7/P14 원본 서식·글꼴 시험, P5/P12/P16 취업지원 시험, P18 신청자 사전 검사 시나리오, test_seed_application.py는 백엔드 회귀 검증이므로 모두 보존한다.

## 신규 검증 계획
- 프런트: PASS/FAIL/NEEDS_REVIEW/null 분리, 같은 신청이 양쪽 목록에 나타남, 중복 슬롯의 문서 ID 선택, 페이지 누락, 다른 사업 직접 URL 차단, 미제출 원본 없음.
- 승인된 신규 시드: 임시 DB/storage에서 생성·중복 방지·자기 데이터 정리·기존 행/파일 불변.
- 브라우저: 기본 진입/새로고침/이력, 두 목록, 선택 원본, 기존 코드·문구 그대로 표시.

구현 중 이 목록 밖의 기존 기대값 변경/삭제가 필요해지면 편집 전 파일·시험·이유를 추가 보고하고 승인을 기다린다. 커밋 전에도 변경된 시험 목록을 다시 대조한다.
