/**
 * 판독 결과(추출값)를 담당자가 읽는 모양으로 바꾼다.
 *
 * 백엔드는 목록·월별 금액·검증 자료 같은 값을 JSON 문자열로 저장한다.
 * 화면에는 그 문자열을 그대로 내지 않고 문장·목록·표로 풀어 쓴다.
 * 저장값과 판정은 바꾸지 않으며, 읽을 수 없는 값은 원래 글자를 그대로 보인다.
 */

export type FieldView =
  | { kind: 'text'; text: string; notes?: string[] }
  | { kind: 'list'; items: string[]; notes?: string[] }
  | { kind: 'pairs'; rows: Array<[string, string]>; notes?: string[] }
  | { kind: 'table'; head: string[]; rows: string[][]; notes?: string[] }
  | { kind: 'hidden' }

/** 화면 표시용 항목 이름. 내부 검증 자료는 무엇을 확인한 값인지로 바꿔 부른다. */
const LABELS: Record<string, string> = {
  쪽표기자료: '쪽 번호 표기',
  독립쪽표기자료: '쪽 번호 표기',
  주소날짜검증자료: '주소 변동일자 표기',
  고지월검증자료: '고지 기간 확인',
  납부쪽표기자료: '납부확인서 쪽 번호',
  납부표완전성자료: '납부 내역 완전성',
  자격이력자료: '건강보험 자격 이력',
  일용근로선택자료: '일용근로 내역 선택 표시',
  일용근로내역자료: '일용근로 내역',
  월별보수외소득월액_건강: '월별 보수외소득월액(건강보험)',
  월별장기요양보험료: '월별 장기요양보험료',
  월별고지금액: '월별 고지금액',
  보험별가입여부: '보험별 가입 여부',
  보험별가입자종별: '보험별 가입자 종별',
  사업장명칭목록: '사업장 명칭',
  발급번호목록: '발급번호',
  생년월일후보: '생년월일 후보',
  가구원목록: '가구원',
  월별납부내역: '월별 고지·납부 내역',
  합계자료: '고지·납부 합계',
  추가첨부쪽: '추가로 첨부된 쪽',
  숫자형식교정: '숫자 표기 자동 교정',
  과거주소미포함의심: '과거 주소 미포함 의심',
  판독검증: '자동 판독 검증',
  판독경고: '판독 시 주의할 점',
  판독검증실패: '확인되지 않은 검증 항목',
  주소이력불확실사유: '주소 이력 불확실 사유',
  구성머리글불완전사유: '보험료 머리글 불완전 사유',
}

/**
 * 자동 판독 검증 이름(engine_v2 Validation.name) → 무엇을 확인하려 했는지.
 * 화면에는 "… 확인 안 됨"으로 붙여 보인다. 검증이 실패했다는 것은 내용이 틀렸거나
 * 읽지 못했다는 뜻이라, 어느 쪽인지 단정하지 않는 말로 쓴다.
 */
