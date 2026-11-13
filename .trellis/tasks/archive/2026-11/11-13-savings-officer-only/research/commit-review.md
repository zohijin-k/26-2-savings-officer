# 커밋 전 검토 — 사용자 승인 대기

구현 브랜치: feat/savings-officer-only, 기준 main e449c55. 커밋·stage·push 미실행. 이번 세션 전 작업 트리 clean이었으며 모든 현재 변경은 이 태스크에서 생성했다.

## 네 갈래 비교
| 구분 | 작업 전 | 구현 후 |
| --- | --- | --- |
| engine_v2 | 1,264 통과 / 3 skip | 1,264 통과 / 3 skip |
| demo/backend | 1,227 통과 | 1,252 통과 = 기존 1,227 + 새 시드 24 + 실제 프런트 연동 1 |
| 시나리오 | 18개 / 1,885 통과 / 실패 0 | 18개 / 1,885 통과 / 실패 0 |
| 프런트 | lint 경고 1 / build 통과 | 새 시험 9 통과 / lint 경고 0 / build 통과 |

엔진 warnings 7, backend warnings 9. lint 경고 감소는 신청자용 StatusBadge export 제거에 따른 것으로 설정 완화가 아니다. 기존 build 큰 chunk 안내는 남아 있다. 최종 프런트는 check의 메모/포커스 보완 후 시험·lint·build도 재통과했다. P4는 마지막 프런트 보완 후 다시 실행해 189/0 확인.

## 보존과 시험 변경
기존 신청 API·판정 저장·DB 모델·engine/engine_v2·기존 backend/engine/시나리오 시험·expected·글꼴 파일 diff 없음. 기존 시험 삭제는 승인된 frontend/src/forms/phone.test.ts의 전화번호 입력 검증 13개만이다. 다른 기존 기대값/시험은 변경·삭제하지 않았다.

새 파일: demo/backend/tools/seed_officer_demo.py, demo/backend/tests/test_seed_officer_demo.py (24개), demo/backend/tests/test_officer_frontend_integration.py (1개), demo/frontend/src/pages/officer/document-groups.ts, demo/frontend/tests/officer.test.ts (9개), 관련 spec/태스크 기록.

## 실제 CLI 결과
저장소의 실제 로컬 demo DB에서 실행했다. 기존 자료는 열지 않고 충돌 시 안전하게 거부한 뒤 전용 UUID 번호를 사용하는 보완을 적용했다. 다음 결과는 최종 구현 실행이다.

```json
{
  "create": {
    "applications": {
      "needs-review": {
        "application_id": 2,
        "needs_review": 1,
        "pass": 4
      },
      "pass": {
        "application_id": 1,
        "needs_review": 0,
        "pass": 5
      }
    },
    "created": 2,
    "existing": 0
  },
  "repeat": {
    "applications": {
      "needs-review": {
        "application_id": 2,
        "needs_review": 1,
        "pass": 4
      },
      "pass": {
        "application_id": 1,
        "needs_review": 0,
        "pass": 5
      }
    },
    "created": 0,
    "existing": 2
  },
  "clean": {
    "deleted_applications": 2,
    "deleted_files": 14,
    "deleted_rows": 22
  },
  "clean-repeat": {
    "deleted_applications": 0,
    "deleted_files": 0,
    "deleted_rows": 0
  }
}
```

정상 신청은 5 PASS/0 확인 필요, 확인 필요 신청은 4 PASS/1 확인 필요. React 실제 목록 컴포넌트 통합 시험에서 9개/1개로 표시되고 정상 신청이 확인 필요 목록에 섞이지 않음을 확인했다. 임시 시험에서 기존 신청·판정·공유 파일 값/bytes 보존을 확인했고, 실제 --clean에서도 기존 합성 잔여 파일 9개의 크기/mtime가 그대로임을 확인했다. 최종 실제 DB에는 시드 신청 0건, 자체 파일 0개가 남는다.

## 삭제한 프런트 파일 (38개)
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

## 제거/정규화한 라우트
- / 의 신청자/사업 선택 진입은 /officer로 정규화.
- /apply/identity, /apply/forms, /apply/subsidy, /apply/upload, /apply/final, /apply/complete, /apply/mypage 제거.
- /officer/criteria/:program, /officer/town, /officer/city 및 타 사업/역할 쿼리 복구 제거.
- 신청자/담당자 전환·취업지원 사업 필터/메뉴/지급 패널 제거.
- 현재 상세: /officer/review/:applicationId?document=:documentId&slot=:slotKey. 옛 /officer/province/review/:id는 현재 상세로 정규화.

## git diff --stat main (추적 파일 원문)
새 파일은 아직 stage하지 않아 아래 stat에 포함되지 않는다. 다음 status와 새 파일 목록을 함께 검토한다.

