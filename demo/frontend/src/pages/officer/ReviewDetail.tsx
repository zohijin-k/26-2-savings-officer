import { useRef, useState } from 'react'
import { fetchReviewDetail, postDecision, type BBox, type DecisionKey, type DocStatus, type OfficerDocument, type RoleKey, type ScoreItemRow } from '../../api.ts'
import StatusBadge from '../../components/StatusBadge.tsx'
import AiSummaryCard from './AiSummaryCard.tsx'
import DocumentViewer from './DocumentViewer.tsx'
import ScoreSheet6 from './ScoreSheet6.tsx'
import { fieldLabel, formatField, plainText, reasonTitle, type FieldView } from './field-format.ts'
import { selectOfficerDocument } from './list-model.ts'
import { useReviewDraft } from './useReviewDraft.ts'
import { reviewSaveError } from './review-save.ts'
import ReviewSaveStatus from './ReviewSaveStatus.tsx'
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

/** 판독 결과 한 칸. JSON 값은 field-format에서 문장·목록·표로 풀어 온다. */
function FieldValue({ view }: { view: Exclude<FieldView, { kind: 'hidden' }> }) {
  const notes = view.notes?.length ? <ul className="field-value__notes">{view.notes.map((note) => <li key={note}>{note}</li>)}</ul> : null
  if (view.kind === 'text') return <div className="field-value"><span>{view.text}</span>{notes}</div>
  if (view.kind === 'list') return <div className="field-value"><ul className="field-value__list">{view.items.map((item, index) => <li key={index}>{item}</li>)}</ul>{notes}</div>
  if (view.kind === 'pairs') return <div className="field-value"><dl className="field-value__pairs">{view.rows.map(([name, value], index) => <div key={index}>
    <dt>{name}</dt><dd>{value}</dd>
  </div>)}</dl>{notes}</div>
  return <div className="field-value">
    <div className="field-value__scroll"><table className="field-value__table">
      <thead><tr>{view.head.map((head) => <th key={head} scope="col">{head}</th>)}</tr></thead>
      <tbody>{view.rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column}>{cell}</td>)}</tr>)}</tbody>
    </table></div>
    {notes}
  </div>
}

