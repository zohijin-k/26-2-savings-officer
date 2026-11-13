import { mockOfficerList, mockReviewDetail, mockDecision } from './pages/officer/mock-data.ts'

export type DocStatus = 'PASS' | 'FAIL' | 'NEEDS_REVIEW'
export type DecisionKey = 'approve' | 'reject' | 'hold'
export interface Finding {
  code: string
  message: string
  how_to_fix: string
  link: string
  severity: 'FAIL' | 'NEEDS_REVIEW'
}
export interface BBox { page: number; x0: number; y0: number; x1: number; y1: number }
export interface OfficerRole {
  key: string
  name: string
  actions: { key: DecisionKey; label: string; result_label: string; tone: string }[]
}
export interface OfficerRowDoc {
  column: string
  slot_key: string
  label: string
  short_label: string
  status: DocStatus | null
  status_label: string
  document_id: number | null
  required: boolean
}
export interface OfficerRow {
  application_id: number
  application_no: string
  name: string
  program_code: string
  documents?: OfficerRowDoc[]
}
export interface OfficerList { rows: OfficerRow[]; page: number; page_count: number; total: number }
export interface ScoreItemRow {
  key: string
  label: string
  score: number
  max_score: number
  band: string
  basis: string
  source_doc: string | null
  source_document_id: number | null
  source_origin: string
  bbox: BBox | null
  incomplete: boolean
  source_slot_key: string | null
  source_file_url: string | null
  source_file_format: string | null
}

export interface ScoreSheetData {
  items: ScoreItemRow[]
  total: number
  max_total: number
  income_percent: number | null
  income_over_limit: boolean
  incomplete: boolean
  tiebreak: number[]
  notes: string[]
}

export interface OfficerDocument {
  document_id: number
  slot_key: string
  label: string
  expected_doc_type: string | null
  detected_doc_type: string | null
  status: DocStatus | null
  findings: Finding[]
  /** 인라인 스트리밍 주소. 뷰어가 이 URL을 그대로 읽는다. */
  file_url: string
  file_name: string
  file_format: string
  page_index: number | null
  extracted: Record<string, string>
  bboxes: Record<string, BBox>
  ocr_confidence: number | null
  ocr_tier: string | null
  /** 실제로 글자를 읽은 엔진 (jbai·applevision·pdftext 등). 담당자 화면 전용 */
  ocr_engine: string | null
  /** 앞 엔진이 실패해 다른 엔진으로 대체한 사유 (예: 전북AI 응답 시간 초과) */
  ocr_fallback_reason: string | null
  /** 판독을 유지한 경우 담당자가 참고할 품질 메모 */
  ocr_quality_note: string | null
  declared_issue_date: string | null
  uploaded_at: string
}


export interface ReviewDetailData {
  application_id: number
  application_no: string
  name: string
  program_code: string
  region: string
  town: string
  ai: {
    final_status: DocStatus | null
    recommended_action: string
    reasons: { code: string; message: string; doc_type: string | null }[]
  }
  score_sheet: ScoreSheetData
  documents: OfficerDocument[]
  decision: { decision: DecisionKey | null; label: string; memo: string | null }
  role: OfficerRole
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) throw new Error(`요청을 처리하지 못했습니다 (${response.status})`)
  return response.json() as Promise<T>
}

// 목업은 명시한 미리보기에서만 사용한다. 빈 DB와 서버 오류는 그대로 표시한다.
export const isOfficerMockActive = () => new URLSearchParams(window.location.search).get('mock') === '1'
export const fetchOfficerList = (page: number): Promise<OfficerList> => isOfficerMockActive()
  ? Promise.resolve(mockOfficerList(page))
  : json(`/api/officer/applications?role=province&program=double_savings&page_size=200&page=${page}`)
export const fetchReviewDetail = async (id: number): Promise<ReviewDetailData> => isOfficerMockActive()
  ? Promise.resolve(mockReviewDetail(id))
  : json(`/api/officer/applications/${id}?role=province`)
export const postDecision = (id: number, decision: DecisionKey, memo: string): Promise<unknown> => isOfficerMockActive()
  ? Promise.resolve(mockDecision(id, decision, memo))
  : json(`/api/officer/applications/${id}/decision`, {
    method: 'POST', body: JSON.stringify({ role: 'province', decision, memo }),
  })
