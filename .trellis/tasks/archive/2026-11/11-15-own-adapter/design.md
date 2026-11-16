# 0~1단계 설계

## 변경 경계와 흐름

```text
PDF 선택 → 메모리 열기 → 쪽별 글자층 품질 확인
                      → 기존 본문/좌표 분류·추출 → 참조 필드
                      → 기존 clean 렌더 → own / AV 원래 호출
                      → 기존 추출 입력 준비·분류·추출 → 관측 필드
                      → 원래 토큰/상자/줄의 메모리 진단
                      → 닫힌 수치·코드 투영 → 결과 저장
```

`ocr_baseline_runtime.reference_page`, `quality`, `variant_image(..., 'clean', ...)`, `recognize`, `extract`와 `ocr_baseline_fields.prepare_pairs`, 기존 분류/추출 경로를 재사용한다. 원본 토큰과 추출기 입력 사본을 구분해 NFKC 이전/이후 차이를 관찰한다. 관찰 wrapper는 원 함수를 그대로 호출하고 `finally`로 복원한다. 새로운 진단은 실제 추출 입력·정답·신뢰도에 영향을 주지 않는다. 서비스 판정을 새로 구현하지 않는다.

## CLI 계약

예정 명령은 `python -B -m engine_v2.tools.own_adapter_diag`이다. 아직 구현되지 않았다.

| 인자 | 설계 |
| --- | --- |
| `--root PATH` | 폴더 입력 또는 상대 ID 해석 루트. 실행 시 필수, 내장 경로 없음. PDF만 선택하고 기존 안전 선택기를 재사용한다. |
| `--ids PATH` | 선택적 UTF-8 목록. root 상대 PDF ID만 허용. 폴더 전체 대신 이 목록을 입력 집합으로 사용한다. 파일명은 선택에만 쓰고 종류 판별에는 전달하지 않는다. |
| `--out PATH` | 필수 출력 폴더. 입력/목록/원자 파일과의 심볼릭링크·하드링크 alias 거부. 기존 결과 폴더 덮어쓰기 금지. 1단계에 resume는 추가하지 않는다. |
| `--limit N` | 선택적 양의 정수, PDF 시도 수 한도. 암호·열기 오류도 시도에 포함한다. 처리 쪽 수와 구별한다. |
| `--engines own applevision` | 공백 구분. 기본 두 엔진, 중복·미등록 엔진 거부. |
| `--fields NHIS_PAYMENT:MEMBERSHIP NHIS_PAYMENT:BILLING_MONTH NHIS_PAYMENT:ISSUE_DATE` | 공백 구분 `종류:필드코드`. 기본은 이 세 필드. 기존 `batch_assess.FIELDS`의 모든 등록 필드에 고정 ASCII 코드 매핑을 제공한다. 미등록 조합 거부. |

전체 입력은 `--root`만, 목록 입력은 `--root`와 `--ids`를 함께 쓴다. 목록의 공백/중복/탈출 ID 처리는 기존 선택 계약을 따르며 숫자 집계만 노출한다. 실제 서류 목록 존재 여부는 에이전트가 검사하지 않고 사용자가 실행하는 명령에서만 검사한다.

2026-11-15 추가 승인: 진단 CLI 내부 선택기에서 바로 아래 사람 폴더 ID와 상대 PDF 경로를 모두 받는다. 폴더는 안전한 기존 inventory 중 해당 폴더 아래 PDF로 확장하고 중복 PDF는 한 번만 처리한다. 빈 줄·주석은 무시하며 잘못되거나 없는 줄은 개수만 센다. 원래 공용 선택기는 수정하지 않는다. 선택 목록은 분류 힌트가 아니며 기본 납부 필드 실행의 비대상 문서·쪽과 분류 불가를 구분해 숫자로 보고한다. 실제 운영 경로는 채팅 명령에만 두고 커밋 문서에는 자리표시만 쓴다.