const CHECKS: Record<string, string> = {
  acquisition_before_loss: '자격취득일이 상실일보다 앞서는지',
  amount_found: '금액 판독',
  birth_consistent: '생년월일 표기 일치',
  brn_checksum: '사업자등록번호 검증 숫자',
  business_entity_consistent: '개인·법인 구분 일치',
  business_issue_location_unique: '발급 정보 위치',
  business_issue_not_future: '발급일이 미래 날짜가 아닌지',
  business_joint_section_read: '공동사업자 칸 판독',
  business_label_grid: '사업자등록증 항목 배치',
  business_number_checksum: '사업자등록번호 검증 숫자',
  business_number_format: '사업자등록번호 형식',
  business_registered_not_after_issue: '사업자등록일이 발급일 이전인지',
  business_single_page: '한 쪽짜리 서류인지',
  business_title: '사업자등록증 제목',
  company_found: '회사명 판독',
  company_names_match: '회사명 일치',
  daily_copy_pages_assigned: '사본별 쪽 구분',
  daily_document_type: '일용근로·노무제공내역서 서식',
  daily_insurance_copies_consistent: '사본 간 보험 구분 일치',
  daily_selection_copies_consistent: '사본 간 선택 표시 일치',
  daily_selection_readable: '선택 표시 판독',
  date_formats: '날짜 형식',
  dates_not_after_issue: '날짜가 발급일 이후가 아닌지',
  doc_no_consistent: '문서번호 일치',
  document_confirmation_number_consistent: '문서확인번호 일치',
  document_number_format: '문서번호 형식',
  document_type: '서류 종류',
  exam_date_found: '시험일 판독',
  exam_date_not_after_issue: '시험일이 발급일 이전인지',
  exam_date_not_future: '시험일이 미래 날짜가 아닌지',
  exam_name_found: '시험명 판독',
  form_recognized: '서식 인식',
  four_rows_in_order: '4대보험 네 줄의 순서',
  history_dates_ordered: '주소 이력 날짜 순서',
  history_dates_read: '자격 이력 날짜 판독',
  history_numbers_sequential: '주소 이력 순번 연속',
  history_tables_readable: '주소 이력 표 판독',
  household_rows_read: '가구원 표 판독',
  insurance_names_recognized: '보험 이름 인식',
  insurance_type_found: '보험 구분 판독',
  interview_date_found: '면접일 판독',
  interview_date_not_future: '면접일이 미래 날짜가 아닌지',
  interview_not_after_confirmation: '면접일이 확인일 이전인지',
  issue_date_consistent: '발급일 표기 일치',
  issue_date_not_future: '발급일이 미래 날짜가 아닌지',
  issue_not_future: '발급일이 미래 날짜가 아닌지',
  monthly_amounts_numeric: '월별 금액 숫자 판독',
  monthly_rows_found: '월별 내역 줄 판독',
  monthly_total_matches: '월별 금액의 합이 합계 줄과 같은지',
  months_continuous: '월이 빠짐없이 이어지는지',
  name_consistent: '성명 표기 일치',
  name_found: '성명 판독',
  nhis_blank_marker: '공란 표시 판독',
  nhis_current_loss_blank: '현재 자격의 상실일이 비어 있는지',
  nhis_document_number: '문서번호 판독',
  nhis_history_cells_read: '자격 이력 칸 판독',
  nhis_issue_location_unique: '발급 정보 위치',
  nhis_neighbor_dates_continuous: '앞뒤 자격 이력 날짜 연결',
  nhis_row_numbers_continuous: '이력 순번 연속',
  nhis_single_page: '한 쪽짜리 서류인지',
  not_cancelled: '취소 표시가 없는지',
  notice_number_read: '통보서 번호 판독',
  numeric_cell_corrections: '자동 교정한 숫자 칸의 금액 계산',
  occurred_before_reported: '주소 변동일이 신고일 이전인지',
  page_complete: '모든 쪽 제출',
  pages_complete: '모든 쪽 제출',
  page_marker_1_of_1: '쪽 번호 1/1 표기',
  page_names_match: '쪽마다 성명 일치',
  paid_total_matches: '월별 납부금액의 합이 납부총액과 같은지',
  payment_billing_absence_certain: '고지가 없는 달(0원·빈칸) 판독',
  payment_columns: '납부확인서 표의 열 구분',
  payment_component_headers: '보험료 항목 머리글',
  payment_date_found: '납부일 판독',
  payment_date_not_future: '납부일이 미래 날짜가 아닌지',
  payment_group_headers: '고지금액·납부금액 머리글',
  payment_information_cells: '납부자 정보 칸 판독',
  payment_purpose: '용도구분 판독',
  payment_query_period: '조회기간 판독',
  payment_single_page: '한 쪽짜리 서류인지',
  payment_sum_row: '합계 줄 판독',
  portal_row_cells: '가입내역 표 칸 판독',
  portal_table_columns: '가입내역 표의 열 구분',
  recent_five_years_covered: '최근 5년 이력 포함',
  row_names_match_header: '표의 성명이 상단 성명과 같은지',
  single_item: '품목이 1건인지',
  single_total: '합계가 1건인지',
  subscriber_matches_first_member: '가입자가 가구원 첫 줄과 같은지',
  supply_plus_vat_matches: '공급가액과 부가세의 합이 합계와 같은지',
}

