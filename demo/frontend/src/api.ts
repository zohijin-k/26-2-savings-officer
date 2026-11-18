import { mockBulkDecision, mockDecision, mockOfficerList, mockOfficerSummary, mockReviewDetail, mockRoles } from './pages/officer/mock-data.ts'

export type DocStatus = 'PASS' | 'FAIL' | 'NEEDS_REVIEW'
export type DecisionKey = 'approve' | 'reject' | 'hold'
export type RoleKey = 'town' | 'city' | 'province'
export const ROLE_KEYS: RoleKey[] = ['town', 'city', 'province']
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
  stage?: string
  scope?: string
  requires_region?: boolean
  requires_town?: boolean
  can_bulk?: boolean
  notes?: string[]
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
  region?: string
  town?: string
  ai_status?: DocStatus | null
  ai_status_label?: string
  total_score?: number | null
  max_total?: number | null
  missing_count?: number
  submitted_at?: string | null
  decision?: DecisionKey | null
  decision_label?: string
  rank?: number | null
  documents?: OfficerRowDoc[]
}
export interface OfficerScope {
  region: string
  town: string
  region_locked: boolean
  town_locked: boolean
  regions: string[]
  towns: string[]
}
export interface OfficerList {
  role?: OfficerRole
  scope?: OfficerScope
  rows: OfficerRow[]
  page: number
  page_count: number
  total: number
}
/** 목록을 부를 때의 역할과 관할. 역할이 시군·읍면동을 요구할 때만 region·town을 쓴다. */
export interface OfficerListQuery { role: RoleKey; region?: string; town?: string }
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

/** 최종 판정 패널 맨 위의 AI 종합의견. 저장된 판정을 풀어 쓴 참고 문구이며 판정을 바꾸지 않는다. */
/** 근거 한 건. 화면에는 코드 대신 label(담당자 문구)과 kind_label(규칙 판정·자동 대조 등)을 보인다. */
export interface SummaryEvidence {
  code: string
  label: string
  kind: 'rule' | 'auto' | 'eligibility' | 'score' | string
  kind_label: string
}
export interface SummaryCheckPoint {
  slot_key: string | null
  title: string
  detail: string
  /** 근거 코드. 서버가 입력에 있던 코드만 남긴다. 화면에는 evidence를 쓴다. */
  codes: string[]
  evidence: SummaryEvidence[]
  /** 원본에서 강조할 판독 항목(문서 bboxes의 키). 위치가 없으면 null. */
  field: string | null
}
export interface OfficerSummary {
  headline: string
  status_explanation: string
  check_points: SummaryCheckPoint[]
  document_notes: { slot_key: string; note: string }[]
  score_note: string
  /** jbai = 전북AI 생성, rules = 제공자 꺼짐·실패 시 규칙 기반 대체 요약 */
  source: 'jbai' | 'rules' | string
  label: string
  model: string | null
  generated_at: string
  cached: boolean
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
export const fetchOfficerRoles = (): Promise<OfficerRole[]> => isOfficerMockActive()
  ? Promise.resolve(mockRoles())
  : json('/api/officer/roles')
export const fetchOfficerList = (query: OfficerListQuery, page: number): Promise<OfficerList> => {
  if (isOfficerMockActive()) return Promise.resolve(mockOfficerList(query, page))
  const params = new URLSearchParams({ role: query.role, program: 'double_savings', page_size: '200', page: String(page) })
  if (query.region) params.set('region', query.region)
  if (query.town) params.set('town', query.town)
  return json(`/api/officer/applications?${params}`)
}
export const fetchReviewDetail = async (id: number, role: RoleKey = 'province'): Promise<ReviewDetailData> => isOfficerMockActive()
  ? Promise.resolve(mockReviewDetail(id, role))
  : json(`/api/officer/applications/${id}?role=${role}`)
export const fetchOfficerSummary = (id: number, role: RoleKey = 'province'): Promise<OfficerSummary> => isOfficerMockActive()
  ? Promise.resolve(mockOfficerSummary(id))
  : json(`/api/officer/applications/${id}/summary?role=${role}`)
export const regenerateOfficerSummary = (id: number, role: RoleKey = 'province'): Promise<OfficerSummary> => isOfficerMockActive()
  ? Promise.resolve(mockOfficerSummary(id))
  : json(`/api/officer/applications/${id}/summary?role=${role}`, { method: 'POST' })
export const postDecision = (id: number, decision: DecisionKey, memo: string, role: RoleKey = 'province'): Promise<unknown> => isOfficerMockActive()
  ? Promise.resolve(mockDecision(id, decision, memo, role))
  : json(`/api/officer/applications/${id}/decision`, {
    method: 'POST', body: JSON.stringify({ role, decision, memo }),
  })
export const postBulkDecision = (ids: number[], decision: DecisionKey, memo: string, role: RoleKey): Promise<{ processed: number }> => isOfficerMockActive()
  ? Promise.resolve(mockBulkDecision(ids, decision, memo, role))
  : json('/api/officer/applications/decisions', {
    method: 'POST', body: JSON.stringify({ role, decision, memo, application_ids: ids }),
  })
