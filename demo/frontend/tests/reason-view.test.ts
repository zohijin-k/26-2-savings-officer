import assert from 'node:assert/strict'
import test from 'node:test'

import { generalReasons } from '../src/pages/officer/list-model.ts'
import { primaryReason, reasonView } from '../src/pages/officer/reason-view.ts'

const ENGINE_LOW = "'주민등록초본'의 일부 항목이 자동으로 판독되지 않았습니다. 담당자가 직접 확인할 예정입니다."

// 백엔드 review_reasons.project_reasons가 스캔 초본(SCAN_UNVERIFIED)에 대해 돌려주는 모양 (합성).
const scan = {
  code: 'ADDRESS_HISTORY_INCOMPLETE', severity: 'NEEDS_REVIEW', doc_type: '주민등록초본', document_id: 7, priority: 2,
  category: 'completeness', category_label: '서류 완결성 확인 필요',
  title: '스캔 주민등록초본의 주소이력 완전성 확인 필요',
  message: '주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다.',
  explanation: '주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다.',
  details: ['스캔 초본은 주소이력 끝부분까지 제출됐는지 자동으로 확정하지 않음'],
  stored_message: '초본 주소 이력 일부를 읽지 못했을 수 있습니다. 전입일과 주소 이력은 담당자가 원본에서 확인합니다.',
  origin: { code: 'LOW_OCR_CONFIDENCE', message: ENGINE_LOW },
}

test('scan abstract reads as completeness, never as low OCR confidence; engine text only in audit', () => {
  const view = reasonView(scan)
  assert.equal(view.category, '서류 완결성 확인 필요')
  assert.equal(view.title, '스캔 주민등록초본의 주소이력 완전성 확인 필요')
  assert.equal(view.body, scan.explanation)
  assert.doesNotMatch(`${view.category} ${view.title} ${view.body} ${view.details.join(' ')}`, /신뢰도|판독되지 않았|누락/)
  assert.deepEqual(view.audit, [
    `자동 판정 기록 원문: ${ENGINE_LOW}`,
    `저장된 안내 문구: ${scan.stored_message}`,
  ])
  // 영문 코드는 어느 칸에도 보이지 않는다.
  assert.doesNotMatch(JSON.stringify(view), /[A-Z]{2,}_[A-Z]/)
})

test('a legacy reason without projection fields still renders its stored title and sentence', () => {
  const view = reasonView({ code: 'MISSING_SIGNATURE', title: '서명 없음', message: 'MISSING_SIGNATURE 서명을 확인하세요.' })
  assert.deepEqual(view, { category: null, title: '서명 없음', body: '서명을 확인하세요.', details: [], audit: [] })
})

test('the backend priority decides what the officer checks first', () => {
  const conflict = { code: 'DECLARED_DATE_UNCERTAIN', message: '합성', priority: 1, doc_type: null }
  assert.equal(primaryReason([scan, conflict]), conflict)
  assert.equal(primaryReason([{ code: 'INCOME_UNDETERMINED', message: '합성', doc_type: null }])?.code, 'INCOME_UNDETERMINED')
  assert.equal(primaryReason([]), null)
})

test('list row does not repeat a reason its shown document already stores, but keeps engine-only reasons', () => {
  const income = { code: 'INCOME_UNDETERMINED', message: '합성', doc_type: null }
  const hiddenDoc = { ...scan, document_id: 9 }
  const engineOnly = { code: 'LOW_OCR_CONFIDENCE', message: '합성', doc_type: '통장사본', document_id: 7 }
  const shown = [{ document_id: 7, findings: [{ code: 'ADDRESS_HISTORY_INCOMPLETE' }] }]
  assert.deepEqual(generalReasons([scan, income, hiddenDoc, engineOnly], shown), [income, hiddenDoc, engineOnly])
})
