import type { DocStatus, OfficerDocument, OfficerList, OfficerRow } from '../../api.ts'

export interface OfficerDocumentRow {
  applicationId: number
  applicationNo: string
  name: string
  documentId: number | null
  slotKey: string
  label: string
  status: DocStatus | null
  required: boolean
}

/** 표시 분류만 만든다. 원래 문서 상태와 신청 전체 판정은 수정하지 않는다. */
export function groupOfficerDocuments(rows: OfficerRow[]) {
  const pass: OfficerDocumentRow[] = []
  const needsReview: OfficerDocumentRow[] = []
  for (const row of rows) {
    if (row.program_code !== 'double_savings') continue
    for (const doc of row.documents ?? []) {
      const item: OfficerDocumentRow = {
        applicationId: row.application_id, applicationNo: row.application_no, name: row.name,
        documentId: doc.document_id, slotKey: doc.slot_key, label: doc.label,
        status: doc.status, required: doc.required,
      }
      if (doc.status === 'PASS') pass.push(item)
      else needsReview.push(item)
    }
  }
  return { pass, needsReview }
}

/** 신청 건 API의 모든 페이지를 취합한 뒤 서류 단위로 분류한다. */
export async function collectOfficerRows(loadPage: (page: number) => Promise<OfficerList>): Promise<OfficerRow[]> {
  const first = await loadPage(1)
  const rows = [...first.rows]
  for (let page = 2; page <= first.page_count; page += 1) {
    rows.push(...(await loadPage(page)).rows)
  }
  return rows
}

/** 슬롯이 같은 미배정 페이지는 ID로 구별한다. 없는 항목을 다른 원본으로 대체하지 않는다. */
export function selectOfficerDocument(documents: OfficerDocument[], documentId: number | null, slotKey: string | null) {
  if (documentId !== null) return documents.find((doc) => doc.document_id === documentId) ?? null
  if (slotKey !== null) return documents.find((doc) => doc.slot_key === slotKey) ?? null
  return null
}
