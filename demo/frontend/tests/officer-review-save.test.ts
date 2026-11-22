import { requireReviewRevision, requireReviewRevisions } from '../src/lib/review-revision.ts'
import test from 'node:test'
import assert from 'node:assert/strict'
import { ReviewDraft, type ReviewSnapshot } from '../src/pages/officer/review-draft.ts'
import { reviewSaveError } from '../src/pages/officer/review-save.ts'
import { HttpError } from '../src/lib/http-error.ts'

const row = (memo = 'server', decision: string | null = null, revision = 1): ReviewSnapshot => ({ revision, decision: { decision, memo } })
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done }); return { promise, resolve } }
function setup() {
  let server = row(), reads = 0, writes = 0
  let load = async () => server
  let write = async (decision: string, memo: string) => { server = row(memo, decision, (server.revision ?? 0) + 1) }
  const editor = new ReviewDraft(() => { reads++; return load() }, (d, m) => { writes++; return write(d, m) }, reviewSaveError)
  return { editor, get reads() { return reads }, get writes() { return writes }, get server() { return server }, set server(v) { server = v },
    set load(v: () => Promise<ReviewSnapshot>) { load = v }, set write(v: (d: string, m: string) => Promise<void>) { write = v } }
}

test('success is based on readback; newer typing survives a delayed save and synchronous duplicate clicks', async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('sent')
  const gate = deferred<void>(); s.write = async (d, m) => { await gate.promise; s.server = row(m, d, (s.server.revision ?? 0) + 1) }
  const first = s.editor.save('hold'), duplicate = s.editor.save('approve')
  await Promise.resolve(); s.editor.edit('new typing'); gate.resolve(); await Promise.all([first, duplicate])
  assert.equal(s.writes, 1); assert.equal(s.editor.state.memo, 'new typing'); assert.equal(s.editor.dirty, true)
  assert.equal(s.server.decision.memo, 'sent'); assert.match(s.editor.state.message, /이후 입력/)
  s.editor.edit('sent'); assert.equal(s.editor.dirty, false)
})

for (const status of [400, 401, 403, 409, 500, 503]) test(`HTTP ${status} retains draft and requires a read before explicit retry`, async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('private draft')
  s.write = async () => { throw new HttpError(status, 'SQL secret') }
  await s.editor.save('hold'); assert.equal(s.editor.state.phase, 'ERROR'); assert.equal(s.editor.state.memo, 'private draft')
  assert.equal(s.editor.state.needsCheck, true); assert.doesNotMatch(s.editor.state.message, /SQL secret/)
  await s.editor.save('hold'); assert.equal(s.writes, 1)
  await s.editor.check(); assert.equal(s.editor.state.needsCheck, false); assert.equal(s.editor.state.memo, 'private draft')
  s.write = async (d, m) => { s.server = row(m, d, (s.server.revision ?? 0) + 1) }; await s.editor.save('hold')
  assert.equal(s.editor.state.phase, 'SAVED'); assert.equal(s.editor.dirty, false)
})

for (const error of [new TypeError('network'), new DOMException('timeout', 'TimeoutError')]) test(`${error.name}: committed response loss recovers by GET without another POST`, async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('committed')
  s.write = async (d, m) => { s.server = row(m, d, (s.server.revision ?? 0) + 1); throw error }
  await s.editor.save('hold'); assert.equal(s.editor.state.needsCheck, true)
  await s.editor.check(); assert.equal(s.writes, 1); assert.equal(s.editor.state.phase, 'SAVED')
})

test('POST success followed by GET failure is unconfirmed, never a false success', async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('sent')
  s.write = async (d, m) => { s.server = row(m, d, (s.server.revision ?? 0) + 1); s.load = async () => { throw new HttpError(503, 'down') } }
  await s.editor.save('hold'); assert.equal(s.editor.state.phase, 'STALE'); assert.match(s.editor.state.message, /재조회/)
  assert.equal(s.editor.state.memo, 'sent'); s.load = async () => s.server; await s.editor.check()
  assert.equal(s.editor.state.phase, 'SAVED'); assert.equal(s.writes, 1)
})

test('preflight detects a changed server snapshot, preserves input and requires explicit acceptance', async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('B draft'); s.server = row('A update', 'hold')
  await s.editor.save('hold'); assert.equal(s.writes, 0); assert.equal(s.editor.state.conflict, true)
  assert.equal(s.editor.state.memo, 'B draft'); await s.editor.check(); assert.equal(s.editor.state.conflict, true)
  s.editor.acceptLatest(); assert.equal(s.editor.state.needsCheck, false); assert.equal(s.editor.dirty, true)
  await s.editor.save('hold'); assert.equal(s.server.decision.memo, 'B draft')
})

test('a GET mismatch after POST remains stale and never overwrites a draft', async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('sent'); s.write = async () => { s.server = row('other writer', 'approve') }
  await s.editor.save('hold'); assert.equal(s.editor.state.conflict, true); assert.equal(s.editor.state.memo, 'sent')
})

test('unmounted response cannot affect another editor or fire saved callbacks', async () => {
  const gate = deferred<ReviewSnapshot>(), s = setup(); await s.editor.check(); s.editor.edit('old application')
  s.load = () => gate.promise; const pending = s.editor.save('hold'); s.editor.dispose()
  const next = setup(); await next.editor.check(); gate.resolve(row()); await pending
  assert.equal(s.writes, 0); assert.equal(next.editor.state.memo, 'server')
})

