/** Keep authorization, transport, and PDF decoding failures distinct. */
export function pdfLoadError(error: unknown): { status: number | null; message: string } {
  const value = error && typeof error === 'object' ? error as { status?: unknown; name?: unknown } : {}
  const status = typeof value.status === 'number' ? value.status : null
  if (status === 401) return { status, message: '로그인 시간이 끝났습니다. 다시 로그인해 주세요.' }
  if (status === 403) return { status, message: '이 서류를 열람할 권한이 없습니다.' }
  if (status === 404) return { status, message: '서류를 찾을 수 없습니다. 신청 상세를 다시 확인해 주세요.' }
  if (status === 0 || value.name === 'TypeError' || value.name === 'UnknownErrorException') {
    return { status, message: '서류를 불러오지 못했습니다. 네트워크 연결을 확인하고 다시 시도해 주세요.' }
  }
  if (status !== null) return { status, message: '서류를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.' }
  return { status, message: 'PDF를 표시하지 못했습니다. 다시 시도해 주세요.' }
}
