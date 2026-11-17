# 가~마 사실 확인 (읽기와 합성 재현만, 운영 코드 변경 없음)

기준 커밋 main `574eb5f`. 실서류와 실서류 결과 폴더는 열지 않았다. 행 번호는 이 커밋 기준이다.
"모름"은 저장소 코드로 확인할 수 없는 사항이다. 합성 재현 스크립트는 작업 공간 `<WORK>/scratch`에 두고 커밋하지 않는다.

## 가. A-스캔(batch_assess) 공정성

| 값 | 어디서 오는가 | 파일:행 | 판정·서식에 영향 |
| --- | --- | --- | --- |
| `detected_type` | 모든 쪽 300dpi 렌더링 → own OCR → `pdftext.classify_pages_with_evidence`(내용) | engine_v2/tools/batch_assess.py:486-492, 539, 616-618 | 내용만 쓴다. 파일·폴더 이름을 보지 않는다. |
| `slot` | `detected_type`으로 두배적금 체크리스트에서 업로드 슬롯을 고름 (`_requirement`) | batch_assess.py:648-661, 671, 680 | 판별된 종류에서 나온다. 이름과 무관. |
| `work_category` | `detected_type`이 INSURANCE_4면 직장가입자, BIZ_REG_PROOF면 사업소득 사업자 (`WORK_MAPPING`) | batch_assess.py:61, 653, 680 | 판별된 종류에서 나온다. 이름과 무관. |
| `group` | **첫 단계 폴더 이름**을 처음 본 순서대로 1, 2, 3…으로 바꾼 숫자. 루트 바로 아래 파일은 0 | batch_assess.py:834-838, 848 | `_assess`·`assess_upload`에 넘기지 않는다. 요약의 "폴더별 동일 종류 복수 파일" 표에서만 쓴다 (batch_assess.py:917-931). 판정·`detected_type`에 영향 없음. |
| 파일 경로 | `assess_upload(path, …)`가 확장자만 씀(`path.suffix`) | demo/backend/upload_assessment.py:71, 133; batch_assess.py:579-580 | 확장자로 사진/PDF 처리만 갈린다(파일 형식). 이름 본문은 쓰지 않는다. |
| 판독 체인 | `read_document`의 CHAIN을 이미 읽은 결과 하나로 바꿔 끼움 | batch_assess.py:583-586 | 이름으로 찾는 FixtureOcr(demo/backend/ocr/fixture.py:381-384)가 A-스캔에서는 돌지 않는다. |

참고: 운영 경로(A, doc_timing)는 CHAIN 전체를 쓰므로 FixtureOcr가 **파일 이름(stem)이 시연 표에 있을 때** 결과를 돌려준다
(fixture.py:381-384, demo/backend/ocr/__init__.py:28). **시연 전용 예외로 기록만 한다. 실서류 측정(A `hub_full_1`)에서 fixture 0건(진 확인). 코드는 바꾸지 않는다.**
진단 도구 crosstab의 TIER 줄에서도 `tier=fixture` 개수를 볼 수 있다.

## 나-1. 운영 경로(read_document)가 서식 미분류로 끝나는 조건

### LocalOcr가 None을 돌려주는 조건 (demo/backend/ocr/localocr.py)

