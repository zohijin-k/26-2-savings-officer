let guard: (() => boolean) | null = null
export const confirmOfficerLeave = () => guard?.() ?? true
export function registerOfficerGuard(next: () => boolean) {
  guard = next
  return () => { if (guard === next) guard = null }
}

let historyGuard: ((event: PopStateEvent) => boolean) | null = null
export const handleOfficerHistory = (event: PopStateEvent) => historyGuard?.(event) ?? false
export function registerOfficerHistory(next: (event: PopStateEvent) => boolean) {
  historyGuard = next
  return () => { if (historyGuard === next) historyGuard = null }
}
