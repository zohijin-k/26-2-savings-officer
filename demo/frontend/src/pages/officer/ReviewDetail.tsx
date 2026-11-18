import { useEffect, useRef, useState } from 'react'
import { fetchReviewDetail, postDecision, type BBox, type DecisionKey, type DocStatus, type OfficerDocument, type ReviewDetailData, type RoleKey, type ScoreItemRow } from '../../api.ts'
import StatusBadge from '../../components/StatusBadge.tsx'
import AiSummaryCard from './AiSummaryCard.tsx'
import DocumentViewer from './DocumentViewer.tsx'
import ScoreSheet6 from './ScoreSheet6.tsx'
import { selectOfficerDocument } from './list-model.ts'
import { tiebreakParts } from './tiebreak.ts'

interface Props {
  role: RoleKey
  applicationId: number
  documentId: number | null
  slotKey: string | null
  onBack: () => void
  onSelect: (documentId: number, slotKey: string) => void
}

const TAB_STATUS: Record<DocStatus, { icon: string; label: string }> = {
  PASS: { icon: '✓', label: '적합' },
  NEEDS_REVIEW: { icon: '?', label: '확인필요' },
  FAIL: { icon: '!', label: '부적합' },
}

const BUTTON_TONE: Record<string, string> = {
  primary: 'btn btn--primary',
  danger: 'btn btn--danger',
  neutral: 'btn',
}

