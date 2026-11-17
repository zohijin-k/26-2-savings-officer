# 작업 D1 — 사실 확인 (읽기만, 코드 변경 없음)

기준 커밋 `345aa0f`. 실서류와 실서류 결과 폴더는 열지 않았다. "모름"은 저장소 코드·기록으로 확인할 수 없는 사항이다.

## a. own 모델 출처

진이 확인한 사실을 기록한다: `engine_v2/models/own/det.onnx`·`rec.onnx`의 SHA256은 `engine_v2/tools/fetch_own_models.py`에 고정된
공개 모델(ch_PP-OCRv5_det_mobile, korean_PP-OCRv5_rec_mobile, RapidOCR v3.10.0) 값과 일치한다. 미세조정은 하지 않았다
(`engine_v2/docs/own-ocr.md`의 2단계는 미착수).

이 사실과 어긋나거나 오해될 수 있는 저장소 표현 (고치지 않음):

| 파일:행 | 왜 어긋나는가 |
| --- | --- |
| docs/DEVELOPMENT.md:107 | "2단계 학습은 진행 중"이라고 쓴다. 미세조정은 미착수다 (engine_v2/docs/own-ocr-history.md:21, 120). |
| engine_v2/docs/own-ocr.md:4 | "2단계에서 … 추가 학습한다"를 확정 문장으로 쓴다. 계획이며 하지 않았다. |
| docs/PROJECT_PLAN.md:16 | 항목 이름이 "학습형 OCR"이다. 본문은 공개 사전학습 모델이라고 쓰지만 이름만 보면 학습시킨 OCR로 읽힐 수 있다. |

"학습시킨 OCR", "OCR 인식률 향상"처럼 이미 학습·개선했다고 쓴 문장은 찾지 못했다. 나머지 검색 결과(own-ocr-history.md, classifier.md 등)는
공개 모델·미세조정 미착수를 바르게 적고 있다.

## b. 외부 전송

**OCR 외부 전송: 조건부 — 진이 확인한 지금 환경(.env 없음, JBAI_·UPSTAGE_ 키 없음)에서는 없음.**

| 계층·경로 | 파일:행 | 외부로 나가는 조건 | 지금 환경 |
| --- | --- | --- | --- |
| 판독 체인 순서 | demo/backend/ocr/__init__.py:28, 38-51 | Fixture → JbaiOcr → LocalOcr → PdfText → UpstageOcr | - |
| JbaiOcr 켜짐 조건 | demo/backend/ocr/jbai.py:148-152 | `JBAI_API_KEY`가 비어 있지 않고 **그리고** `JBAI_ALLOW_REAL_DOCS`가 1/true/yes/on | 꺼짐 |
| JbaiOcr 맡는 서류 | jbai.py:220-239 | 기대 종류가 지원 4종, 첫 쪽 글자 없음, 글자층 쪽 없음 | - |
| 실제 전송 | jbai.py:252-265 → engine_v2/pipeline/jbai_ocr.py:477-482, 444-446 | 쪽 그림(JPEG)을 `/ocr/chat/completions`로 POST. 키가 없으면 477-479에서 설정 오류로 멈춤 | 보내지 않음 |
| 추가 차단 | jbai_ocr.py:414-425 | `JBAI_ALLOW_REAL_DOCS`가 거짓이면 데모 업로드·개인 자료 경로 전송을 막음 | 막힘 |
| UpstageOcr | demo/backend/ocr/upstage.py:27-38, 50 | 키가 있어도 `NotImplementedError`로 끝나 네트워크 코드가 없음 | 보내지 않음 |
| LocalOcr own | demo/backend/ocr/localocr.py:53-67, engine_v2/pipeline/ocr/own.py:38-54 | 내부 CPU ONNX | 내부 |
| 그 밖의 네트워크 코드 | engine_v2/tools/fetch_own_models.py:44, engine_v2/tools/fetch_synth_fonts.py:53 | 개발자가 직접 실행하는 모델·글꼴 내려받기. 서류를 보내지 않음 | 서비스 경로 아님 |