```text
 .trellis/spec/backend/index.md                     |    1 +
 .trellis/spec/frontend/index.md                    |    1 +
 README.md                                          |   99 +-
 demo/README.md                                     |  115 +-
 demo/frontend/index.html                           |    2 +-
 demo/frontend/package.json                         |    3 +-
 demo/frontend/src/App.tsx                          |  109 +-
 demo/frontend/src/api.ts                           |  971 +------
 demo/frontend/src/app-shell.css                    |  176 +-
 demo/frontend/src/components/CriteriaEditor.tsx    |  275 --
 demo/frontend/src/components/FileLink.tsx          |   27 -
 demo/frontend/src/components/FilePreview.tsx       |   78 -
 demo/frontend/src/components/Modal.tsx             |   58 -
 demo/frontend/src/components/PdfPages.tsx          |  171 --
 demo/frontend/src/components/SignaturePad.tsx      |  122 -
 demo/frontend/src/components/Skeleton.tsx          |   30 -
 demo/frontend/src/components/StatusBadge.tsx       |   33 +-
 demo/frontend/src/components/file-preview.css      |  111 -
 demo/frontend/src/components/modal.css             |  117 -
 demo/frontend/src/components/skeleton.css          |  133 -
 demo/frontend/src/forms/FormSheet.tsx              |  232 --
 demo/frontend/src/forms/PdfFormsWorkspace.tsx      | 1115 --------
 demo/frontend/src/forms/consent-model.ts           |   14 -
 demo/frontend/src/forms/email.ts                   |   10 -
 demo/frontend/src/forms/form-field-bindings.ts     |  170 --
 demo/frontend/src/forms/form1-model.ts             |  121 -
 demo/frontend/src/forms/form2-model.ts             |  165 --
 demo/frontend/src/forms/form5-model.ts             |   28 -
 demo/frontend/src/forms/pdf-forms-workspace.css    |  199 --
 demo/frontend/src/forms/phone.test.ts              |   30 -
 demo/frontend/src/forms/phone.ts                   |   29 -
 demo/frontend/src/forms/ymd.ts                     |   25 -
 demo/frontend/src/hooks/useDelayedFlag.ts          |   13 -
 demo/frontend/src/index.css                        |    6 +-
 demo/frontend/src/lib/period.ts                    |   88 -
 demo/frontend/src/navigation-url.ts                |   57 +-
 demo/frontend/src/pages/applicant/ApplyFlow.tsx    |  623 -----
 .../src/pages/applicant/DocumentUpload.tsx         |  637 -----
 demo/frontend/src/pages/applicant/FinalCheck.tsx   |  255 --
 .../frontend/src/pages/applicant/IdentityCheck.tsx |  384 ---
 demo/frontend/src/pages/applicant/MyPage.tsx       |  214 --
 .../frontend/src/pages/applicant/ProgramPicker.tsx |  566 ----
 demo/frontend/src/pages/applicant/SubsidyItems.tsx |  315 ---
 demo/frontend/src/pages/applicant/apply-flow.css   |  285 --
 .../src/pages/applicant/document-upload.css        |  697 -----
 demo/frontend/src/pages/applicant/final-check.css  |  191 --
 .../src/pages/applicant/identity-check.css         |  389 ---
 demo/frontend/src/pages/applicant/my-page.css      |  257 --
 .../src/pages/applicant/program-picker.css         |  439 ----
 .../frontend/src/pages/applicant/subsidy-items.css |  239 --
 .../frontend/src/pages/officer/ApplicationList.tsx |  468 +---
 demo/frontend/src/pages/officer/DocumentViewer.tsx |    4 +-
 demo/frontend/src/pages/officer/OfficerConsole.tsx |  271 +-
 demo/frontend/src/pages/officer/ReviewDetail.tsx   |  600 +----
 demo/frontend/src/pages/officer/ScoreSheet6.tsx    |    3 +-
 demo/frontend/src/pages/officer/format.ts          |   14 -
 demo/frontend/src/pages/officer/mock-data.ts       | 2719 +-------------------
 demo/frontend/src/pages/officer/officer.css        |  833 +-----
 docs/DEVELOPMENT.md                                |   52 +-
 59 files changed, 433 insertions(+), 14956 deletions(-)

```

