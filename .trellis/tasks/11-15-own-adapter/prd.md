# own OCR 어댑터 진단 — 요구사항

현재 상태: 1단계 95d9ef7, 2-1단계 cdbe672, 비교 CLI 2610a2c 커밋 완료. 2-2단계는 A를 운영에 넣지 않고 구조 기반 후보 S를 그림자 평가로 검증하는 중이다(아래 "2-2단계 변경 기준"). 아래 0~1단계 기록은 완료된 이력이다.

기존 상태 기록: 0~1단계 조건부 실행 승인. 아래 2026-11-15 승인 조건을 반영한 뒤 실행한다. 커밋과 2~3단계 구현은 미승인이다. 브랜치는 `work/own-adapter`, 시작 main은 `2b4ab5949a2d7455a3da7da3ab0fd7c1f687e4d8`이다.

## 조건부 승인 반영 — 1단계 보고 첫머리에도 명시

- 오통과 기준은 0단계에서 새로 잰 값이며 고정 상한은 쓰지 않는다. own/글자층 참조 각각 × 서류 종류별 증가가 하나라도 있으면 중단한다. own 전체 0/235 유지는 필수다.
- 글자층 참조는 own 어댑터와 무관하므로 전후 수치가 완전히 같아야 한다. 다르면 중단·보고한다. 새 0단계 값이 PR #7의 own 0/235, 참조 전체 15/235, 납부 5/50과 다르면 1단계로 넘어가지 않는다.
- 1단계 첫 작업은 baseline의 납부 가입구분·고지월·발급일 추출 호출을 함수 이름으로 확인하는 것이다. 진단도 같은 호출을 그대로 쓰며 다른 추출 경로로 우회하지 않는다.
- 가입구분은 동일 추출 경로의 합성 서식 50쪽, 정부형이 고지월·발급일을 출력하면 정부형도 별도로 최소 20쪽을 추가해 서식별 집계한다. 실서류는 읽지 않는다. 동등 서식 여부를 확인할 수 없거나 다를 근거가 있으면 “합성·실서류 서식 차이 가능”과 근거를 보고한다.

## 목표와 배경

글자 인식 CER이 비슷해도 납부확인서 가입구분·고지월의 own 추출 성공률이 AV보다 낮은 원인을 단어·상자·줄·순서·정규화 계약에서 진단한다. 최종 목표는 own clean 합성 일치율을 두 필드 각각 95% 이상으로 올리면서 오통과를 늘리지 않는 것이다. 이번 실행 승인 대상은 0~1단계이며, 진단 후 실제 서류 진단 결과와 별도 수정 계획 승인을 기다린다.

## 요구사항

