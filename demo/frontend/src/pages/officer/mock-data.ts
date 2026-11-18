/** 두배적금 화면을 위한 명시적 합성 미리보기. 실제 인물·기관 서류가 아니다. */
import type {
  DecisionKey, DocStatus, OfficerDocument, OfficerList, OfficerListQuery, OfficerRole, OfficerRow,
  OfficerSummary, ReviewDetailData, RoleKey, ScoreItemRow, ScoreSheetData,
} from '../../api.ts'

const HOLD = { key: 'hold', label: '보류', result_label: '보류', tone: 'neutral' } as const
const REJECT = { key: 'reject', label: '반려', result_label: '반려', tone: 'danger' } as const

/** 백엔드 rules/roles.py와 같은 값. */
const ROLES: Record<RoleKey, OfficerRole> = {
  town: {
    key: 'town', name: '읍·면·동', stage: '선발절차 2·3·4단계', scope: '관할 읍·면·동 접수 건',
    requires_region: true, requires_town: true, can_bulk: false,
    notes: ['구비서류 완비 여부(서명·직인 포함)를 건별로 확인합니다.', '건별 확인이 원칙이라 일괄 처리는 제공하지 않습니다.'],
    actions: [{ key: 'approve', label: '구비서류 완비 확인', result_label: '서류 완비 확인', tone: 'primary' }, HOLD, REJECT],
  },
  city: {
    key: 'city', name: '시군', stage: '선발절차 1·5단계', scope: '관할 시군 전체',
    requires_region: true, requires_town: false, can_bulk: true,
    notes: ['읍·면·동이 작성한 심사표를 취합·검토합니다.', '고득점순으로 배정인원의 120%를 선발해 도에 공문으로 제출합니다.'],
    actions: [{ key: 'approve', label: '1차 선발 (배정인원 120%)', result_label: '1차 선발', tone: 'primary' }, HOLD, REJECT],
  },
  province: {
    key: 'province', name: '도·청년허브센터', stage: '선발절차 6단계', scope: '14개 시군 전체',
    requires_region: false, requires_town: false, can_bulk: true,
    notes: ['2차 검증(중복 조회) 후 고득점순으로 100%를 최종 선정·공고합니다.'],
    actions: [{ key: 'approve', label: '최종 선정 (100%)', result_label: '최종 선정', tone: 'primary' }, HOLD, REJECT],
  },
}
const REGIONS = ['전주시', '군산시', '익산시', '정읍시', '남원시', '김제시', '완주군', '진안군', '무주군', '장수군', '임실군', '순창군', '고창군', '부안군']

