/** 두배적금 화면을 위한 명시적 합성 미리보기. */
import type { DecisionKey, OfficerDocument, OfficerList, OfficerRole, OfficerRow, ReviewDetailData } from '../../api.ts'

const ROLE: OfficerRole = {
  key: 'province', name: '도·청년허브센터',
  actions: [
    { key: 'approve', label: '최종 선정', result_label: '최종 선정', tone: 'primary' },
    { key: 'reject', label: '반려', result_label: '반려', tone: 'danger' },
    { key: 'hold', label: '보류', result_label: '보류', tone: 'neutral' },
  ],
}
function document(id: number, review: boolean): OfficerDocument {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="595" height="842"><rect width="595" height="842" fill="white"/><g font-family="sans-serif" fill="#243852"><text x="50" y="80" font-size="24">합성 시연 원본</text><text x="50" y="130" font-size="18">주민등록초본</text><text x="50" y="200" font-size="16">성명: 가상신청${id}</text><text x="50" y="260" font-size="14">실제 인물·기관 발급 서류가 아닙니다.</text></g></svg>`
  return {
    document_id: id * 10, slot_key: 'resident_abstract', label: '주민등록초본',
    expected_doc_type: '주민등록초본', detected_doc_type: '주민등록초본',
    status: review ? 'NEEDS_REVIEW' : 'PASS',
    findings: review ? [{ code: 'LOW_CONFIDENCE', message: '판독 신뢰도가 낮아 담당자 확인이 필요합니다.', how_to_fix: '원본 서류를 확인해 주세요.', link: '', severity: 'NEEDS_REVIEW' }] : [],
    file_url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`, file_name: '합성_주민등록초본.svg', file_format: 'svg', page_index: null,
    extracted: { 성명: `가상신청${id}` }, bboxes: {}, ocr_confidence: review ? .6 : .98,
    ocr_tier: 'synthetic', ocr_engine: 'synthetic', ocr_fallback_reason: null, ocr_quality_note: null,
    declared_issue_date: '2026-03-05', uploaded_at: '2026-03-06T09:00:00',
  }
}
const details = new Map<number, ReviewDetailData>([1, 2].map((index) => {
  const id = 900000 + index
  const doc = document(id, index === 2)
  return [id, {
    application_id: id, application_no: `SYNTHETIC-${index}`, name: `가상신청${id}`, program_code: 'double_savings',
    region: '전주시', town: '가상동',
    ai: { final_status: doc.status, recommended_action: index === 2 ? '담당자 원본 확인' : '서류 적합', reasons: [] },
    score_sheet: { items: [], total: 0, max_total: 100, income_percent: null, income_over_limit: false, incomplete: false, tiebreak: [], notes: [] },
    documents: [doc], decision: { decision: null, label: '미처리', memo: null }, role: ROLE,
  }]
}))
export function mockOfficerList(page: number): OfficerList {
  const rows: OfficerRow[] = [...details.values()].map((detail) => ({
    application_id: detail.application_id, application_no: detail.application_no, name: detail.name, program_code: detail.program_code,
    documents: detail.documents.map((doc) => ({ column: doc.slot_key, slot_key: doc.slot_key, label: doc.label, short_label: '', status: doc.status, status_label: doc.status === 'PASS' ? '적합' : '확인필요', document_id: doc.document_id, required: true })),
  }))
  return { rows: page === 1 ? rows : [], page, page_count: 1, total: rows.length }
}
export function mockReviewDetail(id: number): ReviewDetailData {
  const detail = details.get(id)
  if (!detail) throw new Error('해당 합성 신청이 없습니다.')
  return detail
}
export function mockDecision(id: number, decision: DecisionKey, memo: string): void {
  const detail = mockReviewDetail(id)
  detail.decision = { decision, memo, label: ROLE.actions.find((action) => action.key === decision)?.result_label ?? decision }
}
