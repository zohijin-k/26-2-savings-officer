/**
 * 서식 원형 재현용 기본 컴포넌트 (PC 전용 고정 레이아웃).
 *
 * 맞추는 것 셋:
 *   1. 표 구조   — 열 경계를 원본 PDF의 실제 선 좌표에서 가져온다
 *   2. 항목 순서 — 서식에 적힌 순서 그대로 (재배열 금지)
 *   3. 문구      — 항목명과 각주(※)를 원문 그대로
 *
 * 설계 근거: .trellis/tasks/09-16-demo-site/design.md 6-A절
 */

import type { ReactNode } from 'react'

import './form-sheet.css'

interface FormSheetProps {
  formNo: string
  title: string
  /** 표제 아래 안내문. 서식 원문의 "○ …" 줄을 그대로 넣는다. */
  notices?: ReactNode[]
  children: ReactNode
}

export function FormSheet({ formNo, title, notices, children }: FormSheetProps) {
  return (
    <div className="form-sheet-scroll">
      <div className="form-sheet">
        <div className="form-sheet__head">
          <div className="form-sheet__no">{formNo}</div>
          <h2 className="form-sheet__title">{title}</h2>
        </div>
        {notices && notices.length > 0 && (
          <div className="form-sheet__notices">
            {notices.map((n, i) => (
              <p key={i}>{n}</p>
            ))}
          </div>
        )}
        {children}
      </div>
    </div>
  )
}

/**
 * 본표. `cols`는 각 열의 너비 비율(%)이며 원본 PDF 선 좌표에서 뽑은 값이다.
 * 행마다 분할이 다르므로 각 셀이 colSpan으로 묶어 쓴다.
 */
export function FormTable({ cols, children }: { cols: number[]; children: ReactNode }) {
  return (
    <table className="form-table">
      <colgroup>
        {cols.map((w, i) => (
          <col key={i} style={{ width: `${w}%` }} />
        ))}
      </colgroup>
      <tbody>{children}</tbody>
    </table>
  )
}

/** 절 제목 띠 (Ⅰ. 기본정보). */
export function FormBand({ span, children }: { span: number; children: ReactNode }) {
  return (
    <tr>
      <td className="fc-band" colSpan={span}>
        {children}
      </td>
    </tr>
  )
}

interface CellProps {
  span?: number
  rowSpan?: number
  center?: boolean
  children?: ReactNode
}

/** 라벨 셀 (항목명). */
export function LabelCell({ span = 1, rowSpan, children }: CellProps) {
  return (
    <td className="fc-label" colSpan={span} rowSpan={rowSpan}>
      {children}
    </td>
  )
}

/** 입력·내용 셀. */
export function Cell({ span = 1, rowSpan, center, children }: CellProps) {
  return (
    <td className={center ? 'fc-center' : undefined} colSpan={span} rowSpan={rowSpan}>
      {children}
    </td>
  )
}

/** 서식 원문의 ※ 각주. 요약하지 말고 그대로 넣을 것. 원본처럼 옅은 형광 배경. */
export function FormNote({ children }: { children: ReactNode }) {
  return (
    <p className="form-note">
      <span>{children}</span>
    </p>
  )
}
