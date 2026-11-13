import { useEffect, useState } from 'react'
import { fetchOfficerList, isOfficerMockActive, type OfficerRow } from '../../api.ts'
import { officerPageUrl, readOfficerPage, type OfficerPage } from '../../navigation-url.ts'
import ApplicationList from './ApplicationList.tsx'
import ReviewDetail from './ReviewDetail.tsx'
import { collectOfficerRows, groupOfficerDocuments } from './document-groups.ts'
import './officer.css'

export default function OfficerConsole() {
  const [page, setPage] = useState(() => readOfficerPage(new URL(window.location.href)))
  const [rows, setRows] = useState<OfficerRow[] | null>(null)
  const [error, setError] = useState('')
  const mock = isOfficerMockActive()
  useEffect(() => {
    const onHistory = () => setPage(readOfficerPage(new URL(window.location.href)))
    window.addEventListener('popstate', onHistory)
    return () => window.removeEventListener('popstate', onHistory)
  }, [])
  useEffect(() => {
    const url = officerPageUrl(page, mock)
    if (`${window.location.pathname}${window.location.search}` !== url) window.history.replaceState(null, '', url)
  }, [page, mock])
  useEffect(() => {
    let active = true
    collectOfficerRows(fetchOfficerList).then((data) => {
      if (active) { setRows(data); setError('') }
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : String(reason))
    })
    return () => { active = false }
  }, [])
  const navigate = (next: OfficerPage) => {
    window.history.pushState(null, '', officerPageUrl(next, mock))
    setPage(next)
    window.scrollTo({ top: 0 })
  }
  if (page.applicationId !== null) return <main className="officer"><ReviewDetail
    key={page.applicationId}
    applicationId={page.applicationId} documentId={page.documentId} slotKey={page.slotKey}
    onBack={() => navigate({ applicationId: null, documentId: null, slotKey: null })}
    onSelect={(documentId, slotKey) => navigate({ ...page, documentId, slotKey })}
  /></main>
  return <main className="officer">
    <h1>서류 검토</h1>
    {mock && <p className="officer__mock">합성 목업 미리보기 · 변경은 브라우저 메모리에만 남습니다.</p>}
    {error ? <p className="officer__error" role="alert">{error}</p> : rows === null ? <p role="status">서류 목록을 불러오는 중입니다.</p> : <ApplicationList
      groups={groupOfficerDocuments(rows)}
      onOpen={(item) => navigate({ applicationId: item.applicationId, documentId: item.documentId, slotKey: item.slotKey })}
    />}
  </main>
}
