# 프런트 구현 인계 (2026-11-13)

## 변경
- App에서 담당자만 마운트. / 및 제거된 진입 경로는 /officer로 정규화.
- double_savings/province 고정 API 조회. 모든 신청 페이지 취합 후 문서 status PASS / 그 외 두 목록. 신청의 통합 판정은 사용하지 않음.
- groupOfficerDocuments: src/pages/officer/document-groups.ts. 입력 OfficerRow[], 출력 {pass, needsReview}; 각 항목 applicationId/applicationNo/name/documentId/slotKey/label/status/required.
- 동일 모듈의 collectOfficerRows가 신청 목록 page_count 전체를 조회하고 selectOfficerDocument는 실제 ID를 우선함. 없는 원본을 첫 문서로 대체하지 않음.
- ReviewDetail은 왼쪽 선택 원본/오른쪽 저장된 findings code/message/how_to_fix 표시. 신청 전체 사유는 별도 접힘 영역. 직접 URL로 다른 사업은 표시하지 않음. 기존 심사표/담당자 저장 동작은 상세에서 유지.
- 목업은 ?mock=1 명시 모드의 작은 두배적금 합성 예제로 교체. API 빈 목록/실패는 목업으로 바꾸지 않음.
- DocumentViewer에서 한 쪽 PDF도 로딩 완료 후 그려지도록 loadedUrl 상태 연결. 기존 pdf.js 원본 렌더/확대/회전은 유지.
- 신청자 전용 API 타입/함수·입력 컴포넌트·코드 제거. 공유 FormSheet는 담당자 심사표에 필요한 표시 컴포넌트만 유지. fonts의 TTF/WOFF2/OFL 여섯 파일은 무변경.

## 제거된 라우트/진입
- / 의 신청자 사업 선택 화면 (현재는 /officer로 정규화)
- /apply/identity, /apply/forms, /apply/subsidy, /apply/upload, /apply/final, /apply/complete, /apply/mypage
- /officer/criteria/:program 및 옛 역할 전환 진입 /officer/town, /officer/city
- 사업 선택/취업지원·신청자 mode 쿼리 복구와 역할/사업/판정 필터 UI
- 새 상세 경로 /officer/review/:id?document=:id&slot=:slot, 기존 /officer/province/review/:id는 읽고 새 경로로 정규화

## 검증
- npm test: 신규 시험 8개 통과. PASS/non-PASS 분리·원래 값 불변·타 사업 제외·중복 슬롯의 ID 선택·없는 원본·전체 페이지·빈 목록/오류·경로 정규화·실제 ApplicationList 렌더 두 영역 확인.
- npm run lint: 통과, 경고 0. 신청자 상태 export 제거로 기존 StatusBadge Fast Refresh 경고도 해소.
- npm run build: 통과. 기존 큰 chunk 안내는 남음.
- 기존 P4 시나리오: 189 통과 / 실패 0. 기존 시험/allowlist 무수정.
- 기존 시험 삭제는 승인된 phone.test.ts 1개뿐. 다른 기존 시험 및 기대값 무수정.
- 신규 tests/officer.test.ts는 Node의 native 타입 제거를 사용하므로 시험 실행은 Node 22.18+ (검증 Node 26.13.1).

## 삭제한 프런트 파일 (전체)
- demo/frontend/src/components/CriteriaEditor.tsx
- demo/frontend/src/components/FileLink.tsx
- demo/frontend/src/components/FilePreview.tsx
- demo/frontend/src/components/Modal.tsx
- demo/frontend/src/components/PdfPages.tsx
- demo/frontend/src/components/SignaturePad.tsx
- demo/frontend/src/components/Skeleton.tsx
- demo/frontend/src/components/file-preview.css
- demo/frontend/src/components/modal.css
- demo/frontend/src/components/skeleton.css
- demo/frontend/src/forms/PdfFormsWorkspace.tsx
- demo/frontend/src/forms/consent-model.ts
- demo/frontend/src/forms/email.ts
- demo/frontend/src/forms/form-field-bindings.ts
- demo/frontend/src/forms/form1-model.ts
- demo/frontend/src/forms/form2-model.ts
- demo/frontend/src/forms/form5-model.ts
- demo/frontend/src/forms/pdf-forms-workspace.css
- demo/frontend/src/forms/phone.test.ts
- demo/frontend/src/forms/phone.ts
- demo/frontend/src/forms/ymd.ts
- demo/frontend/src/hooks/useDelayedFlag.ts
- demo/frontend/src/lib/period.ts
- demo/frontend/src/pages/applicant/ApplyFlow.tsx
- demo/frontend/src/pages/applicant/DocumentUpload.tsx
- demo/frontend/src/pages/applicant/FinalCheck.tsx
- demo/frontend/src/pages/applicant/IdentityCheck.tsx
- demo/frontend/src/pages/applicant/MyPage.tsx
- demo/frontend/src/pages/applicant/ProgramPicker.tsx
- demo/frontend/src/pages/applicant/SubsidyItems.tsx
- demo/frontend/src/pages/applicant/apply-flow.css
- demo/frontend/src/pages/applicant/document-upload.css
- demo/frontend/src/pages/applicant/final-check.css
- demo/frontend/src/pages/applicant/identity-check.css
- demo/frontend/src/pages/applicant/my-page.css
- demo/frontend/src/pages/applicant/program-picker.css
- demo/frontend/src/pages/applicant/subsidy-items.css
- demo/frontend/src/pages/officer/format.ts
