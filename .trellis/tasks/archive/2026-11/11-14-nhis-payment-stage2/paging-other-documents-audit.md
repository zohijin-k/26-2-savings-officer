# 다른 서류의 쪽수 도우미와 판정 연결 조사

읽기 전용 코드 조사. 이번 작업에서 아래 다른 서류의 추출기·규칙은 변경하지 않았다. ‘연결’은 도우미가 있다는 뜻과 최종 누락 FAIL까지 연결된다는 뜻을 구별한다.

| 서류 | 쪽수 관련 수집/검증 | 최종 판정 연결 | 한계 / 별도 작업 후보 |
| --- | --- | --- | --- |
| 납부확인서 | 이번 `payment_paging.collect` → LocalOcr `납부쪽표기자료` | `check_document`가 독립 병합. 확실한 누락은 PAGES_INCOMPLETE FAIL, 불확실은 전용 REVIEW | own·글자층 공통. 상단 탐색 범위와 표 완전성 보완은 현재 사용자 검토 대상 |
| 주민등록초본 | resident 추출기 → `_from_resident`의 `쪽표기자료` | `_check_resident_pages`가 PAGES_INCOMPLETE/PAGES_DUPLICATED FAIL 또는 PAGES_UNREADABLE REVIEW로 연결 | 해당 필드가 없으면 검사 생략. 일반 PdfText 경로는 모두 이 필드를 생성하지 않으므로 전 경로 보장은 아님 |
| 주민등록등본 | `_from_resident` 사용 시 같은 쪽표기 필드 생성 | 전용 쪽수 소비 호출은 초본에만 있음 | 필드가 있어도 등본에 초본의 독립 누락 판정은 실행되지 않음 |
| 건강보험 자격확인(통보)서 | 지원 NHIS 양식에서 `nhis_forms.single_page`: 실제 한 쪽 및 상단의 정확한 1/1 요구 | `nhis_single_page` 구조 검증 실패가 양식 불완전/낮은 신뢰도를 거쳐 REVIEW에 반영 | 전체 쪽수와 받은 쪽의 독립 비교로 PAGES_INCOMPLETE FAIL을 만드는 공통 소비기는 없음. 일반/구형 양식과 경로 구별 필요 |
| 건강보험 자격득실확인서 | 지원 NHIS 양식에서 같은 `single_page` 사용 | 위와 같은 구조 검증 → REVIEW 연결 | 정부형·구형 양식까지 같은 방식으로 독립 누락 FAIL이 연결되는 것은 아님 |
| 4대보험 가입내역확인서 | `insurance_4`의 `_page_marker` / `_portal_page_marker`; `page_complete`, `page_marker_1_of_1` 검증 | LocalOcr의 불완전/검증 실패가 REVIEW에 반영 | 상단 1/1 형식 확인은 있으나 확실한 전체 쪽수>받은 쪽을 독립 PAGES_INCOMPLETE FAIL로 소비하지 않음 |
| 사업자등록증명 | `business_single_page`로 물리적 한 쪽 검사 | 구조 불완전 처리 연결 | 인쇄 전체 쪽수 수집·독립 비교는 없음 |
| 종류 미분류 일반 경로 | LocalOcr `independent_page_markers` → `독립쪽표기자료` | `doc_check`의 특정 초저해상도/미판독 조기 종료 분기에서만 PAGES_INCOMPLETE 추가 가능 | 모든 정상 분류 서류에 실행되는 공통 쪽수 검사가 아님 |

주요 근거: `demo/backend/ocr/localocr.py::_from_resident`, `_from_supported_form`, `LocalOcr._read`; `demo/backend/rules/doc_check.py::_check_resident_pages`, `_check_document`, `check_document`; `engine_v2/extractors/nhis_forms.py::single_page`; `nhis_qualification.py`, `nhis_acquisition_loss.py`, `insurance_4.py`, `business_registration.py`의 명명된 검증. 단일 쪽 양식 검증과 여러 쪽 서류의 누락 판정은 기능이 같지 않다. 연결이 부족한 다른 서류의 수정은 사용자 지시대로 별도 작업이다.
