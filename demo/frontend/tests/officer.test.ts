import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import { createElement, type ComponentType } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'
import { collectOfficerList, firstDocument, importanceOf, matchesFilters, queueCounts, queueOf, selectOfficerDocument, sortRows } from '../src/pages/officer/list-model.ts'
import { officerPageUrl, readOfficerPage } from '../src/navigation-url.ts'
import type { DecisionKey, DocStatus, OfficerDocument, OfficerList, OfficerRow } from '../src/api.ts'
import { fetchReviewDetail } from '../src/api.ts'

function row(id: number, ai: DocStatus | null, decision: DecisionKey | null = null, docs: Array<DocStatus | null> = ['PASS']): OfficerRow {
  return {
    application_id: id, application_no: `FAKE-${id}`, name: `가상${id}`, program_code: 'double_savings',
    region: '전주시', town: '가상동', ai_status: ai, total_score: 80 + id, max_total: 100,
    submitted_at: `2026-03-0${id}T09:00:00`, decision, decision_label: decision ? '최종 선정' : '미처리',
    documents: docs.map((status, index) => ({
      column: `slot${index}`, slot_key: `slot${index}`, label: `합성서류${index}`, short_label: '',
      document_id: status === null ? null : id * 10 + index, status, status_label: status ?? '미제출', required: true,
    })),
  }
}

test('queues split by officer decision first, then by AI verdict, without changing rows', () => {
  const rows = [row(1, 'PASS'), row(2, 'NEEDS_REVIEW'), row(3, 'FAIL'), row(4, null), row(5, 'PASS', 'approve'), row(6, 'FAIL', 'reject')]
  const before = structuredClone(rows)
  assert.deepEqual(rows.map(queueOf), ['pass', 'needs_review', 'needs_review', 'needs_review', 'done', 'done'])
  assert.deepEqual(queueCounts(rows), { needs_review: 3, pass: 1, done: 2 })
  assert.deepEqual(rows, before)
})

test('search and submitted-date filters match number, name and inclusive day range', () => {
  const target = row(3, 'PASS')
  const empty = { search: '', from: '', to: '' }
  assert.equal(matchesFilters(target, { ...empty, search: 'fake-3' }), true)
  assert.equal(matchesFilters(target, { ...empty, search: '가상3' }), true)
  assert.equal(matchesFilters(target, { ...empty, search: '가상4' }), false)
  assert.equal(matchesFilters(target, { ...empty, from: '2026-03-03', to: '2026-03-03' }), true)
  assert.equal(matchesFilters(target, { ...empty, from: '2026-03-04' }), false)
  assert.equal(matchesFilters({ ...target, submitted_at: null }, { ...empty, to: '2026-03-31' }), false)
})

test('importance counts non-PASS originals and missing required documents only', () => {
  const sample = row(1, 'FAIL', null, ['NEEDS_REVIEW', 'FAIL', 'PASS', null])
  assert.equal(importanceOf(sample), 3)
  sample.documents![3].required = false
  assert.equal(importanceOf(sample), 2)
  assert.equal(importanceOf(row(2, 'PASS', null, ['PASS', 'PASS'])), 0)
})

test('importance puts two review documents above one, then oldest first; latest/oldest follow submitted time', () => {
  const one = row(1, 'NEEDS_REVIEW', null, ['NEEDS_REVIEW', 'PASS'])
  const twoNew = row(4, 'NEEDS_REVIEW', null, ['NEEDS_REVIEW', 'NEEDS_REVIEW'])
  const twoOld = row(2, 'NEEDS_REVIEW', null, ['NEEDS_REVIEW', 'NEEDS_REVIEW'])
  const undated = { ...row(3, 'NEEDS_REVIEW', null, ['PASS']), submitted_at: null }
  const rows = [one, twoNew, undated, twoOld]
  const before = structuredClone(rows)
  const ids = (sort: Parameters<typeof sortRows>[1]) => sortRows(rows, sort).map((item) => item.application_id)
  assert.deepEqual(ids('importance'), [2, 4, 1, 3])
  assert.deepEqual(ids('latest'), [4, 2, 1, 3])
  assert.deepEqual(ids('oldest'), [1, 2, 4, 3])
  assert.deepEqual(rows, before)
})

test('opening a row starts at the first non-PASS original and never at a missing one', () => {
  assert.deepEqual(firstDocument(row(1, 'FAIL', null, [null, 'PASS', 'FAIL'])), { documentId: 12, slotKey: 'slot2' })
  assert.deepEqual(firstDocument(row(1, 'PASS', null, ['PASS', 'PASS'])), { documentId: 10, slotKey: 'slot0' })
  assert.equal(firstDocument(row(1, 'FAIL', null, [null])), null)
})

test('multiple unassigned pages select by document ID and missing originals stay empty', () => {
  const documents = [1, 2].map((document_id) => ({ document_id, slot_key: '__unassigned__' })) as OfficerDocument[]
  assert.equal(selectOfficerDocument(documents, 2, '__unassigned__')?.document_id, 2)
  assert.equal(selectOfficerDocument(documents, 99, '__unassigned__'), null)
  assert.equal(selectOfficerDocument(documents, null, 'missing'), null)
  assert.equal(selectOfficerDocument(documents, null, null), null)
})

