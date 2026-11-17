# 작업 A — 운영 호출 경로 (코드 변경 없음)

기준 커밋: main `f6d9827`. 실서류와 결과 폴더는 열지 않았다. 행 번호는 이 커밋 기준이다.
"모름"은 코드에서 확인할 수 없는 운영 환경 사항이다.

## 1. 신청자 PDF 한 건 업로드 경로 (슬롯 지정)

| 단계 | 파일:행 | 엔진 | 글자층 사용 | 쪽 처리 |
| --- | --- | --- | --- | --- |
| 업로드 받기, 파일 저장 | demo/backend/api/documents.py:278-312 | - | - | - |
| 판정 묶음 호출 | demo/backend/api/documents.py:327-336 → demo/backend/upload_assessment.py:42-58 | - | - | - |
| 판독 체인 시작 | demo/backend/ocr/__init__.py:28, 31-51 (`read_document(path, req.doc_type)`) | 계층 순서대로 첫 결과 | - | 문서 단위 |
| Tier1 Fixture | demo/backend/ocr/fixture.py:381-386 | 파일 이름이 시연 표에 있을 때만 | - | - |
| Tier1.2 JbaiOcr | demo/backend/ocr/jbai.py:148-152, 220-239 | `JBAI_API_KEY`와 `JBAI_ALLOW_REAL_DOCS`가 모두 있고, 기대 종류가 지원 4종이고, 첫 쪽에 글자가 없고, 글자층 쪽이 하나도 없을 때만 | 글자층 PDF는 맡지 않음 | 문서 단위 |
| Tier1.5 LocalOcr 진입 | demo/backend/ocr/localocr.py:663-671 | `engine_decision()` (53-67): `ENGINE_V2_OCR`가 있으면 그 값, 없으면 own 모델 3개가 있을 때 own, 없으면 easyocr | - | - |
| 글자층 PDF 판단 | demo/backend/ocr/localocr.py:647-657, 678 | - | 첫 쪽에 공백 아닌 글자가 하나라도 있으면 글자층 PDF로 본다 | 첫 쪽만 봄 |
| 글자층 PDF: 1차 판별 | localocr.py:684 → demo/backend/ocr/pdftext.py:329-354 | - | 첫 쪽 글자만 읽어 판별 | 첫 쪽만 |
| 글자층 PDF: 담당 서식 고르기 | localocr.py:688-697 | - | 납부·득실·자격(통지형)·4대보험·사업자증명·일용·취업서류·미판별만 LocalOcr가 맡음. 그 밖(초본 등)은 None → PdfText | - |
| 글자층 PDF: 쪽 읽기 | localocr.py:716-719 → engine_v2/engine.py:173-204 → engine_v2/pipeline/preprocess.py:83-93, 137-145 | 글자 50자 미만인 쪽에만 `run_ocr(engine)` | 쪽마다 글자 50자 이상이면 글자층 단어를 그대로 씀 | 쪽 단위, 차례로 |
| 글자층 PDF: 미판별 재판별 | localocr.py:722-738 → pdftext.py:118-130 | - | 쪽 전체 글자(글자층 또는 OCR) | 문서 단위 |
| 글자층 PDF: 추출 | localocr.py:739-760, 524-534 (`extract_form`) | - | 위에서 읽은 쪽 | 문서 단위 |
| 이미지 PDF: 쪽 준비 | localocr.py:762-767 → preprocess.py:115-129 | - | 한 쪽이라도 글자층이면 None으로 넘김 | 쪽 단위 |
| 이미지 PDF: OCR | localocr.py:769-774 → engine_v2/pipeline/ocr/__init__.py:158-168 → own.py:114-135 | own(기본), applevision, easyocr, paddle | - | 쪽 단위, 차례로 |
| 이미지 PDF: 판별 | localocr.py:777 → pdftext.py:118-130 | - | - | 문서 단위 |
| 이미지 PDF: 추출 | localocr.py:793-846 | - | - | 문서 단위 |
| Tier2 PdfText | demo/backend/ocr/pdftext.py:406-420, 329-354 | 없음 | 첫 쪽 글자만 정규식으로 판별·추출 | 첫 쪽만 |
| Tier3 Upstage | demo/backend/ocr/upstage.py:35-38, 50 | 키가 있어도 `NotImplementedError` → 건너뜀 | - | - |
| 판독 뒤 공통 처리 | demo/backend/ocr/__init__.py:79-95 | - | file_evidence가 PDF를 두 번 더 열어 쪽마다 글자 수와 큰 이미지를 봄 (file_evidence.py:21-46, 49-93) | 쪽 단위 |
| 서류 단위 판정 | upload_assessment.py:70-73, 133 → demo/backend/rules/doc_check.py:963-978 (안에서 `engine.stage1_document_check.check_single_document`, doc_check.py:633) | - | - | 문서 단위 |
| 납부·자격 짝 재판정 | documents.py:349-353 → upload_assessment.py:137-190 | - | 저장된 판독값만 씀 (다시 읽지 않음) | - |
| 신청 건 단위 판정 | demo/backend/api/review.py:521 → demo/backend/engine_adapter.py:246-270 → engine/pipeline.py:78 | - | - | 신청 건 단위 (업로드 때가 아니라 담당자 검토 때) |

