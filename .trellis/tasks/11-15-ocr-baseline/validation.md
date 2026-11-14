# Validation and review

## Delivered scope

The new CLI and focused tool helpers implement trusted page selection, seeded
clean/scan/phone images, raw OCR metrics, symmetric normalized field agreement,
phase timings, returned-box attribution, resident/payment reference table
regions, durable continuation and numeric text/JSON summaries. Service verdict
comparison is excluded. Existing batch code, operating engines/classifiers/
extractors/decision code and every existing test are unchanged.

The mandatory payment table tests cover both legacy and eight-column government
forms: changing one amount digit produces inside text/digit edits=1 with outside
edits=0; removing one monthly row produces inside missed=1 with outside missed=0.
Missing/uncertain reference table structure remains explicitly unmeasured.
Full, split and fullwidth synthetic identifiers prove identical input masking
and normalized field equality; complete/split cases also use the real extractor.

## Final checks

| Check | Final result |
| --- | --- |
| New synthetic focused tests | 107 passed |
| Full engine tests | 1,748 passed, 3 skipped, 3 xfailed |
| Original engine baseline preserved | 1,641 passed + 107 new tests |
| Full backend tests | 1,410 passed, 2 xfailed |
| Scenario modules, sequential | 18 modules, 1,885 counted checks, zero failures |
| Frontend TypeScript | exit 0 |
| Frontend oxlint | exit 0 |
| Frontend Vite build | exit 0; existing large-chunk advisory |

P14 verifies eight tracked blank templates/geometry/rendering as an aggregate
and has no numeric assertion counter. The other seventeen modules supply the
1,885 counted checks, matching the supplied baseline. No live/remote flags,
downloads or real document execution were used.

Tests ran in a new tracked-source-only isolated checkout with freshly generated
synthetic samples. Only installed dependencies/models were linked. Ignored
input/upload/database trees were neither copied nor inspected. The final
review snapshot was synchronized before the final full engine run. Backend,
scenario and frontend operating sources did not change afterward.

## Environmental failures, reported before correction

1. Initial engine run: one existing external-location test failed because the
   test TMPDIR was incorrectly inside the isolated checkout. The test forbids
   Git calls for external paths, but that location was internal. Moved temporary
   data to a fresh sibling outside the isolated checkout and reran the same
   suite successfully. No test expectation/source change.
2. Initial frontend oxlint: no files found because the isolation inherited an
   ignored ancestor. Initialized a separate Git boundary in the generated
   checkout, then reran the original three commands successfully. No product,
   config or dependency change.
3. Native Apple Vision returned empty words inside the execution sandbox.
   Repeated the same authored synthetic document in approved normal native
   execution; all three Apple variants recognized words. Preserve original
   adapter behavior and explicit empty-result populations rather than masking
   this environmental symptom as a processing error.

## Actual-engine synthetic smoke

One newly authored one-page payment PDF, both installed real local engines,
three variants each: six successful measurements. All six established their
payment table from the same reference text layer. No real document was opened.

| Engine | Variant | Page CER | Table CER | Table digit CER | Fields matched/reference |
| --- | --- | ---: | ---: | ---: | ---: |
| own | clean | 0.015419 | 0.029289 | 0.053435 | 8/14 |
| own | scan | 0.004405 | 0.008368 | 0.015267 | 8/14 |
| own | phone | 0.013216 | 0.000000 | 0.000000 | 7/14 |
| applevision | clean | 0.011013 | 0.012552 | 0.022901 | 5/14 |
| applevision | scan | 0.011013 | 0.016736 | 0.030534 | 7/14 |
| applevision | phone | 0.055066 | 0.071130 | 0.068702 | 6/14 |

All inside table detection-miss rates were zero on this single sample. Exact
per-field denominators and all other numeric metrics are in
`synthetic-summary.json`; compact actual summary text is in
`synthetic-summary.txt`. Field agreement is relative to the text extractor,
not independent accuracy. The figures do not estimate real-corpus accuracy.

Total measured OCR + extraction was 15.15 seconds for the six combinations;
process wall time including rendering/transforms/setup was 16.69 seconds.
This run included cold calls and concurrent regression load. Initial rough
page-based estimate is 17 seconds × eligible pages: about 28 minutes for 100
pages or 4.6 hours for 1,000 pages. Thirty documents mean roughly 8.5 minutes
only when each has one eligible page. Actual page counts, typography and warm
throughput require the operator's pilot; no real-input inventory was performed.

## Disclosure and review evidence

Fresh source sentinels, unreviewed field keys/values, dependency messages,
Python/native noise and attempted filesystem/network mutations are covered by
tests. All sentinels stay absent from output and summary. Closed schema checks
reject arbitrary strings/keys, fractional or inconsistent metric counters,
duplicate/interior-corrupt rows and incompatible configuration. Summary is
tested in a separate process with no input root and no OCR backend imports.

Review fixed limit progress denominators, valid OCR timing retention after
extraction failure, explicit empty/table-unavailable populations and count/rate
consistency checks. No original tests were adjusted for these changes.

New knowledge was recorded in the backend OCR baseline spec: symmetric mask
boundaries, payment reference regions, raster rounding/rotation, numeric schema
validation and synthetic regression isolation. No service spec behavior changed.

Final staged diff: 22 files, all session-owned; only the backend spec index is
an existing modified file. Requested sensitive-prefix, private-storage, masked-
dump and actual operator input/output path scans all found zero matches; absolute
home-path scans also found zero. There are no unstaged tracked changes or
unrecognized dirty files. Numeric scan results are in `validation-results.json`.
Commit is pending explicit user approval. No amend, push or coauthor trailer is
authorized.
