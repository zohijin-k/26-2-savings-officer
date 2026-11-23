/** HTTP status stays available without exposing server exception bodies. */
export class HttpError extends Error {
  readonly status: number
  readonly code?: string

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.name = 'HttpError'
    this.code = code
  }
  static async fromResponse(response: Response, message: string) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    const code = detail && typeof detail === 'object' && 'code' in detail && typeof detail.code === 'string' ? detail.code : undefined
    const safeCode = ['REVIEW_REVISION_CONFLICT', 'REVIEW_REVISION_REQUIRED', 'REVIEW_REVISION_INVALID'].includes(code ?? '') ? code : undefined
    return new HttpError(response.status, message, safeCode)
  }
}
