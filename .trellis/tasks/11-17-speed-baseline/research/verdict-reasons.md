# 작업 D — 판정 사유의 위치 정보와 안내 문구 (읽기만, 코드 변경 없음)

기준 커밋: `fea711b`. "모름"은 이 저장소 코드에서 확인할 수 없는 사항이다.

## 1. assess_upload 결과에 담기는 것

| 항목 | 파일:행 | 내용 |
| --- | --- | --- |
| 판정 상태 | demo/backend/rules/doc_check.py:199-207 | `CheckResult.status`는 PASS / FAIL / NEEDS_REVIEW. FAIL이 재업로드(확실한 미비)에 해당한다. |
| 사유 한 건 | doc_check.py:178-196 | `CheckFinding`: code, message, how_to_fix, link, severity, detail. **서류 종류·쪽 번호·필드 이름·상자 좌표를 담는 구조화된 칸은 없다.** |
| 필드 이름이 들어가는 곳 | doc_check.py:259-273, 628-632 | `_finding(..., field="발급일")`처럼 필드 이름은 how_to_fix 문장을 만드는 format 인자로만 쓰인다 (문장 안의 글자). |
| detail | doc_check.py:185-186 | 담당자 전용 근거 문장(자유 문장). 신청자 API는 내보내지 않는다. |
| 위치 정보가 있는 곳 | demo/backend/ocr/base.py:58-59, documents.py:197-216 (`_ocr_json`의 `bboxes`), documents.py:229, 243 (`page_index`) | 상자 좌표는 사유가 아니라 **판독 결과의 필드별** `bboxes`(쪽 번호 + 좌표)에 있다. 병합 업로드의 쪽 번호는 문서 행의 `page_index`에 있다. 사유와 상자를 잇는 키는 없다. |

## 2. 담당자 화면(demo/frontend)이 받는 것과 보여 주는 것

| 항목 | 파일:행 | 내용 |
| --- | --- | --- |
| 담당자 API 응답 | demo/backend/api/officer.py:669, 673-675 | findings 전체(마스킹), page_index, extracted(필드값), bboxes를 함께 보낸다. findings에 detail도 들어 있다. |
| 프런트 타입 | demo/frontend/src/api.ts:7-13, 100-115 | `Finding`은 code, message, how_to_fix, link, severity만 정의한다(detail 없음). 문서에는 `bboxes`, `page_index`, `extracted`가 있다. |
| 사유 표시 | demo/frontend/src/pages/officer/ReviewDetail.tsx:146-150 | 사유마다 code, message, how_to_fix, link를 보여 준다. 위치로 가는 버튼은 없다. |
| 위치 표시 | ReviewDetail.tsx:153-155 | 판독 필드마다 bbox가 있으면 "원본 위치" 버튼으로 원본의 그 상자를 보여 준다. 사유가 아니라 필드 기준이다. |
| 신청 전체 사유 | ReviewDetail.tsx:122-127, api.ts:138 | 신청 건 단위 사유는 code, message, doc_type(서식 종류)을 보여 준다. |
| 목록 화면 | demo/frontend/src/pages/officer/ApplicationList.tsx:258 | 서류 사유는 message만 보여 준다. |
| detail 표시 | - | 담당자 화면 코드에서 detail을 읽는 곳을 찾지 못했다. 보여 주지 않는 것으로 보인다. |

## 3. 반려(재업로드) 안내 문구

- 안내 문구(how_to_fix)는 **사유 코드별 표** `HOW_TO_FIX`(doc_check.py:80~)에서 고르고, 서식 이름(`label`), 기준일(`cutoff`), 필드 이름 같은 인자로 채운다 (doc_check.py:259-266). 표에 없는 코드는 빈 문장이다.
- 심각도는 코드로 정한다: `REVIEW_ONLY_CODES`(doc_check.py:149~)에 있으면 NEEDS_REVIEW, 아니면 FAIL (doc_check.py:272).
- 일부 사유는 표를 거치지 않고 그 자리에서 문장을 만든다: 행정정보 동의 표시(upload_assessment.py:77-92), 영수증 판독·금액(upload_assessment.py:100-131, 금액이 문장에 들어감), 미상 서식(doc_check.py:508).
- 신청자 응답은 code, message, how_to_fix, link, severity만 내보내고, FAIL이 하나라도 있으면 NEEDS_REVIEW 사유는 숨긴다 (demo/backend/api/common.py:193-205, 212).
- 신청자 화면: 이 저장소의 demo/frontend에는 담당자 화면만 있어, 신청자가 how_to_fix를 어떻게 보는지는 **모름**.

## 4. doc_timing 요약에 쓰는 규칙

- VERDICT 분류: PASS, NEEDS_REVIEW, REUPLOAD(=FAIL), NOT_ASSESSED, OTHER(판정 오류 등).
- REASON 집계: 문서 상태가 NEEDS_REVIEW이면 NEEDS_REVIEW 사유, REUPLOAD(FAIL)이면 FAIL 사유만 센다. 한 문서의 같은 코드는 한 번, 다른 코드는 각각 센다.
- 코드는 등록된 고정 코드 목록(`verify_upload.SAFE_CODES`)에 있을 때만 그대로 쓰고, 그 밖은 UNKNOWN_CODE로 쓴다. message, how_to_fix, detail은 읽지도 저장하지도 않는다.