interface Seed {
  name: string
  region: string
  town: string
  submitted: string
  /** 초본 · 건보료 납부확인서 · 근로확인서류 판정. null이면 미제출. */
  docs: [DocStatus | null, DocStatus | null, DocStatus | null]
  scores: [number, number, number, number]
}
const SEEDS: Seed[] = [
  { name: '김하늘', region: '전주시', town: '효자동', submitted: '2026-03-03T09:12:00', docs: ['PASS', 'PASS', 'PASS'], scores: [40, 25, 22, 9] },
  { name: '이도윤', region: '전주시', town: '효자동', submitted: '2026-03-03T10:40:00', docs: ['NEEDS_REVIEW', 'PASS', 'PASS'], scores: [37, 23, 19, 9] },
  { name: '박서연', region: '전주시', town: '송천동', submitted: '2026-03-04T13:05:00', docs: ['FAIL', 'PASS', 'NEEDS_REVIEW'], scores: [34, 21, 16, 10] },
  { name: '최지우', region: '전주시', town: '송천동', submitted: '2026-03-05T08:55:00', docs: ['PASS', 'PASS', 'PASS'], scores: [37, 25, 25, 8] },
  { name: '정민준', region: '전주시', town: '인후동', submitted: '2026-03-06T16:20:00', docs: ['PASS', null, 'PASS'], scores: [31, 19, 19, 9] },
  { name: '강예린', region: '군산시', town: '나운동', submitted: '2026-03-04T11:30:00', docs: ['PASS', 'PASS', 'PASS'], scores: [40, 21, 19, 10] },
  { name: '조현우', region: '군산시', town: '나운동', submitted: '2026-03-07T09:48:00', docs: ['PASS', 'NEEDS_REVIEW', 'PASS'], scores: [34, 17, 22, 8] },
  { name: '윤채원', region: '군산시', town: '수송동', submitted: '2026-03-09T14:02:00', docs: ['PASS', 'PASS', 'FAIL'], scores: [28, 15, 16, 7] },
  { name: '장시우', region: '익산시', town: '영등동', submitted: '2026-03-05T10:15:00', docs: ['PASS', 'PASS', 'PASS'], scores: [37, 23, 22, 9] },
  { name: '임수아', region: '익산시', town: '영등동', submitted: '2026-03-10T17:33:00', docs: ['NEEDS_REVIEW', 'NEEDS_REVIEW', 'PASS'], scores: [31, 25, 19, 10] },
  { name: '한지호', region: '정읍시', town: '수성동', submitted: '2026-03-11T09:01:00', docs: ['PASS', 'PASS', 'PASS'], scores: [40, 19, 25, 9] },
  { name: '오은우', region: '완주군', town: '봉동읍', submitted: '2026-03-12T15:44:00', docs: ['PASS', 'FAIL', 'PASS'], scores: [34, 17, 16, 8] },
]
const SLOTS = [
  { slot: 'resident_abstract', label: '주민등록초본' },
  { slot: 'health_payment', label: '건강보험료 납부확인서' },
  { slot: 'employment_proof', label: '근로확인서류 (재직증명서)' },
] as const
const FINDINGS: Record<Exclude<DocStatus, 'PASS'>, { code: string; message: string; how_to_fix: string }> = {
  NEEDS_REVIEW: { code: 'LOW_CONFIDENCE', message: '판독 신뢰도가 낮아 담당자 확인이 필요합니다.', how_to_fix: '원본 서류에서 값을 확인해 주세요.' },
  FAIL: { code: 'ISSUED_BEFORE_NOTICE', message: '공고일(2026.3.3.) 이전에 발급된 서류입니다.', how_to_fix: '보완 요청이 없는 사업이므로 선발에서 제외됩니다.' },
}
const BANDS = {
  income: { 40: '100% 미만', 37: '100% 이상 ~ 110% 미만', 34: '110% 이상 ~ 120% 미만', 31: '120% 이상 ~ 130% 미만', 28: '130% 이상' },
  residence: { 15: '1년 미만', 17: '1년 이상 ~ 2년 미만', 19: '2년 이상 ~ 3년 미만', 21: '3년 이상 ~ 4년 미만', 23: '4년 이상 ~ 5년 미만', 25: '5년 이상' },
  work: { 16: '1년 미만', 19: '1년 이상 ~ 2년 미만', 22: '2년 이상 ~ 3년 미만', 25: '3년 이상' },
  age: { 10: '24세 이하', 9: '25~29세', 8: '30~34세', 7: '35세 이상' },
} as Record<string, Record<number, string>>

