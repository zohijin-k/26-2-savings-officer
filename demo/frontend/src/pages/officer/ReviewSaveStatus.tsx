import { useEffect, useRef } from 'react'
import type { ReviewDraft, ReviewSnapshot, DraftState } from './review-draft.ts'

export default function ReviewSaveStatus<T extends ReviewSnapshot>({ editor, state }: { editor: ReviewDraft<T>; state: DraftState<T> }) {
  const status = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (state.conflict) status.current?.focus() }, [state.conflict])
  return <div aria-busy={state.busy}>
    {state.data && <p className="muted">심사 버전 {state.data.revision ?? '확인 필요'}</p>}
    <p ref={status} tabIndex={-1} role="status" aria-live="polite">{state.busy ? '서버에 처리 결과를 확인하고 있습니다.' : state.conflict ? '다른 담당자의 변경과 충돌 · 재검토 필요' : state.needsCheck ? '저장 결과 또는 최신 상태 확인 필요' : editor.dirty ? '수정 중 · 아직 저장하지 않은 메모가 있습니다.' : state.phase === 'SAVED' ? '저장됨 · 서버 조회로 확인했습니다.' : '메모 변경 없음'}</p>
    {state.message && <p className="decision__notice" role={state.needsCheck ? 'alert' : 'status'}>{state.message}</p>}
    <p className="muted">메모는 선택한 심사 결과와 함께 저장됩니다. 다른 변경과 충돌하면 입력을 유지하고 최신 상태를 확인합니다.</p>
    {state.conflict && state.latestReady && state.data && <details open>
      <summary>서버에 저장된 심사 결과와 메모 · 버전 {state.data.revision}</summary>
      <p>{state.data.decision.label ?? ({ approve: '승인', reject: '반려', hold: '보류' }[state.data.decision.decision ?? ''] ?? '미처리')}</p>
      <blockquote style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{state.data.decision.memo || '저장된 메모 없음'}</blockquote>
    </details>}
    {state.needsCheck && <button type="button" className="btn" disabled={state.busy} onClick={() => void editor.check()}>서버 상태 확인</button>}
    {state.conflict && <p>작성 중인 내용은 메모 입력란에 유지됩니다. 최신 메모와 비교한 뒤 아래 버튼으로 재검토를 확인하세요.</p>}
    {state.conflict && <button type="button" className="btn" disabled={state.busy || !state.latestReady} onClick={() => editor.acceptLatest()}>최신 심사 상태를 확인했습니다 · 입력 유지</button>}
  </div>
}
