# Persistent synthetic officer examples

## 1. Scope / Trigger
Use for `demo.backend.tools.seed_officer_demo` and its new regression tests. This CLI adds examples for the savings officer UI without changing API handlers, models, existing stored verdicts or engine rules. Keep the older stage-two `seed_application` contract separate.

## 2. Signatures
```sh
python -m demo.fixtures.make_samples
python -m demo.backend.tools.seed_officer_demo
python -m demo.backend.tools.seed_officer_demo --clean
```
There are no document-path, database, program or application-ID override arguments. Successful stdout is JSON counts/IDs; failures use fixed codes and nonzero exit.

## 3. Contracts
Only this checkout's `demo/demo.db` and matching API storage paths are accepted. Reject symlinked or redirected DB/storage before writes. Read only the six fixed generated sample PDFs in `demo/fixtures/samples`, checking the generator's synthetic notice. No arbitrary file input or external document sources.

Ownership is `form1_json['_seed_officer_demo'] = {'version': 'savings-officer-v1', 'scenario': 'pass' | 'needs-review'}`. New seed applications use a dedicated receipt namespace, because old synthetic tests can leave generic-number form archives even when the demo DB is empty. Never overwrite those files. Repeated invocation reuses verified marked applications and creates no duplicate examples.

Allocate only a new marked Application with a dedicated UUID receipt and the latest existing criteria version; this avoids the ordinary create API's count-based number collision after deletions. Use unchanged API handlers for authored form/consent values, uploads and submission. The old synthetic work sample needs independently authored complete work rows before its first submission, as maintained P4 fixtures do. This supplementation touches only newly marked drafts with no Review and never rewrites stage1_status/findings or an existing judgment. Result: normal five PASS documents, review four PASS and one non-PASS.

Initialize only a missing database: existing `models.init_db()` can backfill legacy application criteria versions. Snapshot existing application/document/consent/review/subsidy rows around seed creation; roll back if any change. Use the existing context-local transaction for API writes, with owned-file rollback on failure.

Cleanup validates owned receipt folders and recorded document/consent/archive paths, preserves files referenced by unrelated applications, and removes only marked rows and owned files. Move files temporarily within the same storage filesystem and restore them *inside* the temporary-directory context on DB failure before its cleanup runs.

## 4. Validation & Error Matrix
| Condition | Behavior |
| --- | --- |
| New valid demo DB | Create normal and review applications |
| Two valid marked examples | created=0, existing=2; unchanged rows/files |
| Missing/non-synthetic fixed sample | Refuse before DB mutation |
| Target/path override, redirected DB/storage | Refuse before accessing target |
| Duplicated marker / changed seed status | Refuse instead of repairing saved verdicts |
| Existing-data side effect / creation failure | Roll back rows and newly owned files |
| Clean with other applications/shared files | Preserve unrelated rows and shared bytes |
| Clean failure after moving files | Restore both DB rows and moved files |
| No marked examples | Clean returns zero counts |

## 5. Good / Base / Bad Cases
Good: seed two authored examples, refresh officer lists, rerun without duplication, then clean only those examples. Base: existing unrelated synthetic applications and files remain byte/value identical. Bad: run P6 --live as a persistent seeder or reset the whole demo DB to avoid a filename collision.

## 6. Tests Required
Use temporary demo-layout SQLite/storage, fixed repository synthetic samples, and unchanged old tests. Cover statuses, submitted officer API visibility, original files/reasons, idempotence, unrelated/shared data preservation, cleanup/recreation, symlinks/override rejection and creation/cleanup rollback. The separate frontend integration test feeds seeded API rows through the actual frontend grouping and React list renderer and verifies both sections plus unchanged stored rows. Report new tests separately from the 1,227-test backend baseline.

## 7. Wrong vs Correct
Wrong: modify engine rules or force a FAIL submission to pass for the demo. Correct: use accepted normal/review fixtures and preserve the existing submission guard. Wrong: restore moved files after leaving TemporaryDirectory. Correct: restore while its files still exist, before context exit.
