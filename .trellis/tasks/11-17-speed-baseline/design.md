# 서류당 처리 시간 기준선 — 설계

## 1. doc_timing CLI (`engine_v2/tools/doc_timing.py`)

```
python -B -m engine_v2.tools.doc_timing --root <HUB_ROOT> --out <RUN_DIR>/x
    [--engines own] [--repeat 1] [--warmup 3] [--sample N] [--seed 20261117]
    [--strata-from <RUN_DIR>/full] [--limit N]
```

- 오류는 고정 코드 한 줄(`ERROR <CODE>`)과 종료 코드 2로 끝낸다: ARGUMENT_ERROR, OUT_EXISTS, INPUT_UNAVAILABLE,
  INPUT_OUTPUT_OVERLAP, ENGINE_UNAVAILABLE, STRATA_INVALID. 인자·경로·예외 메시지는 찍지 않는다.
- `--out`이 이미 있으면(빈 폴더 포함) OUT_EXISTS로 멈춘다. 이어 하기(resume)는 없다. 시간 측정은 한 번에 끝까지 도는 것이 전제다.
- `--engines`는 own, applevision 중에서 고른다. own은 모델 파일이 없으면 ENGINE_UNAVAILABLE.
- 대상은 `--root` 아래 `.pdf`만이다 (`batch_assess.inventory`를 재사용하고, 숨김 파일·심볼릭 링크는 뺀다).

### 1.1 처리 순서와 내부 ID

- 문서 키 = `sha256(루트 상대경로)` 앞 16자. 결과 행 파일(rows.jsonl)에만 들어가고 화면과 요약에는 찍지 않는다.
- 처리 순서는 문서 키 순서다. 폴더 순서나 서식 순서가 시간 흐름(발열 등)과 겹치지 않게 하려는 것이다.
- `--sample N`: 층마다 비례 배분(최대 나머지 방식, 층마다 최소 1건)하고, 층 안에서는 `random.Random(seed)`로 뽑는다. 층은:
  - `--strata-from`가 있으면 이전 doc_timing 실행의 rows.jsonl에 있는 서식 코드(문서 키로 맞춤)를 쓴다. 이전 실행에 없는 문서는 `UNSEEN` 층이다.
  - 없으면 측정 전 사전 점검의 값(글자층 유무 × 쪽수 구간)을 쓰고, `STRATA_BASIS PAGES_TEXT`를 기록한다. 이미지 PDF는 OCR 없이는 서식을 알 수 없어서다.
- `--limit N`은 표본을 뽑은 뒤 처리 순서로 앞의 N건만 남긴다.

### 1.2 측정 전 사전 점검 (시간에 넣지 않음)

PyMuPDF로 열어 암호(ENCRYPTED), 열기 오류(OPEN_ERROR), 0쪽(EMPTY_DOCUMENT)을 거른다. 이런 문서는 처리하지 않고 사유 코드로 센다.
쪽수와 글자층 쪽 수를 센다. 글자층 쪽은 운영 기준과 같게 `len(mask_rrn(page.get_text("text")).strip()) >= TEXT_LAYER_MIN_CHARS`(50)로 본다.
글자층 유무 구분은 TEXT(모든 쪽), NONE(없음), MIXED(일부)이고, 쪽수 구간은 1, 2, 3+이다.

### 1.3 한 건 재기 (운영 경로)

```
ENGINE_V2_OCR=<engine>        # 도구 프로세스 안에서만 설정
t0
ocr = demo.backend.ocr.read_document(path, None)           # 운영 판독 체인 그대로 (CHAIN 전체)
req = 판별 종류에 맞는 업로드 슬롯 (batch_assess._requirement와 같은 규칙, 종류별 캐시)
assess_upload(path, req, identity=None, paper_admin_consent=(종류가 행정정보동의서),
              reader=lambda *_: ocr)                         # 서류 단위 판정 (운영 함수)
t1
전체 = t1 - t0 - (서류 처리 중 모델 불러오기 시간)
```

