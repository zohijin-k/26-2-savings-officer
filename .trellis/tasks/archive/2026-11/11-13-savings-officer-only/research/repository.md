# 저장소 조사 (2026-11-13)

## 확인한 구조와 영향
| 근거 | 현재 동작 | 계획 영향 |
| --- | --- | --- |
| demo/frontend/src/App.tsx:14–21 | ApplyFlow/OfficerConsole 동시 마운트, 신청자 기본 진입 | 담당자만 마운트, 탭/신청자 상태 제거 |
| demo/frontend/src/navigation-url.ts:20 | /apply 또는 기본 URL은 applicant | / 및 옛 경로를 담당자 목록으로 정규화 |
| demo/frontend/src/pages/officer/OfficerConsole.tsx:30–63 | province 기본, 사업/상태/기준 경로를 복원 | province/double_savings 고정; 구 URL의 사업 복구 금지 |
| demo/frontend/src/pages/officer/ApplicationList.tsx | 신청 건 표·여러 필터·사업별 칼럼·정원/선착순 | 서류 단위 두 목록으로 교체 |
| demo/backend/api/officer.py:211 | draft 제외 담당자 목록 | 초안만 만드는 시드는 담당자 목록에 나타나지 않음 |
| demo/backend/api/officer.py:221 | 체크리스트 문서, null 미제출, 미배정 문서 ID 제공 | PASS/그 외를 프런트에서만 분리 가능 |
| demo/backend/api/officer.py:493 / :564 | 사업 필터, 신청 단위 페이지, 최대 200 | 두배적금 필터와 전체 페이지 취합 필요 |
| demo/frontend/src/pages/officer/ReviewDetail.tsx:90 | 최초 슬롯이 없으면 첫 문서로 대체 | ID 선택 추가, 미제출을 다른 문서로 대체하지 않음 |
| demo/backend/api/officer.py:654 | 문서 status/findings/file_url/bboxes 제공 | 사유 재설계 없이 기존 응답 사용 |
| ReviewDetail.tsx:230 이후 | 기존 원본/사유·두배적금 점수·취업지원 지급 패널 | 2단 재사용, 취업지원 패널 제거 |
| demo/frontend/src/api.ts:986 | 기본 무필터 0건/API 실패 시 자동 목업 | 사업 고정과 충돌; 목업은 명시 모드로 정리 제안 |
| demo/frontend/src/pages/officer/mock-data.ts:1923 | 두배적금+취업지원 합성 데이터 생성 | 취업지원 데이터/상세/필터 제거 |
| demo/backend/forms/render.py:40 | 프런트 assets/fonts의 TTF 사용 | 신청자 UI 제거 후에도 전체 글꼴 보존 |
| demo/backend/tests/run_p14_pdf_forms_scenarios.py:50 | 같은 글꼴의 TTF/WOFF2/OFL 검사 | 글꼴 삭제/시험 완화 금지 |

관련 spec: frontend/index.md, pdf-form-workspace.md, backend/index.md, seed-application.md, document-form-contracts.md, failure-filtering.md, guides/cross-layer-thinking-guide.md. 일반 frontend 가이드는 대부분 템플릿 상태여서 실제 코드·시험 근거를 함께 사용한다.

## 외부 링크
사용자가 지정한 안내 저장소 https://github.com/zohijin-k/26-2-capstone 는 웹 열기에서 Cache miss로 내용 확인에 실패했다. 이 작업은 로컬 저장소 증거로 계획할 수 있으며 원격 내용을 추정하지 않는다. README에 다음 사용자 지정 관계를 기록할 계획이다.
- 안내: https://github.com/zohijin-k/26-2-capstone
- 이 저장소: https://github.com/zohijin-k/26-2-savings-officer (로컬 origin과 일치)
- 두배적금 신청자: https://github.com/zohijin-k/26-2-savings-applicant
- 청년 취업지원 신청자: https://github.com/zohijin-k/26-2-youth-applicant
- 청년 취업지원 담당자: https://github.com/zohijin-k/26-2-youth-officer

DEVELOPMENT.md는 옛 통합 저장소 주소·브랜치 표 및 오래된 시험 수치를 포함한다. 이 저장소 현황으로 오해하는 부분만 최소 수정한다. 전체 문서/대시보드 재작성은 하지 않는다.
