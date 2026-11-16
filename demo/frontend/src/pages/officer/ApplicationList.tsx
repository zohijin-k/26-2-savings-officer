/**
 * 신청 목록 — 신청 건 단위 표.
 *
 * 탭(확인 필요 · 적합 · 처리 완료)은 저장값을 바꾸지 않고 화면 분류만 한다.
 * 일괄 처리 바는 필터 줄 자리에 떠서 표가 아래로 밀리지 않는다. 확인 필요 건은
 * 행을 펼쳐 사유를 먼저 읽을 수 있다.
 */
import { Fragment, useEffect, useId, useRef, useState } from 'react'
import type { DecisionKey, DocStatus, OfficerRole, OfficerRow, OfficerScope, ReviewDetailData } from '../../api.ts'
import { EMPTY_FILTERS, QUEUES, SORTS, importanceOf, matchesFilters, queueCounts, queueOf, sortRows, type ListFilters, type Queue, type SortKey } from './list-model.ts'

interface Props {
  rows: OfficerRow[]
  role: OfficerRole | null
  scope?: OfficerScope | null
  initialQueue?: Queue
  initialSort?: SortKey
  busy?: boolean
  notice?: string
  onOpen: (row: OfficerRow) => void
  onScope?: (next: { region?: string; town?: string }) => void
  onBulk?: (ids: number[], decision: DecisionKey) => Promise<void>
  loadReasons?: (id: number) => Promise<ReviewDetailData>
}

type ReasonState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: ReviewDetailData }

const AI_CHIP: Record<DocStatus, { label: string; tone: string }> = {
  PASS: { label: '적합', tone: 'pass' },
  NEEDS_REVIEW: { label: '확인필요', tone: 'needs_review' },
  FAIL: { label: '부적합', tone: 'fail' },
}
const DECISION_TONE: Record<DecisionKey, string> = { approve: 'approve', hold: 'hold', reject: 'reject' }

function formatDayTime(value: string | null | undefined): string {
  if (!value) return '–'
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value)
  return match ? `${match[1]}.${match[2]}.${match[3]} ${match[4]}:${match[5]}` : value
}

function StatusChip({ row }: { row: OfficerRow }) {
  if (row.decision) {
    return <span className={`alist__chip alist__chip--${DECISION_TONE[row.decision]}`}>{row.decision_label ?? row.decision}</span>
  }
  const ai = row.ai_status ? AI_CHIP[row.ai_status] : null
  return <span className={`alist__chip alist__chip--${ai?.tone ?? 'none'}`}>{ai?.label ?? '미심사'}</span>
}