/** 일용근로·노무제공내역서 사본별 검증 (daily_{번호}_…). */
const DAILY_CHECKS: Record<string, string> = {
  applicant_identity: '신청인 성명·생년월일',
  cell_confidence: '표 칸 글자 판독',
  confirmation: '발급 확인 정보',
  continuation: '이어지는 쪽 연결',
  issue_metadata: '발급번호·발급일',
  label_confidence: '항목 이름 판독',
  query_period: '조회기간 판독',
  rows_in_period: '근로 내역이 조회기간 안에 있는지',
  table_headers: '표 머리글',
  table_rows: '표 내역 줄',
}

const ADDRESS_UNCERTAIN: Record<string, string> = {
  NUMBER_GAP: '주소 이력 순번이 중간에 빠져 있음',
  NUMBER_UNREADABLE: '주소 이력 순번을 읽지 못함',
  EMPTY_PAGE: '이력 줄을 하나도 읽지 못한 쪽이 있음',
}
const COMPONENT_ISSUE: Record<string, string[]> = {
  FRAGMENT: ['보수외소득월액 머리글 글자 일부가 다르게 읽힘'],
  GAP: ['보수외소득월액 머리글 중간 줄을 읽지 못함'],
  BOTH: ['보수외소득월액 머리글 글자 일부가 다르게 읽힘', '보수외소득월액 머리글 중간 줄을 읽지 못함'],
}

/** 일반 풀이에서 영문 키가 나오면 한글로 바꾼다. 여기 없는 영문 키는 그대로 둔다. */
const KEY_LABELS: Record<string, string> = {
  status: '결과', period: '기간', periods: '기간', rows: '내역', month: '월', months: '월',
  total: '전체', selected: '선택', copies: '사본', category: '구분', acquired: '취득일', lost: '상실일',
  workplace: '사업장', days: '근로일수', wage: '임금', remuneration: '보수', worker_category: '근로자 구분',
  markers: '쪽 번호', page: '쪽', pages: '쪽', count: '건수', name: '성명', date: '일자', issue_date: '발급일',
  address: '주소', occurred: '발생일', reported: '신고일', reason: '사유', notes: '비고', no: '순번', sido: '시도',
  row: '행', column: '열', categories: '종류', insurance_types: '보험 구분',
}

/** 일반 풀이에서 상태 코드가 나오면 한글로 바꾼다. */
const STATUS_WORDS: Record<string, string> = {
  READABLE: '읽음', UNREADABLE: '읽지 못함', UNDETERMINED: '판단 불가', CONFLICT: '서로 다름',
  COMPLETE: '완전함', INCOMPLETE: '불완전', PARTIAL: '일부', ABSENT: '없음', MISSING: '없음', PRESENT: '있음',
  AMBIGUOUS: '불명확', NOT_REQUIRED: '필요 없음', UNCERTAIN: '불확실', REQUIRED: '필요',
  ZERO_CONFIRMED: '0원 확인', BLANK_CONFIRMED: '빈칸 확인', ZERO_UNCERTAIN: '0원 (불확실)', BLANK_UNCERTAIN: '빈칸 (불확실)',
}

/** 건강보험료 납부확인서 표의 네 항목 (nhis_payment_gov.COMPONENTS 순서). */
const PAYMENT_COMPONENTS = ['건강보험료', '장기요양보험료', '보수외소득월액(건강)', '보수외소득월액(요양)']