export default function ReviewDetail({ role, applicationId, documentId, slotKey, onBack, onSelect }: Props) {
  const [detail, setDetail] = useState<ReviewDetailData | null>(null)
  const [error, setError] = useState('')
  const [memo, setMemo] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [focus, setFocus] = useState<{ documentId: number; bbox: BBox; label: string; scoreKey: string | null } | null>(null)
  useEffect(() => {
    let active = true
    fetchReviewDetail(applicationId, role).then((data) => {
      if (!active) return
      if (data.program_code !== 'double_savings') {
        setError('두배적금 신청 건이 아닙니다.')
        return
      }
      setDetail(data)
      setMemo(data.decision.memo ?? '')
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : String(reason))
    })
    return () => { active = false }
  }, [applicationId, role])

  const activeDoc = detail ? selectOfficerDocument(detail.documents, documentId, slotKey) : null
  const decide = async (decision: DecisionKey) => {
    setSaving(true)
    setNotice('')
    try {
      await postDecision(applicationId, decision, memo, role)
      setDetail(await fetchReviewDetail(applicationId, role))
      setNotice('담당자 판단을 저장했습니다.')
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : String(reason))
    } finally { setSaving(false) }
  }
  const focusScore = (item: ScoreItemRow) => {
    if (!detail || item.source_document_id === null) return
    const doc = detail.documents.find((candidate) => candidate.document_id === item.source_document_id)
    if (!doc) return
    setFocus(item.bbox ? {
      documentId: doc.document_id, bbox: item.bbox, label: item.label, scoreKey: item.key,
    } : null)
    onSelect(doc.document_id, doc.slot_key)
  }
  // AI 종합의견의 확인 포인트 → 원본. 같은 서류가 이미 열려 있어도 반응이 보이도록
  // 위치가 있으면 강조하고, 없으면 원본 영역을 잠깐 표시한다.
  const [pulse, setPulse] = useState(0)
  const leftRef = useRef<HTMLElement>(null)
  const jumpToOriginal = (doc: OfficerDocument, field: string | null, label: string) => {
    const bbox = field ? doc.bboxes[field] : undefined
    setFocus(bbox ? { documentId: doc.document_id, bbox, label, scoreKey: null } : null)
    setPulse((n) => n + 1)
    leftRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    onSelect(doc.document_id, doc.slot_key)
  }
  const tiebreak = detail ? tiebreakParts(detail.score_sheet) : null

  return <div className="review">
    <header className="review__head">
      <button type="button" className="btn btn--sm" onClick={onBack}>← 신청 목록</button>
      {detail && <><strong>{detail.name}</strong><span>{detail.application_no}</span><span>{detail.region} {detail.town}</span></>}
    </header>
    {error ? <p className="officer__error" role="alert">{error}</p> : !detail ? <p role="status">서류를 불러오는 중입니다.</p> : <>
      <nav className="review__tabs" aria-label="신청 서류">
        {detail.documents.map((doc) => {
          const status = doc.status ? TAB_STATUS[doc.status] : null
          const on = activeDoc?.document_id === doc.document_id
          return <button key={doc.document_id} type="button" aria-current={on ? 'true' : undefined}
            className={on ? 'review__tab review__tab--on' : 'review__tab'}
            onClick={() => onSelect(doc.document_id, doc.slot_key)}>
            <span className={`review__tab-status review__tab-status--${doc.status?.toLowerCase() ?? 'none'}`} aria-hidden="true">{status?.icon ?? '–'}</span>
            {doc.label}
            <span className="sr-only">({status?.label ?? '판정 없음'})</span>
          </button>
        })}
      </nav>
      <div className="review__split">
        <section className="review__left" aria-label="신청자 원본 서류" ref={leftRef}>
          {pulse > 0 && <div key={pulse} className="review__pulse" aria-hidden="true" />}
          {activeDoc ? <DocumentViewer doc={activeDoc}
            highlight={focus?.documentId === activeDoc.document_id ? focus.bbox : null}
            highlightLabel={focus?.documentId === activeDoc.document_id ? focus.label : undefined} /> : <p className="empty-state">
            {slotKey ? '이 항목은 원본 서류가 없습니다. 미제출 또는 삭제 여부를 확인해 주세요.' : '확인할 서류를 선택해 주세요.'}
          </p>}
        </section>
        <section className="review__right" aria-label="판독 결과">
          <section className="panel verdict" aria-labelledby="panel-verdict">
            <div className="panel__head"><h2 id="panel-verdict"><span className="panel__step">1</span>최종 판정</h2></div>
            <AiSummaryCard key={applicationId} applicationId={applicationId} role={role}
              documents={detail.documents} onJump={jumpToOriginal} />
            <div className="verdict__grid">
              <div className="verdict__box verdict__box--ai">
                <span className="verdict__tag">AI 제안</span>
                {detail.ai.final_status ? <StatusBadge status={detail.ai.final_status} /> : <span className="verdict__value">미심사</span>}
                {detail.ai.recommended_action && <p>{detail.ai.recommended_action}</p>}
              </div>
              <div className="verdict__box verdict__box--officer">
                <span className="verdict__tag">담당자 판단</span>
                <span className="verdict__value">{detail.decision.label}</span>
                <p>최종 판단은 담당자가 합니다.</p>
              </div>
            </div>
            <p className="notice notice--warning" role="note">
              <span className="notice__icon" aria-hidden="true">!</span>
              <span>보완 요청이 없는 사업입니다. 서류가 미비하면 보완 없이 선발에서 제외됩니다.</span>
            </p>
            <details className="verdict__reasons">
              <summary>신청 전체 사유 {detail.ai.reasons.length}건</summary>
              {detail.ai.reasons.length ? <ul className="reasons">{detail.ai.reasons.map((reason, index) => <li key={index}>
                <code>{reason.code}</code> {reason.message}{reason.doc_type && <em> ({reason.doc_type})</em>}
              </li>)}</ul> : <p className="muted">저장된 신청 전체 사유가 없습니다.</p>}
            </details>
          </section>

          {detail.score_sheet.items.length > 0 && <section className="panel" aria-labelledby="panel-score">
            <div className="panel__head"><h2 id="panel-score"><span className="panel__step">2</span>심사표<small>서식6 · 100점</small></h2></div>
            <p className="score-summary"><strong>{detail.score_sheet.total}</strong><span>/ {detail.score_sheet.max_total}점</span></p>
            {tiebreak && <>
              <p className="tiebreak__label">동점자 비교 값 (우선순위 순)</p>
              <ul className="tiebreak">{tiebreak.map((part) => <li key={part}>{part}</li>)}</ul>
            </>}
            <ScoreSheet6 sheet={detail.score_sheet} activeKey={focus?.scoreKey ?? null} onSelect={focusScore} />
          </section>}

          <section className="panel" aria-labelledby="panel-ocr">
            <div className="panel__head">
              <h2 id="panel-ocr"><span className="panel__step">3</span>판독 결과{activeDoc && <small>{activeDoc.label}</small>}</h2>
              {activeDoc?.status && <StatusBadge status={activeDoc.status} />}
            </div>
            {activeDoc ? <>
              {activeDoc.findings.length ? <ul className="reasons">{activeDoc.findings.map((finding, index) => <li key={index}>
                <code>{finding.code}</code> {finding.message}
                {finding.how_to_fix && <p>{finding.how_to_fix}</p>}
                {finding.link && /^https?:\/\//.test(finding.link) && <a href={finding.link} target="_blank" rel="noreferrer">기존 안내 보기</a>}
              </li>)}</ul> : <p className="muted">이 서류에 저장된 확인 사유가 없습니다.</p>}
              {activeDoc.ocr_quality_note && <p className="ocr-note">{activeDoc.ocr_quality_note}</p>}
              {activeDoc.ocr_fallback_reason && <p className="ocr-note">{activeDoc.ocr_fallback_reason}</p>}
              <dl className="fields">{Object.entries(activeDoc.extracted).map(([key, value]) => <div key={key}>
                <dt>{key}</dt><dd><span>{value}</span>{activeDoc.bboxes[key] && <button type="button" className="btn btn--sm" onClick={() => setFocus({ documentId: activeDoc.document_id, bbox: activeDoc.bboxes[key], label: key, scoreKey: null })}>원본 위치</button>}</dd>
              </div>)}</dl>
            </> : <p className="muted">원본 없는 항목의 기존 저장 사유는 위 신청 전체 사유에서 확인할 수 있습니다.</p>}
          </section>

          <section className="panel decision" aria-labelledby="panel-decision">
            <div className="panel__head">
              <h2 id="panel-decision"><span className="panel__step">4</span>담당자 처리</h2>
              <span className="muted">현재 상태: {detail.decision.label}</span>
            </div>
            <label>검토 메모<textarea value={memo} onChange={(event) => setMemo(event.target.value)} /></label>
            <div className="decision__actions">{detail.role.actions.map((action) => <button key={action.key} type="button"
              className={BUTTON_TONE[action.tone] ?? 'btn'} disabled={saving}
              onClick={() => { void decide(action.key) }}>{action.label}</button>)}</div>
            {notice && <p className="decision__notice" role="status">{notice}</p>}
          </section>
        </section>
      </div>
    </>}
  </div>
}
