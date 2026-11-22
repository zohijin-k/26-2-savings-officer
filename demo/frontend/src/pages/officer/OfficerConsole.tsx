import { confirmOfficerLeave, handleOfficerHistory } from './review-navigation.ts'
import { useEffect, useState } from 'react'
import {
  fetchOfficerList, fetchOfficerRoles, fetchReviewDetail, isOfficerMockActive, postBulkDecision,
  ROLE_KEYS, type DecisionKey, type OfficerList, type OfficerRole, type RoleKey,
} from '../../api.ts'
import { officerPageUrl, readOfficerPage, type OfficerPage } from '../../navigation-url.ts'
import ApplicationList from './ApplicationList.tsx'
import ReviewDetail from './ReviewDetail.tsx'
import { collectOfficerList, firstDocument } from './list-model.ts'
import './officer.css'

const PROGRAM_TITLE = '전북청년 함께 두배적금'
/** 시행지침 신청 기간. 날짜만 비교한다. */
const APPLY_PERIOD = ['2026-03-03', '2026-03-16'] as const
const ROLE_STORAGE = 'officer-role'

function programPhase(today: string): { label: string; tone: string } {
  if (today < APPLY_PERIOD[0]) return { label: '접수 예정', tone: 'info' }
  if (today <= APPLY_PERIOD[1]) return { label: '접수 중', tone: 'success' }
  return { label: '접수 마감', tone: 'neutral' }
}

function readRole(): RoleKey {
  try {
    const saved = window.sessionStorage.getItem(ROLE_STORAGE)
    return ROLE_KEYS.includes(saved as RoleKey) ? saved as RoleKey : 'province'
  } catch { return 'province' }
}

