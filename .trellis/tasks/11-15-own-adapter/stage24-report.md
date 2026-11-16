# 2-4단계: 실서류 기반 legacy 표시 후보 (운영 판별·추출 수정 없음)

기준 커밋 92361b6. 숫자 근거와 연구 스크립트는 작업 공간 밖 장기 결과 폴더(route_stage24_marker)에 있다. 실서류·실서류 결과 폴더 접근 0건. engine_v2/extractors 변경 0줄.

## 실서류 결과 (사용자 실행 hub_shadow_2, 글자층 기준 LEGACY 120쪽)

| 항목 | 글자층 | own | AV |
| --- | --- | --- | --- |
| MARKER(가입구분) O | 0 | 0 | 0 |
| legacy 추출 가입구분 값 | 120쪽(MATCH_OPPORTUNITIES) | | |
| A_325 / A_350 / B LEGACY | 120 / 120 / 110 | 109 / 98 / 98 | 117 / 110 / 100 |
| L LEGACY | 120 | 0 | 118 |
| DIST3 BOSUOE | NA 120 | 2.750-3.000 10, 3.125-3.375 2, 3.375-3.875 108 | 3.000-4.000 21, 4.000-4.500 99 |

합성 fixture의 가입구분 머리글은 실서류를 대표하지 못했다. own 10쪽은 보수외가 2.75~3.0H에 있어 정부형 시험이 요구하는 3.25H보다 가깝다. 거리 규칙만으로는 own 110쪽을 넘기 어렵다.

## 1. legacy 추출기 단서

| 항목 | 함수 | 단서와 정규화 |
| --- | --- | --- |
| 가입구분 | nhis_payment.extract | 모든 쪽 글자를 이어 공백만 지운 문자열(squash)에 직장가입자·직장가입이 있거나, 원문에 정규식 `사업장\s*명칭\s*[:：]?\s*([^\s\|]+)`이 맞으면 직장, 아니면 지역가입자·지역가입이 있으면 지역. "가입구분" 글자는 쓰지 않는다. 값은 직장/지역 둘뿐이다. |
| 고지월 | _extract_monthly, _month_header, _header_block | 월 열 머리글: 한 줄 또는 위아래 1~2줄에 걸친 상자의 글자가 정확히 년월·월별·보험료월·납부월·납부년월·청구월·보험료연월(MONTH_LABELS) 중 하나(common.label_hits). 마지막 머리글 줄 아래 줄마다 확인합니다·국민건강보험공단 줄에서 멈추고, 연말정산 줄은 따로 읽고, 합계·납부총액 줄에서 멈춘다. 연월은 MONTH_RE(2025년 1월, 2025.01, 2025-1 등)와 COMPACT_MONTH_RE(202501)를 대시 통일(normalize_format_text) 뒤 찾고, 없으면 n월(MONTH_ONLY_RE)에 PERIOD_RE(YYYY년M월~YYYY년M월)의 시작 연도를 붙인다. |
| 발급일 | common.header_for_page, _closing_issue_date, _body_issue_date | 줄에 발급일·발급일자·발행일·출력일이 있으면 그 줄 날짜. 어느 쪽에도 없으면 마지막 쪽에서 확인합니다 뒤, 국민건강보험공단·이사장 줄 바로 앞의 날짜만 있는 줄. 그래도 없으면 확인합니다 줄의 날짜 또는 그 아래 6줄 안(공단명 전)의 날짜. |
| 월별 금액 | _header_x, _header_block, _closest_amount, _money_words | 월 머리글 주변 머리글 묶음에서 고지금액·고지보험료, 납부금액·납부보험료·실납부, 건강보험료, 장기요양보험료, 보수외소득월액(건강) 라벨의 가로 중심을 열 위치로 잡고, 각 월 행의 금액 중 가장 가까운 값을 고른다. |
| 성명·생년월일 | common.header_for_page | 성명 라벨 줄(또는 아래 3줄)의 이름, 주민등록번호 라벨 근처 3줄 안의 주민번호 앞자리, 없으면 생년월일 라벨 줄의 날짜. |

글자층에서 120쪽 모두 가입구분이 나온 경로: 위 규칙상 squash된 전체 글자에 직장가입(자)·지역가입(자)가 있거나 사업장명칭 라벨 뒤에 공백이 아닌 글자가 있으면 값이 생긴다. 정부형 판별도 사업장명칭을 정보 칸 게이트로 쓰므로(nhis_payment_gov.recognizes), 사업장명칭 경로는 정부형 서식에서도 똑같이 값을 만든다. 실서류가 어느 경로였는지는 이번 실행의 MARKER_CAND MEMBER_TYPE_VALUE text_layer O 쪽 수로 구분된다(120이면 직장·지역가입 문구, 0이면 사업장명칭 경로).

## 2. 표시 후보

규칙: L_<후보>는 표시가 있으면 LEGACY, 없으면 CURRENT. L_<후보>+A_325는 표시가 있으면 LEGACY, 없으면 A_325. 문구 후보는 묶인 한 줄 안에서 공백·대소괄호·쌍점·마침표·가운뎃점을 지운 뒤 찾는다. 오독 보정은 하지 않고, 여러 줄은 잇지 않는다.

