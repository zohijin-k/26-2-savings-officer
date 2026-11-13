import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import { createElement, type ComponentType } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'
import { collectOfficerRows, groupOfficerDocuments, selectOfficerDocument } from '../src/pages/officer/document-groups.ts'
import { officerPageUrl, readOfficerPage } from '../src/navigation-url.ts'
import type { DocStatus, OfficerDocument, OfficerList, OfficerRow } from '../src/api.ts'
import { fetchReviewDetail } from '../src/api.ts'

function row(id: number, states: Array<DocStatus | null>): OfficerRow {
  return {
    application_id: id, application_no: `FAKE-${id}`, name: `가상${id}`, program_code: 'double_savings',
    documents: states.map((status, index) => ({
      column: 'resident_abstract', slot_key: index === 3 ? '__unassigned__' : `slot${index}`,
      label: `합성서류${index}`, short_label: '', document_id: status === null ? null : id * 10 + index,
      status, status_label: status ?? '미제출', required: true,
    })),
  }
}

test('document PASS alone defines display groups and keeps stored values unchanged', () => {
  const rows = [row(1, ['PASS', 'FAIL', 'NEEDS_REVIEW', null]), row(2, ['PASS'])]
  // Application-level fields must not override the per-document grouping.
  Object.assign(rows[0], { ai_status: 'FAIL' })
  Object.assign(rows[1], { ai_status: 'NEEDS_REVIEW' })
  const before = structuredClone(rows)
  const groups = groupOfficerDocuments(rows)
  assert.deepEqual(groups.pass.map((item) => item.documentId), [10, 20])
  assert.deepEqual(groups.needsReview.map((item) => item.status), ['FAIL', 'NEEDS_REVIEW', null])
  assert.equal(groups.needsReview[2].documentId, null)
  assert.deepEqual(rows, before)
})

test('other programs never appear, even when returned in a response', () => {
  const other = { ...row(2, ['PASS', 'FAIL']), program_code: 'other_program' }
  assert.deepEqual(groupOfficerDocuments([other]), { pass: [], needsReview: [] })
})

test('multiple unassigned pages select by document ID and missing originals stay empty', () => {
  const documents = [1, 2].map((document_id) => ({ document_id, slot_key: '__unassigned__' })) as OfficerDocument[]
  assert.equal(selectOfficerDocument(documents, 2, '__unassigned__')?.document_id, 2)
  assert.equal(selectOfficerDocument(documents, 99, '__unassigned__'), null)
  assert.equal(selectOfficerDocument(documents, null, 'missing'), null)
  assert.equal(selectOfficerDocument(documents, null, null), null)
})

test('all application pages are collected before document grouping', async () => {
  const calls: number[] = []
  const rows = await collectOfficerRows(async (page) => {
    calls.push(page)
    return { rows: [row(page, [page === 1 ? 'PASS' : 'FAIL'])], page, page_count: 3, total: 3 }
  })
  assert.deepEqual(calls, [1, 2, 3])
  assert.equal(groupOfficerDocuments(rows).needsReview.length, 2)
})

test('empty API stays empty and page failures propagate', async () => {
  const empty: OfficerList = { rows: [], page: 1, page_count: 1, total: 0 }
  assert.deepEqual(await collectOfficerRows(async () => empty), [])
  await assert.rejects(collectOfficerRows(async () => { throw new Error('synthetic failure') }), /synthetic failure/)
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

test('actual list component renders the two groups and places a mixed application in both', () => {
  // Compile only this presentation component; no browser globals or server calls are needed.
  const source = readFileSync(new URL('../src/pages/officer/ApplicationList.tsx', import.meta.url), 'utf8')
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
  const module = { exports: {} as { default: ComponentType<{ groups: ReturnType<typeof groupOfficerDocuments>; onOpen: () => void }> } }
  new Function('require', 'module', 'exports', compiled)(createRequire(import.meta.url), module, module.exports)
  const groups = groupOfficerDocuments([row(1, ['PASS', 'NEEDS_REVIEW'])])
  const html = renderToStaticMarkup(createElement(module.exports.default, { groups, onOpen: () => {} }))
  assert.match(html, /aria-label="적합 서류"/)
  assert.match(html, /aria-label="확인 필요 서류"/)
  const sections = html.split('<section').slice(1)
  assert.equal(sections.length, 2)
  assert.match(sections[0], /합성서류0/)
  assert.doesNotMatch(sections[0], /합성서류1/)
  assert.match(sections[1], /합성서류1/)
  assert.doesNotMatch(sections[1], /합성서류0/)
  assert.ok(sections.every((section) => section.includes('가상1')))
})
