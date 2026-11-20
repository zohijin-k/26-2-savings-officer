import { useEffect, useState } from 'react'
import { fetchOfficerSummary, regenerateOfficerSummary, type DocStatus, type OfficerDocument, type OfficerSummary, type RoleKey } from '../../api.ts'
import { VISIBLE_POINTS, evidenceTone, generatedAtLabel, groupedEvidence, orderedNotes, pointHighlight, pointTarget, rankedPoints, shortDocLabel, summaryTag, verdictBand } from './summary-model.ts'

interface Props {
  applicationId: number
  role: RoleKey
  documents: OfficerDocument[]
  /** 저장된 AI 판정. 카드 맨 위 판정 띠의 색과 문구가 된다. */
  finalStatus: DocStatus | null
  /** 저장된 AI 권고 문구. 판정 배지 아래에 보인다. */
  recommendedAction: string
  /** 확인 포인트 클릭: 그 서류를 열고, field가 있으면 원본의 그 위치를 강조한다. */
  onJump: (doc: OfficerDocument, field: string | null, label: string) => void
}

/**
 * 최종 판정 패널의 AI 제안 자리 — AI 판정(배지·권고)과 종합의견을 한 박스에 담은 요약지.
 * 요약을 불러오지 못해도 판정 배지와 권고 문구는 저장값이라 항상 보인다.
 *
 * 첫 화면: 판정 띠(부적합/확인필요/적합) + 한 줄 결론 + 이유 한 줄 + 탈락 사유·확인 필요 목록.
 * 탈락 사유는 하나만으로도 제외되므로 맨 앞에 빨갛게, 개수와 상관없이 모두 보인다.
 * 자세한 문장·서류별·심사표는 누르거나 펼칠 때만 보인다. 근거는 코드 대신 담당자 문구로 보인다.
 * 저장된 판정을 풀어 쓴 참고 문구이며, 판정 값과 담당자 판단은 바꾸지 않는다.
 */