- 판별 종류가 없거나 슬롯이 없는 종류(일용·농어업 등)면 판정은 NOT_ASSESSED로 두고 판정 시간 0으로 기록한다.
- 운영과 다르게 하는 부분(보고 대상):
  1. `read_document`의 기대 종류를 None으로 준다. own 경로에서 기대 종류를 쓰는 계층은 JbaiOcr뿐이고 도구는 JBAI를 끈다.
  2. 도구 프로세스에서 `JBAI_API_KEY`, `JBAI_ALLOW_REAL_DOCS`, `UPSTAGE_API_KEY`를 지운다 (외부 전송 차단). 소켓 연결은 감사 후크로 막고, 시도가 있으면 그 문서를 PROCESSING_ERROR로 센다.
  3. 신원 정보와 신고 발급일은 None이다. 짝 재판정, DB 저장, 파일 저장, 신청 건 단위 판정은 하지 않는다.
  4. 모델은 측정 전에 한 번 불러오고 그 시간을 run.json에 따로 적는다. 운영에서는 첫 이미지 서류가 이 시간을 떠안는다.
  5. 사전 점검에서 파일을 한 번 열기 때문에 OS 파일 캐시가 데워진 상태에서 잰다. 운영에서도 업로드 직후 디스크에 쓴 파일을 읽으므로 같은 조건으로 본다.
- 출력 억제: 문서마다 `private_bench.quiet_dependencies()`와 `logging.disable`로 감싼다. 이 감싸기는 시간 구간 밖이다.

### 1.4 단계 시간

운영 함수를 **위임만 하는 감싸개**로 `unittest.mock.patch.object`를 씌운다. 인자, 반환값, 예외를 그대로 넘긴다.
단계 시간은 배타 시간이다. 단계 안에서 다른 단계가 불리면 그 시간은 바깥 단계에서 뺀다(스택 방식).

| 단계 | 감싸는 함수 |
| --- | --- |
| open | `pymupdf.open`, `fitz.open` |
| text_layer | `pymupdf.Page.get_text` |
| render | `engine_v2.pipeline.preprocess._process_pdf_page`(본문 이미지 꺼내기·렌더링·PNG 만들기), `pymupdf.Page.get_pixmap` |
| ocr | `engine_v2.pipeline.ocr.ENGINES[engine]` |
| model_load | `own.sessions` 감싸개에서 lru 캐시 miss일 때만 (서류 시간에서 뺌) |
| classify | `pdftext.classify`, `classify_with_evidence`, `classify_pages_with_evidence` |
| extract | 각 추출기 모듈 `extract`, `localocr._from_*`·`_generic`, `pdftext.read_page_text` |
| evidence | `file_evidence.attach_file_evidence`, `normalize_image_quality`, `admin_consent_scan.inspect_admin_consent_scan` |
| decision | 도구가 직접 재는 `assess_upload` 구간 |
| other | 전체 − 위 단계 합 (체인 넘기기, 가리기, 변환 등) |

감싸개 비용은 호출당 수 마이크로초다. 감싸개가 운영 결과를 바꾸지 않는다는 것은 시험으로 확인한다(감싼 것과 안 감싼 것의 OcrResult·판정 결과 같음).

### 1.5 예열과 반복

- 예열: 처리 순서 앞의 `--warmup`건(기본 3)을 측정 전에 한 번씩 더 돌린다. 행은 `phase=warmup`으로 따로 남기고 통계에서 뺀다.
  그래서 측정 대상 문서는 하나도 빠지지 않고 모든 반복을 갖는다. (요청 문구 "첫 N건은 예열로 빼고"를 이렇게 구현한다. 승인 때 확인 필요.)
- 반복: `--repeat R`이면 전체 목록을 R번 차례로 돈다(한 바퀴씩). 서류 값은 반복값의 중앙값이다. 흔들림은 서류별 최대/최소 비율이며, 그 중앙값과 p90을 낸다.
- 백분위는 `batch_assess._quantile`(선형 보간)을 그대로 쓴다.

### 1.6 출력 파일 (`--out` 아래)

