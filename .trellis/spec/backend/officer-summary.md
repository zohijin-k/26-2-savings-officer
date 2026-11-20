# Officer AI summary (AI 종합의견)

## 1. Scope / Trigger

Apply when changing `demo/backend/officer_summary.py`, `demo/backend/llm_client.py`, the
`/api/officer/applications/{id}/summary` routes, the `ReviewSummary` table, or the officer
`AiSummaryCard`. The feature sends application-derived data to an external LLM (전북AI), so the
transmission boundary is a contract.

## 2. Signatures

- `GET  /api/officer/applications/{id}/summary?role=` — cached summary, regenerated when the input hash changes.
- `POST /api/officer/applications/{id}/summary?role=` — force regeneration ('다시 생성').
- Response: `{headline, status_explanation, check_points[{slot_key|null, title, detail, codes[], evidence[{code, label, kind, kind_label}], field|null}], document_notes[{slot_key, note}], score_note, source: 'jbai'|'rules', label, model, generated_at, cached}`.
- `evidence` and `field` are added at response time by `_decorate` (not cached), so label wording changes apply to existing caches.
- `officer_summary.summary_payload(detail, form1, identity) -> dict` — the only thing sent.
- `officer_summary.summarize(application_id, detail, form1, identity, *, force=False, provider=None, clock=...)`.
- `llm_client.configured_provider(environ=None, transport=None)` → `JbaiProvider` or `NoneProvider`.
- Env: `PROGRAM_LLM_ENABLED=true` + `PROGRAM_LLM_PROVIDER=jbai` + https `JBAI_BASE_URL` + `JBAI_API_KEY` (all required), `JBAI_LLM_MODEL` (default `MainModel`), `JBAI_RESPONSE_FORMAT` (`json_object`|`prompt`), `JBAI_LLM_TIMEOUT_SEC` (default 30).

## 3. Contracts

- **The summary never changes a verdict.** Input is `review_detail()` output (stored values). No recomputation, no write to `Review`.
- **Allowlist projection.** `summary_payload` builds every key explicitly:
  - Sent: program rules, `ai` statuses/labels/reasons, per-document `slot_key`/`label`/`doc_type`/`status`/findings (code, severity, message)/`ocr_confidence`/notes, `KEEP_FIELDS` OCR values, eligibility rows, exclusion rows, score items with basis, tiebreak income %/residence days/work days, region (시군), age band, non-identifying `FORM_FIELDS` and form dates.
  - Derived only: name fields → `신청자와 일치/다름`; birth fields → `신청서와 일치/다름`; workplace list → count.
  - Never sent: name, application number, identity, phone, email, address, account, bank, workplace name/number, file URLs, bboxes, raw OCR text, household member list, military service, officer memo, birth ordinal from tiebreak.
  - Unknown OCR keys are dropped by default.
- **Scrubbing.** Every sent string passes `_Scrubber`: RRN mask, known literals (applicant names → `신청자`, other names → `(다른 이름)`, birth date variants → `(생년월일)`, workplace → `(사업장)`, form address/phone/email/account), then patterns (RRN, phone, email, ≥10-digit numbers, road addresses). Dates and amounts must survive.
- **Grounding.** `evidence_codes` = reason codes ∪ finding codes ∪ `ELIGIBILITY_<KEY>` (unmet) ∪ `EXCLUSION_<n>` ∪ `SCORE_<KEY>_INCOMPLETE` ∪ `OBS_*` observations. A check point survives validation only with ≥1 known code; unknown `slot_key` → `null`; notes for unknown slots are dropped. `OBS_*` are deterministic stored-value comparisons (name/birth differs, form vs document 전입일/취업일), not rule reasons — the UI marks them differently.
- **No codes on screen.** The screen shows `evidence[].label` (plain Korean from `CODE_LABELS`, observation labels, or the stored reason sentence) with `kind_label` (규칙 판정/자동 대조/자격요건/심사표), never `code`. All visible text passes `_humanize`: known codes → labels, `PASS/FAIL/NEEDS_REVIEW` → 적합/부적합/확인필요, other `UPPER_SNAKE` tokens removed.
- **Jump to original.** `field` is the extracted-field key to highlight (observation field, or `CODE_FIELDS` for rule codes) and is set only when the document has a bbox for it. The UI opens the document, highlights the bbox, and pulses the original panel even when the document is already open.
- **Brevity.** Prompt asks headline ≤40, title ≤15, detail ≤50, explanation ≤90 chars; validation caps at 60/24/90/160 with an ellipsis; at most 4 check points (3 shown, rest folded).
- **Fallback.** Provider off, transport error, non-JSON, or empty headline → `rule_summary(payload)` with `source="rules"`; not stored. Same input failing again within 120 s is not re-sent unless forced.
- **Cache.** `ReviewSummary(application_id unique, input_hash, summary_json, source, model, created_at)`. Hash = sha256 of `{SUMMARY_VERSION, provider, model, payload}`. Bump `SUMMARY_VERSION` when the prompt or projection changes.
- **Prefetch.** `SummaryWorker` starts in the app lifespan only when the provider is `jbai` and `OFFICER_SUMMARY_PREFETCH` is not false. Every 10 s it walks submitted `double_savings` applications ordered by `(submitted_at, id)` and calls `summarize(force=False)` one at a time; matching hashes are skipped, so a cycle with no changes makes no provider call. It never touches `api/review.py` (shared with the applicant repository). An open-before-prefetch request generates inline under the same per-application lock. Errors log only `summary_worker application=<id> error=<ExceptionType>`.
- **Logging.** One fixed-vocabulary line per call: `llm_call purpose=officer_summary mode=… attempt=… outcome=… seconds=…`. Never exception text, URL, key, prompt or response.
- **Retries.** `json_object` → `prompt` once on `http_4xx`/`bad_shape`/`no_content`; no retry on timeout/429/network.

## 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| LLM env incomplete | `NoneProvider`; rule summary, nothing sent |
| Draft application / unknown id | 404 (from `review_detail`) |
| Unknown role | 400 |
| Provider returns prose or broken JSON | one prompt-mode retry, then rule summary |
| Check point cites a code not in input | point dropped |
| A new field is needed by the prompt | add it to `summary_payload` explicitly and extend the secret list in the test |

## 5. Good / Base / Bad Cases

- Good: 초본 low OCR confidence + 신청서 전입일 ≠ 초본 전입일 → headline explains 확인필요, check points cite `LOW_OCR_CONFIDENCE` and `OBS_TRANSFER_IN_DIFFERS`, tab jump to 주민등록초본.
- Base: LLM disabled → identical card shape labeled 규칙 기반 요약.
- Bad: passing `detail` straight to the prompt, or reading `extracted` values not in `KEEP_FIELDS`.

## 6. Tests Required

- `demo/backend/tests/test_officer_summary.py` — projection secrets, derived facts, scrubber, validation, rule summary, provider opt-in/retry/logging, cache/force/failure, prefetch order and change-only regeneration, API.
- `demo/frontend/tests/summary.test.ts` — tag, tab jump target, observation marking, note order, mock preview.
- `npm test`, `npm run lint`, `npm run build`.

## 7. Wrong vs Correct

Wrong:

```python
messages = [{"role": "user", "content": json.dumps(review_detail(aid, role))}]
```

Correct:

```python
payload = summary_payload(detail, app.form1_json, app.identity_json)
messages = build_messages(payload)
```
