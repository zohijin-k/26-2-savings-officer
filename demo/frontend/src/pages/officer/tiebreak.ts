import type { ScoreSheetData } from '../../api.ts'

/**
 * 동점자 비교 값을 화면 문구로 옮긴다.
 *
 * 백엔드 `tiebreak_key`는 `[-총점, 소득%, -거주일수, -근로일수, -생년월일서수]`를
 * 저장한다. 오름차순 정렬용이라 큰 값이 유리한 항목은 부호가 뒤집혀 있다.
 * 생년월일은 화면에 내지 않고, 심사표의 연령 구간으로 대신한다.
 */
export function tiebreakParts(sheet: ScoreSheetData): string[] | null {
  const key = sheet.tiebreak
  if (!Array.isArray(key) || key.length < 5 || key.some((value) => typeof value !== 'number')) return null
  const [, income, residence, work] = key
  const days = (value: number) => (value < 0 ? `${(-value).toLocaleString('ko-KR')}일` : '미확인')
  const age = sheet.items.find((item) => item.key === 'age')?.band
  return [
    `소득 ${income >= 999 ? '미확인' : `${income}%`}`,
    `도 거주 ${days(residence)}`,
    `근로 ${days(work)}`,
    `연령 ${age ?? '미확인'}`,
  ]
}