/** 담당자 판단에 쓰이지 않는 기술 정보. 화면에서 뺀다. */
const HIDDEN = new Set(['원본이미지크기'])

const UNKNOWN = '판단 불가 (원본 확인 필요)'

const ADDRESS_STATUS: Record<string, string> = {
  PRESENT: '주소 변동일자가 표기되어 있음',
  MISSING: '주소 변동일자 표기 없음',
  UNDETERMINED: UNKNOWN,
}
const PERIOD_STATUS: Record<string, string> = {
  READABLE: '고지 기간 확인됨',
  CONFLICT: '기간 표기가 서로 다름 (원본 확인 필요)',
  UNDETERMINED: UNKNOWN,
}
const PAGING_STATUS: Record<string, string> = {
  READABLE: '쪽 번호를 모두 읽음',
  UNREADABLE: '쪽 번호 일부를 읽지 못함',
  ABSENT: '쪽 번호 표기 없음',
  AMBIGUOUS: '쪽 번호가 서로 맞지 않음 (원본 확인 필요)',
  NOT_REQUIRED: '쪽 번호 확인 필요 없음',
}
const SELECTION_STATUS: Record<string, string> = {
  COMPLETE: '모든 근로 내역이 선택됨',
  PARTIAL: '일부 근로 내역만 선택됨',
  CONFLICT: '사본마다 선택 수가 다름 (원본 확인 필요)',
  UNREADABLE: '선택 표시를 읽지 못함',
  ABSENT: '선택 표시 없음',
}

export function fieldLabel(key: string): string {
  return LABELS[key] ?? key
}

type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
type Obj = { [key: string]: Json }

const isObj = (value: unknown): value is Obj => typeof value === 'object' && value !== null && !Array.isArray(value)
const isYm = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}$/.test(value)

/** "2025-10" → "2025년 10월" */
export function yearMonth(value: unknown): string {
  if (!isYm(value)) return value == null ? '–' : String(value)
  const [year, month] = value.split('-')
  return `${year}년 ${Number(month)}월`
}

function period(value: unknown): string | null {
  if (!Array.isArray(value) || value.length !== 2 || !value.every(isYm)) return null
  return value[0] === value[1] ? yearMonth(value[0]) : `${yearMonth(value[0])} ~ ${yearMonth(value[1])}`
}

function won(value: unknown): string {
  const number = typeof value === 'number' ? value : typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value.trim()) ? Number(value) : NaN
  return Number.isFinite(number) ? `${number.toLocaleString('ko-KR')}원` : value == null || value === '' ? '–' : String(value)
}

function status(map: Record<string, string>, value: unknown): string {
  if (typeof value !== 'string' || !value) return UNKNOWN
  return map[value] ?? `확인 필요 (${value})`
}

function yesNo(value: unknown, yes = '예', no = '아니오'): string {
  return value === true ? yes : value === false ? no : '판단 불가'
}

/** 화면에 낼 필요가 없는 내부 값(위치·신뢰도·버전·검증용 사본). */
const INTERNAL_KEYS = new Set(['bbox', 'bboxes', 'version', 'policy', 'marker_states', 'form_page_indices',
  'financial_fields', 'month_rows', 'digits', 'coverage_basis', 'period_label_present', 'explicit_year'])
const isInternalKey = (key: string) =>
  INTERNAL_KEYS.has(key) || key.includes('신뢰도') || /confidence/i.test(key)

const keyLabel = (key: string) => KEY_LABELS[key] ?? key

function plain(value: Json): string {
  if (value === null || value === '') return '–'
  if (typeof value === 'boolean') return yesNo(value)
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') return STATUS_WORDS[value] ?? value
  if (Array.isArray(value)) {
    const p = period(value)
    if (p) return p
    return value.length ? value.map(plain).join(', ') : '없음'
  }
  const parts = Object.entries(value).filter(([key]) => !isInternalKey(key)).map(([key, item]) => `${keyLabel(key)} ${plain(item)}`)
  return parts.length ? parts.join(' · ') : '–'
}

