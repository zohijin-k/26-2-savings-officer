import type { OfficerDocument, OfficerList, OfficerRow } from '../../api.ts'

/** 신청 목록의 탭. 저장값을 바꾸지 않고 화면 분류만 만든다. */
export type Queue = 'needs_review' | 'pass' | 'done' | 'rejected'

export const QUEUES: { key: Queue; label: string; empty: string }[] = [
  { key: 'needs_review', label: '확인 필요', empty: '확인이 필요한 신청이 없습니다.' },
  { key: 'pass', label: '적합', empty: '적합으로 판정된 미처리 신청이 없습니다.' },
  { key: 'done', label: '처리 완료', empty: '처리를 마친 신청이 없습니다.' },
  { key: 'rejected', label: '반려', empty: '반려한 신청이 없습니다.' },
]

export type SortKey = 'importance' | 'latest' | 'oldest'

export const SORTS: { key: SortKey; label: string }[] = [
  { key: 'importance', label: '중요도순' },
  { key: 'latest', label: '최신순' },
  { key: 'oldest', label: '등록순' },
]

export interface ListFilters {
  search: string
  /** YYYY-MM-DD. 빈 문자열이면 조건 없음. */
  from: string
  to: string
}

export const EMPTY_FILTERS: ListFilters = { search: '', from: '', to: '' }

/**
 * 담당자가 반려한 건은 반려 탭, 그 밖의 판단(선정·완비 확인·보류)이 있으면 처리 완료다.
 * 판단이 없으면 AI 판정이 적합인 건만 적합 탭에, 나머지(확인필요·부적합·미심사)는
 * 확인 필요 탭에 둔다.
 */
export function queueOf(row: OfficerRow): Queue {
  if (row.decision === 'reject') return 'rejected'
  if (row.decision) return 'done'
  return row.ai_status === 'PASS' ? 'pass' : 'needs_review'
}

/** 검색어(신청번호·성명)와 접수일 범위. 탭과 무관한 조건만 거른다. */
export function matchesFilters(row: OfficerRow, filters: ListFilters): boolean {
  const keyword = filters.search.trim().toLowerCase()
  if (keyword && !`${row.application_no} ${row.name}`.toLowerCase().includes(keyword)) return false
  const day = row.submitted_at?.slice(0, 10) ?? ''
  if (filters.from && (!day || day < filters.from)) return false
  if (filters.to && (!day || day > filters.to)) return false
  return true
}

export function queueCounts(rows: OfficerRow[]): Record<Queue, number> {
  const counts: Record<Queue, number> = { needs_review: 0, pass: 0, done: 0, rejected: 0 }
  for (const row of rows) counts[queueOf(row)] += 1
  return counts
}

/**
 * 중요도 = 담당자가 확인해야 할 서류 수. 적합이 아닌 원본(확인필요·부적합)과
 * 제출되지 않은 필수 서류를 센다. 저장된 판정은 읽기만 한다.
 */
export function importanceOf(row: OfficerRow): number {
  return (row.documents ?? []).filter((doc) => doc.status !== 'PASS' && (doc.document_id !== null || doc.required)).length
}

/**
 * 중요도순: 확인할 서류가 많은 건이 위, 같으면 먼저 접수한 건이 위.
 * 최신순·등록순: 접수일시 기준. 접수일시가 없는 건은 항상 맨 아래.
 * 원래 배열은 바꾸지 않는다.
 */
export function sortRows(rows: OfficerRow[], sort: SortKey): OfficerRow[] {
  const time = (row: OfficerRow) => row.submitted_at ?? ''
  const byTime = (a: OfficerRow, b: OfficerRow, direction: 1 | -1) => {
    if (!time(a) || !time(b)) return time(a) ? -1 : time(b) ? 1 : 0
    return time(a) < time(b) ? -direction : time(a) > time(b) ? direction : 0
  }
  return [...rows].sort((a, b) => {
    if (sort === 'latest') return byTime(a, b, -1)
    if (sort === 'oldest') return byTime(a, b, 1)
    return importanceOf(b) - importanceOf(a) || byTime(a, b, 1)
  })
}

/** 목록에서 행을 열 때 먼저 보여 줄 서류: 적합이 아닌 첫 원본, 없으면 첫 원본. */
export function firstDocument(row: OfficerRow): { documentId: number; slotKey: string } | null {
  const docs = (row.documents ?? []).filter((doc) => doc.document_id !== null)
  const pick = docs.find((doc) => doc.status !== 'PASS') ?? docs[0]
  return pick && pick.document_id !== null ? { documentId: pick.document_id, slotKey: pick.slot_key } : null
}

/** 신청 건 API의 모든 페이지를 모은다. 역할·관할 정보는 첫 페이지 값을 쓴다. */
export async function collectOfficerList(loadPage: (page: number) => Promise<OfficerList>): Promise<OfficerList> {
  const first = await loadPage(1)
  const rows = [...first.rows]
  for (let page = 2; page <= first.page_count; page += 1) {
    rows.push(...(await loadPage(page)).rows)
  }
  return { ...first, rows, page: 1, page_count: 1, total: rows.length }
}

/** 슬롯이 같은 미배정 페이지는 ID로 구별한다. 없는 항목을 다른 원본으로 대체하지 않는다. */
export function selectOfficerDocument(documents: OfficerDocument[], documentId: number | null, slotKey: string | null) {
  if (documentId !== null) return documents.find((doc) => doc.document_id === documentId) ?? null
  if (slotKey !== null) return documents.find((doc) => doc.slot_key === slotKey) ?? null
  return null
}
