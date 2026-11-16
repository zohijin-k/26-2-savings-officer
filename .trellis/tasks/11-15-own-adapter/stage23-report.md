# 2-3단계: 그림자 후보 확장과 실서류 위치 분포 (운영 판별·추출 수정 없음)

기준 커밋 fd87b4c. 숫자 근거와 연구 스크립트는 작업 공간 밖 장기 결과 폴더(route_stage23_shadow)에 있다. 실서류·실서류 결과 폴더 접근 0건. engine_v2/extractors 변경 0줄.

## 실서류 그림자 결과 (사용자 실행, 글자층 기준 LEGACY 120쪽)

| 규칙 | 글자층 | own | AV | 판단 |
| --- | --- | --- | --- | --- |
| CURRENT | LEGACY 120 | GOV 120 | LEGACY 118 / GOV 2 | SHADOW_CHECK 불일치 0 |
| A | LEGACY 120 | LEGACY 110 / GOV 10 | LEGACY 120 | own 목표 114 미달, 기존 정부형 시험 8개 충돌 |
| S | LEGACY 110 / GOV 10 | GOV 120 | LEGACY 58 / GOV 62 | 탈락(글자층 정답 경로 변경) |

합성 재현 3쪽은 실서류 구조를 대표하지 못한다. 재현 사례 4의 상한(3.2489H)은 이제 기준으로 쓰지 않는다.

## 추가 후보

| 후보 | 정의 |
| --- | --- |
| A_300 | A와 식이 같다(C−3.00H ≤ cy < C−0.5H). 별칭으로만 출력(CANDIDATE_ALIAS A_300 A). |
| A_325, A_350 | A의 상한만 C−3.25H, C−3.50H. 하한 C−0.5H. |
| B | 제목·메타 게이트 + 기존 정부형 판독기의 구조 검사 5개(payment_group_headers, payment_component_headers, payment_columns, monthly_rows_found, months_continuous) 모두 통과. 머리글 반복 수 조건 없음. |
| L | legacy 전용 표시가 있으면 LEGACY, 없으면 CURRENT. CURRENT+L과 같은 규칙이므로 별칭(CANDIDATE_ALIAS CURRENT+L L). |
| A_325+L, A_350+L | 표시가 있으면 LEGACY, 없으면 해당 거리 규칙. |

### legacy 전용 표시: 가입구분

| 근거 | 내용 |
| --- | --- |
| legacy 추출기 | nhis_payment.extract는 legacy 경로에서만 가입구분 필드를 만든다(정부형 판독기에는 이 항목이 없다). 기존 legacy 시험 fixture(test_nhis_extractors payment_pages)와 합성 legacy 50쪽이 가입구분 머리글을 가진다. |
| 합성 정부형 20쪽 | 세 경로 모두 0/20. legacy 50쪽은 세 경로 모두 50/50. |
| 기존 정부형 시험 fixture 전부 | 엔진 시험 전체에서 판별 함수 호출 529회를 조사했다. 운영 판별이 정부형으로 본 259회(237개 시험)와 어느 후보든 정부형으로 본 263회 모두에서 표시 0회. 표시가 있는 30회(26개 시험)는 모두 운영 판별 LEGACY다. |
| 정부형 렌더 배치 | p2_payment_samples 기하 변형(배율·흔들림·기울기)과 p2_shape3 분할 머리글 정부형 렌더에서 0회(새 시험이 고정). 2-2단계 렌더 격자 12쪽은 legacy 생성물이며 표시가 없다(직장가입자만 있음). |
| 정규화 | 묶인 한 줄의 글자를 이어 붙인 뒤 공백, 대·소괄호, 쌍점, 마침표, 가운뎃점을 지우고 가입구분 포함 여부를 본다. 같은 줄에서 두 상자로 갈라진 가입 / 구분은 잡는다. 글자 혼동 보정은 하지 않는다(가입구븐은 없음으로 센다). 세로로 갈라진 경우는 잇지 않는다. 가입자구분은 표시가 아니다. |
| 택하지 않은 안 | 직장가입자/지역가입자 값 문구는 정부형 fixture에 없지만 제목·다른 서식에 나올 수 있는 값이고, 렌더 격자에만 가상 칸으로 들어 있어 결과를 생성기 선택에 맡기게 된다. 머리글인 가입구분만 쓴다. |

## 위치 분포 출력

글자층 기준 납부확인서 쪽마다 엔진별로 첫 월 중심 위쪽 보수외(소득월액) 포함 상자 중심 거리(H)를 가까운 순으로 정렬해 세 번째 값을 구간으로 센다. 구간: 0.000-2.000, 2.000-4.000은 0.125H, 4.000-6.000은 0.5H, 6.000+, NA(3개 미만·첫 월 없음·납부 분기 없음). 아래 끝 포함, 위 끝 미포함. 출력: DIST3 <엔진> BOSUOE|INCOME <구간> <쪽 수>, MARKER <엔진> O|X <쪽 수>(납부 분기가 없는 경로만 NA). 새 후보 줄은 CANDIDATE_RULES/ALIAS/ROUTE/CROSS다. 기존 시험이 SHADOW_* 줄의 규칙을 CURRENT·A·S로 고정하므로 접두어를 나눴다.

## 합성 평가 (원 70쪽·렌더 12쪽·재현 3쪽)

