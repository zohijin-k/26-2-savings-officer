import { HttpError } from '../../lib/http-error.ts'

export interface ReviewSnapshot {
  revision: number | null
  decision: { decision: string | null; memo: string | null; label?: string; decided_at?: string | null; officer_role?: string | null; notice?: string | null }
}
export type SavePhase = 'IDLE' | 'DIRTY' | 'SAVING' | 'SAVED' | 'ERROR' | 'STALE' | 'CONFLICT'
export interface DraftState<T> {
  data: T | null; memo: string; busy: boolean; phase: SavePhase; message: string
  loadError: string; needsCheck: boolean; conflict: boolean; latestReady: boolean
}
const token = (value: ReviewSnapshot) => JSON.stringify([value.revision, value.decision])
const matches = (value: ReviewSnapshot, wanted: { decision: string; memo: string; expectedRevision: number }) =>
  value.revision === wanted.expectedRevision + 1 && value.decision.decision === wanted.decision && (value.decision.memo ?? '') === wanted.memo

/** Memory-only editor. The baseline revision is enforced by the server CAS. */
export class ReviewDraft<T extends ReviewSnapshot> {
  state: DraftState<T> = { data: null, memo: '', busy: false, phase: 'IDLE', message: '', loadError: '', needsCheck: false, conflict: false, latestReady: false }
  private baseline: T | null = null
  private wanted: { decision: string; memo: string; expectedRevision: number } | null = null
  private generation = 0
  private live = true
  private listeners = new Set<() => void>()
  private load: () => Promise<T>
  private write: (decision: string, memo: string, expectedRevision: number) => Promise<unknown>
  private errorText: (error: unknown) => string
  private onSaved: () => void
  constructor(load: () => Promise<T>, write: (decision: string, memo: string, expectedRevision: number) => Promise<unknown>, errorText: (error: unknown) => string, onSaved: () => void = () => {}) {
    this.load = load; this.write = write; this.errorText = errorText; this.onSaved = onSaved
  }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private update(next: Partial<DraftState<T>>) { this.state = { ...this.state, ...next }; this.listeners.forEach((listener) => listener()) }
  activate() { this.live = true; this.update({ busy: false }); void this.check() }
  dispose() { this.live = false; this.generation++ }
  get dirty() { return this.state.memo !== (this.baseline?.decision.memo ?? '') }
  get protected() { return this.dirty || (this.baseline !== null && this.state.busy) || this.state.needsCheck }
  edit(memo: string) { this.update({ memo, message: this.state.needsCheck ? this.state.message : '', phase: this.state.busy ? 'SAVING' : this.state.needsCheck ? this.state.phase : memo === (this.baseline?.decision.memo ?? '') ? 'IDLE' : 'DIRTY' }) }
  private confirmed(data: T) {
    this.baseline = data; this.wanted = null
    this.update({ data, needsCheck: false, conflict: false, phase: this.dirty ? 'DIRTY' : 'SAVED',
      message: this.dirty ? '요청한 처리 결과와 메모를 저장했습니다. 이후 입력한 메모는 아직 저장하지 않았습니다.' : '처리 결과와 메모를 저장했습니다.' })
    this.onSaved()
  }
  async check() {
    if (this.state.busy) return
    const request = ++this.generation
    this.update({ busy: true, loadError: '' })
    try {
      const data = await this.load()
      if (!this.live || request !== this.generation) return
      if (!this.baseline) {
        this.baseline = data
        this.update({ data, memo: data.decision.memo ?? '', phase: 'IDLE', message: '' })
      } else if (this.wanted && matches(data, this.wanted)) this.confirmed(data)
      else if (token(data) !== token(this.baseline)) {
        this.update({ data, phase: 'CONFLICT', needsCheck: true, conflict: true, latestReady: true, message: '서버의 심사 결과 또는 메모가 달라졌습니다. 입력은 유지됩니다. 최신 상태를 확인해 주세요.' })
      } else {
        this.wanted = null
        this.update({ data, needsCheck: false, conflict: false, phase: this.dirty ? 'DIRTY' : 'IDLE', message: '현재 서버 상태를 확인했습니다. 입력한 메모를 확인한 뒤 처리 버튼으로 다시 저장할 수 있습니다.' })
      }
    } catch (error) {
      if (this.live && request === this.generation) this.update(this.baseline
        ? { phase: 'STALE', needsCheck: true, message: this.errorText(error) }
        : { loadError: this.errorText(error) })
    } finally { if (this.live && request === this.generation) this.update({ busy: false }) }
  }
  acceptLatest() {
    if (this.state.busy || !this.state.conflict || !this.state.latestReady || !this.state.data) return
    this.baseline = this.state.data; this.wanted = null
    this.update({ conflict: false, needsCheck: false, phase: this.dirty ? 'DIRTY' : 'IDLE', message: '최신 상태를 기준으로 다시 검토합니다. 입력한 메모는 유지되며 아직 저장되지 않았습니다.' })
  }
  async save(decision: string) {
    if (!this.baseline || this.state.busy || this.state.needsCheck) return
    const expectedRevision = this.baseline.revision
    if (!Number.isSafeInteger(expectedRevision) || expectedRevision === null || expectedRevision < 1) {
      this.update({ phase: 'ERROR', needsCheck: true, message: '심사 버전이 없어 저장할 수 없습니다. 서버 상태를 확인해 주세요.' }); return
    }
    const request = ++this.generation, wanted = { decision, memo: this.state.memo, expectedRevision }
    this.update({ busy: true, phase: 'SAVING', message: '' })
    let acknowledged = false
    try {
      const current = await this.load()
      if (!this.live || request !== this.generation) return
      if (token(current) !== token(this.baseline)) {
        this.update({ data: current, phase: 'CONFLICT', needsCheck: true, conflict: true, latestReady: true, message: '저장 전 서버 변경을 확인해 요청을 보내지 않았습니다. 최신 상태를 확인해 주세요. 입력한 메모는 유지됩니다.' }); return
      }
      this.wanted = wanted
      await this.write(wanted.decision, wanted.memo, wanted.expectedRevision)
      acknowledged = true
      if (!this.live || request !== this.generation) return
      const verified = await this.load()
      if (!this.live || request !== this.generation) return
      if (matches(verified, wanted)) this.confirmed(verified)
      else this.update({ data: verified, phase: 'CONFLICT', needsCheck: true, conflict: true, latestReady: true, message: '조회한 서버 상태가 요청한 결과와 다릅니다. 입력한 메모는 유지됩니다. 최신 상태를 확인해 주세요.' })
    } catch (error) {
      if (error instanceof HttpError && error.status === 409 && error.code === 'REVIEW_REVISION_CONFLICT') {
        this.wanted = null // A rejected write must never be recovered as a success.
        if (!this.live || request !== this.generation) return
        this.update({ phase: 'CONFLICT', needsCheck: true, conflict: true, latestReady: false,
          message: '다른 담당자의 변경과 충돌하여 저장하지 않았습니다. 작성 중인 메모는 유지됩니다. 최신 심사 상태를 확인하고 재검토해 주세요.' })
        try {
          const latest = await this.load()
          if (this.live && request === this.generation) this.update({ data: latest, latestReady: true })
        } catch { /* Keep the conflict gate closed until a successful explicit read. */ }
        return
      }
      if (this.live && request === this.generation) this.update({ phase: acknowledged ? 'STALE' : 'ERROR', needsCheck: true,
        message: acknowledged ? '서버가 저장 요청을 처리했으나 재조회하지 못했습니다. 입력한 메모는 유지됩니다. 서버 상태 확인으로 결과를 확인해 주세요.' : this.errorText(error) })
    } finally { if (this.live && request === this.generation) this.update({ busy: false }) }
  }
  /** Fingerprint/check updates share the lock but never replace a memo draft. */
  async run(work: () => Promise<T>) {
    if (this.state.busy || this.state.needsCheck) return
    const request = ++this.generation
    this.update({ busy: true, message: '' })
    try {
      const data = await work()
      if (!this.live || request !== this.generation) return
      this.update({ data })
      if (this.baseline && token(data) !== token(this.baseline)) this.update({ phase: 'CONFLICT', needsCheck: true, conflict: true, latestReady: true, message: '원본 확인 중 서버의 심사 결과가 달라졌습니다. 입력한 메모는 유지됩니다. 최신 상태를 확인해 주세요.' })
    } catch (error) { if (this.live && request === this.generation) this.update({ phase: 'ERROR', needsCheck: true, message: this.errorText(error) }) }
    finally { if (this.live && request === this.generation) this.update({ busy: false }) }
  }
}