병합 업로드(`slot_key=auto`, documents.py:300-302, 357-468)는 `split_pdf_pages`(pdftext.py:423-452)로
쪽마다 글자층만 읽고 OCR을 하지 않는다. 슬롯 지정 업로드와 다른 경로다.

## 2. 글자층 PDF에 OCR이 도는가

**한 줄 답:** 쪽마다 글자가 50자 이상이면 OCR을 하지 않고 글자층만 쓴다. OCR은 글자층 PDF 안의 글자 50자 미만 쪽(첨부 이미지 쪽 등)에만, 그 쪽만 돈다.

근거:
- 글자층 PDF인지는 첫 쪽 글자 유무 하나로 정한다 (localocr.py:647-657, 678). 문서 단위 판단이다.
- 그 뒤 쪽마다 `TEXT_LAYER_MIN_CHARS = 50`(preprocess.py:25, 89-93)로 글자층/OCR을 나눈다. 글자층 쪽은 글자층 단어를 OcrResult("text_layer")로 감싸고(engine.py:179-194), 그 밖의 쪽만 `run_ocr`(engine.py:195-203)를 탄다. 쪽 단위 판단이다.
- 초본처럼 LocalOcr가 맡지 않는 글자층 PDF는 PdfText가 **첫 쪽 글자만** 읽는다 (pdftext.py:346-354). 나머지 쪽은 읽지 않는다.
- 첫 쪽에 글자가 조금(1~49자) 있는 이미지 PDF는 글자층 PDF 경로로 들어가고, 글자 50자 미만인 쪽은 렌더링·OCR한다.
- 첫 쪽이 이미지이고 뒤쪽에 글자층이 있는 PDF는 LocalOcr가 None을 돌려주고(localocr.py:766-767), PdfText도 첫 쪽 글자가 없어 None이 된다. 결과는 tier "none", 신뢰도 0이다 (ocr/__init__.py:53-62).

## 3. engine_v2 경로와 demo/backend 경로

| 부분 | demo/backend (운영 업로드) | engine_v2 (`engine_v2.engine.run`, tools/run_engine.py) | 같은가 |
| --- | --- | --- | --- |
| 쪽 준비 | preprocess.py `preprocess` | 같음 | 같음 |
| 쪽 읽기 | engine.py `_load_pages` (localocr.py:717-719에서 호출) | engine.py:242 `_load_pages` | 같음 (글자층 PDF일 때) |
| 이미지 PDF 쪽 읽기 | localocr.py:769-774 자체 반복문 (`allow_page_errors` 없음, 한 쪽이라도 오류면 None) | engine.py:195-203 | 다름 (같은 `run_ocr`를 쓰지만 반복문과 오류 처리가 다름) |
| 기본 엔진 | localocr.py:53-67: 맥에서도 own | engine_v2/pipeline/ocr/__init__.py:140-142: 맥이면 applevision | 다름 |
| 판별 | pdftext.py `classify_pages_with_evidence` (내용 기반) | 신고한 종류로 추출기를 고름 (engine.py:87) | 다름 |
| 추출 | 각 추출기 `extract` + localocr.py `_from_*` 변환 | engine.py:93-94 `extract_form(extractor)` | 추출기 함수는 같고 변환은 다름 |
| 서류 판정 | doc_check.py `check_document` + engine/stage1 | engine.py:104-170 rulepack 규칙 | 다름 |

## 4. 쪽 처리 방식, own 스레드, 모델 불러오기