| 조건 | 파일:행 | 다음 계층 결과 |
| --- | --- | --- |
| 파일 없음, 확장자가 pdf/jpg/jpeg/png 밖 | localocr.py:675-676 | PdfText: 이미지 판정 또는 None |
| (글자층 길) 첫 쪽에 공백 아닌 글자가 하나라도 있으면 글자층 PDF로 봄 | localocr.py:647-657, 678 | - |
| (글자층 길) `pdftext._read_pdf`가 None | localocr.py:684-686 | - |
| (글자층 길) 첫 쪽 판별이 LocalOcr 담당 밖 서식(초본·동의서 등) | localocr.py:688-690 | PdfText가 첫 쪽으로 판독 |
| (글자층 길) 자격확인서인데 통지형 아님 | localocr.py:691-697 | PdfText |
| (글자층 길) OCR 엔진 off | localocr.py:698-699 | - |
| (글자층 길) `_load_pages`가 문자열(오류)을 돌려줌. 4종 밖은 한 쪽이라도 OCR 오류면 오류 | localocr.py:716-721, engine_v2/engine.py:195-203 | PdfText: 첫 쪽 글자로 판독(서식 X 가능) |
| (글자층 길) **첫 쪽 판별 실패 → 모든 쪽(글자층+OCR)으로 다시 판별했는데 일용·초본·등본이 아님** | localocr.py:722-730 | **다시 판별에서 납부·자격 등을 찾아도 버림.** PdfText가 첫 쪽만으로 X를 냄 |
| (그림 길) `preprocess`가 ValueError (암호, 지원 안 하는 형식, **흑백 마스크 그림의 색 변환 오류**) | localocr.py:762-765, engine_v2/pipeline/preprocess.py:116-118, 143-144, 158 | PdfText: 첫 쪽 글자 없음 → None → tier none |
| (그림 길) 한 쪽이라도 글자 50자 이상(첫 쪽은 글자 없음) | localocr.py:766-767, preprocess.py:89-93 | tier none |
| (그림 길) 한 쪽이라도 OCR 오류 (`run_ocr`가 error를 돌려줌: 모델 없음, own 줄 너비 4096 초과 등) | localocr.py:769-773, engine_v2/pipeline/ocr/__init__.py:158-168, own.py:126-127 | tier none |
| (그림 길) 판별 실패이고 오른쪽 위 쪽 표시(n/m)도 없음 | localocr.py:777-784 | tier none |
| (그림 길) 판별 실패지만 쪽 표시가 있음 → 서식 없는 결과를 돌려줌 | localocr.py:778-791 | tier localocr, 서식 X |
| (그림 길) 자격확인서인데 통지형 아님 → `_generic`이 다시 판별 실패 | localocr.py:813-819, 841, 616-626 | tier none 가능 |
| LocalOcr 안의 **모든 예외** (OcrFallback 아님) | demo/backend/ocr/__init__.py:48-49 | 조용히 다음 계층. **사유가 남지 않는다** |

**OcrFallback:** LocalOcr와 PdfText는 OcrFallback을 내지 않는다. OcrFallback을 내는 곳은 JbaiOcr뿐이다
(demo/backend/ocr/jbai.py:245-295). doc_timing은 JBAI를 끄므로(doc_timing.py:60 `DISABLED_ENV`) 실서류 A 실행에서 대체 사유는 **생기지 않는다.**

### PdfTextOcr가 서식 미분류로 끝나는 조건 (demo/backend/ocr/pdftext.py)

| 조건 | 파일:행 |
| --- | --- |
| 첫 쪽 글자가 없으면 None (그림 PDF) | pdftext.py:346-350 |
| **첫 쪽 글자만** 키워드 판별. 키워드가 둘째 쪽 이후에만 있거나, 첫 쪽 글자층이 깨진 글자(스캐너가 넣은 숨은 글자층 등)이면 X | pdftext.py:346-352, 108-115, 103-105 |
| 판별은 공백 제거 후 고정 키워드 부분 일치 하나뿐 (좌표 대체 판별 없음) | pdftext.py:26-52, 108-115 |

### 운영 경로(A)와 A-스캔의 차이