function localDay(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export default function OfficerConsole() {
  const [page, setPage] = useState(() => readOfficerPage(new URL(window.location.href)))
  const [roles, setRoles] = useState<OfficerRole[]>([])
  const [roleKey, setRoleKey] = useState<RoleKey>(readRole)
  const [scope, setScope] = useState<{ region?: string; town?: string }>({})
  const [list, setList] = useState<OfficerList | null>(null)
  const [loadedKey, setLoadedKey] = useState('')
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const mock = isOfficerMockActive()
  const phase = programPhase(localDay())

  useEffect(() => {
    const onHistory = (event: PopStateEvent) => { if (!handleOfficerHistory(event)) setPage(readOfficerPage(new URL(window.location.href))) }
    window.addEventListener('popstate', onHistory)
    return () => window.removeEventListener('popstate', onHistory)
  }, [])
  useEffect(() => {
    const url = officerPageUrl(page, mock)
    if (`${window.location.pathname}${window.location.search}` !== url) window.history.replaceState({ ...window.history.state, officerIndex: Number(window.history.state?.officerIndex ?? 0) }, '', url)
  }, [page, mock])
  useEffect(() => {
    let active = true
    fetchOfficerRoles().then((data) => { if (active) setRoles(data) }).catch(() => { /* 역할 이름은 목록 응답으로도 알 수 있다 */ })
    return () => { active = false }
  }, [])
  const requestKey = `${roleKey}|${scope.region ?? ''}|${scope.town ?? ''}|${reload}`
  const loading = loadedKey !== requestKey
  useEffect(() => {
    let active = true
    collectOfficerList((next) => fetchOfficerList({ role: roleKey, ...scope }, next)).then((data) => {
      if (active) { setList(data); setError(''); setLoadedKey(requestKey) }
    }).catch((reason: unknown) => {
      if (active) { setError(reason instanceof Error ? reason.message : String(reason)); setLoadedKey(requestKey) }
    })
    return () => { active = false }
  }, [roleKey, scope, requestKey])

  const navigate = (next: OfficerPage) => {
    if (next.applicationId !== page.applicationId && !confirmOfficerLeave()) return
    window.history.pushState({ ...window.history.state, officerIndex: Number(window.history.state?.officerIndex ?? 0) + 1 }, '', officerPageUrl(next, mock))
    setPage(next)
    window.dispatchEvent(new Event('officer:route'))
    window.scrollTo({ top: 0 })
  }
  const switchRole = (next: RoleKey) => {
    if (next === roleKey || !confirmOfficerLeave()) return
    try { window.sessionStorage.setItem(ROLE_STORAGE, next) } catch { /* 저장 못 해도 전환은 된다 */ }
    setRoleKey(next)
    setScope({})
    setNotice('')
  }
  const bulk = async (ids: number[], decision: DecisionKey) => {
    setBusy(true)
    setNotice('')
    try {
      const { processed } = await postBulkDecision(ids, decision, `${list?.role?.name ?? ''} 일괄 처리`.trim(), roleKey, Object.fromEntries((list?.rows ?? []).filter((row) => ids.includes(row.application_id)).map((row) => [row.application_id, row.revision])))
      setNotice(`${processed}건을 처리했습니다.`)
      setReload((value) => value + 1)
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : String(reason))
    } finally { setBusy(false) }
  }

  const activeRole = list?.role?.key === roleKey ? list.role : roles.find((role) => role.key === roleKey) ?? null
  const roleOptions = roles.length ? roles : activeRole ? [activeRole] : []

  return <main className="officer">
    <header className="officer__program">
      <h1>{PROGRAM_TITLE}</h1>
      <span className={`officer__phase officer__phase--${phase.tone}`}>{phase.label}</span>
    </header>
    {mock && <p className="officer__mock">
      <strong>목업 데이터</strong> 합성 신청 건으로 채운 화면입니다. 판단 버튼은 눌리지만 브라우저 메모리에만 남고 새로고침하면 되돌아갑니다.
      주소에서 <code>?mock=1</code>을 지우면 실제 데이터만 봅니다.
    </p>}

    {page.applicationId !== null ? <ReviewDetail
      key={`${page.applicationId}:${roleKey}`}
      role={roleKey}
      applicationId={page.applicationId} documentId={page.documentId} slotKey={page.slotKey}
      onBack={() => { setReload((value) => value + 1); navigate({ applicationId: null, documentId: null, slotKey: null }) }}
      onSelect={(documentId, slotKey) => navigate({ ...page, documentId, slotKey })}
    /> : null}
    <div hidden={page.applicationId !== null} inert={page.applicationId !== null}>
      <div className="officer__role-bar">
        <div className="officer__roles" role="group" aria-label="역할 전환">
          {roleOptions.map((role) => <button key={role.key} type="button" aria-pressed={role.key === roleKey}
            className={role.key === roleKey ? 'officer__role officer__role--on' : 'officer__role'}
            onClick={() => switchRole(role.key as RoleKey)}>{role.name}</button>)}
        </div>
        {activeRole && <p className="officer__scope">
          <strong>{activeRole.stage ?? activeRole.name}</strong>{activeRole.scope && <> · 보이는 범위: {activeRole.scope}</>}
          {list?.scope?.region && activeRole.requires_region && <> · {list.scope.region}{activeRole.requires_town && list.scope.town ? ` ${list.scope.town}` : ''}</>}
        </p>}
      </div>
      <p className="officer__desc">{activeRole?.notes?.length ? activeRole.notes.join(' ') : '두배적금 신청 서류와 심사표 점수를 확인합니다.'}</p>

      {error ? <p className="officer__error" role="alert">
        {error} <button type="button" className="alist__link" onClick={() => setReload((value) => value + 1)}>다시 시도</button>
      </p> : list === null ? <p className="officer__loading" role="status">신청 목록을 불러오는 중입니다.</p> : <div aria-busy={loading || undefined} className={loading ? 'officer__list officer__list--loading' : 'officer__list'}>
        <ApplicationList
          key={roleKey}
          rows={list.rows}
          role={activeRole}
          scope={list.scope ?? null}
          busy={busy}
          notice={notice}
          onScope={(next) => setScope(next)}
          onBulk={bulk}
          loadReasons={(id) => fetchReviewDetail(id, roleKey)}
          onOpen={(row) => {
            const doc = firstDocument(row)
            navigate({ applicationId: row.application_id, documentId: doc?.documentId ?? null, slotKey: doc?.slotKey ?? null })
          }}
        />
      </div>}
    </div>
  </main>
}
