import { useEffect, useState } from 'react'
import { fetchReviewDetail, postDecision, type BBox, type DecisionKey, type ReviewDetailData, type ScoreItemRow } from '../../api.ts'
import StatusBadge from '../../components/StatusBadge.tsx'
import DocumentViewer from './DocumentViewer.tsx'
import ScoreSheet6 from './ScoreSheet6.tsx'
import { selectOfficerDocument } from './document-groups.ts'

interface Props {
  applicationId: number
  documentId: number | null
  slotKey: string | null
  onBack: () => void
  onSelect: (documentId: number, slotKey: string) => void
}

export default function ReviewDetail({ applicationId, documentId, slotKey, onBack, onSelect }: Props) {
  const [detail, setDetail] = useState<ReviewDetailData | null>(null)
  const [error, setError] = useState('')
  const [memo, setMemo] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [focus, setFocus] = useState<{ documentId: number; bbox: BBox; label: string; scoreKey: string | null } | null>(null)
  useEffect(() => {
    let active = true
    fetchReviewDetail(applicationId).then((data) => {
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
  }, [applicationId])

  const activeDoc = detail ? selectOfficerDocument(detail.documents, documentId, slotKey) : null
  const decide = async (decision: DecisionKey) => {
    setSaving(true)
    setNotice('')
    try {
      await postDecision(applicationId, decision, memo)
      setDetail(await fetchReviewDetail(applicationId))
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

  return <div className="review">
    <header className="review__head">
      <button type="button" className="review__back" onClick={onBack}>← 서류 목록</button>
      {detail && <><strong>{detail.name}</strong><span>{detail.application_no}</span><span>{detail.region} {detail.town}</span></>}
    </header>
    {error ? <p className="officer__error" role="alert">{error}</p> : !detail ? <p role="status">서류를 불러오는 중입니다.</p> : <>
      <nav className="review__tabs" aria-label="신청 서류">
        {detail.documents.map((doc) => <button key={doc.document_id} type="button"
          className={activeDoc?.document_id === doc.document_id ? 'review__tab review__tab--on' : 'review__tab'}
          onClick={() => onSelect(doc.document_id, doc.slot_key)}>{doc.label}</button>)}
      </nav>
      <div className="review__split">
        <section className="review__left" aria-label="신청자 원본 서류">
          {activeDoc ? <DocumentViewer doc={activeDoc}
            highlight={focus?.documentId === activeDoc.document_id ? focus.bbox : null}
            highlightLabel={focus?.documentId === activeDoc.document_id ? focus.label : undefined} /> : <p className="empty-state">
            {slotKey ? '이 항목은 원본 서류가 없습니다. 미제출 또는 삭제 여부를 확인해 주세요.' : '확인할 서류를 선택해 주세요.'}
          </p>}
        </section>
        <section className="review__right" aria-label="확인 사유">
          <section className="panel">
            <h2>확인 사유{activeDoc ? ` — ${activeDoc.label}` : ''}</h2>
            {activeDoc ? <>
              {activeDoc.status && <StatusBadge status={activeDoc.status} />}
              {activeDoc.findings.length ? <ul className="reasons">{activeDoc.findings.map((finding, index) => <li key={index}>
                <code>{finding.code}</code> {finding.message}
                {finding.how_to_fix && <p>{finding.how_to_fix}</p>}
                {finding.link && /^https?:\/\//.test(finding.link) && <a href={finding.link} target="_blank" rel="noreferrer">기존 안내 보기</a>}
              </li>)}</ul> : <p className="muted">이 서류에 저장된 확인 사유가 없습니다.</p>}
              {activeDoc.ocr_quality_note && <p>{activeDoc.ocr_quality_note}</p>}
              {activeDoc.ocr_fallback_reason && <p>{activeDoc.ocr_fallback_reason}</p>}
              <dl className="fields">{Object.entries(activeDoc.extracted).map(([key, value]) => <div key={key}>
                <dt>{key}</dt><dd>{value}{activeDoc.bboxes[key] && <button type="button" onClick={() => setFocus({ documentId: activeDoc.document_id, bbox: activeDoc.bboxes[key], label: key, scoreKey: null })}>원본 위치</button>}</dd>
              </div>)}</dl>
            </> : <p className="muted">원본 없는 항목의 기존 저장 사유는 아래 신청 전체 사유에서 확인할 수 있습니다.</p>}
          </section>
          <details className="panel">
            <summary>신청 전체 사유</summary>
            {detail.ai.final_status && <StatusBadge status={detail.ai.final_status} />}
            <p>{detail.ai.recommended_action}</p>
            {detail.ai.reasons.length ? <ul className="reasons">{detail.ai.reasons.map((reason, index) => <li key={index}>
              <code>{reason.code}</code> {reason.message}{reason.doc_type && <em> ({reason.doc_type})</em>}
            </li>)}</ul> : <p className="muted">저장된 신청 전체 사유가 없습니다.</p>}
          </details>
          {detail.score_sheet.items.length > 0 && <details className="panel"><summary>심사표 (서식6)</summary>
            <ScoreSheet6 sheet={detail.score_sheet} activeKey={focus?.scoreKey ?? null} onSelect={focusScore} />
          </details>}
          <section className="panel decision">
            <h2>담당자 판단</h2>
            <p>현재 상태: {detail.decision.label}</p>
            <label>검토 메모<textarea value={memo} onChange={(event) => setMemo(event.target.value)} /></label>
            <div className="decision__actions">{detail.role.actions.map((action) => <button key={action.key} type="button" disabled={saving} onClick={() => { void decide(action.key) }}>{action.label}</button>)}</div>
            {notice && <p role="status">{notice}</p>}
          </section>
        </section>
      </div>
    </>}
  </div>
}