## 메모리와 출력 계약

| 대상 | 내용 |
| --- | --- |
| 메모리 전용 | 원본 OcrWord/OcrResult/PageImage, % Word, 실제 group_lines 결과, 참조·관측 의미값, 근거 상자. 텍스트·좌표는 저장하지 않음. |
| `run.json` | schema_version, 고정 엔진/필드코드, clean 설정의 고정 수치, 한도. 실제 인자 문자열·입력 위치 digest도 저장하지 않음. |
| `results.jsonl` | document 정수 일련번호, page 정수, type/form/field/engine/code의 등록 코드, counted 0/1. |
| `summary.json`, `summary.txt` | 종류 × 서식 × 필드 × 엔진 × 코드 count/rate, eligible/diagnosed/missing_reference/unsupported_evidence와 처리·건너뜀 수. |

코드 비율 분모는 해당 셀의 진단 완료 쪽-필드 수이며 OK도 포함한다. 실패만의 분포를 추가하면 별도 분모를 명시한다. 0 분모 rate는 null이다. 처리 문서/쪽, 암호, 열기 오류, 글자층 제외, 엔진 오류, 한도 미처리 수를 별도로 센다. 실행 실패·참조 부재를 OCR 실패로 세지 않는다.

운영 상태 어휘는 `ENCRYPTED`, `OPEN_ERROR`, `EMPTY_DOCUMENT`, `NO_TEXT_LAYER`, `SHORT_TEXT_LAYER`, `BROKEN_TEXT_LAYER`, `REFERENCE_MISSING`, `REFERENCE_UNATTRIBUTABLE`, `CLASSIFICATION_FAILED`, `ENGINE_UNAVAILABLE`, `OCR_ERROR`, `EXTRACTION_ERROR`, `EMPTY_OCR`, `LIMIT_REMAINING`이다. 실패 원인 코드 추가가 아니라 가용성/제외 집계이며 보고에서 구별한다.

exit 0은 처리 완료(예상된 제외 포함), 1은 실행 오류 기록, 2는 인자·출력·스키마 오류, 130은 중단이다. 오류 메시지는 등록 코드만 사용한다.

2026-11-15 실행 상태 보강: 기존 baseline 의미의 `REFERENCE_ERROR`(참조 추출 예외), `RENDER_ERROR`(clean 렌더 예외), `PROCESSING_ERROR`(guard/의존성 처리 예외)를 가용성/실행 오류로 구분한다. 이 셋은 새 원인 코드가 아니며 `counted=0`으로 원인 진단 분모에서 제외한다. 열두 원인 코드의 순서와 의미는 바꾸지 않는다.

## 누출 차단

1. 정확한 키 집합, 허용 enum과 정수/유한 수치/null만 받는 닫힌 serializer를 출력 직전에 적용한다. 입력 repr, 임의 dict key, OCR diagnostics/warnings, `str(exception)`은 직렬화하지 않는다. 문서 ID 예외를 허용하는 기존 baseline row 스키마는 재사용하지 않는다.
2. `batch_assess.guarded`의 Python/native 출력 억제·쓰기/DB/네트워크 차단과 `_memory_bridge`를 적용한다. AV의 임시 PNG도 메모리 브리지로 처리하고 원 OCR callable 알고리즘은 유지한다. 출력 쓰기는 guard 밖에서 투영된 숫자/코드로만 한다.
3. argparse/의존성/검증 오류에도 인자나 traceback을 출력하지 않는다. 결과 파일명은 위 네 개로 고정한다. 문서는 일련번호로만 구분한다.
4. 파일명·폴더·PDF 본문·참조/관측값·예외·로그·임의 key·native 출력에 sentinel을 주입해 stdout/stderr 및 모든 결과 파일에서 부재를 확인한다. 값 해시와 좌표도 스키마가 거부해야 한다.
5. 에이전트 실행은 새 합성 폴더만 선택한다. 민감 경로 문자열은 커밋할 문서에 넣지 않고 실제 사용자 명령은 1단계 보고의 채팅에서만 완성한다.