| ID | 요구사항 |
| --- | --- |
| R01 | 회귀 묶음을 수정 전에 순차 실행한다. 기준은 engine 1,748 passed / 3 skipped / 3 xfailed, backend 1,410 passed / 2 xfailed, 시나리오 18개 / 1,885개 검사 / 실패 0, 프런트 세 명령 성공이다. 차이가 하나라도 나면 해당 지점에서 중단·보고하며 기존 시험이나 기대값을 바꾸지 않는다. |
| R02 | 기존 410쌍 생성기·정답·seed·지표를 그대로 사용해 own과 글자층 참조의 오통과·확실한 오FAIL·REVIEW·PASS·실행 오류와 분모를 저장한다. 원자료와 집계는 외부 임시 기준값 폴더에 보관하고 커밋하지 않는다. |
| R03 | 기존 합성 생성 경로가 있는 서류를 사용해 모든 등록 필드 × own/AV × clean/scan/phone을 측정한다. 참조 필드 부재, 생성기 부재, 분류 실패, OCR 오류, AV 빈 출력은 분리하고 성공률 0 또는 100으로 대체하지 않는다. |
| R04 | 원본 서류 및 그 결과 저장소는 열기·목록 조회·실행·존재 확인도 하지 않는다. 사용자가 실행하는 명령만 후속 보고에 제공한다. 가림 덤프는 나중에 필요한 경우에만 own 토큰 구조 존재를 먼저 확인하고 구조 참고에 한정하며 값·좌표를 시험·코드·보고로 전사하지 않는다. |
| R05 | 1단계에서는 OCR 엔진, 운영 어댑터, 추출기, 분류기, 판정 규칙·임계값·재업로드 사유·쪽수 검증을 수정하지 않는다. 새 진단 도구와 독립 합성 시험·문서만 추가한다. |
| R06 | 진단 도구는 PDF 폴더 또는 루트 상대 목록을 받고 기존 본문/좌표 기반 분류와 clean 렌더를 사용한다. 목록은 바로 아래 사람 폴더 ID(그 폴더의 PDF 전체)와 상대 PDF 경로를 모두 허용하며 빈 줄·주석을 무시하고 잘못되거나 없는 대상은 내용 없이 개수만 센다. 목록은 선택에만 쓰며 기본 납부 필드 실행에서는 납부로 판별되지 않은 문서를 건너뛰고 센다. 정답은 동일 쪽 글자층의 기존 추출값이다. 기본 필드는 납부 가입구분·고지월·발급일이며 다른 등록 필드도 지정할 수 있다. |
| R07 | 실패 코드는 사용자 지정 순서의 최초 해당 하나이다. 단계별 충족 증거가 없으면 원인을 추정하지 않는다. 단순 정확 일치와 정규화 일치를 구분하며 실제 추출에 임의의 보정값을 넣지 않는다. |
| R08 | 진단 stdout/stderr와 결과 파일은 허용된 코드 이름·정수·유한 수치·null만 사용한다. 문서는 숫자 일련번호로만 식별한다. 글자·실제 필드값·경로·파일명·좌표·입력 해시·예외 메시지·traceback을 내보내지 않는다. |
| R09 | 납부확인서 합성 글자층 PDF를 최소 50쪽 진단한다. 기존 생성기/셀 렌더러가 받는 가상 셀 입력으로 legacy 50쪽을 만들고 정부형도 별도로 최소 20쪽 추가하고 서식별로 집계한다. 이름·가입표기·날짜/월 형식의 입력 조합은 실행 계획에 사전 고정하며 추출 결과에 맞춰 조정하지 않는다. 기존 410쌍 코퍼스는 변경하지 않는다. |
| R10 | 모든 실패 코드, 우선순위 충돌, 라벨 없는 필드, 개인정보 누출 차단, 입력 선택·건너뜀·분모·엔진 오류를 새 합성 시험으로 검증한다. 기존 시험 파일과 공용 픽스처는 수정하지 않는다. |
| R11 | 작업 생성, 실행 계획, 1단계 커밋, 2~3단계 계획 및 커밋은 각각 승인받는다. amend·push·공저자 trailer는 금지한다. 커밋 전 지정된 다섯 패턴 검사가 전부 0이어야 한다. |

## 수용 기준과 중단 지점

| 기준 | 확인할 결과 |
| --- | --- |
| AC01 → R01 | 네 회귀 묶음이 제공 기준과 일치하며 로그·종료코드가 보관된다. 불일치는 수정 없이 즉시 보고한다. |
| AC02 → R02~R03 | `/tmp/own_adapter_before/`에 410쌍 820경로와 전 필드 OCR 기준값, 실행 조건·소스 식별·코퍼스 동일성 증거가 있다. 미측정 종류/필드도 드러난다. |
| AC03 → R04~R08 | own/AV 경로 비교표와 값 없는 진단 CLI가 있고, 실서류 접근·운영 코드 변경·문자열 누출이 없다. |
| AC04 → R09~R10 | 납부 50쪽 이상 코드 분포, 새 시험의 정확한 수, 기존 시험 수 보존을 보고한다. |
| AC05 → R11 | 1단계 완료 보고 및 커밋 승인 요청에서 멈춘다. 실제 서류 결과와 수정 계획 승인 전에는 2단계를 시작하지 않는다. |

## 이후 단계에 보존할 조건

