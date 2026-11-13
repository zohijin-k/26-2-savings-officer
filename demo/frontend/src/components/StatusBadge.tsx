import type { DocStatus } from '../api.ts'

const PRESENTATION = {
  PASS: { label: '적합', icon: '✓' },
  NEEDS_REVIEW: { label: '확인필요', icon: '?' },
  FAIL: { label: '부적합', icon: '!' },
} satisfies Record<DocStatus, { label: string; icon: string }>

export default function StatusBadge({ status }: { status: DocStatus }) {
  const presentation = PRESENTATION[status]
  return <span className={`status-badge status-badge--${status.toLowerCase()}`} role="status">
    <span aria-hidden="true">{presentation.icon}</span><span>{presentation.label}</span>
  </span>
}