| 후보 | 종류 | 정의 | 근거(legacy 추출기) | 정부형 시험 입력 | legacy 시험 입력 |
| --- | --- | --- | --- | ---: | ---: |
| RRN_LABEL | 라벨 | 주민등록번호 | header_for_page의 생년월일 경로 라벨(정부형은 가입자성명·생년월일) | 0 | 61회(21개 시험) |
| MEMBER_CLASS_LABEL | 라벨 | 가입구분 또는 가입자구분 | 가입구분 필드의 머리글 변형 | 0 | 100회(50) |
| LEGACY_ALIAS_LABEL | 라벨 | 고지보험료·납부보험료·실납부·출력일·발행일 | _extract_monthly 금액 열 별칭과 header_for_page 발급일 별칭 중 정부형에 없는 것 | 0 | 3회(1) |
| YEAR_MONTH_ROWS | 표 구조 | 맨 왼쪽 상자(공백 제거, 대시 통일)가 통째로 legacy 연월(MONTH_RE·COMPACT_MONTH_RE)인 줄 3개 이상 | 월별 행의 첫 열 연월(정부형 행은 n월) | 0 | 133회(68) |
| MONTH_TABLE_ROWS | 머리글+표 구조 | legacy 월 머리글(_month_header) 아래, 합계·납부총액·확인합니다·국민건강보험공단 줄 전까지 연월이 있는 줄 3개 이상 | _extract_monthly의 행 규칙(기간 줄로 n월에 연도 붙이기는 제외) | 0 | 132회(68) |
| MEMBER_TYPE_VALUE | **값 패턴** | 직장가입 또는 지역가입 | extract의 가입구분 값 문구 | 0(정부형 판독 fixture) | 219회(103) |

정부형 시험 입력: 엔진 시험 전체(2166개)의 판별 호출 569회 중 운영 판별이 정부형으로 본 293회(265개 시험)와 어느 규칙이든 정부형으로 본 301회. 정부형 렌더 변형(p2_payment_samples 배율·흔들림·기울기, p2_shape3 분할 머리글)도 여기에 들어 있고 새 시험이 따로 고정한다. MEMBER_TYPE_VALUE만 정부형으로 판별된 호출 32회(운영 24회)에 나오는데, 모두 2-2단계 렌더 격자(grid_pdf, "legacy 3개월 표에 가상 성분 문구를 반복한 것")의 진단 시험이다. 정부형 판독 fixture에는 0회이므로 후보로 남기고 값 패턴으로 표시한다.

합성 원 70쪽: 정부형 20쪽은 여섯 후보 모두 세 경로 0/20. legacy 50쪽은 세 경로 같다: RRN_LABEL 0, MEMBER_CLASS_LABEL 50, LEGACY_ALIAS_LABEL 0, YEAR_MONTH_ROWS 50, MONTH_TABLE_ROWS 40, MEMBER_TYPE_VALUE 50. 렌더 12쪽(격자 9쪽 + 재현 3쪽)은 세 경로 모두 MEMBER_TYPE_VALUE만 12/12이고 나머지는 0이다.

### 뺀 단서

| 단서 | 이유 |
| --- | --- |
| 사업장명칭 (가입구분 직장 판정 정규식) | 정부형 판별 게이트 자체가 쓴다. 정부형 시험 입력 297회 |
| 발급일, 발급일자, 날짜가 있는 발급일 줄 | 정부형 시험 입력 56회, 24회, 30회(p2_payment_headers, p2_shape3 등) |
| 정확한 월 머리글 년월, 보험료월 | 정부형 입력 1회(test_p2_payment), 2회(p2_payment_headers 등). 월별은 정부형 머리글이다 |
| 줄 시작 연월 3줄 이상 | 정부형 판독 fixture 26회(p2_payment_headers 14, p2_shape3 2, review_regressions 2 등). 기간 줄·날짜 줄이 줄 머리에 온다. 맨 왼쪽 상자 전체로 좁혀 YEAR_MONTH_ROWS로 남겼다 |
| 납부총액, 합계, 확인합니다, 국민건강보험공단 | 정부형 서식에도 있다(정부형 195회 등) |

## 3. 합성·시험 평가

### 새 규칙을 운영 판별 자리에 넣었을 때 기존 엔진 시험 (2166개, 기대값 변경 없음)

| 규칙 | 실패 | 판별·판독 시험 | 진단 미러(route_diag / shadow_route / shadow_candidates) |
| --- | ---: | ---: | --- |
| L_RRN_LABEL, L_MEMBER_CLASS_LABEL, L_LEGACY_ALIAS_LABEL, L_YEAR_MONTH_ROWS, L_MONTH_TABLE_ROWS | 0 | 0 | 0 |
| 위 다섯의 +A_325 | 각 40 | 0 | 29 / 7 / 4 |
| L_MEMBER_TYPE_VALUE | 24 | 0 | 0 / 12 / 12 (렌더 격자 기대값) |
| L_MEMBER_TYPE_VALUE+A_325 | 60 | 0 | 29 / 17 / 14 |