function markers(value: unknown): string | null {
  if (!Array.isArray(value) || !value.length) return null
  return value.map((marker) => Array.isArray(marker) && marker.length === 2 ? `${marker[0]}/${marker[1]}쪽` : '읽지 못함').join(', ')
}

function monthly(value: Json): FieldView | null {
  if (!isObj(value)) return null
  const months = Object.keys(value).filter(isYm).sort()
  if (!months.length) return { kind: 'text', text: '없음' }
  return { kind: 'table', head: ['월', '금액'], rows: months.map((month) => [yearMonth(month), won(value[month])]) }
}

/** 필드별 풀이. 모양이 예상과 다르면 null을 돌려 일반 풀이로 넘긴다. */
const SPECIFIC: Record<string, (value: Json) => FieldView | null> = {
  월별고지금액: monthly,
  월별장기요양보험료: monthly,
  월별보수외소득월액_건강: monthly,

  가입내역: (value) => {
    if (!Array.isArray(value) || !value.every(isObj)) return null
    if (!value.length) return { kind: 'text', text: '없음' }
    const rows = value as Obj[]
    return {
      kind: 'table',
      head: ['보험', '가입자 종별', '상태', '자격취득일', '사업장'],
      rows: rows.map((row) => [row['보험'], row['가입자종별'], row['상태'], row['자격취득일'], row['사업장명칭']].map((cell) => plain(cell ?? null))),
    }
  },

  보험별가입여부: (value) => isObj(value)
    ? { kind: 'pairs', rows: Object.entries(value).map(([name, joined]) => [name, yesNo(joined, '가입', '미가입')]) }
    : null,

  보험별가입자종별: (value) => isObj(value)
    ? { kind: 'pairs', rows: Object.entries(value).map(([name, kind]) => [name, plain(kind)]) }
    : null,

  조회기간: (value) => {
    const p = period(value)
    return p ? { kind: 'text', text: p } : null
  },

  쪽표기자료: (value) => {
    if (!isObj(value)) return null
    const text = markers(value.markers)
    return { kind: 'text', text: text ?? '쪽 번호를 읽지 못함' }
  },

  주소날짜검증자료: (value) => isObj(value) ? { kind: 'text', text: status(ADDRESS_STATUS, value.status) } : null,

  고지월검증자료: (value) => {
    if (!isObj(value)) return null
    const periods = Array.isArray(value.periods) ? value.periods.map(period).filter((p): p is string => !!p) : []
    const rows: Array<[string, string]> = [['결과', status(PERIOD_STATUS, value.status)]]
    rows.push(['고지 기간', periods.length ? [...new Set(periods)].join(', ') : period(value.period) ?? '읽지 못함'])
    return { kind: 'pairs', rows }
  },

  납부쪽표기자료: (value) => {
    if (!isObj(value)) return null
    const rows: Array<[string, string]> = [['결과', status(PAGING_STATUS, value.status)]]
    const text = markers(value.markers)
    if (text) rows.push(['읽은 쪽 번호', text])
    if (typeof value.uploaded_page_count === 'number') rows.push(['제출한 쪽수', `${value.uploaded_page_count}쪽`])
    if (typeof value.expected_total === 'number') rows.push(['서류 전체 쪽수', `${value.expected_total}쪽`])
    return { kind: 'pairs', rows }
  },

  납부표완전성자료: (value) => {
    if (!isObj(value)) return null
    const months = Array.isArray(value.months) ? value.months.filter(isYm) : []
    return {
      kind: 'pairs',
      rows: [
        ['조회 기간', period(value.period) ?? '읽지 못함'],
        ['표에 있는 월', months.length ? `${months.length}개월 (${yearMonth(months[0])} ~ ${yearMonth(months[months.length - 1])})` : '읽지 못함'],
        ['합계 표기 확인', yesNo(value.printed_total_observed)],
        ['금액 계산 일치', yesNo(value.arithmetic_complete)],
        ['발급 정보 판독', yesNo(value.issue_information_read)],
      ],
    }
  },

  자격이력자료: (value) => {
    if (!isObj(value) || !Array.isArray(value.rows)) return null
    const covered = value.recent_five_years_covered
    const years = typeof value.coverage_years === 'number' ? value.coverage_years : 5
    const notes = [`최근 ${years}년 이력 포함: ${yesNo(covered, '포함', '미포함')}`]
    const p = period(value.period)
    if (p) notes.unshift(`조회 기간: ${p}`)
    const rows = value.rows.filter(isObj)
    if (!rows.length) return { kind: 'text', text: '읽은 자격 이력 없음', notes }
    return {
      kind: 'table', head: ['구분', '취득일', '상실일'],
      rows: rows.map((row) => [plain(row.category ?? null), plain(row.acquired ?? null), row.lost ? plain(row.lost) : '유지 중']),
      notes,
    }
  },

  일용근로선택자료: (value) => {
    if (!isObj(value)) return null
    const rows: Array<[string, string]> = [['결과', status(SELECTION_STATUS, value.status)]]
    if (Array.isArray(value.copies)) value.copies.filter(isObj).forEach((copy, index, all) => {
      const label = all.length > 1 ? `사본 ${index + 1}` : '선택 수'
      rows.push([label, typeof copy.total === 'number' && typeof copy.selected === 'number'
        ? `${copy.total}건 중 ${copy.selected}건 선택` : '읽지 못함'])
    })
    if (Array.isArray(value.copies) && value.copies.length > 1) rows.push(['사본 내용 일치', yesNo(value.copies_consistent)])
    return { kind: 'pairs', rows }
  },

  일용근로내역자료: (value) => {
    if (!isObj(value) || !Array.isArray(value.rows)) return null
    const notes: string[] = []
    const p = period(value.period)
    if (p) notes.push(`조회 기간: ${p}`)
    const rows = value.rows.filter(isObj)
    if (!rows.length) return { kind: 'text', text: '읽은 근로 내역 없음', notes }
    const sorted = [...rows].sort((a, b) => String(a.month ?? '').localeCompare(String(b.month ?? '')))
    return {
      kind: 'table', head: ['월', '사업장', '근로일수', '임금'],
      rows: sorted.map((row) => [yearMonth(row.month), plain(row.workplace ?? null),
        typeof row.days === 'number' ? `${row.days}일` : '–', won(row.wage)]),
      notes,
    }
  },
}
SPECIFIC['독립쪽표기자료'] = SPECIFIC['쪽표기자료']