## 실패 코드 순서와 배타 조건

먼저 원래 추출기를 실행한다. 글자층 필드와 baseline의 기존 대칭 의미 비교에서 일치하면 OK다. 나머지는 관찰 predicate를 사전에 계산하고 아래 순서의 최초 참 하나만 고른다. 재배열/정규화 실험은 메모리 사본에만 적용하며 실제 성공 결과로 저장하지 않는다.

| 순서 | 코드 | 증거 조건 |
| --- | --- | --- |
| 1 | OK | 실제 기존 추출 경로의 필드가 참조와 일치. |
| 2 | LABEL_NOT_FOUND | 참조에서 확인된 필수 anchor 글자가 원문·공백 제거·토큰 연결·Unicode 사본 어디에도 없음. 띄어짐/분할/정규화로 찾을 수 있으면 제외. |
| 3 | LABEL_SPACED | 같은 상자 안 anchor 글자 사이 공백 제거만으로 발견. 상자 사이 분할은 다음 코드. |
| 4 | LABEL_SPLIT | 같은 상자에는 없으나 공간적으로 인접한 여러 상자/줄 연결에서 정확히 발견. 이웃 열 문자를 전역 결합하지 않음. |
| 5 | VALUE_NOT_FOUND | 참조 literal 근거는 있지만 관측에는 동일·정규화·공간 정렬된 오인식 후보도 전혀 없음. 형식/순서 또는 치환 증거가 있으면 제외. |
| 6 | VALUE_OTHER_LINE | 해당 추출기가 같은 줄/칸을 요구하는데 정확한 값이 다른 줄로 묶임. 원래 아래 칸을 읽는 필드에는 적용하지 않음. |
| 7 | LINE_MERGED | 참조의 별도 칸/열이 관측 줄에 섞였다는 상자 증거가 있고 분리 사본으로 실패 해소. 긴 줄이라는 이유만으로 판정하지 않음. |
| 8 | ORDER | 앞 구조 조건 없이 글자·토큰은 동일하며 순서만 고친 사본에서 필드 일치. |
| 9 | NORMALIZE | 앞 구조 조건 없이 NFC/NFKC/명시된 문장부호·공백 변환 사본에서만 원 추출 경로 일치. 이미 baseline NFKC로 성공했다면 OK. 숫자 유사문자로 값 생성 금지. |
| 10 | PATTERN_MISMATCH | anchor와 정확한 literal 구성 요소, 영역·순서는 맞으나 현재 형식 문법과 불일치. 오인식 글자 포함 시 다음 코드. |
| 11 | OCR_CHAR | 참조 근거와 공간적으로 유일하게 정렬된 관측 후보에 치환/삽입/삭제 오류가 있음. 후보 불확실 시 OTHER. |
| 12 | OTHER | 위 증거를 확정할 수 없음. |

단순 부분문자열 부재로 LABEL_NOT_FOUND/VALUE_NOT_FOUND를 구현하면 후속 코드가 도달 불가능해진다. 위 배타 조건과 우선순위 충돌 시험을 고정한다. 이 코드는 관측 기반 진단이며 인과 증명을 주장하지 않는다. 새 실패 코드는 현재 계획에 없다. 필요하면 대문자 코드·정의·분모 영향을 보고한다.

## 라벨 없는 필드와 파생 필드

- 가입구분에 `가입구분` 라벨을 강제하지 않는다. legacy는 본문 직장/지역 표기 또는 사업장명칭 값으로 도출하므로 실제 분기의 anchor만 본다. 정부 양식의 미지원/미출력 필드를 임의로 채우지 않는다.
- 고지월은 월 머리글·월 행·연도/조회기간에서 도출된다. 목록 전체를 OCR에 literal 검색하지 않고 참조 근거를 구성 요소로 분해한다. 근거가 없으면 REFERENCE_UNATTRIBUTABLE로 센다.
- 발급일은 라벨 또는 확인 문장 아래·기관명 위 날짜다. 무라벨 날짜에 LABEL_NOT_FOUND를 부여하지 않는다.
- 다른 등록 필드도 실제 일치율을 계산하되 파생/구조 필드의 원인 근거가 없으면 이를 드러내고 추정하지 않는다.