function paper(id: number, label: string, name: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="595" height="842"><rect width="595" height="842" fill="white"/><g font-family="sans-serif" fill="#243852"><text x="50" y="80" font-size="24">합성 시연 원본</text><text x="50" y="130" font-size="18">${label}</text><text x="50" y="200" font-size="16">성명: ${name}</text><text x="50" y="260" font-size="14">실제 인물·기관 발급 서류가 아닙니다. (${id})</text></g></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function scoreSheet(scores: Seed['scores'], docId: number, seed: number): ScoreSheetData {
  const keys = ['income', 'residence', 'work', 'age'] as const
  const labels = ['중위소득', '도 거주기간', '근로기간', '연령']
  const maxes = [40, 25, 25, 10]
  const items: ScoreItemRow[] = keys.map((key, index) => ({
    key, label: labels[index], score: scores[index], max_score: maxes[index], band: BANDS[key][scores[index]],
    basis: `${BANDS[key][scores[index]]} 구간 (합성 값)`, source_doc: '주민등록초본', source_document_id: docId,
    source_origin: 'synthetic', bbox: { page: 0, x0: 50, y0: 180, x1: 300, y1: 205 }, incomplete: false,
    source_slot_key: 'resident_abstract', source_file_url: null, source_file_format: null,
  }))
  const total = scores.reduce((sum, value) => sum + value, 0)
  const income = { 40: 92.4, 37: 104.2, 34: 114.8, 31: 126.1, 28: 133.5 }[scores[0]] ?? 999
  return {
    items, total, max_total: 100, income_percent: income, income_over_limit: false, incomplete: false,
    tiebreak: [-total, income, -(400 + seed * 97), -(200 + seed * 53), -739000 - seed], notes: [],
  }
}

interface MockEntry { row: OfficerRow; detail: ReviewDetailData }
const entries = new Map<number, MockEntry>(SEEDS.map((seed, index) => {
  const id = 900001 + index
  const documents: OfficerDocument[] = []
  seed.docs.forEach((status, slotIndex) => {
    if (status === null) return
    const { slot, label } = SLOTS[slotIndex]
    const documentId = id * 10 + slotIndex
    documents.push({
      document_id: documentId, slot_key: slot, label, expected_doc_type: label, detected_doc_type: label, status,
      findings: status === 'PASS' ? [] : [{ ...FINDINGS[status], link: '', severity: status }],
      file_url: paper(documentId, label, seed.name), file_name: `합성_${label}.svg`, file_format: 'svg', page_index: null,
      extracted: { 성명: seed.name, 발급일: '2026-03-02' }, bboxes: {}, ocr_confidence: status === 'NEEDS_REVIEW' ? .6 : .98,
      ocr_tier: 'synthetic', ocr_engine: 'synthetic', ocr_fallback_reason: null, ocr_quality_note: null,
      declared_issue_date: '2026-03-02', uploaded_at: seed.submitted,
    })
  })
  const statuses = seed.docs.filter((value): value is DocStatus => value !== null)
  const missing = seed.docs.some((value) => value === null)
  const ai: DocStatus = statuses.includes('FAIL') || missing ? 'FAIL' : statuses.includes('NEEDS_REVIEW') ? 'NEEDS_REVIEW' : 'PASS'
  const sheet = scoreSheet(seed.scores, documents[0]?.document_id ?? 0, index)
  const row: OfficerRow = {
    application_id: id, application_no: `SYN-2026-${String(index + 1).padStart(6, '0')}`, name: seed.name,
    program_code: 'double_savings', region: seed.region, town: seed.town, ai_status: ai,
    ai_status_label: { PASS: '적합', NEEDS_REVIEW: '확인필요', FAIL: '부적합' }[ai],
    total_score: sheet.total, max_total: 100, missing_count: missing ? 1 : 0, submitted_at: seed.submitted,
    decision: null, decision_label: '미처리', rank: null,
    documents: SLOTS.map(({ slot, label }, slotIndex) => {
      const status = seed.docs[slotIndex]
      return {
        column: slot, slot_key: slot, label, short_label: '', status,
        status_label: status === null ? '미제출' : { PASS: '적합', NEEDS_REVIEW: '확인필요', FAIL: '부적합' }[status],
        document_id: status === null ? null : id * 10 + slotIndex, required: true,
      }
    }),
  }
  const detail: ReviewDetailData = {
    application_id: id, application_no: row.application_no, name: seed.name, program_code: 'double_savings',
    region: seed.region, town: seed.town,
    ai: {
      final_status: ai,
      recommended_action: ai === 'PASS' ? '서류 적합' : ai === 'FAIL' ? '선발 제외 검토' : '담당자 원본 확인',
      reasons: missing ? [{ code: 'MISSING_REQUIRED', message: '필수 서류(건강보험료 납부확인서)가 제출되지 않았습니다.', doc_type: null }] : [],
    },
    score_sheet: sheet, documents, decision: { decision: null, label: '미처리', memo: null }, role: ROLES.province,
  }
  return [id, { row, detail }]
}))

/** 결정을 누른 역할을 기억해 둔다. 처리상태 표기는 그 역할의 결과 라벨을 쓴다. */
function apply(id: number, decision: DecisionKey, memo: string, role: RoleKey): void {
  const entry = entries.get(id)
  if (!entry) throw new Error('해당 합성 신청이 없습니다.')
  const label = ROLES[role].actions.find((action) => action.key === decision)?.result_label ?? decision
  entry.row.decision = decision
  entry.row.decision_label = label
  entry.detail.decision = { decision, memo, label }
}

// 미리보기에서 반려 탭이 비지 않도록 부적합 건 하나를 도 역할이 반려해 둔다.
apply(900008, 'reject', '근로확인서류가 공고일(2026.3.3.) 이전에 발급되어 선발에서 제외합니다.', 'province')

export function mockRoles(): OfficerRole[] {
  return [ROLES.town, ROLES.city, ROLES.province]
}

export function mockOfficerList(query: OfficerListQuery, page: number): OfficerList {
  const role = ROLES[query.role]
  const all = [...entries.values()].map((entry) => entry.row)
  const withApplications = REGIONS.filter((region) => all.some((row) => row.region === region))
  const region = role.requires_region ? (query.region || withApplications[0] || REGIONS[0]) : ''
  const inRegion = region ? all.filter((row) => row.region === region) : all
  const towns = [...new Set(inRegion.map((row) => row.town ?? '').filter(Boolean))].sort()
  const town = role.requires_town ? (query.town || towns[0] || '') : ''
  const scoped = town ? inRegion.filter((row) => row.town === town) : inRegion
  const rows = [...scoped].sort((a, b) => (b.total_score ?? 0) - (a.total_score ?? 0)).map((row) => ({ ...row }))
  return {
    role, scope: { region, town, region_locked: Boolean(role.requires_region), town_locked: Boolean(role.requires_town), regions: REGIONS, towns },
    rows: page === 1 ? rows : [], page, page_count: 1, total: rows.length,
  }
}

export function mockReviewDetail(id: number, role: RoleKey = 'province'): ReviewDetailData {
  const entry = entries.get(id)
  if (!entry) throw new Error('해당 합성 신청이 없습니다.')
  return { ...entry.detail, role: ROLES[role] }
}

/** 미리보기용 종합의견. 서버의 규칙 기반 요약과 같은 모양을 합성 판정에서 만든다. */
export function mockOfficerSummary(id: number): OfficerSummary {
  const { detail } = entries.get(id) ?? (() => { throw new Error('해당 합성 신청이 없습니다.') })()
  const label = { PASS: '적합', NEEDS_REVIEW: '확인필요', FAIL: '부적합' } as const
  const flagged = detail.documents.filter((doc) => doc.status && doc.status !== 'PASS')
  const status = detail.ai.final_status ? label[detail.ai.final_status] : '미심사'
  const total = `심사표 ${detail.score_sheet.total}/${detail.score_sheet.max_total}점`
  return {
    headline: flagged.length || detail.ai.reasons.length
      ? `${status}: ${[...flagged.map((doc) => `${doc.label} ${doc.status ? label[doc.status] : ''}`), ...detail.ai.reasons.map((r) => r.message)].slice(0, 2).join(', ')} · ${total}`
      : `모든 서류 적합 · ${total}`,
    status_explanation: `AI 제안은 '${status}'입니다. ${detail.ai.reasons[0]?.message ?? flagged[0]?.findings[0]?.message ?? '저장된 확인 사유가 없습니다.'}`,
    check_points: [
      ...detail.ai.reasons.map((reason) => ({ slot_key: null, title: '필수 서류 미제출', detail: reason.message, codes: [reason.code],
        evidence: [{ code: reason.code, label: '필수 서류 미제출', kind: 'rule', kind_label: '규칙 판정' }], field: null })),
      ...flagged.flatMap((doc) => doc.findings.map((finding) => {
        const label = finding.code === 'LOW_CONFIDENCE' ? '자동 판독 신뢰도 낮음' : '공고일 이전 발급'
        return { slot_key: doc.slot_key, title: label, detail: finding.how_to_fix, codes: [finding.code],
          evidence: [{ code: finding.code, label, kind: 'rule', kind_label: '규칙 판정' }], field: null }
      })),
    ].slice(0, 4),
    document_notes: detail.documents.map((doc) => ({
      slot_key: doc.slot_key,
      note: `${doc.status ? label[doc.status] : '판정 없음'} · ${doc.findings[0]?.message ?? '저장된 확인 사유 없음'}`,
    })),
    score_note: `${total} (${detail.score_sheet.items.map((item) => `${item.label} ${item.score}/${item.max_score}`).join(', ')}).`,
    source: 'rules', label: '규칙 기반 요약', model: null, generated_at: '2026-03-12T09:00:00', cached: false,
  }
}

export function mockDecision(id: number, decision: DecisionKey, memo: string, role: RoleKey = 'province'): void {
  apply(id, decision, memo, role)
}

export function mockBulkDecision(ids: number[], decision: DecisionKey, memo: string, role: RoleKey): { processed: number } {
  if (!ROLES[role].can_bulk) throw new Error(`'${ROLES[role].name}' 역할은 건별 확인이 원칙이라 일괄 처리를 할 수 없습니다.`)
  ids.forEach((id) => apply(id, decision, memo, role))
  return { processed: ids.length }
}