- 수정은 own 출력 → 추출기 입력 경계에 한정한다. AV 동일 입력의 구조는 전후 완전히 동일해야 한다.
- 합친 신뢰도는 구성 요소 최솟값 이하, 분할 신뢰도는 원값 유지다. 0.9 미만의 기존 REVIEW 경로는 유지한다.
- 보호 필드는 자격득실 가입구분·취득일, 자격확인서 발급일, 초본·납부 성명·생년월일이다. 다른 own 필드가 2%p 넘게 떨어지면 중단·보고 후 승인을 기다린다.
- 합성 전후 오통과는 엔진별 × 서류 종류별 새 기준값 대비 하나라도 늘면 즉시 중단한다. 글자층 참조 전후 수치는 완전히 같아야 하며 다르면 중단한다. own 전체 0/235 유지, AV 일치율 동일, own 시간 10% 초과 증가 시 보고 조건을 보존한다.
- 추출기 규칙 수정이 필요하면 변경하지 않고 이유·대안을 보고해 승인받는다. 양 엔진 모두 실패하는 제외 필드는 측정표에는 남기되 개선 대상으로 삼지 않는다.

## 확인된 위험과 보류 사항

1. PR #7의 own 0/235, 참조 전체 15/235·납부 5/50은 0단계 재현 확인용이다. 새 측정이 다르면 1단계 진입을 중단·보고한다. 고정 상한 대신 재현된 새 기준값과 엔진별 × 종류별 증가 여부 및 참조 완전 동일성을 사용한다.
2. Apple Vision은 sandbox에서 빈 결과를 반환한 전력이 있다. 합성 입력으로 환경 문제를 분리하고 숫자로 보고하며, 빈 출력을 인식률 근거로 단정하지 않는다.
3. 간이 본문 생성기 및 쪽별로 완결되지 않는 일용근로 부록은 유효 참조 필드가 없을 수 있다. 분모를 숨기거나 추출기 oracle로 채우지 않는다.

설계는 `design.md`, 실행 순서·명령은 `implement.md`, 코드 근거는 `research/source-map.md`에 둔다.

## Route-observation follow-up approved on 2026-11-15

- Add engine-wise page dispatch distributions and reference-versus-engine dispatch cross-tabulations using only counts and fixed form/engine names.
- Add ROUTE_MISMATCH immediately after OK and before label/evidence causes, with independent precedence tests.
- Rerun the same 70-page synthetic diagnosis and engine_v2 suite. Report government-page code changes and verify pass-count growth equals added tests.
- Inspect and report existing form-selection predicates. Keep implementation changes within diagnostic code/tests/documents.
- Repeat the supplied five-pattern scan over the entire staged diff and report its exact staged path list. Request commit approval after these additions.
- Keep actual operator paths in chat commands only. Private documents remain inaccessible throughout this follow-up.

## Stage 2-1 requirements and acceptance

The operator's 120-page route/field aggregates are recorded once in research/route-conditions.md. The purpose of this stage is to expose which government routing conditions differ between the actual extraction inputs for text_layer, own and applevision.