## 호환성 및 후속 설계

1단계는 운영 공유 파일 무변경으로 AV를 보존한다. 관찰 wrapper 복원 및 두 엔진 원본 토큰·신뢰도 불변을 시험한다. 2단계 계획은 실제 분포를 얻은 뒤 own 전용 경계, 해상도 무관 기준, 칸 경계, 최솟값 신뢰도, AV 동일 입력 구조 시험으로 구체화한다. 지금 합치기/줄 재구성 알고리즘을 확정하지 않는다.

## 조건부 승인 후 보강

진단 추출은 baseline의 `ocr_baseline_runtime.extract`를 그대로 호출한다. 실제 호출 관찰에서 `nhis_payment.extract`와 정부형 `nhis_payment_gov.extract` 진입을 구분해 LEGACY/GOVERNMENT/OTHER 코드로 집계하고, 입력 파일명이나 생성기 메타데이터로 분기를 강제하지 않는다. legacy 50쪽, 정부형 20쪽을 별도로 진단한다.

## Approved route-observation extension

The diagnostic row's form and observed_form use null for paths without completed extraction. A completed OTHER dispatch remains explicit. Successful reference extraction retains its form when classification fails. Summary dispatch counts deduplicate document/page identities across fields and reject contradictory forms for the same engine/path. Closed summary validation covers the new distributions and full cross-tabulation, including integer count types and zero cells.

The causal order now begins OK, ROUTE_MISMATCH, LABEL_NOT_FOUND, followed by the existing remaining causes. Missing reference and execution/availability statuses preserve their populations. Compare the observed and reference forms before reference-evidence eligibility for a present-reference field mismatch. This makes an unsupported government billing-month evidence case attributable to the observed route difference. Existing readers and form recognition predicates retain their current implementation.

## Stage 2-1 proposed design

### Observation boundary and compatibility

Add a diagnostic-only helper under engine_v2/tools for route-condition analysis. Observe the original nhis_payment.extract and nhis_payment_gov.recognizes calls during each primary extraction, always delegate and restore wrappers on success, failure and interruption. Analyze the exact prepared inputs received at that call. Reuse original MONTH, DOCUMENT_NUMBER, component/cluster/layout helpers and permitted format normalization. Compare the decomposed predicate with the original recognizes result to detect drift. Counterfactual evidence replays contribute zero route-condition observations.

Keep extract_with_form's existing three-item return contract and the original results.jsonl record keys. Retain run.json's current metadata fields. Collect new in-memory observations separately from field records. Summaries gain one closed route_conditions section. Its aggregates are keyed by reference form and engine, making the synthetic legacy/government populations distinguishable. Count each document/page/engine once across fields. No page identifiers or raw measurements are added to the condition summaries.

For a reference-confirmed payment page whose observed path becomes OTHER, analyze identically prepared copies and record PAYMENT_DISPATCH_CALLED X. Treat these as prospective predicate observations, distinct from an observed recognizes call. Missing/empty/error OCR contributes availability counts and contributes zero O/X patterns. A diagnostic-analysis failure contributes CONDITION_ERROR, preserves measured fields/routes and produces a visible failed diagnostic population. A formula/actual-return disagreement contributes PREDICATE_DIVERGENCE and fails the validation gate.

### Condition order