| 항목 | A: `read_document` (doc_timing) | A-스캔: batch_assess | 파일:행 |
| --- | --- | --- | --- |
| 그림 쪽 입력 | 쪽 면적 90% 이상을 덮는 **가장 큰 그림 하나를 원본 해상도로 꺼냄** (SMask·마스크·다른 층 무시). 없으면 300dpi 렌더링 | **모든 쪽을 300dpi로 렌더링**(모든 층 합성, 투명도는 흰 바탕, alpha 없음) | preprocess.py:95-130 / batch_assess.py:486-492 |
| 글자층 쪽 | 글자 50자 이상 쪽은 OCR 없이 글자층 단어 사용 | 글자층 쪽도 렌더링해 OCR (글자층은 비교용 참조로만) | preprocess.py:89-93, engine.py:178-194 / batch_assess.py:493-495, 770-776 |
| 글자층 PDF 판정 | 첫 쪽 글자 1자 이상이면 글자층 길 | 없음 (항상 OCR) | localocr.py:647-657 / - |
| 판별 함수 | 글자층 길: `classify_with_evidence`(첫 쪽 글자) → 실패 시 모든 쪽 다시 판별(일용·초본만 채택). 그림 길: `classify_pages_with_evidence`(모든 쪽) | `classify_pages_with_evidence`(모든 쪽 OCR) | pdftext.py:346-352, localocr.py:722-730, 777 / batch_assess.py:539 |
| 판별 실패 처리 | None → 다음 계층 → tier none 또는 pdftext X | 서식 없는 결과로 계속 | ocr/__init__.py:53-60 / batch_assess.py:570-572 |
| 오류 처리 | LocalOcr 예외는 삼키고 사유 없음, 한 쪽이라도 OCR 오류면 전체 None | 쪽 OCR 예외면 엔진 ERROR 행 | ocr/__init__.py:48-49, localocr.py:771-773 / batch_assess.py:636-641 |
| 예상 서식 전달 | doc_timing은 None. 운영 업로드는 슬롯 종류를 넘기지만 LocalOcr·PdfText는 무시 | None | localocr.py:664, pdftext.py:412 / batch_assess.py:586 |
| 쪽 수·크기 제한 | 없음. own 검출은 긴 변 1600px 이하로 줄임, 인식 줄 너비 4096 초과면 ValueError | 같은 OCR 함수 | own.py:70, 126-127 |
| 대상 확장자 | doc_timing은 PDF만 | pdf, jpg, jpeg, png, heic, gif, jfif | doc_timing.py:714-715 / batch_assess.py:31 |
| 이름으로 찾는 Fixture | 켜짐 (stem) | 꺼짐 | fixture.py:381-384 / batch_assess.py:583-586 |

## 나-2. 합성 재현 (같은 합성 그림, A = `read_document`, A-스캔 = `batch_assess.process_file`)

합성 원본: `documentai_corpus_v2.sources(0)`의 초본·납부확인서·자격확인서 그림(300dpi)을 여러 방식으로 PDF에 넣었다.

| 조건 | A 서식 / tier | A-스캔 서식 | 실패 단계 |
| --- | --- | --- | --- |
| 그림 하나 300dpi (기준) | 맞음 / localocr | 맞음 | - |
| 쪽 회전 90·270, 그림 변환 회전 90 | 맞음 / localocr | 맞음 | 재현 안 됨 |
| 그림 100dpi, 120dpi | 맞음 / localocr | 맞음 | 재현 안 됨 |
| 흑백 1비트, JPEG | 맞음 / localocr | 맞음 | 재현 안 됨 |
| **숨은 글자층(보이지 않는 글자 50자 이상, 서식과 무관한 글자)** | **X / pdftext** (3종 모두) | 맞음 | 첫 쪽 글자층만 판별, OCR 안 함 |
| **첫 쪽 글자 1~49자 + 그림** | 초본은 맞음, **납부·자격 X / pdftext** | 맞음 | localocr.py:729-730 다시 판별 결과 버림 |
| **첫 쪽 그림 + 둘째 쪽 글자층** | **X / none** (3종 모두) | 맞음 | localocr.py:766-767 |
| **흑백 마스크 그림(ImageMask)** | **X / none** (초본·납부) | 맞음 | preprocess ValueError → localocr.py:764-765 |
| **2층 MRC: 저해상도 배경 + 고해상도 글자 마스크** | **X / none** | 맞음 | 가장 큰 그림 = 마스크 → ValueError |
| **2층 MRC: 고해상도 빈 배경 + 저해상도 글자 마스크** | **X / none** | 맞음 | 가장 큰 그림 = 빈 배경만 꺼냄 → OCR 0자 |
| **투명 배경 그림(SMask)** | **X / none** | 맞음 | SMask 무시 → 검은 바탕에 검은 글자 → OCR 0자 |

해석: A-스캔은 렌더링이 모든 층과 투명도를 합성하므로 위 조건에서 모두 판별한다. 실서류에서 각 조건이 몇 건인지는 진의 실서류 진단(trace)으로 센다.
회전·저해상도는 합성에서 재현되지 않았으므로 원인 후보에서 낮게 둔다(실서류에서 따로 센다).

