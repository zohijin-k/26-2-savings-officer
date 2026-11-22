import { HttpError } from './http-error.ts'

export function requireReviewRevision(revision: number | null | undefined): asserts revision is number {
  if (!Number.isSafeInteger(revision) || revision === null || revision === undefined || revision < 1 || revision > 9_007_199_254_740_990) {
    throw new HttpError(428, '최신 심사 버전을 조회하고 검토한 뒤 저장해 주세요.', 'REVIEW_REVISION_REQUIRED')
  }
}

/** Never turn an unversioned list into an unconditional write to an old server. */
export function requireReviewRevisions(ids: number[], revisions: Record<number, number | null | undefined>) {
  if (new Set(ids).size !== ids.length || Object.keys(revisions).length !== ids.length) {
    throw new HttpError(428, '선택한 신청의 최신 심사 버전을 다시 확인해 주세요.', 'REVIEW_REVISION_REQUIRED')
  }
  ids.forEach((id) => requireReviewRevision(revisions[id]))
}
