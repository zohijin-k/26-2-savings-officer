import type { OfficerDocumentRow } from './document-groups.ts'

interface Props {
  groups: { pass: OfficerDocumentRow[]; needsReview: OfficerDocumentRow[] }
  onOpen: (item: OfficerDocumentRow) => void
}

export default function ApplicationList({ groups, onOpen }: Props) {
  return <div className="document-lists">
    <DocumentList title="적합 서류" items={groups.pass} onOpen={onOpen} />
    <DocumentList title="확인 필요 서류" items={groups.needsReview} onOpen={onOpen} />
  </div>
}

function DocumentList({ title, items, onOpen }: { title: string; items: OfficerDocumentRow[]; onOpen: Props['onOpen'] }) {
  return <section className="document-list" aria-label={title}>
    <h2>{title} <span>{items.length}건</span></h2>
    {items.length === 0 ? <p className="empty-state">해당 서류가 없습니다.</p> : <ul>
      {items.map((item) => <li key={`${item.applicationId}:${item.documentId ?? item.slotKey}`}>
        <button type="button" className="document-item" onClick={() => onOpen(item)}>
          <strong>{item.label}</strong>
          <span>{item.name} <small>{item.applicationNo}</small></span>
          {item.documentId === null && <em>미제출 — 원본 없음</em>}
          <span className="document-item__open">원본 및 사유 보기 →</span>
        </button>
      </li>)}
    </ul>}
  </section>
}