The ordered condition vocabulary is PAYMENT_DISPATCH_CALLED, GOV_TITLE, DOCUMENT_NUMBER_LABEL, DOCUMENT_NUMBER_PATTERN, GOV_NUMBER_GATE, PAYER_NUMBER_LABEL, WORKPLACE_LABEL, INFO_GRID_GATE, COMPONENT_TOP_FOUND, FIRST_MONTH_FOUND, HEADER_COMPONENT_TOP_FOUND, HEADER_BOSUOE_GE3, HEADER_INCOME_GE3, GOV_PREDICATE, LEGACY_TITLE. Definitions and source functions are in research/route-conditions.md. Output each condition as O or X. Pattern rows use this exact O/X order and the actual final LEGACY/GOVERNMENT/OTHER route. The brief file prints CONDITION_ORDER so pasted pattern rows are self-contained.

### Measurement bins

Compute measurements on the NFKC/masked extraction copies. Never serialize the raw number. Intervals are left-inclusive and right-exclusive. The final interval includes all larger finite values. NA counts unavailable measurements explicitly.

| Metric code | Measurement | Fixed bin boundaries / codes |
| --- | --- | --- |
| HEADER_BOSUOE_COUNT | Final reconstructed header_text count of 보수외 | N0, N1, N2, N3, N4_9, GE10 |
| HEADER_INCOME_COUNT | Final reconstructed header_text count of 소득월액 | N0, N1, N2, N3, N4_9, GE10 |
| HEADER_HEIGHT_RATIO | Original candidate band height 3 * first-month box height / page height, before component trimming. No first month yields NA. | [0,.01) LT_001, [.01,.02) R001_002, [.02,.05) R002_005, [.05,.10) R005_010, [.10,.25) R010_025, [.25,infinity) GE_025, NA |
| BOX_HEIGHT_MEDIAN_RATIO | Median positive box height / page height over actual prepared words | [0,.005) LT_0005, [.005,.01) R0005_001, [.01,.02) R001_002, [.02,.05) R002_005, [.05,.10) R005_010, [.10,infinity) GE_010, NA |
| BOX_CHAR_MEDIAN | Median len(squash(word.text)) on prepared words | [0,1) LT1, [1,4) R1_4, [4,8) R4_8, [8,16) R8_16, [16,32) R16_32, [32,64) R32_64, [64,infinity) GE64, NA |
| PAGE_BOX_COUNT | Number of prepared boxes | ZERO, N1_49, N50_99, N100_199, N200_399, N400_799, GE800 |

All coordinate calculations retain the original normalized-page interpretation. Reject nonfinite/invalid geometry as diagnostic-analysis failure. A missing component top or first month produces the original empty header string and count bin N0. Missing first month gives NA for header height. Header height measures the recognizer's search band, allowing tall boxes to be detected even when trimming leaves few selected words. A full observed predicate records both X and O counts, including zeros. Histogram bins include zero cells in JSON/full text. Brief output may omit zero histogram/pattern cells while retaining both O/X condition counts and the fixed condition/bin definitions.

### Outputs

Retain run.json, results.jsonl, summary.json and summary.txt. Add summary_brief.txt to the fixed output allowlist. Add route_conditions with condition_order, aggregate condition counts, binned distributions, observed condition patterns to final routes, and availability/error populations. Validate key sets, reviewed code values, nonnegative integer counts, exact partition sums and page deduplication before writing. Existing results.jsonl rows and existing summary sections must match the accepted baseline on the preserved corpus.

The brief file prints population/availability counts, ROUTE and ROUTE_CROSS, condition order and O/X counts, distribution definitions/nonzero counts, pattern rows, and field-code/status rows with nonzero counts. Preserve full routes including zero cells so a missing government population is explicit. Field rows identify type, reference form, field, engine, code and count. Include existing comparison/eligibility denominators for interpreting REFERENCE_MISSING and unavailable paths. Exclude text, values, paths, filenames, coordinates, raw medians and exception messages.

### CLI error matrix and precedence