- 서비스 코드(demo/backend, engine, engine_v2의 시험·도구 제외)에서 네트워크로 나가는 호출은 jbai_ocr.py:446 하나뿐이다.
- `ENGINE_V2_OCR=easyocr`(또는 own 모델이 없어 easyocr로 대체될 때) easyocr가 처음 실행 때 자기 모델을 내려받는지는 저장소 코드로 확인할 수 없다: **모름**. 서류를 보내는 경로는 아니다.
- 실행 방법: 코드는 `.env`를 직접 읽지 않는다(demo/backend/requirements.txt:8의 설명대로 `uvicorn --env-file`일 때만 읽힘).

**전북AI LLM 호출 코드: 없음.** 저장소의 전북AI 호출은 `jbai_ocr.py`의 OCR/표 인식 작업(`TASK_OCR`, `TASK_TABLE`, jbai_ocr.py:40-41, 473)뿐이다.
반려 안내 문구 같은 글 생성 호출은 찾지 못했다. 반려 안내 문구는 지금 코드 표(`HOW_TO_FIX`, doc_check.py:80~)로 만든다.

## c. G2 재현 (11/13 "핵심 항목 추출 145/165", "서류 분류 20/25")

- 도구: `engine_v2.tools.documentai_staged`(내부에서 `documentai_corpus_v2.run`). 기록: `.trellis/tasks/archive/2026-11/11-13-documentai-measurement-audit/measurement-v2-n5-final.md:1, 21-22`.
- 세트: `--samples 5 --seed 20261113`의 `normal_baseline` 그룹(조건 original) 25건 = 5종 × 5건. 숫자는 B 단계(own OCR).
- 명령: `.venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output <WORK>/paired.json`
- 재현(이번 작업의 회귀 실행, HEAD `fea711b`·`345aa0f` 같은 결과): **서류 분류 20/25, 핵심 항목 145/165로 같다.** 차이 없음.

놓친 항목 (own, normal_baseline 25건):

| 서류 종류 | 항목 | 놓친 수 | 상태 | 원인 코드 | 근거 |
| --- | --- | --- | --- | --- | --- |
| nhis_payment | 월별고지금액 | 5/5 | MISSING | 구조 | 글자 그대로의 참조(A)는 맞고 own(B)만 빠짐. 11/13 기록: payment_component_headers·payment_columns·paid_total_matches 검증 실패 (report.md:30). 이번에 다시 진단하지 않음 |
| nhis_payment | 월별장기요양보험료 | 5/5 | MISSING | 구조 | 위와 같음 |
| nhis_payment | 건강보험료 | 5/5 | MISSING | 구조 | 위와 같음 |
| nhis_payment | 장기요양보험료 | 5/5 | MISSING | 구조 | 위와 같음 |
| insurance_4 | 성명·생년월일·발급일·발급번호·가입내역 | 25 (5종 × 5) | UNEXTRACTED_CLASSIFICATION | 판별 | 아래 진단. A·B 둘 다 판별 실패 |

145/165의 분모는 판별 성공으로 추출기가 불린 항목만이다. 4대보험 25항목은 분모 밖이다(전체 작성 항목 기준 145/190).

**4대보험 가입내역 0/5 진단 (진단만, 고치지 않음):** 판별 키워드는 `4대사회보험가입자가입내역확인서`, `4대사회보험정보연계`다
(demo/backend/ocr/pdftext.py:34, 108-115, 공백 제거 후 부분 일치). 합성 서식에서 제목이 두 줄("4대 사회보험" / "가입자 가입내역 확인서")이고,
둘째 줄과 같은 높이 왼쪽에 용도 표시 "확인용"이 있다. 쪽 읽기 순서로 이으면 `4대사회보험확인용가입자가입내역확인서`가 되어 첫 키워드가 끊기고,
둘째 키워드 문구는 이 서식에 없다. 좌표 대체 판별(pdftext.py:118-130)은 일용근로·주민등록표만 본다. 그래서 5건 모두 None이다.
글자를 완벽히 준 A 단계도 같으므로 OCR 원인이 아니다.

## d. batch_assess