export default function AiSummaryCard({ applicationId, role, documents, finalStatus, recommendedAction, onJump }: Props) {
  const [summary, setSummary] = useState<OfficerSummary | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [active, setActive] = useState<number | null>(null)
  const [showAll, setShowAll] = useState(false)

  // 신청 건마다 key로 새로 마운트되므로 첫 상태가 곧 '불러오는 중'이다. 재시도는 retry()가 초기화한다.
  useEffect(() => {
    let live = true
    fetchOfficerSummary(applicationId, role).then((data) => {
      if (live) setSummary(data)
    }).catch((reason: unknown) => {
      if (live) setError(reason instanceof Error ? reason.message : String(reason))
    }).finally(() => {
      if (live) setBusy(false)
    })
    return () => { live = false }
  }, [applicationId, role, attempt])

  const retry = () => {
    setBusy(true)
    setError('')
    setAttempt((n) => n + 1)
  }
  const regenerate = async () => {
    setBusy(true)
    setError('')
    setActive(null)
    try {
      setSummary(await regenerateOfficerSummary(applicationId, role))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally { setBusy(false) }
  }

  const band = verdictBand(finalStatus)
  const action = recommendedAction ? <p className="ai-summary__action"><b>AI 권고</b>{recommendedAction}</p> : null

  if (!summary) {
    return <section className="ai-summary" aria-label="AI 종합의견" aria-busy={busy}>
      <div className="ai-summary__head"><span className="ai-summary__title">AI 종합의견</span></div>
      <div className="ai-summary__verdict">
        <span className={`ai-summary__badge ai-summary__badge--${band.tone}`}>{band.label}</span>
      </div>
      {action}
      {error ? <p className="ai-summary__error" role="alert">
        종합의견을 불러오지 못했습니다. <button type="button" className="btn btn--sm" onClick={retry}>다시 시도</button>
      </p> : <div className="ai-summary__skeleton" role="status">
        <span className="sr-only">종합의견을 불러오는 중입니다.</span>
        <i /><i /><i />
      </div>}
    </section>
  }

  const tag = summaryTag(summary)
  const notes = orderedNotes(summary, documents)
  const ranked = rankedPoints(summary.check_points, documents)
  const failCount = ranked.filter((row) => row.severity === 'fail').length
  const reviewCount = ranked.length - failCount
  const visible = Math.max(VISIBLE_POINTS, failCount)
  return <section className="ai-summary" aria-label="AI 종합의견" aria-busy={busy}>
    <div className="ai-summary__head">
      <span className="ai-summary__title">AI 종합의견</span>
      <span className={`ai-summary__tag ai-summary__tag--${tag.tone}`}>{tag.text}</span>
      <span className="ai-summary__time">{generatedAtLabel(summary.generated_at)}</span>
      <button type="button" className="ai-summary__refresh" disabled={busy} onClick={() => { void regenerate() }}
        aria-label="종합의견 다시 생성">{busy ? '생성 중…' : '다시 생성'}</button>
    </div>

    <div className="ai-summary__verdict">
      <span className={`ai-summary__badge ai-summary__badge--${band.tone}`}>{band.label}</span>
      <p className="ai-summary__headline">{summary.headline}</p>
    </div>
    {summary.status_explanation && <p className="ai-summary__why">{summary.status_explanation}</p>}
    {action}

    {ranked.length > 0 && <p className="ai-summary__counts">
      {failCount > 0 && <span className="ai-summary__count ai-summary__count--fail">탈락 사유 <b>{failCount}</b>건</span>}
      {reviewCount > 0 && <span className="ai-summary__count">확인 필요 <b>{reviewCount}</b>건</span>}
    </p>}
    {ranked.length > 0 ? <ol className="ai-summary__points" aria-label="탈락 사유와 담당자 확인할 것">
      {ranked.slice(0, showAll ? undefined : visible).map(({ point, severity }, index) => {
        const target = pointTarget(point, documents)
        const on = active === index
        return <li key={index}>
          <button type="button" className={`ai-summary__point ai-summary__point--${severity}${on ? ' ai-summary__point--on' : ''}`}
            aria-expanded={on} onClick={() => {
              setActive(index)
              if (target) onJump(target, pointHighlight(point, target), point.title)
            }}>
            <span className="ai-summary__num" aria-hidden="true">{index + 1}</span>
            <span className="ai-summary__body">
              <span className="ai-summary__line">
                <span className={`ai-summary__sev ai-summary__sev--${severity}`}>{severity === 'fail' ? '탈락 사유' : '확인 필요'}</span>
                <strong>{point.title}</strong>
                {target && <span className="ai-summary__doc">{shortDocLabel(target.label)}</span>}
              </span>
              <span className="ai-summary__evidence">{groupedEvidence(point).map((group) =>
                <span key={group.kindLabel} className={`ai-summary__ev ai-summary__ev--${evidenceTone(group.kind)}`}>
                  <b>{group.kindLabel}</b>{group.labels.join(', ')}
                </span>)}</span>
              {on && point.detail && <span className="ai-summary__detail">{point.detail}</span>}
            </span>
            {target && <span className="ai-summary__go" aria-hidden="true">원본 ›</span>}
          </button>
        </li>
      })}
    </ol> : <p className="ai-summary__clear">원본에서 따로 확인할 항목이 없습니다.</p>}
    {ranked.length > visible && <button type="button" className="ai-summary__toggle"
      onClick={() => setShowAll((value) => !value)}>
      {showAll ? '접기' : `확인 필요 ${ranked.length - visible}건 더 보기`}
    </button>}

    {(notes.length > 0 || summary.score_note) && <details className="ai-summary__more">
      <summary>자세히 · 서류별 판독 · 심사표</summary>
      {notes.length > 0 && <ul>{notes.map(({ doc, note }) => <li key={doc.document_id}>
        <button type="button" className="ai-summary__jump" onClick={() => onJump(doc, null, doc.label)}>{shortDocLabel(doc.label)}</button>
        <span>{note}</span>
      </li>)}</ul>}
      {summary.score_note && <p className="ai-summary__score"><b>심사표</b>{summary.score_note}</p>}
    </details>}

    <p className="ai-summary__foot">저장된 판정을 요약한 참고 문구입니다. 최종 판단은 담당자가 합니다.</p>
    {error && <p className="ai-summary__error" role="alert">{error}</p>}
  </section>
}