export default function ReviewDetail({ role, applicationId, documentId, slotKey, onBack, onSelect }: Props) {
  const draft = useReviewDraft({
    load: async () => {
      const data = await fetchReviewDetail(applicationId, role)
      if (data.program_code !== 'double_savings') throw new Error('두배적금 신청 건이 아닙니다.')
      return data
    },
    write: (decision, memo, expectedRevision) => postDecision(applicationId, decision as DecisionKey, memo, role, expectedRevision),
    errorText: reviewSaveError,
  })
  const { data: detail, memo, busy: saving, loadError: error, editor } = draft
  const [focus, setFocus] = useState<{ documentId: number; bbox: BBox; label: string; scoreKey: string | null } | null>(null)
  const [formNo, setFormNo] = useState<string | null>(null)

  const activeDoc = detail && formNo === null ? selectOfficerDocument(detail.documents, documentId, slotKey) : null
  const activeForm = detail?.forms.find((form) => form.form_no === formNo)
  const viewerDoc = activeForm ? { ...activeForm, file_format: 'pdf' } : activeDoc
  const selectOriginal = (id: number, slot: string) => {
    setFormNo(null)
    onSelect(id, slot)
  }
  const focusScore = (item: ScoreItemRow) => {
    if (!detail || item.source_document_id === null) return
    const doc = detail.documents.find((candidate) => candidate.document_id === item.source_document_id)
    if (!doc) return
    setFocus(item.bbox ? {
      documentId: doc.document_id, bbox: item.bbox, label: item.label, scoreKey: item.key,
    } : null)
    selectOriginal(doc.document_id, doc.slot_key)
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
    selectOriginal(doc.document_id, doc.slot_key)
  }
  const tiebreak = detail ? tiebreakParts(detail.score_sheet) : null
  // 서류 버튼 줄: ←/→로 이전·다음 서류, Home/End로 처음·마지막 서류를 연다. 포커스도 함께 옮긴다.
  const moveTab = (event: React.KeyboardEvent<HTMLElement>) => {
    if (!detail || !detail.documents.length) return
    const docs = detail.documents
    const current = Math.max(0, docs.findIndex((doc) => doc.document_id === activeDoc?.document_id))
    const next = event.key === 'ArrowRight' ? (current + 1) % docs.length
      : event.key === 'ArrowLeft' ? (current - 1 + docs.length) % docs.length
        : event.key === 'Home' ? 0 : event.key === 'End' ? docs.length - 1 : null
    if (next === null) return
    event.preventDefault()
    selectOriginal(docs[next].document_id, docs[next].slot_key)
    event.currentTarget.querySelectorAll<HTMLButtonElement>('.review__tab')[next]?.focus()
  }

  return <div className="review">
    <header className="review__head">
      <button type="button" className="btn btn--sm" onClick={onBack}>← 신청 목록</button>
      {detail && <><strong>{detail.name}</strong><span>{detail.application_no}</span><span>{detail.region} {detail.town}</span></>}
    </header>
    {error ? <p className="officer__error" role="alert">{error} <button type="button" className="btn" onClick={() => void editor.check()}>다시 시도</button></p> : !detail ? <p role="status">서류를 불러오는 중입니다.</p> : <>
      <nav className="review__tabs" aria-label="신청 서류 (← → 키로 이동)" onKeyDown={moveTab}>
        {detail.documents.map((doc) => {
          const status = doc.status ? TAB_STATUS[doc.status] : null
          const on = activeDoc?.document_id === doc.document_id
          return <button key={doc.document_id} type="button" aria-current={on ? 'true' : undefined}
            className={`review__tab review__tab--${doc.status?.toLowerCase() ?? 'none'}${on ? ' review__tab--on' : ''}`}
            onClick={() => selectOriginal(doc.document_id, doc.slot_key)}>
            <span className={`review__tab-status review__tab-status--${doc.status?.toLowerCase() ?? 'none'}`} aria-hidden="true">{status?.icon ?? '–'}</span>
            {doc.label}
            <span className="sr-only">({status?.label ?? '판정 없음'})</span>
          </button>
        })}
      </nav>
      {detail.forms.length > 0 && <nav className="review__tabs" aria-label="작성서식">
        <strong>작성서식</strong>
        {detail.forms.map((form) => <button key={form.form_no} type="button"
          className={`review__tab${formNo === form.form_no ? ' review__tab--on' : ''}`}
          aria-current={formNo === form.form_no ? 'true' : undefined}
          onClick={() => { setFormNo(form.form_no); setFocus(null) }}>{form.label}</button>)}
      </nav>}
      <div className="review__split">
        <section className="review__left" aria-label="신청자 원본 서류" ref={leftRef}>
          {pulse > 0 && <div key={pulse} className="review__pulse" aria-hidden="true" />}
          {viewerDoc ? <DocumentViewer doc={viewerDoc}
            highlight={activeDoc && focus?.documentId === activeDoc.document_id ? focus.bbox : null}
            highlightLabel={activeDoc && focus?.documentId === activeDoc.document_id ? focus.label : undefined} /> : <p className="empty-state">
            {slotKey ? '이 항목은 원본 서류가 없습니다. 미제출 또는 삭제 여부를 확인해 주세요.' : '확인할 서류를 선택해 주세요.'}
          </p>}
        </section>
        <section className="review__right" aria-label="판독 결과">
          <section className="panel verdict" aria-labelledby="panel-verdict">
            <div className="panel__head"><h2 id="panel-verdict"><span className="panel__step">1</span>최종 판정</h2></div>
            <AiSummaryCard key={applicationId} applicationId={applicationId} role={role}
              documents={detail.documents} finalStatus={detail.ai.final_status}
              recommendedAction={detail.ai.recommended_action} onJump={jumpToOriginal} />
            <div className="verdict__box verdict__box--officer">
              <span className="verdict__tag">담당자 판단</span>
              <span className="verdict__value">{detail.decision.label}</span>
              <p>최종 판단은 담당자가 합니다.</p>
            </div>
            <p className="notice notice--warning" role="note">
              <span className="notice__icon" aria-hidden="true">!</span>
              <span>보완 요청이 없는 사업입니다. 서류가 미비하면 보완 없이 선발에서 제외됩니다.</span>
            </p>
            <details className="verdict__reasons" open={detail.ai.reasons.length > 0}>
              <summary>신청 전체 사유 {detail.ai.reasons.length}건</summary>
              {detail.ai.reasons.length ? <ul className="reasons">{detail.ai.reasons.map((reason, index) => <li key={index}>
                {reasonTitle(reason) && <strong className="reasons__title">{reasonTitle(reason)}</strong>}{' '}
                {plainText(reason.message)}{reason.doc_type && <em> ({reason.doc_type})</em>}
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
                {reasonTitle(finding) && <strong className="reasons__title">{reasonTitle(finding)}</strong>}{' '}
                {plainText(finding.message)}
                {finding.how_to_fix && <p>{plainText(finding.how_to_fix)}</p>}
                {finding.link && /^https?:\/\//.test(finding.link) && <a href={finding.link} target="_blank" rel="noreferrer">기존 안내 보기</a>}
              </li>)}</ul> : <p className="muted">이 서류에 저장된 확인 사유가 없습니다.</p>}
              {activeDoc.ocr_quality_note && <p className="ocr-note">{activeDoc.ocr_quality_note}</p>}
              {activeDoc.ocr_fallback_reason && <p className="ocr-note">{activeDoc.ocr_fallback_reason}</p>}
              <dl className="fields">{Object.entries(activeDoc.extracted).map(([key, value]) => {
                const view = formatField(key, value)
                if (view.kind === 'hidden') return null
                const label = fieldLabel(key)
                return <div key={key}>
                  <dt>{label}</dt><dd><FieldValue view={view} />{activeDoc.bboxes[key] && <button type="button" className="btn btn--sm" onClick={() => setFocus({ documentId: activeDoc.document_id, bbox: activeDoc.bboxes[key], label, scoreKey: null })}>원본 위치</button>}</dd>
                </div>
              })}</dl>
            </> : <p className="muted">{activeForm ? '작성서식의 입력 내용은 원본 열람 영역의 PDF에서 확인해 주세요.' : '원본 없는 항목의 기존 저장 사유는 위 신청 전체 사유에서 확인할 수 있습니다.'}</p>}
          </section>

          <section className="panel decision" aria-labelledby="panel-decision">
            <div className="panel__head">
              <h2 id="panel-decision"><span className="panel__step">4</span>담당자 처리</h2>
              <span className="muted">현재 상태: {detail.decision.label}</span>
            </div>
            <label>검토 메모<textarea value={memo} onChange={(event) => editor.edit(event.target.value)} /></label>
            <div className="decision__actions">{detail.role.actions.map((action) => <button key={action.key} type="button"
              className={BUTTON_TONE[action.tone] ?? 'btn'} disabled={saving || draft.needsCheck}
              onClick={() => { void editor.save(action.key) }}>{action.label}</button>)}</div>
            <ReviewSaveStatus editor={editor} state={draft} />
          </section>
        </section>
      </div>
    </>}
  </div>
}