test('all application pages are collected and keep the first page role and scope', async () => {
  const calls: number[] = []
  const list = await collectOfficerList(async (page) => {
    calls.push(page)
    return { role: { key: 'city', name: '시군', actions: [] }, rows: [row(page, 'PASS')], page, page_count: 3, total: 3 }
  })
  assert.deepEqual(calls, [1, 2, 3])
  assert.equal(list.rows.length, 3)
  assert.equal(list.role?.key, 'city')
})

test('empty API stays empty and page failures propagate', async () => {
  const empty: OfficerList = { rows: [], page: 1, page_count: 1, total: 0 }
  assert.deepEqual((await collectOfficerList(async () => empty)).rows, [])
  await assert.rejects(collectOfficerList(async () => { throw new Error('synthetic failure') }), /synthetic failure/)
})

test('an unknown explicit mock detail rejects through the normal error path', async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', {
    configurable: true, value: { location: { search: '?mock=1' } },
  })
  try {
    await assert.rejects(fetchReviewDetail(123), /해당 합성 신청이 없습니다/)
  } finally {
    if (original) Object.defineProperty(globalThis, 'window', original)
    else Reflect.deleteProperty(globalThis, 'window')
  }
})

test('root and removed entry URLs resolve to the officer list', () => {
  for (const path of ['/', '/apply/upload', '/officer/criteria/other_program', '/officer/city']) {
    const page = readOfficerPage(new URL(`http://localhost${path}?program=other_program&mode=applicant`))
    assert.equal(page.applicationId, null)
    assert.equal(officerPageUrl(page, false), '/officer')
  }
})

test('detail selection survives URL round trip without restoring role or business filters', () => {
  const page = { applicationId: 12, documentId: 87, slotKey: '__unassigned__' }
  const url = officerPageUrl(page, true)
  assert.deepEqual(readOfficerPage(new URL(`http://localhost${url}`)), page)
  assert.equal(new URL(`http://localhost${url}`).searchParams.get('mock'), '1')
  assert.equal(readOfficerPage(new URL('http://localhost/officer/review/999999999999999999999')).applicationId, null)
})

function loadList() {
  // Compile only this presentation component; no browser globals or server calls are needed.
  const require = createRequire(import.meta.url)
  const load = (relative: string): Record<string, unknown> => {
    const source = readFileSync(new URL(relative, import.meta.url), 'utf8')
    const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
    const module = { exports: {} as Record<string, unknown> }
    const local = (name: string) => name === './list-model.ts' ? load('../src/pages/officer/list-model.ts') : require(name)
    new Function('require', 'module', 'exports', compiled)(local, module, module.exports)
    return module.exports
  }
  return load('../src/pages/officer/ApplicationList.tsx').default as ComponentType<Record<string, unknown>>
}

test('actual list component shows one queue tab of application rows with counts', () => {
  const List = loadList()
  const rows = [row(1, 'PASS'), row(2, 'NEEDS_REVIEW'), row(3, 'PASS', 'approve')]
  const role = { key: 'province', name: '도·청년허브센터', can_bulk: true, actions: [] }
  const review = renderToStaticMarkup(createElement(List, { rows, role, onOpen: () => {}, onBulk: async () => {} }))
  assert.match(review, /role="tablist"/)
  assert.match(review, /확인 필요<span class="alist__count alist__count--loud">1<\/span>/)
  assert.match(review, /적합<span class="alist__count">1<\/span>/)
  assert.match(review, /처리 완료<span class="alist__count">1<\/span>/)
  assert.match(review, /FAKE-2/)
  assert.doesNotMatch(review, /FAKE-1|FAKE-3/)
  assert.match(review, /aria-label="전체 선택"/)
  const pass = renderToStaticMarkup(createElement(List, { rows, role, initialQueue: 'pass', onOpen: () => {} }))
  assert.match(pass, /FAKE-1/)
  assert.doesNotMatch(pass, /FAKE-2|FAKE-3/)
  // Without bulk permission (읍·면·동) the checkbox column stays but carries no inputs.
  assert.doesNotMatch(pass, /type="checkbox"/)
})

test('tiebreak key renders in priority order without exposing birth dates', async () => {
  const { tiebreakParts } = await import('../src/pages/officer/tiebreak.ts')
  const sheet = {
    items: [{ key: 'age', band: '25~29세' }], total: 86, max_total: 100, income_percent: 104.2,
    income_over_limit: false, incomplete: false, tiebreak: [-86, 104.2, -1310, -484, -739000], notes: [],
  } as unknown as Parameters<typeof tiebreakParts>[0]
  assert.deepEqual(tiebreakParts(sheet), ['소득 104.2%', '도 거주 1,310일', '근로 484일', '연령 25~29세'])
  assert.deepEqual(tiebreakParts({ ...sheet, items: [], tiebreak: [-50, 999, 0, 0, 0] }),
    ['소득 미확인', '도 거주 미확인', '근로 미확인', '연령 미확인'])
  assert.equal(tiebreakParts({ ...sheet, tiebreak: [] }), null)
})