SPECIFIC['가구원목록'] = (value) => {
  if (!Array.isArray(value) || !value.every(isObj)) return null
  if (!value.length) return { kind: 'text', text: '없음' }
  const rows = value as Obj[]
  const columns = ['성명', '생년월일', '자격취득일', '자격상실일'].filter((key) => rows.some((row) => key in row))
  return {
    kind: 'table', head: columns,
    rows: rows.map((row) => columns.map((key) => key === '자격상실일' && !row[key] ? '유지 중' : plain(row[key] ?? null))),
    notes: [`총 ${rows.length}명`],
  }
}

SPECIFIC['월별납부내역'] = (value) => {
  if (!Array.isArray(value) || !value.every(isObj)) return null
  if (!value.length) return { kind: 'text', text: '없음' }
  const rows = (value as Obj[]).filter((row) => isObj(row['고지']) || isObj(row['납부']))
  if (!rows.length) return null
  const used = PAYMENT_COMPONENTS.filter((name) => rows.some((row) =>
    [row['고지'], row['납부']].some((part) => isObj(part) && part[name] != null && part[name] !== '0')))
  const columns = used.length ? used : PAYMENT_COMPONENTS.slice(0, 1)
  const cell = (part: Json | undefined, name: string) => isObj(part) && part[name] != null ? won(part[name]) : '–'
  return {
    kind: 'table', head: ['월', ...columns.map((name) => `${name} (고지 / 납부)`)],
    rows: rows.map((row) => [yearMonth(row['월']), ...columns.map((name) => `${cell(row['고지'], name)} / ${cell(row['납부'], name)}`)]),
    notes: used.length < PAYMENT_COMPONENTS.length ? ['모든 달이 0원인 항목은 생략했습니다.'] : undefined,
  }
}