test('generic checklist failure/recheck retains the unsaved decision memo', async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('generic draft')
  await s.editor.run(async () => { throw new HttpError(500, 'private') }); await s.editor.check()
  assert.equal(s.editor.state.memo, 'generic draft'); assert.equal(s.editor.dirty, true)
  await s.editor.run(async () => s.server); assert.equal(s.editor.state.memo, 'generic draft')
})

test('initial read alone does not guard navigation or create a sensitive draft', async () => {
  const s = setup(), gate = deferred<ReviewSnapshot>(); s.load = () => gate.promise
  const pending = s.editor.check(); assert.equal(s.editor.state.busy, true); assert.equal(s.editor.protected, false)
  gate.resolve(row()); await pending; assert.equal(s.editor.protected, false)
})


test('CAS rejects a change between preflight and POST; no automatic rebase or retry', async () => {
  let server = row('baseline'), writes = 0
  const seen: number[] = []
  const editor = new ReviewDraft(async () => server, async (d, m, expected) => {
    writes++; seen.push(expected)
    if (writes === 1) {
      server = row('A latest', 'hold', 2)
      throw new HttpError(409, 'private server detail', 'REVIEW_REVISION_CONFLICT')
    }
    assert.equal(expected, server.revision)
    server = row(m, d, expected + 1)
  }, reviewSaveError)
  await editor.check(); editor.edit('B local'); await editor.save('hold')
  assert.equal(editor.state.phase, 'CONFLICT'); assert.equal(editor.state.memo, 'B local')
  assert.equal(editor.state.data?.decision.memo, 'A latest'); assert.equal(editor.state.latestReady, true)
  assert.equal(editor.state.needsCheck, true); assert.doesNotMatch(editor.state.message, /private server/)
  await editor.save('hold'); assert.equal(writes, 1)
  await editor.check(); assert.equal(editor.state.conflict, true); assert.equal(writes, 1)
  editor.acceptLatest(); assert.equal(editor.state.needsCheck, false)
  await editor.save('hold'); assert.deepEqual(seen, [1, 2]); assert.equal(server.revision, 3)
  assert.equal(server.decision.memo, 'B local'); assert.equal(editor.state.phase, 'SAVED')
})

test('CAS conflict with latest GET unavailable cannot accept an old version', async () => {
  let unavailable = false, writes = 0
  const editor = new ReviewDraft(async () => { if (unavailable) throw new HttpError(503, 'down'); return row() }, async () => {
    writes++; unavailable = true; throw new HttpError(409, 'conflict', 'REVIEW_REVISION_CONFLICT')
  }, reviewSaveError)
  await editor.check(); editor.edit('local'); await editor.save('hold'); editor.acceptLatest()
  assert.equal(editor.state.needsCheck, true); assert.equal(editor.state.latestReady, false)
  await editor.save('hold'); assert.equal(writes, 1); assert.equal(editor.state.memo, 'local')
})

test('revision change alone invalidates baseline even with identical memo and decision', async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('local')
  s.server = row('server', null, 2); await s.editor.save('hold')
  assert.equal(s.writes, 0); assert.equal(s.editor.state.conflict, true)
})

test('unrelated business 409 is not classified as revision conflict', async () => {
  const s = setup(); await s.editor.check(); s.editor.edit('local')
  s.write = async () => { throw new HttpError(409, 'business') }; await s.editor.save('hold')
  assert.equal(s.editor.state.conflict, false); assert.equal(s.editor.state.phase, 'ERROR')
  assert.match(s.editor.state.message, /업무 상태/)
})

test('missing read revision fails closed before POST', async () => {
  const s = setup(); s.server = { revision: null, decision: { decision: null, memo: null } }
  await s.editor.check(); s.editor.edit('local'); await s.editor.save('hold')
  assert.equal(s.writes, 0); assert.equal(s.editor.state.needsCheck, true)
})

test('HTTP error parsing exposes only the supported structured code', async () => {
  const error = await HttpError.fromResponse(new Response(JSON.stringify({detail:{code:'REVIEW_REVISION_CONFLICT',message:'SQL private'}}),{status:409}), 'safe')
  assert.equal(error.code, 'REVIEW_REVISION_CONFLICT'); assert.equal(error.message, 'safe')
  const business = await HttpError.fromResponse(new Response(JSON.stringify({detail:'other 409'}),{status:409}), 'safe')
  assert.equal(business.code, undefined)
})


test('transport accepts observed version maps without changing stale tokens', () => {
  assert.doesNotThrow(() => requireReviewRevisions([1, 2], {1: 1, 2: 4}))
  assert.doesNotThrow(() => requireReviewRevision(1))
})

for (const revision of [undefined, null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER]) test(`unversioned/invalid transport token ${revision} fails closed`, () => {
  assert.throws(() => requireReviewRevision(revision), (error: unknown) => error instanceof HttpError && error.status === 428)
  assert.throws(() => requireReviewRevisions([1], {1: revision}), (error: unknown) => error instanceof HttpError && error.code === 'REVIEW_REVISION_REQUIRED')
})

test('bulk transport rejects duplicate, extra and missing application tokens', () => {
  assert.throws(() => requireReviewRevisions([1, 1], {1: 1}))
  assert.throws(() => requireReviewRevisions([1], {1: 1, 2: 1}))
  assert.throws(() => requireReviewRevisions([1, 2], {1: 1}))
})