| 질문 | 답 | 파일:행 |
| --- | --- | --- |
| 판정 경로 | 서비스 `assess_upload`로 서류 단위 판정. 다만 **판독은 운영 경로가 아니다**: 모든 쪽을 300dpi로 렌더링해 OCR을 강제로 돌리고(글자층 쪽 포함), 그 결과를 운영 변환 함수와 `read_document` 마무리에 넣는다 | engine_v2/tools/batch_assess.py:471-511, 520-528, 531-587, 664-680 |
| 엔진 | own(기본), 선택으로 own + applevision. 글자층 참조는 비교용 | batch_assess.py:744-753, 770-776, 1000 |
| 단위 | 파일 하나(PDF와 jpg·png·heic·gif·jfif). 첫 단계 폴더는 숫자 그룹으로만 쓰고 신청 건 단위 판정은 없음 | batch_assess.py:31, 213-231, 834-838 |
| 슬롯 | 판별 종류로 고르는 두배적금 슬롯. 일용·농어업 등은 NOT_ASSESSED | batch_assess.py:648-680 |
| 암호 | `ENCRYPTED` 오류, document_status ERROR, open_failed 참 | batch_assess.py:482-483, 732-741 |
| 열기 오류 | `OPEN_ERROR`(이미지는 `DECODE_ERROR`), ERROR | batch_assess.py:496-500, 733-741 |
| 출력 | 화면은 진행 숫자와 요약 표(코드·종류·비율). 결과 파일: run.json에 **루트 절대경로**(820행), results.jsonl에 **루트 상대경로 ID**(844행). 값은 저장하지 않음 | batch_assess.py:785-786, 820, 844, 877-978 |
| 적합/확인 필요/재업로드 | PASS/FAIL/NEEDS_REVIEW/NOT_ASSESSED/ERROR 개수와 비율을 냄. 분모가 오류 포함 전체 파일 수 | batch_assess.py:885-886 |
| 사유 상위 10개 | **없음.** 사유는 상태 구분 없이 전체에서 세고(문서당 같은 코드 한 번), 기준일/품질/기타로 나눠 전부 출력 | batch_assess.py:936-940 |
| 사유 1위만 있는 건수 | **없음** | - |

부족한 점과 최소 변경 제안 (구현은 승인 후):
1. `--summarize`에 표 하나 추가: PDF만, 제외(ENCRYPTED·OPEN_ERROR·EMPTY_DOCUMENT)와 그 밖의 오류를 따로 세고, 판정 분모(PASS+NEEDS_REVIEW+FAIL)로 비율을 내고,
   NEEDS_REVIEW와 FAIL 각각의 사유 상위 10개(그 상태의 심각도 사유만, 문서당 코드 한 번)와 "1위 사유만 있는 문서 수"를 숫자·코드로 낸다. 기존 표는 그대로 둔다. 결과 행은 바꾸지 않으므로 오늘 밤 실행 결과에 나중에 적용할 수 있다.
2. (선택) 판독을 운영 경로(`read_document`)로 하는 선택 옵션. 지금 A 값은 "모든 쪽 own OCR 강제" 판정이므로 운영 업로드 판정과 다를 수 있다. 운영 경로 판정 분포는 doc_timing의 DECISION 줄로 따로 볼 수 있다(사유 없음).
3. (선택) run.json의 루트 절대경로를 숫자 지문으로 바꾸기. 출력 규칙(값·경로 없음)과 맞추기 위함.

## e. 판정 사유와 위치

`research/verdict-reasons.md`를 그대로 쓴다. 추가로 사유 코드마다 관련 항목(필드)을 하나로 정할 수 있는지 셌다.

- 범위: 등록 코드 107개(`demo/backend/tools/verify_upload.py:474~`) 가운데 `assess_upload`가 낼 수 있는 서류 단위 사유 40개
  (doc_check.py, upload_assessment.py, engine/stage1_document_check.py에서 나오는 코드, 상태 낱말 ALL_CLEAR·MISSING·READABLE 제외).
- 나머지 67개는 서류 판정 사유가 아니다: 상태 낱말(PASS, FAIL, NEEDS_REVIEW, INFO, MET, NOT_MET, UNDETERMINED, ALL_CLEAR, MISSING, READABLE)과
  점수·소득·근로 연속성·자격 단계 코드(scoring.py, facts.py, work_continuity.py, eligibility_blockers.py, engine/stage2).
- 판단 근거는 코드가 나오는 자리(어떤 판독 필드를 읽는지)다. 사유에 필드가 구조적으로 담기는 경우는 없다(verdict-reasons.md 1절).