## 나-3. 기존 결과 파일로 알 수 있는 것과 없는 것

| 필요한 것 | doc_timing rows.jsonl | batch_assess results.jsonl |
| --- | --- | --- |
| 문서 키 | `key` = 루트 기준 상대경로 UTF-8의 sha256 앞 16자 (doc_timing.py:119-120, 718) | `id` = 루트 기준 상대경로 (batch_assess.py:844) |
| 대응 방법 | 두 실행의 루트가 같으면 `sha256(id)[:16] == key`. 루트가 다르면 대응 0건 → 도구가 ROOT_MISMATCH로 알림 | |
| 서식 | `form` | `detected_type` (own) |
| tier | `tier` | 없음 (판독 체인을 쓰지 않음) |
| 글자층 | `text_layer`(TEXT/NONE/MIXED), `first_image_later_text`, `pages` | `page_count`, `text_layer_pages`, `text_reference.detected_type`(모든 쪽 글자층일 때만) |
| 판독기 대체 사유 | **저장 안 함** (doc_timing.py:347-352, 376-382). 그리고 A 실행에서는 대체 사유 자체가 생기지 않음(JBAI 꺼짐) | 없음 |
| LocalOcr가 None을 낸 단계 | **알 수 없음.** 다시 실행해야 함 (trace) | - |

## 다. G1 원인 확인 (합성)

합성 4대보험 서식에서 own OCR과 글자층 참조 둘 다 판별 입력이 `…4대사회보험확인용가입자가입내역확인서…`이다(제목 둘째 줄 왼쪽의 용도 표시 "확인용"이 끼어듦).
키워드 `4대사회보험가입자가입내역확인서`(pdftext.py:34)가 끊기고 `4대사회보험정보연계`는 서식에 없어 X. own과 참조가 같으므로 OCR 원인이 아니다.
4대보험 추출기 자체의 서식 인식은 두 조각이 떨어져 있어도 받아들인다(engine_v2/extractors/insurance_4.py:106-107). 그래서 후보 규칙은 `pdftext.classify_with_evidence` 한 곳만 바꾸면 된다.

## 라. 동의서 표시 판독

| 항목 | 파일:행 | 내용 |
| --- | --- | --- |
| 판독 호출 조건 | demo/backend/upload_assessment.py:61-66 | 슬롯이 동의서이고 종이 동의서이고 판별이 ADMIN_INFO_CONSENT일 때 `inspect_admin_consent_scan` |
| 사유 조건 | upload_assessment.py:74-92 | `동의여부`가 "동의함"이 아니고 "동의하지 않음"도 아니면 ADMIN_CONSENT_MARK_UNREADABLE(NEEDS_REVIEW). 서명은 "있음"이 아니면 ADMIN_CONSENT_SIGNATURE_UNREADABLE |
| 서식 좌표 없음 | demo/backend/ocr/admin_consent_scan.py:38-40 | 서식5 좌표·원본이 없으면 둘 다 확인필요 |
| 원본 서식 그림 | admin_consent_scan.py:43-48 | 원본 서식5 첫 쪽을 가로 1200px로 렌더링 |
| 스캔 그림 | admin_consent_scan.py:13-22, 49-53 | **첫 쪽만** 가로 1200px로 렌더링하고, 원본 크기로 **그대로 늘이거나 줄임**(위치 맞춤·기울기 보정 없음, 가로세로 비율 무시). 실패하면 확인필요 |
| 표시 판독 | admin_consent_scan.py:25-33, 55-59 | 원본 좌표의 체크 칸(약 10×12pt, demo/fixtures/form_coords/서식5.json `agree.동의함`·`agree.동의하지 않음`)에서 원본과 밝기 차이 45 초과 화소 비율이 0.035 넘으면 표시로 봄 |
| 결과 | admin_consent_scan.py:62-65 | 표시가 **정확히 하나**일 때만 그 값, 없거나 둘 다면 확인필요 |
| 서명 | admin_consent_scan.py:60-61 | 서명 칸 차이 비율 0.012 초과 |

