import type { DocStatus, OfficerDocument, OfficerSummary, SummaryCheckPoint } from '../../api.ts'

/** 카드 머리의 출처 태그. 생성 주체를 숨기지 않는다. */
export function summaryTag(summary: Pick<OfficerSummary, 'source'>): { text: string; tone: 'ai' | 'rules' } {
  return summary.source === 'rules'
    ? { text: '규칙 기반 요약', tone: 'rules' }
    : { text: '전북AI · 참고용', tone: 'ai' }
}

/** 확인 포인트가 가리키는 서류. 서버가 slot_key를 검증하지만, 화면에 없는 서류면 이동하지 않는다. */
export function pointTarget(point: SummaryCheckPoint, documents: OfficerDocument[]): OfficerDocument | null {
  if (!point.slot_key) return null
  return documents.find((doc) => doc.slot_key === point.slot_key) ?? null
}

/** 원본에서 강조할 위치. 서버가 고른 판독 항목에 좌표가 있을 때만. */
export function pointHighlight(point: SummaryCheckPoint, doc: OfficerDocument | null): string | null {
  return doc && point.field && doc.bboxes[point.field] ? point.field : null
}

/** '2025년 건강보험료 납부확인서' → '건강보험료 납부확인서', '근로확인서류(4대보험…)' → '근로확인서류'. */
export function shortDocLabel(label: string): string {
  return label.replace(/^\d{4}년\s*/, '').replace(/\s*\(.*\)\s*$/, '').trim() || label
}

/** 근거 종류별 색. 규칙 판정과 저장값 자동 대조를 구분해 보인다. */
export function evidenceTone(kind: string): 'rule' | 'auto' | 'other' {
  return kind === 'rule' ? 'rule' : kind === 'auto' ? 'auto' : 'other'
}

/** 근거를 종류별 한 묶음으로: [자동 대조] 명의가 신청자와 다름, 생년월일이 신청서와 다름. */
export function groupedEvidence(point: SummaryCheckPoint): { kind: string; kindLabel: string; labels: string[] }[] {
  const groups = new Map<string, { kind: string; kindLabel: string; labels: string[] }>()
  for (const item of point.evidence) {
    const group = groups.get(item.kind_label) ?? { kind: item.kind, kindLabel: item.kind_label, labels: [] }
    if (!group.labels.includes(item.label)) group.labels.push(item.label)
    groups.set(item.kind_label, group)
  }
  return [...groups.values()]
}

/** 첫 화면에 보일 확인 포인트 수. 나머지는 '더 보기'로 접는다. 탈락 사유는 개수와 상관없이 모두 보인다. */
export const VISIBLE_POINTS = 3

/**
 * 확인 포인트의 무게. 'fail'은 그 하나만으로 선발에서 제외되는 사유(보완 요청이 없는 사업),
 * 'review'는 담당자가 원본을 보고 판단할 항목이다. 요약은 판정을 바꾸지 않으므로
 * 저장된 근거로만 정한다: 자격요건·제외대상 미충족, 필수 서류 미제출, 부적합(FAIL) 판독 사유.
 */
export type PointSeverity = 'fail' | 'review'
export function pointSeverity(point: SummaryCheckPoint, documents: OfficerDocument[]): PointSeverity {
  if (point.evidence.some((item) => item.kind === 'eligibility')) return 'fail'
  if (point.codes.some((code) => code.startsWith('MISSING_REQUIRED_DOC') || code === 'MISSING_REQUIRED')) return 'fail'
  const scope = point.slot_key ? documents.filter((doc) => doc.slot_key === point.slot_key) : documents
  const failCodes = new Set(scope.flatMap((doc) => doc.findings.filter((f) => f.severity === 'FAIL').map((f) => f.code)))
  return point.codes.some((code) => failCodes.has(code)) ? 'fail' : 'review'
}

/** 탈락 사유를 맨 앞으로. 같은 무게 안에서는 서버가 준 순서를 지킨다. */
export function rankedPoints(points: SummaryCheckPoint[], documents: OfficerDocument[]): { point: SummaryCheckPoint; severity: PointSeverity }[] {
  const rows = points.map((point) => ({ point, severity: pointSeverity(point, documents) }))
  return [...rows.filter((row) => row.severity === 'fail'), ...rows.filter((row) => row.severity === 'review')]
}

/** 카드 맨 위 판정 띠. 저장된 AI 판정(final_status)을 그대로 옮긴다. */
export function verdictBand(status: DocStatus | null): { tone: 'fail' | 'review' | 'pass' | 'none'; label: string } {
  if (status === 'FAIL') return { tone: 'fail', label: '부적합' }
  if (status === 'NEEDS_REVIEW') return { tone: 'review', label: '확인필요' }
  if (status === 'PASS') return { tone: 'pass', label: '적합' }
  return { tone: 'none', label: '미심사' }
}

/** 서류별 메모를 화면 서류 순서대로. 화면에 없는 서류 메모는 버린다. */
export function orderedNotes(summary: Pick<OfficerSummary, 'document_notes'>, documents: OfficerDocument[]): { doc: OfficerDocument; note: string }[] {
  const bySlot = new Map(summary.document_notes.map((note) => [note.slot_key, note.note]))
  return documents.flatMap((doc) => {
    const note = bySlot.get(doc.slot_key)
    return note ? [{ doc, note }] : []
  })
}

/** 'YYYY-MM-DDTHH:MM:SS' → 'MM.DD HH:MM'. 읽을 수 없으면 원문. */
export function generatedAtLabel(value: string): string {
  const match = /^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value)
  return match ? `${match[1]}.${match[2]} ${match[3]}:${match[4]}` : value
}