| ID | Requirement and observable acceptance |
| --- | --- |
| R21 | Inspect all LEGACY/GOVERNMENT/OTHER dispatch functions, input transformations and the default legacy behavior. Record source-grounded, testable hypotheses for the opposing synthetic/operator directions. |
| R22 | Add page-level aggregate O/X condition counts for all three paths, binned structural distributions and a condition-pattern to observed-route cross-tabulation. Preserve existing output fields and records. New content contains only fixed codes, O/X, bin names and numeric page counts. |
| R23 | Add static value-free --help with exit 0, distinct location/selection errors, and UNEXPECTED_ERROR with a reviewed exception-type name. ARGUMENT_ERROR covers argument parsing/validation. Add summary_brief.txt with routes, condition outputs and nonzero field-code rows, with enough population counts to interpret exclusions. |
| R24 | Reuse the exact preserved 70 pages, separated by reference LEGACY 50 / GOVERNMENT 20. Report all new aggregate families, verify previous field flags/routes remain equal and preserve evidence outside Git. Generator changes are deferred. |
| R25 | Add independent condition, boundary, parity, privacy, CLI-error and brief-output tests. Check that engine_v2 pass growth above 1875 equals the collected newly added tests, retaining 3 skipped / 3 xfailed. A failure in an existing test requires a report before any attempted expectation change. |
| R26 | Preserve source boundaries for classifiers, extractors, decisions, adapters, generators and shared runtime helpers. Test files and documentation are required deliverables outside tools. The literal tools-outside regression condition therefore schedules the full regression bundle unless the user narrows that condition during plan review. |
| R27 | Keep operator input paths solely in chat commands. Provide the requested absolute-cd/caffeinate invocation and a separate command that prints only summary_brief.txt after implementation. Private inputs and results receive zero agent accesses. |
| R28 | Follow the same Trellis task. Approve the plan before implementation, and approve the staged commit separately. Ask for the five scan patterns at the precommit gate, scan the whole staged diff, report exact paths and stop for commit approval. |

The design owns condition/bin/error contracts. The implementation plan owns the change sequence and verification gates. The accepted implementation baseline is commit 95d9ef7 with engine_v2 1875 passed / 3 skipped / 3 xfailed. Stage 2-2 starts after the operator supplies the expanded diagnosis and separately authorizes the next change.

## Stage 2-1 implementation approval

On 2026-11-15 the user approved implementation. Changes under engine_v2/tools/, engine_v2/tests/, engine_v2/docs/ and .trellis/ require engine_v2 tests only. A changed path outside this set triggers backend, all 18 scenario modules and frontend checks as well. Report both git diff --name-only main...HEAD and working-tree paths to prove the decision. For H1/H2, report supporting/refuting synthetic numbers and exact summary_brief row families the operator should inspect. The five supplied patterns are available for the final staged-diff scan.

## 2-2단계 현재 목표와 추천안

실서류 legacy의 own 가입구분·고지월·발급일 일치율을 각각 95% 이상으로 회복하고, 엔진·서류 종류별 잘못된 통과 증가를 0으로 유지한다. 사용자가 제공한 120쪽 재진단과 이번 구조·합성 연구의 숫자, 세 안 비교, 알려진 시험 영향은 research/route-stage22.md에 한 번씩 정리했다.

추천안 A는 첫 월 상자 높이 배수에 의존하는 탐색을 일반 상자 높이 중앙값 H와 첫 월 중심 C 기준의 [C−3H, C−0.5H)로 바꾼다. 실제 폭은 2.5H다. 이후 component-top 절단, 가로/줄 조립, 제목·메타 대체 조건과 반복 임계값은 기존 의미를 유지한다. 같은 식을 글자층·own·AV에 적용한다. 정상 전체 표·금액·기간 검증과 confidence 계산은 기존 추출기가 맡는다. 2순위 정부형 own의 머리글 인식·조립 수정은 이번 추천 범위에서 보류하고 원인과 후속안을 보고한다.

### 2-2단계 요구사항과 수용 기준