실패 단계 후보(진단 코드로 나눔): 서식 좌표 없음 / 스캔 열기 실패 / 첫 쪽이 동의서가 아님 / 가로세로 비율 차이 / 위치 어긋남(평행 이동) / 표시 없음 / 표시 둘 다.

**LOW_IMAGE_QUALITY (동의서 FAIL 14건에 붙은 것)의 기준:**

| 단계 | 파일:행 | 내용 |
| --- | --- | --- |
| 화질 점수 | demo/backend/ocr/file_evidence.py:49-93, 96-115 | PDF: 글자 50자 미만 쪽마다 쪽의 90% 이상 덮는 가장 큰 그림의 원본 DPI. 200 이상 0.9, 150 이상 0.7, 그 밖 0.5. 문서 점수는 쪽 최솟값. 사진: 짧은 변 1400px 이상 0.9, 1000 이상 0.75, 700 이상 0.55, 그 밖 0.35 |
| 기준선 | engine/config.py:14 | 0.6 미만이면 화질 미달 (PDF는 150dpi 미만, 사진은 짧은 변 1000px 미만) |
| 상태 | engine/stage1_document_check.py:21-31 | 미달이고 (판별 성공 그리고 필수 항목 읽힘)이면 NEEDS_REVIEW, 그 밖이면 FAIL |
| 필수 항목 못 읽음 | demo/backend/rules/doc_check.py:165-173, 990-1010 | ADMIN_CONSENT_MARK_UNREADABLE·ADMIN_CONSENT_SIGNATURE_UNREADABLE·ADMIN_CONSENT_IDENTITY_UNREADABLE 포함 |
| 마무리 | upload_assessment.py:133 | 동의서 사유를 더한 뒤 `finalize_image_quality`를 다시 부른다 |

그래서 동의서는 **원본 그림 150dpi 미만이고 표시나 서명을 못 읽으면 FAIL(재업로드)**, 표시와 서명을 모두 읽으면 같은 화질이어도 NEEDS_REVIEW다.

## 마. G2 납부확인서 월별 표 (합성 20개 놓침)

합성 납부확인서는 8열 정부 서식 판독기(`nhis_payment_gov`, engine_v2/extractors/nhis_payment.py:347-350)로 간다.

| 단계 | 결과 (own) | 근거 |
| --- | --- | --- |
| 월 행 | 12행 찾음 (통과) | nhis_payment_gov.py:240-248 |
| 묶음 머리글(고지금액·납부금액) | 통과 | nhis_payment_gov.py:243-249 |
| **열 머리글** | **실패: 9칸 중 3열·7열이 `소득월액(건강)`로 읽힘** (기대 `보수외소득월액(건강)`) | nhis_payment_gov.py:253-260, 147-158 |
| 열 경계 | 실패 (머리글 실패의 결과) | nhis_payment_gov.py:263-266 |
| 행 묶음·값 형식·합계 | 실행되지 않음 | nhis_payment_gov.py:267-268 |

원인: 열 머리글 단어는 `word.y0 > group_bottom`(묶음 머리글 단어 아래쪽 y의 최댓값)일 때만 받는다(nhis_payment_gov.py:250, 253).
own OCR의 묶음 머리글 상자 아래쪽이 글자층보다 조금 아래(쪽 높이 대비 약 0.15%p)로 잡혀, 3열·7열 `보수외` 단어의 위쪽 y가 그 경계보다 작아져 빠진다.
4열·8열 `보수외`는 위쪽 y가 조금 더 커서 들어온다. 그래서 단계 코드는 **HEADER(머리글 띠 경계 잘림, HEADER_BAND_CUT)** 이고,
월별고지금액·월별장기요양보험료·건강보험료·장기요양보험료 4항목 × 5건이 모두 이 한 원인에서 빠진다(검증 실패 `payment_component_headers`, `payment_columns`, `paid_total_matches`).
글자층 참조에서는 같은 단어가 경계 아래에 있어 통과한다.

실서류의 NHIS_PAYMENT_PAGING_UNCERTAIN(doc_check.py:933-960)과 MISSING_BILLING_MONTHS(doc_check.py:397-445)는 월별 표 검증 결과(`payment_completeness`, `payment_period`)를 거쳐 나온다.
같은 원인인지는 실서류 진단(payment 단계 코드 × 사유 교차표)으로 확인한다.