- 쪽은 **차례로** 처리한다: preprocess.py:145(목록 내포), engine.py:178 반복문, localocr.py:770 반복문. 스레드 풀이나 프로세스 풀은 없다.
- 업로드 엔드포인트는 `async def`(documents.py:279) 안에서 동기 함수 `assess_upload`를 바로 부른다(documents.py:327). 그래서 판독하는 동안 이벤트 루프가 막힌다. 동시 업로드가 서로를 기다리는지는 실행 설정(워커 수)에 달렸고, 운영 실행 설정은 **모름**. README의 실행 예시는 `uvicorn demo.backend.main:app --reload --port 8000`(워커 옵션 없음)이다.
- own ONNX 스레드: `intra_op_num_threads = 2`, `inter_op_num_threads = 1`로 고정돼 있다 (own.py:43-45). 환경 변수로 바꾸는 길은 없다. OpenCV·numpy 스레드 수는 따로 정하지 않는다 (실제 값은 **모름**, 라이브러리 기본값).
- own 모델은 `@lru_cache(maxsize=1)`인 `sessions()`(own.py:38-54)로 **프로세스마다 한 번** 불러온다. 첫 OCR 호출(own.py:115) 때 불리며, 이때 모델 파일 SHA256 확인(fetch_own_models.py:23-30)도 함께 한다. 앱 시작(main.py:24-29)에서는 미리 불러오지 않는다. 그래서 프로세스의 첫 이미지 서류가 불러오는 시간을 떠안는다.
- `engine_decision()`은 요청마다 모델 파일 3개가 있는지 확인한다(localocr.py:65). 파일 존재 확인만 하고 불러오지는 않는다.

## 5. 측정 도구가 운영과 다르게 하는 부분 (작업 B에 반영)

- 신청 건 단위 판정(review.py:521)은 업로드 때 돌지 않으므로 서류당 시간에서 뺀다.
- 슬롯: 운영에서는 신청자가 고른 슬롯 기대 종류가 `read_document`에 들어간다. own 경로에서 기대 종류를 쓰는 계층은 JbaiOcr뿐이고(fixture·LocalOcr·PdfText는 무시), 도구는 JBAI를 끈다. 그래서 도구는 `expected=None`으로 읽고, 판별된 종류로 슬롯을 골라 판정한다 (batch_assess `_requirement`와 같은 방식).
- 신원 정보(성명·생년월일 대조)와 신고 발급일은 없으므로 None으로 둔다. 짝 재판정(documents.py:349-353)과 DB 저장은 하지 않는다.
- 병합 업로드 경로는 재지 않는다.
- 서버 부분은 시간에서 뺀다: HTTP 요청·파일 받기와 디스크 쓰기(documents.py:278-312), DB 조회·저장(`_load`, `_checklist`, `_replace_existing`, `_save_row`, `_list_documents`), 응답 만들기.
- 기본 두배적금 체크리스트에 업로드 슬롯이 없는 종류(일용근로·농어업 증명·취업지원패키지 서류·미판별)는 판독·추출까지만 재고 판정은 NOT_ASSESSED로 센다.
- 도구가 감싸개를 설치할 때 추출기 모듈을 미리 import한다. 운영에서는 첫 사용 때 import되므로 그 시간은 예열 실행이 대신 받는다.
- 모델은 미리 불러오지 않는다. 첫 OCR 호출의 불러오기 시간은 COLD_START로 따로 적고 그 서류 시간에서 뺀다.

## 6. 6단계 후보 (이번 작업에서는 바꾸지 않음)

1. 글자층 판정을 첫 쪽 하나로 정한다 (localocr.py:647-657, 678; pdftext.py:346-354). 첫 쪽이 이미지이고 뒤쪽이 글자층인 문서는 아무 계층도 읽지 않아 신뢰도 0이 된다. 글자층 PDF로 판정돼 PdfText가 맡는 서식은 첫 쪽만 읽는다.
2. 쪽을 차례로 처리하고(preprocess.py:145, engine.py:178, localocr.py:770), own ONNX 스레드를 intra 2·inter 1로 고정했다 (own.py:43-45).
3. own 모델을 첫 OCR 호출 때 불러온다 (own.py:38-54, 115). 앱 시작 때 미리 불러오지 않아(main.py:24-29) 프로세스의 첫 이미지 서류가 불러오기·SHA256 확인 시간을 떠안는다.
4. 업로드 처리 중 서버가 막힌다: `async def` 업로드 엔드포인트가 동기 판독·판정을 직접 부른다 (documents.py:279, 327).
