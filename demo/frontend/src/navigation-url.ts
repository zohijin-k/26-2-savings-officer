export interface OfficerPage {
  applicationId: number | null
  documentId: number | null
  slotKey: string | null
}

export function readOfficerPage(url: URL): OfficerPage {
  const route = /^\/officer(?:\/province)?\/review\/([1-9]\d*)\/?$/.exec(url.pathname)
  if (!route) return { applicationId: null, documentId: null, slotKey: null }
  const applicationId = Number(route[1])
  const document = url.searchParams.get('document')
  const documentId = document && /^[1-9]\d*$/.test(document) ? Number(document) : null
  return {
    applicationId: Number.isSafeInteger(applicationId) ? applicationId : null,
    documentId: Number.isSafeInteger(documentId) ? documentId : null,
    slotKey: url.searchParams.get('slot'),
  }
}

export function officerPageUrl(page: OfficerPage, mock: boolean): string {
  const params = new URLSearchParams()
  if (mock) params.set('mock', '1')
  if (page.applicationId !== null) {
    if (page.documentId !== null) params.set('document', String(page.documentId))
    if (page.slotKey !== null) params.set('slot', page.slotKey)
  }
  const path = page.applicationId === null ? '/officer' : `/officer/review/${page.applicationId}`
  return params.size ? `${path}?${params}` : path
}