## 합성 측정 결과 (커밋 2·3, 그림자 전용, 운영 불변)

### 나-2 재현 PDF를 진단 도구로 실제 own 실행 (41건)

| 원인 코드 | 건수 | A-스캔 방식으로 서식 찾음 |
| --- | --- | --- |
| HIDDEN_TEXT_LAYER | 3 | 3 |
| FEW_CHARS_DISCARD | 2 | 2 |
| FIRST_IMAGE_LATER_TEXT | 3 | 3 |
| PREPROCESS_ERROR (예외 ValueError) | 4 | 4 |
| BACKGROUND_ONLY | 4 | 4 |

### G1·G2 (own, original 25건씩). 주 숫자는 측정 정의의 165항목 고정 분모, 190 기준은 참고

| 세트 | 조건 | G1 | G2 (165 고정) | 참고: 추출기 불린 항목 / 전체 190 |
| --- | --- | --- | --- | --- |
| 발표용 | 운영 그대로 | 20/25 | 145/165 | 145/165 · 145/190 |
| 검증 | 운영 그대로 | 20/25 | 145/165 | 145/165 · 145/190 |
| 발표용 | G1 N | 25/25 | 145/165 | 165/190 (4대보험 20 추가, 가입내역 5 불일치) |
| 검증 | G1 N | 25/25 | 145/165 | 165/190 |
| 발표용 | P1 0.1 / 0.2 / 0.3 | 20/25 | 165/165 | 165/190 |
| 검증 | P1 0.1 / 0.2 / 0.3 | 20/25 | 165/165 | 165/190 |
| 발표용 | G1 N + P1 0.1 | 25/25 | 165/165 | 185/190 |
| 검증 | G1 N + P1 0.1 | 25/25 | 165/165 | 185/190 |

### P1 410쌍 (기준: 커밋 1 회귀 결과)

| 여유 | own 잘못된 통과 | 참조 잘못된 통과 | 납부 참조 | 바뀐 행 |
| --- | --- | --- | --- | --- |
| 0.1 | 0/235 | 15/235 | 5/50 | 23 |
| 0.2 | 0/235 | 15/235 | 5/50 | 23 (0.1과 행 단위로 같음) |
| 0.3 | 0/235 | 15/235 | 5/50 | 28 |

| 바뀐 행 (own, 납부확인서) | 0.1 | 0.2 | 0.3 |
| --- | --- | --- | --- |
| issued_after_application NEEDS_REVIEW→FAIL | 5 | 5 | 5 |
| issued_too_early NEEDS_REVIEW→FAIL | 5 | 5 | 5 |
| original NEEDS_REVIEW→PASS | 5 | 5 | 5 |
| monochrome NEEDS_REVIEW→PASS | 5 | 5 | 5 |
| layout_variant NEEDS_REVIEW→PASS | 3 | 3 | 3 |
| **low_resolution FAIL→NEEDS_REVIEW** | 0 | 0 | **5** |

0.3은 기대 FAIL인 저해상도 납부 5건을 NEEDS_REVIEW로 약하게 만든다. 운영 후보는 가장 작은 **0.1**.

### C1 (합성)

100dpi 동의서(표시 미판독): 운영 FAIL(LOW_IMAGE_QUALITY) → C1 NEEDS_REVIEW. 다른 필수 항목 미판독(REQUIRED_FIELD_UNREADABLE)은 C1에서도 FAIL 유지(시험).

### 동의서 표시 (합성 서식5 480변형 = 표시 4종 × 이동 5 × 확대 3 × 회전 2 × 흐림 2 × 해상도 2)

