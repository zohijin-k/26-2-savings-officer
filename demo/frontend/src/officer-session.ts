/**
 * 담당자 로그인 세션. 서버가 서명한 쿠키(`officer_session`, HttpOnly)를 브라우저가
 * 실어 보내므로 화면은 토큰을 읽거나 저장하지 않는다. 규격은
 * `.trellis/spec/frontend/officer-documents.md`(Officer login)와 `backend/access-control.md`.
 */
export const OFFICER_SESSION_EXPIRED = 'officer-session-expired'

export type OfficerSessionState =
  | { kind: 'signed-in'; expiresAt: number }
  | { kind: 'signed-out' }
  | { kind: 'unconfigured'; detail: string }

export type OfficerLoginResult =
  | { kind: 'signed-in'; expiresAt: number }
  | { kind: 'rejected'; detail: string }
  | { kind: 'unconfigured'; detail: string }

const UNCONFIGURED_FALLBACK = '담당자 로그인 설정이 필요합니다. 관리자에게 문의해 주세요.'

/** 담당자 API가 401·503을 내면 로그인 화면으로 돌아가라는 이벤트를 낸다. 로그인 요청 자체는 빼고 본다. */
export function officerSessionResponse(path: string, response: Pick<Response, 'status'>): void {
  if (typeof window === 'undefined' || !path.startsWith('/api/officer/') || path.split('?')[0] === '/api/officer/login') return
  if (response.status === 401 || response.status === 503) window.dispatchEvent(new Event(OFFICER_SESSION_EXPIRED))
}

async function detailOf(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null
  return typeof body?.detail === 'string' && body.detail ? body.detail : fallback
}

async function expiryOf(response: Response): Promise<number> {
  const body = await response.json() as { expires_at?: unknown }
  if (typeof body.expires_at !== 'number') throw new Error('담당자 세션 응답에 만료 시각이 없습니다.')
  return body.expires_at
}

/** 연결 자체가 실패하면 예외를 그대로 던진다. 화면이 다시 시도 안내를 보여 준다. */
export async function readOfficerSession(): Promise<OfficerSessionState> {
  const response = await fetch('/api/officer/session', { credentials: 'same-origin' })
  if (response.ok) return { kind: 'signed-in', expiresAt: await expiryOf(response) }
  if (response.status === 503) return { kind: 'unconfigured', detail: await detailOf(response, UNCONFIGURED_FALLBACK) }
  if (response.status === 401) return { kind: 'signed-out' }
  throw new Error(`담당자 세션을 확인하지 못했습니다 (${response.status})`)
}

export async function loginOfficer(password: string): Promise<OfficerLoginResult> {
  const response = await fetch('/api/officer/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  if (response.ok) return { kind: 'signed-in', expiresAt: await expiryOf(response) }
  if (response.status === 503) return { kind: 'unconfigured', detail: await detailOf(response, UNCONFIGURED_FALLBACK) }
  return { kind: 'rejected', detail: await detailOf(response, `로그인하지 못했습니다 (${response.status})`) }
}

export async function logoutOfficer(): Promise<void> {
  await fetch('/api/officer/logout', { method: 'POST', credentials: 'same-origin' })
}
