import assert from 'node:assert/strict'
import test from 'node:test'
import {
  loginOfficer, logoutOfficer, OFFICER_SESSION_EXPIRED, officerSessionResponse, readOfficerSession,
} from '../src/officer-session.ts'

function withWindow(run: (events: string[]) => void): void {
  const original = globalThis.window
  const events: string[] = []
  globalThis.window = { dispatchEvent: (event: Event) => { events.push(event.type); return true } } as Window & typeof globalThis
  try { run(events) } finally { globalThis.window = original }
}

async function withFetch(reply: (path: string, init?: RequestInit) => Response, run: (calls: string[]) => Promise<void>): Promise<void> {
  const original = globalThis.fetch
  const calls: string[] = []
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${String(input)}`)
    return reply(String(input), init)
  }) as typeof fetch
  try { await run(calls) } finally { globalThis.fetch = original }
}

const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

test('only officer API 401 and 503 responses send the login screen back', () => {
  withWindow((events) => {
    officerSessionResponse('/api/officer/applications?role=province&page=1', { status: 401 })
    officerSessionResponse('/api/officer/applications/7', { status: 503 })
    assert.deepEqual(events, [OFFICER_SESSION_EXPIRED, OFFICER_SESSION_EXPIRED])
  })
  withWindow((events) => {
    for (const status of [200, 403, 404, 422, 500]) officerSessionResponse('/api/officer/applications', { status })
    // A wrong password is answered on the login form itself.
    officerSessionResponse('/api/officer/login', { status: 401 })
    // Originals and applicant routes are guarded by the owner check, not the officer session.
    officerSessionResponse('/api/files/3', { status: 401 })
    officerSessionResponse('/api/applications/3', { status: 503 })
    assert.deepEqual(events, [])
  })
})

test('the session check tells signed-in, signed-out and unconfigured apart', async () => {
  await withFetch(() => reply(200, { authenticated: true, expires_at: 1_900_000_000 }), async (calls) => {
    assert.deepEqual(await readOfficerSession(), { kind: 'signed-in', expiresAt: 1_900_000_000 })
    assert.deepEqual(calls, ['GET /api/officer/session'])
  })
  await withFetch(() => reply(401, { detail: '담당자 로그인이 필요합니다.' }), async () => {
    assert.deepEqual(await readOfficerSession(), { kind: 'signed-out' })
  })
  await withFetch(() => reply(503, { detail: '관리자가 .env 에 OFFICER_PASSWORD 를 설정해야 합니다' }), async () => {
    assert.deepEqual(await readOfficerSession(), { kind: 'unconfigured', detail: '관리자가 .env 에 OFFICER_PASSWORD 를 설정해야 합니다' })
  })
  await withFetch(() => reply(500, {}), async () => {
    await assert.rejects(readOfficerSession())
  })
})

test('login posts only the password and reports the server reason', async () => {
  let sent: unknown = null
  await withFetch((_, init) => { sent = JSON.parse(String(init?.body)); return reply(200, { authenticated: true, expires_at: 1_900_000_000 }) }, async (calls) => {
    assert.deepEqual(await loginOfficer('synthetic-password'), { kind: 'signed-in', expiresAt: 1_900_000_000 })
    assert.deepEqual(calls, ['POST /api/officer/login'])
    assert.deepEqual(sent, { password: 'synthetic-password' })
  })
  await withFetch(() => reply(401, { detail: '비밀번호가 올바르지 않습니다.' }), async () => {
    assert.deepEqual(await loginOfficer('wrong'), { kind: 'rejected', detail: '비밀번호가 올바르지 않습니다.' })
  })
  await withFetch(() => reply(429, { detail: '로그인을 잠시 후 다시 시도해 주세요.' }), async () => {
    assert.deepEqual(await loginOfficer('wrong'), { kind: 'rejected', detail: '로그인을 잠시 후 다시 시도해 주세요.' })
  })
  await withFetch(() => reply(503, { detail: '관리자가 담당자 세션 서명 설정을 완료해야 합니다' }), async () => {
    assert.deepEqual(await loginOfficer('any'), { kind: 'unconfigured', detail: '관리자가 담당자 세션 서명 설정을 완료해야 합니다' })
  })
  await withFetch(() => new Response('not json', { status: 401 }), async () => {
    assert.deepEqual(await loginOfficer('wrong'), { kind: 'rejected', detail: '로그인하지 못했습니다 (401)' })
  })
  await withFetch(() => reply(200, { authenticated: false }), async (calls) => {
    await logoutOfficer()
    assert.deepEqual(calls, ['POST /api/officer/logout'])
  })
})