## git status --short
```text
 M .trellis/spec/backend/index.md
 M .trellis/spec/frontend/index.md
 M README.md
 M demo/README.md
 M demo/frontend/index.html
 M demo/frontend/package.json
 M demo/frontend/src/App.tsx
 M demo/frontend/src/api.ts
 M demo/frontend/src/app-shell.css
 D demo/frontend/src/components/CriteriaEditor.tsx
 D demo/frontend/src/components/FileLink.tsx
 D demo/frontend/src/components/FilePreview.tsx
 D demo/frontend/src/components/Modal.tsx
 D demo/frontend/src/components/PdfPages.tsx
 D demo/frontend/src/components/SignaturePad.tsx
 D demo/frontend/src/components/Skeleton.tsx
 M demo/frontend/src/components/StatusBadge.tsx
 D demo/frontend/src/components/file-preview.css
 D demo/frontend/src/components/modal.css
 D demo/frontend/src/components/skeleton.css
 M demo/frontend/src/forms/FormSheet.tsx
 D demo/frontend/src/forms/PdfFormsWorkspace.tsx
 D demo/frontend/src/forms/consent-model.ts
 D demo/frontend/src/forms/email.ts
 D demo/frontend/src/forms/form-field-bindings.ts
 D demo/frontend/src/forms/form1-model.ts
 D demo/frontend/src/forms/form2-model.ts
 D demo/frontend/src/forms/form5-model.ts
 D demo/frontend/src/forms/pdf-forms-workspace.css
 D demo/frontend/src/forms/phone.test.ts
 D demo/frontend/src/forms/phone.ts
 D demo/frontend/src/forms/ymd.ts
 D demo/frontend/src/hooks/useDelayedFlag.ts
 M demo/frontend/src/index.css
 D demo/frontend/src/lib/period.ts
 M demo/frontend/src/navigation-url.ts
 D demo/frontend/src/pages/applicant/ApplyFlow.tsx
 D demo/frontend/src/pages/applicant/DocumentUpload.tsx
 D demo/frontend/src/pages/applicant/FinalCheck.tsx
 D demo/frontend/src/pages/applicant/IdentityCheck.tsx
 D demo/frontend/src/pages/applicant/MyPage.tsx
 D demo/frontend/src/pages/applicant/ProgramPicker.tsx
 D demo/frontend/src/pages/applicant/SubsidyItems.tsx
 D demo/frontend/src/pages/applicant/apply-flow.css
 D demo/frontend/src/pages/applicant/document-upload.css
 D demo/frontend/src/pages/applicant/final-check.css
 D demo/frontend/src/pages/applicant/identity-check.css
 D demo/frontend/src/pages/applicant/my-page.css
 D demo/frontend/src/pages/applicant/program-picker.css
 D demo/frontend/src/pages/applicant/subsidy-items.css
 M demo/frontend/src/pages/officer/ApplicationList.tsx
 M demo/frontend/src/pages/officer/DocumentViewer.tsx
 M demo/frontend/src/pages/officer/OfficerConsole.tsx
 M demo/frontend/src/pages/officer/ReviewDetail.tsx
 M demo/frontend/src/pages/officer/ScoreSheet6.tsx
 D demo/frontend/src/pages/officer/format.ts
 M demo/frontend/src/pages/officer/mock-data.ts
 M demo/frontend/src/pages/officer/officer.css
 M docs/DEVELOPMENT.md
?? .trellis/spec/backend/officer-demo-seeding.md
?? .trellis/spec/frontend/officer-documents.md
?? .trellis/tasks/11-13-savings-officer-only/
?? .trellis/workspace/codex/
?? demo/backend/tests/test_officer_frontend_integration.py
?? demo/backend/tests/test_seed_officer_demo.py
?? demo/backend/tools/seed_officer_demo.py
?? demo/frontend/src/pages/officer/document-groups.ts
?? demo/frontend/tests/

```

## 검수 제한
브라우저 접근 호스트가 unavailable을 반환하여 실제 브라우저 시각 검수와 메모 전환 수동 검수는 수행하지 못했다. 실제 시드 API 응답→동일 프런트 분류 함수→동일 React 목록 렌더러 통합 시험 및 코드 교차검토를 완료했다. 로컬 임시 검증 서버는 종료했고 기존 8000 포트 서비스는 중지/변경하지 않았다.

## 커밋 제안
1. feat(demo): focus repository on savings officer review
   - README.md, docs/DEVELOPMENT.md, demo/README.md
   - demo/frontend 변경·삭제 전체와 새 분류 모듈/시험
   - 새 시드 CLI와 신규 backend 시험 2개
   - .trellis/spec 관련 지침·index 및 이 태스크의 PRD/설계/실행/검증 기록

별도 후속 bookkeeping: .trellis/workspace/codex 초기화 파일은 work commit에서 제외하고 완료 기록 단계에서 처리한다. 알아보지 못한 사용자 변경 파일은 없다. 커밋 승인 전 git add/commit 하지 않는다. push하지 않는다.

## 승인 기록
2026-11-13 사용자 응답 `commit apply`로 위 작업 커밋 승인됨. 본문 수치와 목록은 승인 전 검토 시점의 기록으로 보존한다.
