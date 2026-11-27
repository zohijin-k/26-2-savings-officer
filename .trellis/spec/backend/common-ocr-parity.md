# Common OCR parity (savings-officer ↔ youth, 11-27)

두배적금(savings-officer 백엔드)과 youth 백엔드는 **같은 검증된 공통 OCR 기술**을 쓰고, 행정 판정 규칙(Document AI)은
사업별로 둔다. 두 저장소는 독립 저장소로 남고, 공통 부분은 같은 소스를 각 저장소에 둔다(외부 패키지·모노레포 아님).

## 공통 (두 저장소에서 같아야 함)

- 파일 전체: `engine_v2/pipeline/**`(PDF 렌더링·글자층·전처리·공유 그림 표시·PP-OCRv5 ONNX 검출·인식·스레드 배분·
  짧은 글자 상자 방향 보정·쪽 동시 읽기), `engine_v2/extractors/resident_abstract.py`·`address_dates.py`(초본 구조 추출),
  `engine_v2/tools/fetch_own_models.py`(모델 출처·SHA-256 고정), 백엔드 OCR 계층 `demo/backend/ocr/__init__.py`·`base.py`·
  `file_evidence.py`·`fixture.py`·`jbai.py`·`upstage.py`.
- 섞인 파일의 공통 블록: `localocr.py`(엔진 선택, 모델 미리 불러오기 `preload_own`, 300dpi 대체 판독 `render_pages`·
  `LocalOcr._render_retry`, 초본 변환 `_from_resident`와 완결성 신호, 공유 그림 쪽 묶음 `_shared_image_groups`, 스캔 초본
  안전장치 `SCAN_ABSTRACT_REVIEW_GUARD`), `pdftext.py`(종류 판별 `classify_with_evidence` 등), `doc_check.py`의 초본 쪽
  완전성 검사 `_check_resident_pages`·`_repeats_from_shared_image`·`CODE_PAGE_IMAGE_SHARED`·`RESIDENT_HISTORY_REASON_LEGEND`.
- 모델: det `ch_PP-OCRv5_det_mobile`, rec `korean_PP-OCRv5_rec_mobile`, 사전 `ppocrv5_korean_dict` (해시는 manifest).

## 사업별 (달라도 됨, manifest에 '제외'로만 기록)

- `localocr._business_resident_marks`: 두배적금은 인쇄된 '열람용' 표시를 담당자 확인으로 남긴다(11-18 S3). youth는 없음.
- `localocr._from_nhis`·`_from_insurance4`·`_from_supported_form`, `pdftext.read_page_text`의 열람용 표시, 그 밖의
  `doc_check`·`facts`·`upload_assessment`·`engine_adapter`·`engine/` 규칙(납부확인서 쪽수·고지금액, 4대보험 사업장명,
  동의 표시 확실성, 화질 정책, 부재 FAIL 완화, 영수증·범용 사업 수동 검토 등)은 각 사업의 판정 규칙이다.

## 검사

- `engine_v2/common_ocr_manifest.json`은 두 저장소에서 바이트 단위로 같다. 공통 파일 SHA-256과 섞인 파일의 공통 블록
  SHA-256(앞 주석 포함 원문), 모델 해시를 담는다.
- `demo/backend/tests/test_common_ocr_parity.py`(CI 필수 목록 `common_ocr_parity`)가 현재 코드와 manifest를 비교한다.
  모델 없이 돈다.
- 공통 코드를 고칠 때: 두 저장소에 같은 변경 → 각 저장소에서
  `python -m engine_v2.tools.common_ocr_parity --write` → 두 manifest가 같은지 확인
  (`python -m engine_v2.tools.common_ocr_parity --compare <다른 저장소>`가 `COMMON_OCR_IDENTICAL`).
- 실제 ONNX 동등성(같은 모델·같은 CPU·같은 문서에서 상자·글자·신뢰도·종류 판별 입력·공통 필드가 같음)은 시험 밖의
  검증 환경에서 확인한다(PR 본문에 결과 기록).

## 공통 동작 메모

- 스레드(11-19): `OWN_OCR_INTRA_THREADS`·`OWN_OCR_PAGE_WORKERS`가 둘 다 비어 있으면 자동. 한 쪽씩 읽을 때 intra 4(논리
  코어 이내), 2쪽은 코어 8개 이상이면 intra 4 × 2, 3쪽 이상은 intra 2 × 최대 4. 둘 중 하나라도 설정하면 고정값.
- 공유 그림(11-19 D10): 판독기는 쪽을 덮는 본문 그림을 그대로 읽으므로, 한 그림(xref)을 여러 쪽이 쓰면 같은 OCR 입력이
  된다. 전처리는 그런 쪽에만 72dpi 렌더 해시를 남기고, 같은 그림·서로 다른 렌더에서 되풀이된 쪽표기는
  `PAGE_IMAGE_SHARED`(확인필요)다. 같은 그림·같은 렌더(실제로 같은 쪽 두 번)·다른 그림의 반복은 `PAGES_DUPLICATED`(FAIL).
  OCR 입력 그림 자체는 바꾸지 않는다.
- 300dpi 대체 판독(11-18 O1): 1차 경로가 종류를 정하지 못한 PDF만 화면과 같은 합성 렌더로 한 번 더 읽고, 종류를 찾았을
  때만 그 결과와 `RENDER_RETRY:<코드>`를 남긴다.