| ID | 요구사항과 관측 가능한 기준 |
| --- | --- |
| R31 | 사용자가 재실행한 legacy 120쪽에서 own 세 필드 각각 최소114/120 일치, 참조 LEGACY120 유지와 같은 참조/비교 분모를 확인한다. 에이전트의 합성 검증과 사용자 실서류 검증 결과를 구분한다. |
| R32 | 허용된 가림 자료는 구조만 읽고 원본 서류·나머지 결과 저장소를 읽지 않는다. 내용/좌표를 고정값으로 전사하지 않는다. 실제 사용자 실행 경로는 채팅에만 둔다. |
| R33 | 현 코드에서 글자층·AV LEGACY / own GOVERNMENT가 되는 실제 OCR 합성 3쪽과 독립 구조 사례를 보존한다. 수정 후 세 경로 모두 LEGACY여야 한다. |
| R34 | 기존 합성 legacy50·정부형20와 렌더 연구12쪽의 글자층·AV 분기는 현재와 같아야 한다. 전체 합성 검증 중 차이가 나타나면 목록과 이유를 보고하고 승인을 기다린다. |
| R35 | 서식 분기와 그 관찰에 필요한 최소 helper만 수정한다. 판정·신뢰도 보정·재업로드·쪽수 규칙, OCR 어댑터·엔진, 원 410쌍 생성기를 보존한다. 값 추측과 파일명 힌트는 0건이어야 한다. |
| R36 | research/route-stage22.md에 명시한 정상 기하 fixture 1건과 의도된 버그 기대값 영향 2건을 구현 승인에 포함해 검토한다. 추가 기존 시험 실패나 미승인 기대값 수정은 원인 보고 후 중단한다. |
| R37 | 엔진1983/3skip/3xfail과 backend1410/2xfail에서 통과 증가분이 각 새 시험 수와 같아야 한다. 18시나리오1885검사/실패0, 프런트3명령 exit0을 확인한다. backend 직전 가용15GiB 이상과 작업/장기 결과 분리를 지킨다. |
| R38 | 원 410쌍의 own/reference × 종류별 잘못된 PASS·FAIL·담당자 확인·PASS를 전후 비교한다. 새 음성 PASS 또는 잘못된 PASS 증가 하나라도 즉시 중단한다. own0/235와 모든 글자층 참조 결과를 유지한다. |
| R39 | 모든 원 합성 종류/필드 × own/AV × clean/scan/phone을 비교한다. own 필드 2%p 초과 하락은 보고·승인 대기, AV 값 변화는 이유를 보고한다. 70쪽 진단 분기 교차표도 전후 보존한다. |
| R40 | 결과 폴더 비교 CLI가 없으므로 기존 검증·집계를 재사용한 ocr_baseline_compare.py를 만든다. 종류/필드/엔진/변형별 일치율·CER·단어F1은 전/후/차이(%p), 시간은 전/후/차이(초)로 출력한다. 미측정·분모·코호트 차이를 고정 코드와 숫자로 보인다. |
| R41 | 비교 도구 stdout와 오류/도움말에 실제 값·ID·파일명·경로·좌표·해시·예외 메시지가 없어야 한다. 원 결과 JSON만 읽고 원본 문서를 열지 않는다. |
| R42 | 사용자가 지정한 진단·전체 OCR 재측정·결과 비교 명령을 경로를 채운 한 줄로 채팅에 제공한다. 진단 결과 확인 명령은 summary_brief.txt만 출력한다. |
| R43 | 한국어 표 보고, staged 전체 다섯 패턴0건과 정확한 스테이징 목록을 제출하고 별도 커밋 승인을 요청한다. 공저자 줄·amend·push 실행은 0건이다. |

### 수용 범위와 보류

A는 합성 70쪽과 렌더12쪽에서 글자층/AV 경로를 보존하고 재현3쪽 own을 교정했다. 실제120쪽의 95%는 후속 사용자 집계가 필요하다. 일반 상자 중앙값도 엔진 관측치이므로 모든 경계 변형에서 동일 분기를 보장하지 않는다. 정부형 own20쪽은 같은 식으로 해결되지 않았으며, 정확한 머리글 일치6/9 또는7/9와 열 경계 실패를 별도 보정 과제로 남긴다. 아직 미해결 제품 결정은 추천안과 알려진 시험 영향의 구현 승인이다.

## 2-2단계 변경 기준 (2026-11-16 사용자 결정)

A는 기존 정부형 시험 8개 실패로 운영에 넣지 않고 되돌렸다. 구조 기반 후보 S(첫 월 바로 위의 연속 머리글 줄 묶음, 정의는 stage22-stop.md)를 채택해 운영 판별·추출을 바꾸지 않는 그림자 평가로 먼저 검증한다. 아래 기준은 R33·R34를 대체한다.

