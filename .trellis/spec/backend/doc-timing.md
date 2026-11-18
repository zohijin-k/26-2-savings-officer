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
  Every reader of doc_timing rows (`load_strata`, `classify_recovery_diag`
  crosstab/compare/run --timing, label_review on its branch) goes through `validate_row`, which
  accepts formats 1-3; a format bump must keep older formats readable.
- rows.jsonl uses a 16-hex key of the root-relative path. Screen, run.json and
  summary_brief.txt contain numbers, O/X and fixed codes only, never paths, names,
  keys, values or exception text. run.json records machine, cores, power, load,
  versions, ONNX threads actually used, times and git commit.
- Never run timing concurrently with regression suites or other measurements.