SPECIFIC['합계자료'] = (value) => {
  if (!Array.isArray(value) || value.length !== 8) return null
  return {
    kind: 'table', head: ['항목', '고지 합계', '납부 합계'],
    rows: PAYMENT_COMPONENTS.map((name, index) => [name, won(value[index]), won(value[index + 4])]),
  }
}

SPECIFIC['추가첨부쪽'] = (value) => {
  if (!Array.isArray(value)) return null
  return { kind: 'text', text: value.length ? `${value.map((page) => `${plain(page)}쪽`).join(', ')} (본 서류 표와 별개인 쪽)` : '없음' }
}

SPECIFIC['숫자형식교정'] = (value) => {
  if (!Array.isArray(value)) return null
  if (!value.length) return { kind: 'text', text: '교정 없음' }
  const where = value.filter(isObj).map((item) => [item.row, item.column].filter((part) => part != null && part !== '').map(plain).join(' · '))
  return { kind: 'text', text: `숫자 ${value.length}곳의 표기를 자동으로 교정했습니다. 원본과 대조해 주세요.`,
    notes: where.filter(Boolean).length ? where.filter(Boolean) : undefined }
}

/** 검증 이름 하나 → "… 확인 안 됨". 모르는 영문 이름이면 null. */
export function checkPhrase(name: string): string | null {
  const known = CHECKS[name]
  if (known) return `${known} 확인 안 됨`
  let match = /^(.+)_required$/.exec(name)
  if (match) return `필수 항목을 읽지 못함: ${fieldLabel(match[1])}`
  match = /^(.+)_consistent$/.exec(name)
  if (match && !/^[a-z_]+$/.test(match[1])) return `${fieldLabel(match[1])} 표기 일치 확인 안 됨`
  match = /^daily_(\d+)_(.+)$/.exec(name)
  if (match && DAILY_CHECKS[match[2]]) return `사본 ${match[1]}: ${DAILY_CHECKS[match[2]]} 확인 안 됨`
  match = /^business_(.+)_read$/.exec(name)
  if (match && !/^[a-z_]+$/.test(match[1])) return `사업자등록증 ${match[1]} 칸 판독 확인 안 됨`
  match = /^payment_column_(\d)_sum$/.exec(name)
  if (match) {
    const column = Number(match[1])
    const component = PAYMENT_COMPONENTS[(column - 1) % 4]
    if (component && column <= 8) return `${column <= 4 ? '고지' : '납부'} ${component} 열 합계 확인 안 됨`
  }
  return /[a-zA-Z]/.test(name) ? null : name
}

/** 쉼표로 이은 코드 목록을 한글 문장 목록으로. 모르는 영문 코드는 건수로만 알린다. */
function codeList(raw: string, translate: (code: string) => string[] | string | null, unknownLabel: string): FieldView {
  const codes = raw.split(',').map((code) => code.trim()).filter(Boolean)
  const items: string[] = []
  let unknown = 0
  for (const code of codes) {
    const phrase = translate(code)
    if (phrase === null) unknown++
    else items.push(...(Array.isArray(phrase) ? phrase : [phrase]))
  }
  const unique = [...new Set(items)]
  if (unknown) unique.push(`${unknownLabel} ${unknown}건`)
  return unique.length ? { kind: 'list', items: unique } : { kind: 'text', text: '없음' }
}