- `run.json`: schema_version, 시작·끝 시각, git 커밋과 dirty O/X, 기계 모델(`sysctl hw.model`), CPU 코어(전체·성능·효율),
  전원(AC/BATTERY/UNKNOWN), 시작·끝 부하 평균 3개, 파이썬·pymupdf·onnxruntime·numpy·opencv·Pillow(·ocrmac) 버전,
  own 스레드(실제 세션의 intra/inter), 엔진별 모델 불러오기 초, 옵션 값(숫자·코드만), 층 기준, JBAI·Upstage 끔 O/X.
  경로는 넣지 않는다.
- `rows.jsonl`: 측정 한 번에 한 줄. 문서 키, 엔진, 반복 번호, phase(warmup/measure/skipped), 코드, 서식 코드(DocType 이름 또는 X),
  글자층 구분, 쪽수, 쪽수 구간, OCR 호출 수, tier 코드, 판정 상태, 단계별 초, 전체 초. 값·이름·경로 없음.
- `summary_brief.txt`: 숫자·O/X·코드만. 줄 머리는 RUN, SKIP, WARMUP, MODEL_LOAD, OVERALL, TARGET, BY_FORM, BY_TEXT_LAYER,
  BY_PAGES, STAGE, REPEAT, SLOW_FORM이다. 목표 줄은 `TARGET own MEAN_LE_2_5S O`, `TARGET own P95_LE_5S X` 꼴(2.5초·5초와 같으면 O)이다.
- 화면: 시작 경고(`WARNING LOAD_HIGH`, `WARNING ON_BATTERY`), 진행(`progress engine pass done total elapsed_s`), 끝에 summary_brief 내용.

## 2. ocr_baseline 값 유무 저장

- `ocr_baseline_fields.compare_fields(..., presence=False)`: 키워드를 더한다. `presence=True`일 때만 필드마다 `actual_present`를 넣는다.
  값은 이미 계산하는 `actual_present`(90행)를 그대로 0/1로 바꾼 것이다. 참조가 없는 필드(missing_reference)는 계산 전에 끝나므로 0이다.
  기본값 False라서 기존 호출과 기존 시험 기대값은 그대로다.
- `ocr_baseline.process_file`은 `presence=True`로 부른다.
- `ocr_baseline.validate_row`: 필드 키가 기존 6개이거나, 6개 + `actual_present`일 때 받는다. `actual_present`가 있으면 0/1 정수이고,
  match=1이면 1, missing_reference=1이면 0이어야 한다. 예전 결과 행(6개)도 그대로 읽힌다.
- `FIELD` 틀과 `build_summary`는 바꾸지 않는다. 그래서 summary.json·summary.txt 숫자는 그대로다.

## 3. ocr_baseline_compare 분포와 교차표

필드 측정 하나(문서, 쪽, 엔진, 변형, 필드)를 다음 중 하나로 나눈다. 참조가 없는 필드는 세지 않는다.

| 분류 | 조건 |
| --- | --- |
| MATCH | eligible=1, match=1 |
| BLANK | eligible=1, match=0, type_match=1, actual_present=0 |
| WRONG | eligible=1, match=0, type_match=1, actual_present=1 |
| OTHER | eligible=1, match=0, type_match=0 (다른 종류로 판별) |
| NA | eligible=1, match=0, type_match=1, actual_present 없음 (예전 결과) |

- 분포 줄: `OUTCOME type field engine variant side MATCH BLANK WRONG OTHER NA` (side는 BEFORE/AFTER).
- 교차표 줄: `TRANSITION type field engine variant before after count`. 0이 아닌 칸만 쓴다. 한쪽에만 있는 측정은 ABSENT로 쓴다.
- 문서 ID는 맞추는 데만 쓰고 출력하지 않는다. 기존 줄(STATUS, COHORT, EXCLUSION, FIELD, RECOGNITION, TIME, GRID)은 그대로 두고 새 줄은 뒤에 붙인다.

## 4. 바꾸지 않는 것

demo/backend 전부, engine/, engine_v2의 extractors·pipeline·classifier·rules·engine.py, 기존 시험 파일, 생성기, 410쌍 코퍼스.