| ID | 기준 |
| --- | --- |
| R44 | 생성 서식을 아는 합성 자료(렌더 12쪽, 재현 3쪽)는 "현재 분기 유지"가 아니라 "생성 서식대로 분기"가 기준이다. 렌더 12쪽은 글자층·own·AV 세 경로 모두 LEGACY여야 한다. 현재 대비 바뀐 수는 보고 항목으로만 남긴다. |
| R45 | 원 합성 70쪽(legacy50·정부형20)과 기존 판별 시험은 글자층·AV 분기를 현재와 같게 유지하고 기대값 변경 없이 통과해야 한다. |
| R46 | test_own_adapter_route_diag.py의 진단 미러 시험 29개는 S를 운영 코드에 넣을 때 고친다. 그때 목록과 이유를 보고하고 승인을 받는다. 그림자 평가 단계에서는 건드리지 않는다. |
| R47 | own_adapter_diag는 CURRENT·A·S를 같은 실제 납부 추출 입력에서 쪽마다 계산해 SHADOW_ROUTE <규칙> <엔진> <분기> <쪽 수>와 SHADOW_CROSS <규칙> <엔진> <글자층 분기> <후보 분기> <쪽 수>를 summary.txt·summary_brief.txt에 낸다. CURRENT 그림자는 실제 운영 분기와 쪽마다 같아야 한다(SHADOW_CHECK, 불일치·규칙 오류는 종료 코드 1). |
| R48 | 렌더 12쪽, 재현 3쪽, 원 70쪽의 그림자 결과가 연구 평가표와 쪽마다 같아야 한다. |
| R49 | 실서류 판단 기준(S 그림자): 글자층 LEGACY 120(현재와 같음), AV LEGACY 118 이상, own LEGACY 114 이상. 글자층이 하나라도 바뀌면 정답 경로가 흔들리는 것이므로 S를 운영에 넣기 전에 따로 검토한다. |
| R50 | 검색은 engine_v2/data와 실서류 결과 폴더를 제외한다. 커밋 전 다섯 패턴 검사와 스테이징 목록 보고 후 그림자 평가 커밋 승인을 따로 받는다. |

## 2-3단계: 그림자 후보 확장과 실서류 위치 분포 (2026-11-16 사용자 지시)

실서류 그림자 결과에서 S는 글자층 정답 경로를 바꿔 탈락했고, A는 own LEGACY 110(목표 114)과 기존 정부형 시험 8개 충돌이 남았다. 재현 사례 4의 상한은 더 이상 기준이 아니다. 운영 판별·추출은 바꾸지 않는다. 결과와 근거는 stage23-report.md에 둔다.

| ID | 요구사항과 기준 |
| --- | --- |
| R51 | 그림자 진단에 A_325, A_350, B, L, A_325+L, A_350+L을 추가한다. A_300은 A와 같으므로 별칭, CURRENT+L은 L의 별칭으로 출력한다. 기존 CURRENT·A·S 출력과 시험은 그대로 둔다. |
| R52 | legacy 전용 표시는 legacy 추출기와 fixture에서 정하고, 합성 정부형 20쪽·기존 정부형 시험 입력 전부·정부형 렌더 배치에 0회여야 한다. 정규화와 근거를 적는다. |
| R53 | 글자층 기준 납부확인서 쪽마다 엔진별 D3_BOSUOE·D3_INCOME 구간과 표시 O/X를 summary_brief.txt에 DIST3·MARKER 줄로 낸다. |
| R54 | 모든 후보를 원 70쪽·렌더 12쪽·재현 3쪽·기존 엔진 시험 전체에 적용한 분기와 실패 목록을 보고한다. 기대값은 바꾸지 않는다. CURRENT 그림자 = 운영 분기를 유지한다. |
| R55 | 실서류 채택 기준(다음 단계 판단): 글자층 LEGACY 120, AV LEGACY 118 이상, own LEGACY 114 이상, 기존 판별 시험 기대값 변경 없이 통과, 원 70쪽 글자층·AV 분기 유지. 여러 후보가 만족하면 L 계열을 우선한다. |

