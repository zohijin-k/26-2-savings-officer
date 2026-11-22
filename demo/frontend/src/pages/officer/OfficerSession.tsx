import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { isOfficerMockActive } from '../../api.ts'
import { loginOfficer, logoutOfficer, OFFICER_SESSION_EXPIRED, readOfficerSession } from '../../officer-session.ts'
import './officer.css'
import './officer-session.css'

type View =
  | { kind: 'checking' }
  | { kind: 'signed-in'; expiresAt: number }
  | { kind: 'signed-out'; notice: string }
  | { kind: 'unconfigured'; detail: string }
  | { kind: 'unreachable' }

const EXPIRED = '로그인 시간이 끝났습니다. 다시 로그인해 주세요.'
const UNREACHABLE = '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'

/**
 * 로그인한 담당자에게만 담당자 화면을 그린다. 따로 로그인 주소를 두지 않아서
 * 로그인하면 보던 주소(목록, 심사 상세)가 그대로 열린다. `?mock=1`은 확인 없이 그린다.
 */
export default function OfficerSession({ children, headerHost }: { children: ReactNode; headerHost: HTMLElement | null }) {
  const [mock] = useState(isOfficerMockActive)
  const [view, setView] = useState<View>({ kind: 'checking' })
  const [check, setCheck] = useState(0)
  const [slowCheck, setSlowCheck] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (mock) return
    let active = true
    readOfficerSession().then((state) => {
      if (!active) return
      if (state.kind === 'signed-out') setView((current) => ({ kind: 'signed-out', notice: current.kind === 'signed-in' ? EXPIRED : '' }))
      else setView(state)
    }).catch(() => { if (active) setView({ kind: 'unreachable' }) })
    return () => { active = false }
  }, [mock, check])

  // 담당자 API가 401·503을 내면(api.ts) 서버에 다시 물어 로그인 칸이나 설정 안내로 바꾼다.
  useEffect(() => {
    if (mock) return
    const recheck = () => setCheck((value) => value + 1)
    window.addEventListener(OFFICER_SESSION_EXPIRED, recheck)
    return () => window.removeEventListener(OFFICER_SESSION_EXPIRED, recheck)
  }, [mock])

  const expiresAt = view.kind === 'signed-in' ? view.expiresAt : null
  useEffect(() => {
    if (expiresAt === null) return
    const timer = setTimeout(() => setView({ kind: 'signed-out', notice: EXPIRED }), Math.max(0, expiresAt * 1000 - Date.now()))
    return () => clearTimeout(timer)
  }, [expiresAt])

  // 첫 확인은 보통 바로 끝난다. 늦어질 때만 안내를 보여 새로고침마다 화면이 깜빡이지 않게 한다.
  useEffect(() => {
    const timer = setTimeout(() => setSlowCheck(true), 400)
    return () => clearTimeout(timer)
  }, [])

  if (mock) return children

  const login = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const result = await loginOfficer(password)
      setPassword('')
      if (result.kind === 'rejected') setError(result.detail)
      else setView(result)
    } catch {
      setError(UNREACHABLE)
    } finally {
      setBusy(false)
    }
  }

  const logout = async () => {
    if (busy) return
    setBusy(true)
    let notice = '로그아웃했습니다.'
    try {
      await logoutOfficer()
    } catch {
      notice = '서버에 연결하지 못해 로그아웃을 확인하지 못했습니다.'
    } finally {
      setBusy(false)
    }
    setView({ kind: 'signed-out', notice })
  }

  if (view.kind === 'signed-in') {
    const bar = (
      <div className="officer-session-bar">
        <span className="officer-session-bar__label">담당자 로그인됨</span>
        <button type="button" className="btn btn--sm" disabled={busy} onClick={() => void logout()}>로그아웃</button>
      </div>
    )
    return <>{headerHost && createPortal(bar, headerHost)}{children}</>
  }

  if (view.kind === 'checking') {
    return <main className="officer-login" aria-busy="true">
      {slowCheck && <p className="officer-login__status" role="status">로그인 상태를 확인하고 있습니다.</p>}
    </main>
  }

  return (
    <main className="officer-login">
      <section className="officer-login__card" aria-labelledby="officer-login-title">
        <p className="officer-login__eyebrow">전북청년 함께 두배적금 · 담당자</p>
        <h1 id="officer-login-title">담당자 로그인</h1>
        {view.kind === 'unconfigured' && <>
          <p role="alert">{view.detail}</p>
          <button type="button" className="btn" onClick={() => setCheck((value) => value + 1)}>다시 확인</button>
        </>}
        {view.kind === 'unreachable' && <>
          <p role="alert">{UNREACHABLE}</p>
          <button type="button" className="btn" onClick={() => setCheck((value) => value + 1)}>다시 시도</button>
        </>}
        {view.kind === 'signed-out' && <form onSubmit={(event) => void login(event)}>
          {view.notice && !error && <p className="officer-login__status" role="status">{view.notice}</p>}
          <label htmlFor="officer-password">담당자 비밀번호</label>
          <input id="officer-password" type="password" autoComplete="current-password" required autoFocus
            aria-invalid={Boolean(error)} aria-describedby={error ? 'officer-login-error' : undefined}
            value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} />
          {error && <p id="officer-login-error" role="alert">{error}</p>}
          <button className="btn btn--primary" type="submit" disabled={busy}>{busy ? '확인 중' : '로그인'}</button>
        </form>}
      </section>
    </main>
  )
}