| 구분 | 수 | 코드 |
| --- | --- | --- |
| O (한 항목) | 14 | ADMIN_CONSENT_MARK_UNREADABLE(동의여부), ADMIN_CONSENT_NOT_GIVEN(동의여부), ADMIN_CONSENT_SIGNATURE_UNREADABLE(서명잉크확인), DECLARED_DATE_MISMATCH(발급일), DECLARED_DATE_UNCERTAIN(발급일), DOCUMENT_ISSUED_AFTER_APPLICATION(발급일), DOCUMENT_ISSUED_TOO_EARLY(발급일), MISSING_ADDRESS_DATES(주소날짜검증자료), MISSING_ADDRESS_HISTORY(주소변동내역), MISSING_BILLING_MONTHS(월별 고지 내역), MISSING_SIGNATURE(서명), PAST_ADDRESS_OMISSION_SUSPECTED(주소이력), RECEIPT_AMOUNT_MISMATCH(결제금액), RECEIPT_AMOUNT_UNREADABLE(결제금액) |
| 여러 개 | 12 | ADMIN_CONSENT_IDENTITY_MISMATCH·_UNCERTAIN·_UNREADABLE(성명·생년월일), IDENTITY_MISMATCH, IDENTITY_UNCERTAIN, NHIS_SUBSCRIBER_IDENTITY_REVIEW, NHIS_DEPENDENT_INSURED_PERSON(성명·생년월일·가구원), RESIDENT_APPLICANT_UNREADABLE(초본신청인 성명·생년월일), NHIS_HISTORY_PERIOD_MISSING·_UNREADABLE(자격이력자료·발급일), MISSING_REQUIRED_FIELD·REQUIRED_FIELD_UNREADABLE(경우마다 다른 필드, 문장 인자로만 전달) |
| 해당 없음 | 14 | UNREADABLE_FILE, LOW_IMAGE_QUALITY, IMAGE_RESOLUTION_TOO_LOW, SCREEN_CAPTURE_SUSPECTED, LOW_OCR_CONFIDENCE, WRONG_DOCUMENT_TYPE, UNKNOWN_DOCUMENT_TYPE, PAGES_DUPLICATED, PAGES_INCOMPLETE, PAGES_UNREADABLE, NHIS_PAYMENT_PAGING_UNCERTAIN, RECEIPT_OCR_UNAVAILABLE, DAILY_RECORDS_PARTIALLY_SELECTED(발급 선택 범위), MISSING_REQUIRED_DOC(서류 미제출; 서류 판정에서 실제로 나오는지는 모름) |

**O 비율: 14/40 = 35.0%.** O인 코드라도 화면에서 원본 위치를 보이려면 그 필드에 bbox가 있어야 한다. 파생 필드(주소날짜검증자료, 월별 고지 내역 등)에
bbox가 있는지는 서식마다 다르며 이번에 확인하지 않았다: 모름.

## f. doc_timing 결과 행의 판정 상태·사유 (A 주 지표용)

| 항목 | 저장 여부 | 파일:행 |
| --- | --- | --- |
| 판정 상태 | **저장함**: 결과 행 `decision` = PASS / FAIL / NEEDS_REVIEW / NOT_ASSESSED / ERROR (측정 반복마다 한 줄) | engine_v2/tools/doc_timing.py:316, 327, 347-352 |
| 판별 종류·글자층·쪽수·판독 계층 | 저장함: `form`, `text_layer`, `pages`, `tier` | doc_timing.py:347-352 |
| 제외·오류 | 저장함: `phase=skipped` + `code` ENCRYPTED/OPEN_ERROR/EMPTY_DOCUMENT, 처리 오류는 `code` PROCESSING_ERROR/GUARD_BLOCKED | doc_timing.py:347-352, 오류 처리 부분 |
| 사유 코드 | **저장하지 않음.** `assess_upload` 결과의 `findings`를 읽지 않는다 | doc_timing.py:318-327 |

최소 변경 제안 (구현은 승인 후): `measure`에서 `checked.findings`의 `(code, severity)`를 문서당 중복 없이 정렬해 결과 행에 `reasons` 목록으로 저장한다.
코드는 `verify_upload.SAFE_CODES`에 있을 때만 그대로, 그 밖은 UNKNOWN_CODE로 쓰고 문장(message·how_to_fix·detail)은 읽지 않는다. 결과 행 형식 판을 올린다.
요약 줄 추가는 하지 않는다(A7·A8은 측정 정의 문서의 계산식으로 결과 행에서 센다). 시간 측정 구간 밖에서 하므로 시간 값에는 영향이 없다.
