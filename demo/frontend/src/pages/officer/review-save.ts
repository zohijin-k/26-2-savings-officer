import { HttpError } from '../../lib/http-error.ts'

/** A failed response may follow a committed write. Never claim success or retry automatically. */
export function reviewSaveError(error: unknown): string {
  if (error instanceof HttpError) {
    if (error.status === 409 && error.code === 'REVIEW_REVISION_CONFLICT') return '다른 변경과 충돌했습니다 (409). 입력한 메모는 유지됩니다. 서버 상태를 확인한 뒤 다시 시도해 주세요.'
    if (error.status === 409) return '업무 상태가 달라 처리할 수 없습니다 (409). 입력한 메모는 유지됩니다. 서버 상태와 처리 조건을 확인해 주세요.'
    if (error.status === 428) return '최신 심사 버전이 필요합니다 (428). 입력한 메모는 유지됩니다. 서버 상태를 확인해 주세요.'
    if (error.status === 503) return '일시적으로 저장할 수 없습니다 (503). 입력한 메모는 유지됩니다. 잠시 후 다시 시도해 주세요.'
    if (error.status === 500) return '서버 오류로 저장 결과를 확인하지 못했습니다 (500). 입력한 메모는 유지됩니다. 서버 상태를 확인한 뒤 다시 시도해 주세요.'
    if (error.status === 401) return '담당자 세션이 만료되었습니다. 다시 로그인해 주세요.'
    if (error.status === 403) return '이 신청을 처리할 권한이 없습니다 (403). 입력한 메모는 유지됩니다.'
    return `처리 결과를 저장하지 못했습니다 (${error.status}). 입력한 메모를 확인한 뒤 다시 시도해 주세요.`
  }
  if (error instanceof Error && (error.name === 'TimeoutError' || error.name === 'AbortError')) {
    return '응답 시간이 초과되어 저장 결과를 확인하지 못했습니다. 입력한 메모는 유지됩니다. 서버 상태를 확인한 뒤 다시 시도해 주세요.'
  }
  return '서버에 연결하지 못해 저장 결과를 확인하지 못했습니다. 입력한 메모는 유지됩니다. 연결을 확인한 뒤 다시 시도해 주세요.'
}
