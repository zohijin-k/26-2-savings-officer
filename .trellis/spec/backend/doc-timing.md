# Per-document timing

Apply to `engine_v2.tools.doc_timing` and its tests. Measure how long the demo
service takes to process one uploaded PDF, from reading through the per-document
verdict, on the own engine. Never change operating code to make it measurable.

## Production path

- Call the functions the upload endpoint calls: `demo.backend.ocr.read_document`
  (the unmodified reader `CHAIN`) and `demo.backend.upload_assessment.assess_upload`
  with `reader=lambda *_: ocr`. Do not use `engine_v2.engine.run`, forced
  rendering or forced OCR of text-layer pages.
- Fix the engine to own via `ENGINE_V2_OCR=own` inside the tool process. Remove
  `JBAI_API_KEY`, `JBAI_ALLOW_REAL_DOCS` and `UPSTAGE_API_KEY` before importing the
  reader chain so nothing leaves the machine; keep the batch network guard.
- `expected=None` is equivalent on the own path because only JbaiOcr reads it.
  Choose the slot from the detected kind with the batch_assess rule. Kinds without
  a default double-savings slot are read and extracted but `NOT_ASSESSED`.
- Outside the timed region: HTTP/file receipt, database reads/writes, paired NHIS
  reassessment, application-level judgement, slot lookup, output suppression and
  the untimed pre-check (encryption, open errors, page/text-layer counts).

## Stage timing

- Stages come from delegation-only `patch.object` wrappers that pass arguments,
  results and exceptions through unchanged. Prove equivalence with a test that
  compares wrapped and unwrapped `OcrResult` and verdicts.
- Stage time is exclusive: a nested stage's time is removed from its parent. Unwind
  frames by identity; equal-looking same-name frames once broke equivalence when
  `list.remove` dropped the wrong frame and the reader chain fell back silently.
- `own.sessions` cache misses are COLD_START: recorded once, removed from the stage
  and from the document total. Do not preload the model; the first OCR call loads it
  as in production. Anything outside named stages is OTHER.

## Runs and outputs

- `--out` must not exist (OUT_EXISTS). No resume. Warm-up re-runs the first N
  processable documents before measurement; every document stays in statistics.
  Repeats are whole passes; per-document value is the median, spread is max/min.
- `--sample` stratifies by form from `--strata-from` (a previous run), else by
  text layer × page bin. Allocation is proportional, at least one per stratum,
  deterministic for a seed. Processing order is the document-key order.
- Row format 2 adds `reasons`: distinct, sorted `[code, severity]` pairs from the
  verdict findings, recorded after the timed region. Only `verify_upload.SAFE_CODES`
  survive (others become UNKNOWN_CODE); message, guidance and detail are never read.
  Format 1 rows stay readable (also for `--strata-from`). No summary lines use them;
  A7/A8 are computed from rows per the task's measurement definitions.
- Row format 3 adds `intra_threads` and `page_workers` (ints ≥ 1): the own OCR
  settings in force. `engine_v2.pipeline.ocr.own` reads `OWN_OCR_INTRA_THREADS`
  (default 2) and `OWN_OCR_PAGE_WORKERS` (default 4; 1 = pages read sequentially)
  once at import; unset/empty keeps the default silently, anything but 1-6 plain
  digits > 0 keeps the default with one warning line that never echoes the value.
  run.json `options.ocr_threads` and the summary `OCR_THREADS` line also carry
  `page_workers_cap` = min(page_workers, cpu_count // intra_threads), at least 1.
  `run_ocr_pages` reads pages concurrently only when `ENGINES["own"]` is the real
  reader or a wrapper reaching it through `__wrapped__` (doc_timing's timing wrapper
  qualifies). A reader swapped in by a test (e.g. a fake handing out page results in
  call order) is called sequentially on the caller's thread, whatever
  `OWN_OCR_PAGE_WORKERS` says; to test concurrency, patch `own.recognize` instead.
- Automatic thread choice (11-19, `own.AUTO_THREADS`): when neither `OWN_OCR_*` variable is set
  (unset or empty), a document read one page at a time (one OCR page, one page worker, a swapped
  reader, any thread that is not a page worker) uses `sessions()` with `single_intra_threads()` =
  min(4, cpu_count) threads; 2+ pages read concurrently use `page_sessions(slot)` with
  `INTRA_OP_THREADS` (2) each, every slot its own session (slot 0 is not the single session), so
  page_workers x 2 <= cpu_count. `prepare_page_workers` loads no page session when it returns 1.
  Two-page documents (T4b, 11-19, auto only): `page_intra_threads(2)` = `TWO_PAGE_INTRA_THREADS`
  (4) when 2 x 4 <= cpu_count (and `MAX_PAGE_WORKERS` >= 2), so both pages are read at once on two
  intra-4 page sessions; with fewer cores they keep the intra-2 rule. Page sessions are cached per
  `(slot, intra_threads)` (`page_sessions(slot, intra_threads)`, both always passed), so the
  two-page sessions never share with 3+-page ones; one page and 3+ pages are unchanged. Slot 0
  reuses the single `sessions()` when `shares_single_session(slot, intra)` (fixed mode as before;
  auto only when the page threads equal `single_intra_threads()`, i.e. two pages), so auto preload
  holds 6 sessions on 8+ cores (single intra 4, four intra 2, one more intra 4); doc_timing does
  not exclude a shared slot 0 twice.
  11-27: `TWO_PAGE_INTRA_THREADS` is 2 (was 4). Same code, 4 interleaved rounds on the 8-core M2 (4P+4E):
  intra 4 x 2 read two-page scans in 2.35 s vs 1.73 s for intra 2 x 2 (round means apart), so two pages
  use the intra-2 page sessions (slot 0 unshared), preload holds 5 sessions, and doc_timing counts a
  two-page document as `2 2`. The knob and the `(slot, intra_threads)` cache keys stay.
  Setting either variable turns auto off: every session uses `INTRA_OP_THREADS` and page slot 0
  shares `sessions()`, exactly as before. Server preload loads the single and every page session, including the two-page ones
  (`prepare_page_workers(MAX_PAGE_WORKERS)` then `prepare_page_workers(2)`).
  Row format 3 and the `OCR_THREADS` line are unchanged (they carry the page-session values);
  run.json `options.ocr_thread_mode` and the summary `OCR_THREADS_MODE` line give the mode
  (`auto`/`fixed`), single and page threads and the worker cap; `OCR_THREADS_USED intra workers n`
  (run.json `ocr_threads_used`) counts measured documents by the threads and page workers they
  were actually read with (documents without own OCR are not counted; a two-page document in
  auto counts as `4 2`). doc_timing excludes every
  page-session load as cold start in auto mode (slot 0 included).
  Every reader of doc_timing rows (`load_strata`, `classify_recovery_diag`
  crosstab/compare/run --timing, label_review on its branch) goes through `validate_row`, which
  accepts formats 1-3; a format bump must keep older formats readable.
- rows.jsonl uses a 16-hex key of the root-relative path. Screen, run.json and
  summary_brief.txt contain numbers, O/X and fixed codes only, never paths, names,
  keys, values or exception text. run.json records machine, cores, power, load,
  versions, ONNX threads actually used, times and git commit.
- Never run timing concurrently with regression suites or other measurements.