| Code | Trigger | Exit |
| --- | --- | ---: |
| ARGUMENT_ERROR | Unknown/missing flags, invalid integer or invalid/duplicate engine/field/limit selection | 2 |
| SYMLINK_REJECTED | Explicit root/out/ids argument is a symlink, including a dangling link | 2 |
| ROOT_NOT_DIR | Root is missing or is not a directory | 2 |
| OUT_INSIDE_ROOT | Output equals root or lies under root | 2 |
| ROOT_INSIDE_OUT | Root lies under output | 2 |
| OUT_EXISTS | Output already exists after overlap checks | 2 |
| IDS_NOT_FOUND | Specified list file is missing | 2 |
| IDS_INVALID | List is not a regular file, has unsafe hardlink/alias or overlaps output | 2 |
| LOCATION_REJECTED | Existing repository ignored/external location policy rejects an argument | 2 |
| OUTPUT_ERROR | Closed-schema rejection or fixed artifact-writing contract failure | 2 |
| UNEXPECTED_ERROR | Remaining unexpected exception, plus reviewed exception type only | 2 |
| INTERRUPTED | Keyboard interrupt | 130 |

Apply argument validation first, then explicit symlink checks, root/overlap/existence checks, existing location policy and ids validation. Terminal argument symlinks are rejected. Existing safe inventory behavior still counts/skips descendant symlinks. Preserve invalid/missing selector-line counters and per-line UTF-8 handling. IDS_INVALID concerns the list container/alias contract, so malformed individual selector lines retain their existing counted-skip behavior.

Use a fixed built-in exception vocabulary for the exception_type field. Map a custom exception to its nearest reviewed built-in base class. This permits exception-type reporting without exposing arbitrary custom class names or message contents. Static --help works without filesystem access or loading OCR dependencies and exits 0. Main must distinguish help's successful exit from unexpected exceptions.

### Regression scope superseded by the approval below

The requested new test file and required task/spec/usage documents reside outside engine_v2/tools. Applying the user's tools-outside-files condition literally schedules engine/backend/scenario/frontend verification in the tracked-source isolation. The user can narrow this condition to operating code during plan approval. Existing tests/expectations have zero planned modifications. Known filename assertions use FILENAMES, so adding summary_brief through that constant does not require an expectation rewrite. Any newly discovered old-test conflict is reported before changing expectations.

## Stage 2-1 implementation approval

On 2026-11-15 the user approved implementation. Changes under engine_v2/tools/, engine_v2/tests/, engine_v2/docs/ and .trellis/ require engine_v2 tests only. A changed path outside this set triggers backend, all 18 scenario modules and frontend checks as well. Report both git diff --name-only main...HEAD and working-tree paths to prove the decision. For H1/H2, report supporting/refuting synthetic numbers and exact summary_brief row families the operator should inspect. The five supplied patterns are available for the final staged-diff scan.

## 2-2단계 추천 설계 A

### 경계와 실제 식

nhis_payment_gov.recognizes의 머리글 후보 선택만 일반 높이 H와 첫 월 중심 C의 [C−3H, C−0.5H)로 바꾼다. 폭2.5H를 명시한다. H는 page_lines가 만든 유효 양수 상자 높이의 중앙값이다. 첫 월 후보 자격과 선택, 원 component-top 절단, header cluster/line 조립, 제목·문서번호 또는 정보 머리글 게이트, 반복 문자열 >=3 조건은 유지한다. 엔진 이름별 분기와 원 토큰/신뢰도 변경을 도입하지 않는다.

작은 내부 helper에서 실제 인식용 머리글과 정상 높이/첫 월을 구하고 recognizes와 진단 helper가 같은 선택을 사용하게 해 관찰 드리프트를 막는다. 기존 세 항목 추출 API와 필드 결과 투영은 유지한다. HEADER_HEIGHT_RATIO는 실제 새 검색 폭2.5H/쪽 높이를 기록하도록 정의와 문서·관찰을 함께 변경한다. 구간 이름과 조건 순서는 유지한다. 이 의도된 관찰 의미 변화에 따른 알려진 시험 영향은 연구 문서에 명시했다.

