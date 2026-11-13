# Trellis check 결과 (2026-11-13)

## 범위
전체 변경 프런트, 신규 seed_officer_demo CLI 및 신규 시드/프런트 통합 시험을 PRD·승인 조건·spec과 대조했다. 기존 API·판정 저장·DB 모델·규칙·engine/engine_v2 및 기존 백엔드/엔진/시나리오 시험에는 diff가 없다. 프런트 기존 시험 삭제는 승인된 phone.test.ts 하나다. TTF/WOFF2/OFL 여섯 글꼴 파일도 원본 그대로다.

## 발견과 수정
1. 명시적 mock에서 존재하지 않는 신청 ID의 상세 호출이 Promise 생성 전에 동기 throw하던 문제를 확인했다. fetchReviewDetail을 async로 바꾸어 상세의 기존 오류 처리 경로에서 표시되게 했다. 신규 officer.test.ts에 해당 오류 경계 회귀 시험을 추가했다. 구현 단계의 async 보완과 병행해 발견되었으며 check는 회귀 시험을 추가했다.
2. OfficerConsole이 문서 ID/슬롯을 key에 넣어 같은 신청의 문서 탭을 옮길 때 ReviewDetail을 재생성하고 작성 중 메모를 잃던 회귀를 수정했다. key는 applicationId만 사용하며 선택 문서는 props로 갱신한다.
3. 유지된 심사표에서 근거를 클릭하면 원본 문서만 바뀌고 기존 bbox 강조가 사라지던 회귀를 수정했다. 문서 ID를 포함한 focus로 선택 문서에만 강조를 적용하고 심사표의 activeKey를 연결했다. 판정·사유 데이터는 변경하지 않는다.
4. 실제 CLI 검증의 일반 신청 번호 파일 충돌을 부모가 발견했다. 단순히 API create 후 이름을 바꾸면 count 기반 번호가 기존 행의 gap에서 UNIQUE 충돌할 수 있음을 추가로 확인·보고했다. 시드 구현 담당자가 신규 소유 Application만 UUID 전용 번호/현재 criteria_version으로 생성하고 이후 기존 patch/self-check/consent/upload/submit을 사용하는 방식으로 수정했다. 일반 파일 잔여물 및 번호 gap에 관한 신규 회귀 시험이 추가되었다. 기존 API 코드는 변경하지 않았다.

## 확인한 계약
- 서류 분류는 status === PASS 여부만 사용한다. API의 신청 통합 판정은 분류 조건에 쓰지 않는다.
- 기존 API의 모든 신청 페이지를 모은 뒤 분류한다. 미제출 null 및 같은 슬롯의 미배정 페이지도 문서 ID와 슬롯을 보존한다.
- 없는 문서 ID는 첫 문서로 대체하지 않고 빈 원본 상태를 표시한다. 상세 응답의 사업도 다시 확인한다.
- 원본은 기존 파일 API의 inline 스트림을 사용하고 기존 findings의 code/message/how_to_fix를 표시한다.
- 시드는 고정 저장소 합성 PDF만 읽고 본문 합성 표식까지 확인한다. 입력 파일/DB/사업 변경 인자는 없다.
- 기존 DB에서 init_db를 호출하지 않고 기존 행 snapshot을 비교한다. 시드 실패는 새 행/파일을 되돌리며 clean 실패도 임시 이동 파일을 먼저 복원한다.
- 정리는 자체 생성 marker의 행과 소유 namespace/기록 경로만 대상으로 하며 다른 신청이 참조하는 공유 파일을 보호한다.

## check 직접 실행
- npm test: 신규 프런트 9개 통과, 실패·skip 0.
- npm run lint: 통과, 경고 0.
- npm run build: 통과. 기존 500kB chunk 크기 안내만 남음.
- protected 경로 및 기존 시험 diff, 글꼴 diff 점검: 변경 없음.

최종 네 갈래 회귀 결과와 실제 CLI/브라우저 검수 증거는 부모 세션의 최종 검증 보고서가 소유한다. 이 check에서 실제 저장소 DB/storage는 읽거나 만들거나 정리하지 않았다. 브라우저에서 메모 입력 후 같은 신청의 다른 문서 탭으로 이동하는 수동 확인은 부모에게 요청했다.

## 남은 차단 사항
없음. 문서 목록 서버 전용 페이지 API/대규모 운영 최적화 및 사유 세부 재설계는 승인된 범위 밖으로 유지했다.
