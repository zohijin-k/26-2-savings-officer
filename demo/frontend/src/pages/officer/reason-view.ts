/**
 * 담당자 화면의 확인 사유 한 줄 (11-27).
 *
 * 백엔드 review_reasons가 응답 때 붙인 분류(category_label)·제목(title)·설명(explanation)을 쓴다.
 * 엔진이 저장한 원문(origin·stored_message)은 감사·진단 칸에만 보인다. 영문 코드는 어디에도 보이지 않는다.
 */
import { plainText, reasonTitle } from './field-format.ts'

export interface ReasonLike {
  code?: string | null
  title?: string | null
  message?: string | null
  explanation?: string | null
  category?: string | null
  category_label?: string | null
  details?: string[] | null
  severity?: string | null
  document_id?: number | null
  priority?: number | null
  stored_message?: string | null
  origin?: { code?: string | null; message?: string | null } | null
}

export interface ReasonView {
  category: string | null
  title: string | null
  body: string
  details: string[]
  /** 감사·진단: 엔진이 저장한 원문. 일반 화면에서는 접어 둔다. */
  audit: string[]
}

export function reasonView(item: ReasonLike): ReasonView {
  const body = plainText(item.explanation || item.message)
  const audit = [
    item.origin?.message ? `자동 판정 기록 원문: ${plainText(item.origin.message)}` : '',
    item.stored_message && plainText(item.stored_message) !== body ? `저장된 안내 문구: ${plainText(item.stored_message)}` : '',
  ].filter(Boolean)
  return {
    category: plainText(item.category_label) || null,
    title: reasonTitle(item),
    body,
    details: (item.details ?? []).map(plainText).filter(Boolean),
    audit,
  }
}

/** 담당자가 먼저 확인할 사유: 백엔드 우선순위 1번(없으면 첫 사유). */
export function primaryReason<T extends ReasonLike>(reasons: readonly T[]): T | null {
  return reasons.find((reason) => reason.priority === 1) ?? reasons[0] ?? null
}
