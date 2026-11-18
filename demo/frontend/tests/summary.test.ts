import assert from 'node:assert/strict'
import test from 'node:test'
import type { OfficerDocument } from '../src/api.ts'
import { mockOfficerSummary, mockReviewDetail } from '../src/pages/officer/mock-data.ts'
import { evidenceTone, generatedAtLabel, orderedNotes, pointHighlight, pointTarget, shortDocLabel, summaryTag } from '../src/pages/officer/summary-model.ts'

function doc(id: number, slot: string, label: string): OfficerDocument {
  return {
    document_id: id, slot_key: slot, label, expected_doc_type: label, detected_doc_type: label, status: 'PASS',
    findings: [], file_url: '', file_name: '', file_format: 'pdf', page_index: null, extracted: {}, bboxes: {},
    ocr_confidence: null, ocr_tier: null, ocr_engine: null, ocr_fallback_reason: null, ocr_quality_note: null,
    declared_issue_date: null, uploaded_at: '',
  } as OfficerDocument
}
const DOCS = [doc(6, 'resident_abstract', '주민등록초본'), doc(7, 'nhis_payment', '건강보험료 납부확인서')]

test('the source tag never hides who wrote the summary', () => {
  assert.deepEqual(summaryTag({ source: 'jbai' }), { text: '전북AI · 참고용', tone: 'ai' })
  assert.deepEqual(summaryTag({ source: 'rules' }), { text: '규칙 기반 요약', tone: 'rules' })
})

test('check points jump only to documents on screen', () => {
  const point = { title: 't', detail: '', codes: ['X'], evidence: [], field: null }
  assert.equal(pointTarget({ ...point, slot_key: 'nhis_payment' }, DOCS)?.document_id, 7)
  assert.equal(pointTarget({ ...point, slot_key: 'ghost' }, DOCS), null)
  assert.equal(pointTarget({ ...point, slot_key: null }, DOCS), null)
})

test('evidence kinds are told apart and documents get short names', () => {
  assert.equal(evidenceTone('auto'), 'auto')
  assert.equal(evidenceTone('rule'), 'rule')
  assert.equal(evidenceTone('eligibility'), 'other')
  assert.equal(shortDocLabel('2025년 건강보험료 납부확인서'), '건강보험료 납부확인서')
  assert.equal(shortDocLabel('근로확인서류(4대보험 가입내역 확인서)'), '근로확인서류')
})

test('a check point highlights the original only where the field has coordinates', () => {
  const resident = { ...DOCS[0], bboxes: { 전입일: { page: 0, x0: 1, y0: 1, x1: 2, y1: 2 } } } as OfficerDocument
  const point = { slot_key: 'resident_abstract', title: 't', detail: '', codes: ['X'], evidence: [], field: '전입일' }
  assert.equal(pointHighlight(point, resident), '전입일')
  assert.equal(pointHighlight({ ...point, field: '성명' }, resident), null)
  assert.equal(pointHighlight(point, null), null)
})

test('document notes follow the tab order and drop unknown slots', () => {
  const notes = orderedNotes({ document_notes: [
    { slot_key: 'nhis_payment', note: 'b' }, { slot_key: 'ghost', note: 'x' }, { slot_key: 'resident_abstract', note: 'a' },
  ] }, DOCS)
  assert.deepEqual(notes.map(({ doc: d, note }) => [d.slot_key, note]), [['resident_abstract', 'a'], ['nhis_payment', 'b']])
})

test('generated time is shortened and unknown formats pass through', () => {
  assert.equal(generatedAtLabel('2026-11-17T22:28:47'), '11.17 22:28')
  assert.equal(generatedAtLabel('어제'), '어제')
})

test('mock preview summary uses only the synthetic verdict it describes', () => {
  const detail = mockReviewDetail(900003)
  const summary = mockOfficerSummary(900003)
  assert.equal(summary.source, 'rules')
  assert.ok(summary.headline.startsWith('부적합'))
  const codes = new Set(detail.documents.flatMap((d) => d.findings.map((f) => f.code)))
  assert.ok(summary.check_points.length > 0 && summary.check_points.every((p) => p.codes.every((c) => codes.has(c))))
  // 화면에 보이는 근거 문구에는 코드가 없다.
  assert.ok(summary.check_points.every((p) => p.evidence.every((e) => !/[A-Z]{2,}_[A-Z]/.test(e.label + e.kind_label))))
  assert.deepEqual(summary.document_notes.map((n) => n.slot_key), detail.documents.map((d) => d.slot_key))
  assert.ok(!JSON.stringify(summary).includes(detail.name))
})

test('evidence of the same kind is shown as one group', async () => {
  const { groupedEvidence } = await import('../src/pages/officer/summary-model.ts')
  const groups = groupedEvidence({ slot_key: null, title: 't', detail: '', codes: [], field: null, evidence: [
    { code: 'A', label: '명의가 신청자와 다름', kind: 'auto', kind_label: '자동 대조' },
    { code: 'B', label: '생년월일이 신청서와 다름', kind: 'auto', kind_label: '자동 대조' },
    { code: 'C', label: '자동 판독 신뢰도 낮음', kind: 'rule', kind_label: '규칙 판정' },
  ] })
  assert.deepEqual(groups.map((g) => [g.kindLabel, g.labels.join(', ')]), [
    ['자동 대조', '명의가 신청자와 다름, 생년월일이 신청서와 다름'], ['규칙 판정', '자동 판독 신뢰도 낮음']])
})