독립 가상 입력만으로 실제 OCR 재현3쪽과 구조 단위 패딩 불변성을 추가한다. 기존 합성 providers/Source 렌더러를 호출하는 새 시험 fixture는 허용하며 원 생성기와 410쌍 샘플은 바꾸지 않는다. 형식 자체를 바꾸어 측정 성공을 만드는 작업은 수행하지 않는다. 사전 고정한 12개 렌더 변형 모두의 현재/후보 수치는 장기 연구 결과에 보존한다.

### 비교 CLI

서명은 python -B -m engine_v2.tools.ocr_baseline_compare --before RESULT_DIR --after RESULT_DIR이다. 쓰기와 원 문서 접근 없이 두 결과의 run.json/results.jsonl을 기존 닫힌 검증 함수로 읽고 기존 build_summary/metrics 집계를 재사용한다. 등록된 전체 종류·필드·선택 엔진·변형 합집합의 격자를 출력한다. ASCII 필드 코드는 기존 FIELD_CODES를 재사용한다.

지표는 FIELD_AGREEMENT, PAGE_CER_MEAN, POOLED_CER, WORD_F1, OCR_TIME_PER_PAGE_S, TOTAL_TIME_PER_PAGE_S와 분자/분모·시도 상태다. 비율 전/후와 차이는 %p, 시간 전/후와 차이는 초로 명시한다. 차이는 음수도 허용하는 유한 수치다. CER>1을 보존한다. 미측정은 NA로 출력하고 분모0을 숨기지 않는다. 읽기 전용 요약에는 값/텍스트/ID/파일명/경로/해시/동적 예외 메시지가 포함되지 않는다.

설정 불일치·훼손된 결과·중복 행·인자 오류는 고정 코드로 처리한다. 입력 코호트/루트 식별 차이는 원문 없는 고정 상태와 숫자로 표시한다. 결과 JSON만으로 파일 바이트 동일성을 증명할 수 없으므로 합성은 원 입력 manifest로 따로 검증한다. 도움말·오류 경계와 음수 차이, 0분모, 미측정 종류, CER>1, 부분 코호트, 중복·훼손 결과를 시험한다.

### 검증 게이트

운영 코드 변경이므로 engine/backend/18 scenarios/frontend 전체를 순차 실행한다. backend 직전 df -h /가용15GiB 이상을 확인한다. 기준은 cdbe672 engine1983/3skip/3xfail과 원 baseline backend1410/2xfail, scenarios18/1885/0, frontend3명령0이다. 허용한 기대값 영향 외 기존 시험 실패는 즉시 보고한다.

410쌍은 원 samples5/seed20261113·분모·개별 상태를 보존한다. 각 엔진·종류의 새 음성 PASS 증가를 발견하면 이후 측정을 멈춘다. reference 결과는 완전히 같아야 한다. 전체 OCR 측정은 보존된 모든 합성 종류와6경로를 사용하며 own 필드2%p 초과 저하·AV 값 변화·참조/분모 변화의 이유를 보고한다. 70쪽 분기와 재현3쪽 결과를 별도 표로 남긴다. 원본 OCR 토큰/신뢰도, 판정/재업로드/쪽수 로직과 금액의 근거를 보존한다.

### 남은 위험

같은 중앙값 식도 provider 관측의 영향을 받으며, 새로운 밴드가 불완전한 정부형을 legacy로 보낼 수 있다. 연구 격자 전체에서 own은 GOVERNMENT7/12가 남는다. 추천안은 정식 재현3쪽을 해결하고 원 참조·AV를 보존하는 최소 변경이다. 2순위 머리글 정확 인식/조립과 열 경계 증거는 별도 변경으로 보류한다. 실제120쪽에서의95%와 글자층/AV 경로 영향은 사용자 재진단으로 확인한다.