| 판독 | 표시 없음 120 | 동의 120 | 비동의 120 | 둘 다 120 |
| --- | --- | --- | --- | --- |
| 운영 | BOTH 120 | BOTH 120 | BOTH 120 | BOTH 120 |
| 위치 맞춤(칸 전체) | BOTH 120 | BOTH 120 | BOTH 120 | BOTH 120 |
| 위치 맞춤 + 칸 안쪽 | NONE 91, BOTH 24, **AGREE 4, DISAGREE 1** | AGREE 27 | DISAGREE 19 | BOTH 41 |
| 칸 안쪽 + 상관 강할 때만 (운영 후보) | NONE 16, BOTH 24, 보류 80, **잘못 읽음 0** | AGREE 16, BOTH 24, 보류 80 | DISAGREE 16, BOTH 24, 보류 80 | BOTH 40, 보류 80 |

원인: 표시 없는 원본 서식을 300dpi 그림으로 만들기만 해도 체크 칸 테두리가 벡터 원본과 다르게 그려져 두 칸 모두 잉크 비율 0.17(기준 0.035)이 된다.
기존 시나리오(run_p7_scenarios.py:450-470)는 벡터 원본 위에 벡터 표시를 그린 입력만 다룬다.

## 11-18 운영 반영 전 확인 (합성과 코드만)

### L1 재현 (가짜 OCR, 2쪽 초본 + 1쪽)

| 덧붙인 쪽 | 수정 전 | 수정 후 (`bafa2f9`) |
| --- | --- | --- |
| 없음 | PASS | PASS |
| 완전히 빈 쪽 | NEEDS_REVIEW (PAGES_UNREADABLE, LOW_OCR_CONFIDENCE) | 쪽 확인 통과, LOW_OCR_CONFIDENCE로 NEEDS_REVIEW 유지 (머리 상자 일치 검사가 모든 쪽을 셈) |
| 머리 상자(제목·쪽표기 2/2·성명 줄)만 되풀이된 쪽 | **FAIL PAGES_DUPLICATED** (진의 L1과 같은 모양) | PASS |
| 본문 있는 중복 쪽 | FAIL PAGES_DUPLICATED | FAIL PAGES_DUPLICATED |
| 1/3·2/3 + 머리 상자만 있는 2/3 | - | FAIL PAGES_INCOMPLETE (내용 없는 쪽이 빠진 쪽을 채우지 않음) |

### L2·A3: 고지월과 소득 판정

- `고지월` 문자열은 어떤 판정 규칙도 읽지 않는다. 소득 판정은 `facts._monthly_premium`이 **월별고지금액**에서 판정 대상 석 달(2025-10~12)만 읽는다
  (건강보험료 평균 필드는 쓰지 않는다). 통과 조건: 업로드 판정 PASS, 신뢰도 0.85 이상, 검토 검증 실패 없음, 양식판독상태 완전(있을 때) (`_payment_amounts_trusted`).
- L2 오류에서 10~12월 줄은 2025년으로 맞게 들어가므로 보험료 평균은 바뀌지 않았다(잘못된 통과 위험 아님). `payment_period`는 같은 해 조회기간을 이미 맞게 다룬다.
- A3 재현: 고지금액·납부금액 묶음 머리글 아래 건강/장기요양 두 칸 표에서 **건강보험료 칸을 못 읽으면** `_closest_amount`(거리 제한 없음)가 가장 가까운 장기요양 칸을 고르고,
  합계 줄도 묶음 머리글 가운데에 가까운 장기요양 합계를 골라 산술 검증이 맞아떨어진다 → 월별고지금액 = 장기요양 금액, 검증 실패 없음 → **잘못된 통과 위험 확인**.
  머리글이 온전하고 칸을 모두 읽으면 재현되지 않는다(건강 칸을 맞게 고르고, 합계 불일치로 확인 필요).
- 수정(L2 커밋에 포함): 건강·장기요양 칸이 따로 있는 표에서, 한 줄에 장기요양 칸이 따로 없거나 장기요양 금액이 0 이상의 건강보험료보다 크면 그 줄의 건강보험료를 버리고
  `monthly_amounts_numeric` 실패(검토 검증)로 둔다. 음수 줄(환급·정산)은 비교하지 않는다. 머리글 위치로 칸을 가르는 방식은 기존 합성 서식(라벨 오른쪽에 금액 열)에서 오판해 쓰지 않았다.

### A4: 납부확인서 가입구분