export default function ApplicationList({
  rows, role, scope = null, initialQueue = 'needs_review', initialSort = 'importance', busy = false, notice = '',
  onOpen, onScope, onBulk, loadReasons,
}: Props) {
  const uid = useId()
  const [queue, setQueue] = useState<Queue>(initialQueue)
  const [filters, setFilters] = useState<ListFilters>(EMPTY_FILTERS)
  const [sort, setSort] = useState<SortKey>(initialSort)
  const [selected, setSelected] = useState<number[]>([])
  const [openId, setOpenId] = useState<number | null>(null)
  const [reasons, setReasons] = useState<Record<number, ReasonState>>({})
  const selectAll = useRef<HTMLInputElement>(null)

  const matching = rows.filter((row) => matchesFilters(row, filters))
  const counts = queueCounts(matching)
  const shown = sortRows(matching.filter((row) => queueOf(row) === queue), sort)
  const shownIds = shown.map((row) => row.application_id)
  const picked = selected.filter((id) => shownIds.includes(id))
  const canBulk = Boolean(role?.can_bulk && onBulk)
  const allChecked = shownIds.length > 0 && picked.length === shownIds.length
  const filtered = filters.search !== '' || filters.from !== '' || filters.to !== ''
  const columnCount = 7

  useEffect(() => {
    if (selectAll.current) selectAll.current.indeterminate = picked.length > 0 && !allChecked
  }, [picked.length, allChecked])

  const changeQueue = (next: Queue) => {
    setQueue(next)
    setSelected([])
    setOpenId(null)
  }
  const toggleRow = (id: number) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])
  const load = (id: number) => {
    if (!loadReasons) return
    setReasons((current) => ({ ...current, [id]: { status: 'loading' } }))
    loadReasons(id).then((data) => {
      setReasons((current) => ({ ...current, [id]: { status: 'ready', data } }))
    }).catch((reason: unknown) => {
      setReasons((current) => ({ ...current, [id]: { status: 'error', message: reason instanceof Error ? reason.message : String(reason) } }))
    })
  }
  const toggleReasons = (id: number) => {
    if (openId === id) { setOpenId(null); return }
    setOpenId(id)
    if (!reasons[id] || reasons[id].status === 'error') load(id)
  }
  const runBulk = (decision: DecisionKey) => {
    if (!onBulk || picked.length === 0) return
    void onBulk(picked, decision).then(() => setSelected([]))
  }

  return <div className="alist">
    <div className="alist__head">
      <div className="alist__tabs" role="tablist" aria-label="처리 단계">
        {QUEUES.map((item) => <button key={item.key} type="button" role="tab" id={`${uid}-tab-${item.key}`}
          aria-selected={queue === item.key} aria-controls={`${uid}-panel`}
          className={queue === item.key ? 'alist__tab alist__tab--on' : 'alist__tab'}
          onClick={() => changeQueue(item.key)}>
          {item.label}
          <span className={item.key === 'needs_review' && counts[item.key] > 0 ? 'alist__count alist__count--loud' : 'alist__count'}>{counts[item.key]}</span>
        </button>)}
      </div>
    </div>

    <div className={picked.length > 0 && canBulk ? 'alist__bar alist__bar--selecting' : 'alist__bar'}>
      {picked.length > 0 && canBulk && role ? <div className="alist__selection" role="group" aria-label="일괄 처리">
        <strong>{picked.length}건 선택</strong>
        <div className="alist__selection-actions">
          {role.actions.map((action) => <button key={action.key} type="button" disabled={busy}
            className={action.tone === 'primary' ? 'btn btn--primary btn--sm' : action.tone === 'danger' ? 'btn btn--danger btn--sm' : 'btn btn--sm'}
            onClick={() => runBulk(action.key)}>{action.result_label}</button>)}
        </div>
        <button type="button" className="alist__link" disabled={busy} onClick={() => setSelected([])}>선택 해제</button>
      </div> : <div className="alist__filters">
        {role?.requires_region && scope && onScope && <label className="alist__scope">
          <span className="sr-only">시군</span>
          <select value={scope.region} onChange={(event) => onScope({ region: event.target.value, town: '' })}>
            {scope.regions.map((region) => <option key={region} value={region}>{region}</option>)}
          </select>
        </label>}
        {role?.requires_town && scope && onScope && <label className="alist__scope">
          <span className="sr-only">읍면동</span>
          <select value={scope.town} onChange={(event) => onScope({ region: scope.region, town: event.target.value })} disabled={scope.towns.length === 0}>
            {scope.towns.length === 0 && <option value="">접수 읍면동 없음</option>}
            {scope.towns.map((town) => <option key={town} value={town}>{town}</option>)}
          </select>
        </label>}
        <input className="alist__search" type="search" placeholder="신청번호 또는 성명" aria-label="신청번호 또는 성명 검색"
          value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} />
        <div className="alist__period" role="group" aria-label="접수일">
          <span>접수일</span>
          <input type="date" aria-label="접수일 시작" value={filters.from} max={filters.to || undefined}
            onChange={(event) => setFilters({ ...filters, from: event.target.value })} />
          <span aria-hidden="true">~</span>
          <input type="date" aria-label="접수일 끝" value={filters.to} min={filters.from || undefined}
            onChange={(event) => setFilters({ ...filters, to: event.target.value })} />
        </div>
      </div>}
      <span className="alist__notice" role="status">{notice}</span>
      <div className="alist__sorts" role="group" aria-label="정렬">
        {SORTS.map((item) => <button key={item.key} type="button" aria-pressed={sort === item.key}
          className={sort === item.key ? 'alist__sort alist__sort--on' : 'alist__sort'}
          onClick={() => setSort(item.key)}>{item.label}</button>)}
      </div>
    </div>

    <div className="alist__panel" role="tabpanel" id={`${uid}-panel`} aria-labelledby={`${uid}-tab-${queue}`}>
      <table className="alist__table">
        <colgroup>
          <col className="alist__col-check" />
          <col className="alist__col-no" />
          <col className="alist__col-name" />
          <col className="alist__col-region" />
          <col className="alist__col-time" />
          <col className="alist__col-status" />
          <col className="alist__col-more" />
        </colgroup>
        <thead>
          <tr>
            {canBulk ? <th scope="col" className="alist__check">
              <input ref={selectAll} type="checkbox" aria-label="전체 선택" checked={allChecked} disabled={shownIds.length === 0}
                onChange={() => setSelected(allChecked ? [] : shownIds)} />
            </th> : <td className="alist__check" aria-hidden="true" />}
            <th scope="col">신청번호</th>
            <th scope="col">성명</th>
            <th scope="col">시군·읍면동</th>
            <th scope="col">접수일시</th>
            <th scope="col">처리상태</th>
            <th scope="col"><span className="sr-only">확인 필요 사유</span></th>
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => {
            const id = row.application_id
            const open = openId === id
            const checked = picked.includes(id)
            const rejected = row.decision === 'reject'
            const hasReasons = rejected || (!row.decision && row.ai_status !== 'PASS')
            const importance = importanceOf(row)
            return <Fragment key={id}>
              <tr className={['alist__row', checked ? 'alist__row--checked' : '', open ? 'alist__row--open' : ''].filter(Boolean).join(' ')}
                onClick={() => onOpen(row)}>
                {canBulk ? <td className="alist__check" onClick={(event) => event.stopPropagation()}>
                  <input type="checkbox" aria-label={`${row.application_no} 선택`} checked={checked} onChange={() => toggleRow(id)} />
                </td> : <td className="alist__check" aria-hidden="true" />}
                <td>
                  <button type="button" className="alist__open" aria-label={`${row.application_no} ${row.name} 심사 화면 열기`}
                    onClick={(event) => { event.stopPropagation(); onOpen(row) }}>{row.application_no}</button>
                </td>
                <td className="alist__name">{row.name}</td>
                <td className="alist__region">{row.region ?? '–'}{row.town && <small>{row.town}</small>}</td>
                <td className="alist__time">{formatDayTime(row.submitted_at)}</td>
                <td><StatusChip row={row} /></td>
                <td className="alist__more" onClick={(event) => event.stopPropagation()}>
                  {hasReasons && loadReasons && <button type="button" className="alist__toggle" aria-expanded={open}
                    aria-controls={`${uid}-reasons-${id}`} aria-label={`${row.application_no} ${rejected ? '반려' : '확인 필요'} 사유 보기`}
                    onClick={() => toggleReasons(id)}>사유{importance > 0 && <span className="alist__toggle-count" aria-label={`확인할 서류 ${importance}건`}>{importance}</span>}<span className="alist__chevron" aria-hidden="true" /></button>}
                </td>
              </tr>
              {open && <tr className="alist__reason-row">
                <td colSpan={columnCount}>
                  <Reasons id={`${uid}-reasons-${id}`} row={row} state={reasons[id]} onRetry={() => load(id)} onOpen={() => onOpen(row)} />
                </td>
              </tr>}
            </Fragment>
          })}
          {shown.length === 0 && <tr className="alist__empty-row">
            <td colSpan={columnCount}>
              <p>{filtered ? '조건에 맞는 신청이 없습니다.' : QUEUES.find((item) => item.key === queue)?.empty}</p>
              {filtered && <button type="button" className="alist__link" onClick={() => setFilters(EMPTY_FILTERS)}>조건 지우기</button>}
            </td>
          </tr>}
        </tbody>
      </table>
    </div>
  </div>
}