/** 문장에 섞인 영문 사유 코드(예: REQUIRED_FIELD_UNREADABLE). 백엔드 officer_summary._CODE_TOKEN과 같다. */
const CODE_TOKEN = /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g

/** 화면에 내기 전 마지막 안전망: 문장에 남은 영문 코드를 지우고 빈 괄호를 정리한다. */
export function plainText(text: string | null | undefined): string {
  return (text ?? '')
    .replace(CODE_TOKEN, '')
    .replace(/\(\s*[,·:]?\s*\)/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

/** 사유 제목. 백엔드가 붙인 한글 title만 쓰고, 코드는 절대 보이지 않는다. */
export function reasonTitle(item: { code?: string | null; title?: string | null }): string | null {
  const title = plainText(item.title)
  return title && title !== item.code ? title : null
}

/** 판독경고: 엔진 경고 문장을 공백으로 이어 저장한다. 문장별 목록으로 나누고 겹치는 문장은 뺀다. */
function warningList(raw: string): FieldView {
  const sentences = plainText(raw)
    .split(/(?<=[.다])\s+(?=\S)/)
    .map((sentence) => sentence.trim())
    .filter(Boolean)
  const unique = [...new Set(sentences)]
  if (!unique.length) return { kind: 'text', text: '없음' }
  return unique.length === 1 ? { kind: 'text', text: unique[0] } : { kind: 'list', items: unique }
}

/** JSON이 아닌, 쉼표로 이은 영문 코드 칸. */
const CODE_FIELDS: Record<string, (raw: string) => FieldView> = {
  판독경고: warningList,
  판독검증실패: (raw) => codeList(raw, checkPhrase, '그 밖의 자동 검증 확인 안 됨:'),
  주소이력불확실사유: (raw) => codeList(raw, (code) => ADDRESS_UNCERTAIN[code] ?? (/[a-zA-Z]/.test(code) ? null : code), '그 밖의 사유'),
  구성머리글불완전사유: (raw) => codeList(raw, (code) => COMPONENT_ISSUE[code] ?? (/[a-zA-Z]/.test(code) ? null : code), '그 밖의 사유'),
}

/** 모양만 보고 푸는 일반 풀이. */
function generic(value: Json): FieldView {
  if (Array.isArray(value)) {
    const p = period(value)
    if (p) return { kind: 'text', text: p }
    if (!value.length) return { kind: 'text', text: '없음' }
    if (value.every(isObj)) {
      const rows = value as Obj[]
      const head = [...new Set(rows.flatMap((row) => Object.keys(row)))].filter((key) => !isInternalKey(key))
      return { kind: 'table', head: head.map(keyLabel), rows: rows.map((row) => head.map((key) => plain(row[key] ?? null))) }
    }
    return { kind: 'list', items: value.map(plain) }
  }
  if (isObj(value)) {
    const rows = Object.entries(value).filter(([key]) => !isInternalKey(key)).map(([key, item]): [string, string] => [keyLabel(key), plain(item)])
    return rows.length ? { kind: 'pairs', rows } : { kind: 'text', text: '없음' }
  }
  return { kind: 'text', text: plain(value) }
}

export function formatField(key: string, raw: unknown): FieldView {
  if (HIDDEN.has(key)) return { kind: 'hidden' }
  if (raw === null || raw === undefined || raw === '') return { kind: 'text', text: '읽은 값 없음' }
  let value: Json
  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    if (trimmed === 'true' || trimmed === 'false') return { kind: 'text', text: yesNo(trimmed === 'true') }
    if (CODE_FIELDS[key]) return CODE_FIELDS[key](trimmed)
    if (!/^[[{]/.test(trimmed)) return { kind: 'text', text: raw }
    try { value = JSON.parse(trimmed) as Json } catch { return { kind: 'text', text: raw } }
  } else {
    value = raw as Json
  }
  try {
    return SPECIFIC[key]?.(value) ?? generic(value)
  } catch {
    return generic(value)
  }
}
