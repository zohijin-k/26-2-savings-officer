import { useEffect, useLayoutEffect, useState } from 'react'
import { ReviewDraft, type ReviewSnapshot } from './review-draft.ts'
import { registerOfficerGuard, registerOfficerHistory } from './review-navigation.ts'

/** Guard drafts in mounted memory. Native unload warns; it cannot restore after reload. */
export function useOfficerDraftGuard(protectedInput: boolean, source?: { readonly protected: boolean }) {
  useLayoutEffect(() => {
    const protectedNow = () => source?.protected ?? protectedInput
    const confirm = () => !protectedNow() || window.confirm('저장하지 않은 입력 또는 확인하지 못한 저장 결과가 있습니다. 이 화면을 떠나 입력을 버릴까요? 취소하면 계속 편집합니다.')
    const unregister = registerOfficerGuard(confirm)
    const unload = (event: BeforeUnloadEvent) => { if (protectedNow()) { event.preventDefault(); event.returnValue = '' } }
    // The root router invokes this guard before changing or remounting its screen.
    let priorUrl = window.location.href
    let priorIndex = Number(window.history.state?.applicantIndex ?? window.history.state?.officerIndex ?? 0)
    let restoring = false
    const route = () => { priorUrl = window.location.href; priorIndex = Number(window.history.state?.applicantIndex ?? window.history.state?.officerIndex ?? priorIndex) }
    const history = (event: PopStateEvent) => {
      if (restoring) { restoring = false; event.stopImmediatePropagation(); return true }
      const nextIndex = Number(event.state?.applicantIndex ?? event.state?.officerIndex ?? priorIndex)
      if (protectedNow() && !confirm()) {
        event.stopImmediatePropagation()
        const delta = priorIndex - nextIndex
        if (delta) { restoring = true; window.history.go(delta) }
        else window.history.replaceState(event.state, '', priorUrl)
        return true
      } else { priorUrl = window.location.href; priorIndex = nextIndex }
      return false
    }
    window.addEventListener('applicant:route', route)
    window.addEventListener('officer:route', route)
    window.addEventListener('beforeunload', unload)
    const unregisterHistory = registerOfficerHistory(history)
    return () => { unregister(); window.removeEventListener('applicant:route', route); window.removeEventListener('officer:route', route); window.removeEventListener('beforeunload', unload); unregisterHistory() }
  }, [protectedInput, source])
}

export function useReviewDraft<T extends ReviewSnapshot>(options: {
  load: () => Promise<T>; write: (decision: string, memo: string, expectedRevision: number) => Promise<unknown>
  errorText: (error: unknown) => string; onSaved?: () => void
}) {
  const [editor] = useState(() => new ReviewDraft(options.load, options.write, options.errorText, options.onSaved))
  const [state, setState] = useState(editor.state)
  useEffect(() => {
    const unsubscribe = editor.subscribe(() => setState(editor.state))
    editor.activate()
    return () => { editor.dispose(); unsubscribe() }
  }, [editor])
  useOfficerDraftGuard(editor.protected, editor)
  return { ...state, editor, dirty: editor.dirty }
}