- 판독기(`nhis_payment.extract`, legacy)는 모든 쪽 글자를 이어 `직장가입자`·`직장가입`을 먼저 찾고, 사업장명칭 정규식 뒤에 아무 글자나 있어도 직장으로 정한다.
  하단 안내문 "※ 직장가입자의 보수월액보험료 …"가 있으면 지역가입자 서류도 직장이 된다(합성 재현: 시험 `test_footer_notice_makes_production_member_type_work…`).
  정부 서식 판독기(`nhis_payment_gov`)는 가입구분을 채우지 않는다.
- 쓰임: 서류 판정(doc_check)은 가입구분을 읽지 않는다. `facts._insurance_facts`가 기록된 가입구분을 두 칸 근거(사업장관리번호·사업장명칭)보다 앞세우고,
  `scoring.score_income`이 확정된 가입구분의 상한 행(`row[category]`)으로 140% 충족/초과를 정하고 점수 구간 행을 고른다.
  직장 상한이 모든 가구원 수에서 지역보다 높다(1인 118,821 / 46,072). **지역을 직장으로 잘못 정하면 보험료가 두 상한 사이일 때 소득 요건 충족으로 잘못 판정된다.**
- MEMBER_TYPE_VALUE(`nhis_payment_gov.member_type_value`, ddfeae4): 모든 쪽의 묶은 줄 어디든 `직장가입`·`지역가입`이 부분 문자열로 있으면 legacy로 보낸다(영역 제한 없음).
  같은 안내문 줄이 이 조건을 만족하므로, 실서류 120쪽이 모두 이 표시로 legacy가 됐을 가능성이 있다(판별 결과는 실서류에서 맞았으므로 그대로 둠).

### A1: 화질 FAIL 경로와 두 기준

- LOW_IMAGE_QUALITY: `doc_check.finalize_image_quality`가 원본 화질 점수(`file_evidence.objective_image_quality`, PDF는 가장 큰 덮는 그림의 DPI 200↑ .9 / 150↑ .7 / 그 밖 .5,
  사진은 짧은 변 1400↑ .9 / 1000↑ .75 / 700↑ .55 / 그 밖 .35)가 0.6 미만이면 붙인다. 서식 판별 실패이거나 "필수 항목 못 읽음" 코드가 있으면 FAIL, 아니면 NEEDS_REVIEW
  (engine/stage1_document_check.py `image_quality_status`). 필수 항목 코드: REQUIRED_FIELD_UNREADABLE, RESIDENT_APPLICANT_UNREADABLE, RECEIPT_AMOUNT_UNREADABLE,
  RECEIPT_OCR_UNAVAILABLE, NHIS_HISTORY_PERIOD_UNREADABLE, ADMIN_CONSENT_IDENTITY/MARK/SIGNATURE_UNREADABLE, 확인 필요 MISSING_BILLING_MONTHS, 이름 없는 NHIS_SUBSCRIBER_IDENTITY_REVIEW.
  자격확인서는 양식판독상태가 있고 불완전이거나 성명·생년월일·발급일이 비면 REQUIRED_FIELD_UNREADABLE → 원본 150dpi 미만이면 FAIL.
- IMAGE_RESOLUTION_TOO_LOW(항상 FAIL): 원본 그림 짧은 변 600px 미만 **그리고** 긴 변 800px 미만 **그리고** 미판독(서식 모름 또는 서식별 필수 항목 절반 미만)
  (`file_evidence.resolution_defect`). 이 사유가 있으면 LOW_IMAGE_QUALITY는 붙지 않는다.
- 두 기준이 다른 이유: 0.6은 DPI(또는 사진 짧은 변) 구간으로 만든 상대 점수이고 데모 가정값(engine/config.py)이다. 600/800은 절대 화소 크기의 좁은 하한으로,
  미판독일 때만 쓰도록 11-13 실패 사례 작업에서 추정해 정했다(archive 11-13-fail-cases design.md). 그래서 900×1200 사진은 0.55로 화질 미달이지만 600/800 규칙에는 걸리지 않는다.
  라벨 도구 화면 문구의 위치는 저장소 허용 범위에서 찾지 못했다(doc_check.py의 IMAGE_RESOLUTION_TOO_LOW 상세 문구에 같은 숫자가 있다).