/** 펼친 행 — 적합이 아닌 서류와 그 사유, 미제출 필수 서류, 신청 전체 사유. 저장된 값만 보여 준다. */
function Reasons({ id, row, state, onRetry, onOpen }: {
  id: string
  row: OfficerRow
  state: ReasonState | undefined
  onRetry: () => void
  onOpen: () => void
}) {
  const data = state?.status === 'ready' ? state.data : null
  const documents = data?.documents.filter((doc) => doc.status !== 'PASS') ?? []
  const missing = (row.documents ?? []).filter((doc) => doc.document_id === null && doc.required)
  const general = data?.ai.reasons ?? []
  const rejected = row.decision === 'reject'
  return <div className="alist__reasons" id={id} role="region" aria-label={`${row.application_no} ${rejected ? '반려' : '확인 필요'} 사유`}>
    {(!state || state.status === 'loading') && <p className="alist__reasons-note" role="status">사유를 불러오는 중입니다.</p>}
    {state?.status === 'error' && <p className="alist__reasons-note" role="alert">
      사유를 불러오지 못했습니다. <button type="button" className="alist__link" onClick={onRetry}>다시 시도</button>
    </p>}
    {data && <>
      {rejected && <div className="alist__reject-memo">
        <strong>반려 사유</strong>
        <p>{data.decision.memo?.trim() || '담당자가 남긴 반려 사유가 없습니다.'}</p>
      </div>}
      <ul className="alist__reason-list">
        {documents.map((doc) => <li key={doc.document_id}>
          <strong>{doc.label}</strong>
          {doc.status && <span className={`alist__chip alist__chip--${AI_CHIP[doc.status].tone}`}>{AI_CHIP[doc.status].label}</span>}
          {doc.findings.length > 0 && <ul>{doc.findings.map((finding, index) => <li key={index}>{finding.message}</li>)}</ul>}
        </li>)}
        {missing.map((doc) => <li key={doc.slot_key}>
          <strong>{doc.label}</strong><span className="alist__chip alist__chip--fail">미제출</span>
        </li>)}
        {general.map((reason, index) => <li key={`general-${index}`}>{reason.message}</li>)}
      </ul>
      {!rejected && documents.length === 0 && missing.length === 0 && general.length === 0 && <p className="alist__reasons-note">저장된 사유가 없습니다. 심사 화면에서 서류를 확인해 주세요.</p>}
      <button type="button" className="alist__link" onClick={onOpen}>심사 화면 열기 →</button>
    </>}
  </div>
}