+A_325의 40개는 2-3단계 A_325(36개, 당시 2072개 기준)와 같은 진단 미러에 2-3단계 시험 4개가 더해진 것이다. 진단 미러 실패는 판별을 바꾸면 반드시 생기며 운영 반영 때 따로 고친다(R46).

### 합성 분기 (G = GOVERNMENT, L = LEGACY)

| 자료 / 경로 | CURRENT | L_RRN·L_MEMBER_CLASS·L_ALIAS·L_YM_ROWS·L_MONTH_TABLE | 같은 다섯의 +A_325 | L_MEMBER_TYPE_VALUE | L_MEMBER_TYPE_VALUE+A_325 |
| --- | --- | --- | --- | --- | --- |
| 원70 legacy50 / 세 경로 | L50 | L50 | L50 | L50 | L50 |
| 원70 정부형20 / 글자층·AV | G20 | G20 | G20 | G20 | G20 |
| 원70 정부형20 / own | L20 | L20 | L20 | L20 | L20 |
| 렌더12 / 글자층 | G9 L3 | G9 L3 | G9 L3 | L12 | L12 |
| 렌더12 / own | G12 | G12 | G10 L2 | L12 | L12 |
| 렌더12 / AV | G2 L10 | G2 L10 | G3 L9 | L12 | L12 |
| 재현3 / 글자층 | L3 | L3 | L3 | L3 | L3 |
| 재현3 / own | G3 | G3 | G1 L2 | L3 | L3 |
| 재현3 / AV | L3 | L3 | L3 | L3 | L3 |

원 70쪽 글자층·AV 분기는 모든 새 규칙에서 그대로다. 라벨·구조 다섯 후보는 합성 자료에서 CURRENT(+A_325는 A_325)와 같은 분기를 낸다. 실서류에서의 차이는 표시 쪽 수에서만 생긴다.

## 4. 실서류 채택 기준과 읽을 줄

| 기준 | 읽을 줄 |
| --- | --- |
| 글자층 LEGACY 120 그대로 | CANDIDATE_ROUTE L_<후보> text_layer LEGACY 120 |
| AV LEGACY 118 이상 | CANDIDATE_ROUTE L_<후보> applevision LEGACY |
| own LEGACY 114 이상 | CANDIDATE_ROUTE L_<후보> own LEGACY |
| 기존 판별·판독 시험 기대값 변경 없이 통과 | 위 표: 열두 규칙 모두 판별·판독 실패 0 |
| 원 70쪽 글자층·AV 분기 유지 | 위 표: 열두 규칙 모두 유지 |
| 여럿이 만족하면 | 라벨(RRN·MEMBER_CLASS·ALIAS) > 구조(YEAR_MONTH_ROWS·MONTH_TABLE_ROWS) > 값 패턴(MEMBER_TYPE_VALUE) |

예측: L_<후보>는 CURRENT에 LEGACY만 더하므로 글자층 120·AV 118 이상이 보장된다. CURRENT own이 GOV 120이므로 own LEGACY는 MARKER_CAND <후보> own O 쪽 수와 같다. L_<후보>+A_325의 own LEGACY는 표시 O 쪽과 A_325 LEGACY 109쪽의 합집합이다. 어느 후보도 own O가 114에 못 미치면, 실서류는 정부형 서식과 같은 인쇄 문구를 공유한다는 뜻이다. 그 경우 표시 방식으로는 풀 수 없으므로 다음 단계에서 다른 접근을 정한다.

## 검증

- 엔진 시험: 2264 passed / 3 skipped / 3 xfailed / 실패 0 = 2166 + 새 시험 98(test_own_adapter_marker_candidates.py 수집 98).
- 기존 시험 변경 1줄: test_own_adapter_shadow_candidates.py의 끝-끝 시험이 brief CANDIDATE_* 줄의 토큰을 고정 목록으로 검사하므로, 허용 목록에 shadow.MARKER_RULES를 더했다. 기대 분기와 기존 줄 내용은 바꾸지 않았다.
- 변경 경로는 engine_v2/tools, engine_v2/tests, engine_v2/docs, .trellis뿐이라 engine_v2 시험만 실행했다.
- 메모리 평가(보존 캐시)와 실제 도구 native 재실행(원 70쪽 111 PDF 지문 일치, 렌더 12쪽)이 246경로 × 19항목(분기 1, 규칙 12, 표시 6), 비교 4674개에서 모두 같다. 규칙 오류 0, 종료 코드 0.
- 기존 출력 보존(2-3단계 실행 결과와 비교): results.jsonl·run.json 바이트 동일. summary.json 기존 8개 절 동일, 새 절은 shadow_markers. summary.txt는 기존 내용이 접두다. summary_brief.txt는 기존 줄 순서를 유지한다. 추가 줄 계열은 MARKER_CAND_RULES, MARKER_CAND_KIND, MARKER_CAND, CANDIDATE_ROUTE, CANDIDATE_CROSS(새 규칙)뿐이다.