메모리 평가(보존 캐시)와 실제 도구 native 재실행이 246경로 × 13항목(9규칙·분기·D3 2개·표시)에서 모두 같다. 규칙 오류 0, 종료 코드 0.

| 자료 / 엔진 | CURRENT | A(=A_300) | S | A_325 | A_350 | B | L | A_325+L | A_350+L |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 원70 legacy50 / 세 경로 | L50 | L50 | L50 | L50 | L50 | L50 | L50 | L50 | L50 |
| 원70 정부형20 / 글자층·AV | G20 | G20 | G20 | G20 | G20 | G20 | G20 | G20 | G20 |
| 원70 정부형20 / own | L20 | L20 | L20 | L20 | L20 | L20 | L20 | L20 | L20 |
| 렌더12 / 글자층 | G9 L3 | G9 L3 | L12 | G9 L3 | G12 | L12 | G9 L3 | G9 L3 | G12 |
| 렌더12 / own | G12 | G7 L5 | L12 | G10 L2 | G10 L2 | L12 | G12 | G10 L2 | G10 L2 |
| 렌더12 / AV | G2 L10 | G2 L10 | L12 | G3 L9 | G4 L8 | L12 | G2 L10 | G3 L9 | G4 L8 |
| 재현3 / 글자층 | L3 | L3 | L3 | L3 | G3 | L3 | L3 | L3 | G3 |
| 재현3 / own | G3 | L3 | L3 | G1 L2 | G1 L2 | L3 | G3 | G1 L2 | G1 L2 |
| 재현3 / AV | L3 | L3 | L3 | L3 | G1 L2 | L3 | L3 | L3 | G1 L2 |

표시 O: 원70 legacy 50/50(세 경로), 정부형 0/20, 렌더12 0/12. D3: 원70 정부형 글자층·AV 보수외 2.875-3.000, 소득월액 2.125-2.250 / own 보수외 NA(쪽당 1~2개), 소득월액 2.250-2.375 / legacy 50쪽 모두 NA. 렌더12는 2.125-3.625에 퍼져 있다.

## 기존 엔진 시험에 후보를 운영 판별 자리에 넣었을 때 (기대값 변경 없음, 2072개 기준)

| 후보 | 실패 | 판별·판독 시험 | 진단 미러(route_diag 29 + shadow_route) |
| --- | ---: | ---: | ---: |
| A (=A_300) | 53 | 8 (기울기 6, 세로분할 2) | 45 |
| S | 48 | 0 | 48 |
| A_325 / A_325+L | 36 | 0 | 36 |
| A_350 / A_350+L | 40 | 0 | 40 |
| B | 73 | 23 | 50 |
| L | 0 | 0 | 0 |

B의 23개는 손상·불완전 정부형(월 누락·머리글 누락·합계 누락·성분 순서 바뀜·분할 머리글 복구 불가·불확실 정산)을 정부형 경로에서 검토로 보내야 하는 시험들이다(test_p2_payment 4, test_p2_payment_headers 3, test_payment_stage2_structure 14, test_layout_dump_structure 2). B는 이들을 legacy로 보내므로 탈락이다. 진단 미러 실패는 판별을 바꾸면 반드시 생기는 것으로, 운영 반영 때 따로 고친다(R46과 같음).

## 실서류 판정 기준과 읽을 줄

| 기준 | 읽을 줄 |
| --- | --- |
| 글자층 LEGACY 120 그대로 | CANDIDATE_ROUTE <후보> text_layer LEGACY 120 |
| AV LEGACY 118 이상 | CANDIDATE_ROUTE <후보> applevision LEGACY |
| own LEGACY 114 이상 | CANDIDATE_ROUTE <후보> own LEGACY |
| 기존 판별 시험 기대값 변경 없이 통과 | 위 표(합성): A_325·A_350·L 계열 통과, A·B 실패 |
| 원 70쪽 글자층·AV 분기 유지 | 위 표(합성): 모든 후보 유지 |

예측: L은 CURRENT에 LEGACY만 더하므로 글자층 120·AV 118 이상이 보장되고, own LEGACY는 MARKER own O 쪽 수와 같다(CURRENT own GOV 120). A_325·A_350은 A보다 넓은 밴드여서 own LEGACY가 A의 110보다 늘기 어렵다. 따라서 MARKER own O가 114 이상이면 L이 기준을 만족하고, 거리 문턱에 의존하지 않으므로 우선한다. own O가 모자라면 A_325+L의 own LEGACY와 DIST3 own 분포로 다음 후보를 정한다.

## 검증

- 엔진 시험: 2166 passed / 3 skipped / 3 xfailed / 실패 0 = 2072 + 새 시험 94(test_own_adapter_shadow_candidates.py 수집 94). 기존 시험·기대값 수정 0.
- 변경 경로는 engine_v2/tools, engine_v2/tests, engine_v2/docs, .trellis뿐이므로 engine_v2 시험만 실행했다.
- 기존 출력 보존(원70·렌더12 native 재실행): results.jsonl·run.json 바이트 동일, summary.json 기존 7개 절 동일(새 절 shadow_candidates), summary.txt 기존 내용이 접두, summary_brief.txt 기존 줄 순서 유지. 추가 줄 계열은 CANDIDATE_RULES/ALIAS/ROUTE/CROSS, DIST3, MARKER뿐이다.
