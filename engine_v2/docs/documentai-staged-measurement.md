# Paired DocumentAI measurement v2

This is a synthetic-only successor to [the v1 measurement](documentai-measurement.md). V1 code, tests and result reports remain unchanged. The new command never reads an existing user-document directory, downloads fonts/models, or changes production OCR/classification/extraction/verdict logic.

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_staged \
  --samples 5 --seed 20261113 --output /tmp/documentai-paired-v2-n5.json
```

Use a new `.json` destination whose parent already exists. The command refuses an existing JSON, sibling Markdown or metric checkpoint, so it cannot overwrite an older report. It emits fixed-vocabulary progress and a numeric completion summary. A value-free `.rows.jsonl` checkpoint retains completed pairs, and final JSON/Markdown contain no raw OCR or extracted values. Generated source images are temporary and removed automatically. Run sequentially because instrumentation and native-output suppression are process-global.

## Corpus and conservative source policy

Five distinct fictitious identity/date sets replace v1's modulo-four name loop. Both source definitions and actual submitted input hashes are checked for uniqueness within every document/condition. Even intentionally unreadable byte inputs carry distinct generic sample/type tokens. Names/dates vary but layout/font families remain shared; five samples do not imply five independent templates or population confidence.

Original geometry, typography, purpose marks and every source label are preserved from the existing fictitious fixture providers. The ambiguous insurance purpose/title proximity and payment table geometry are retained: there is no evidence that they are impossible in real documents. No source is tuned until it passes classification. An additional bounded `layout_variant` stress preserves every character while varying row positions. Each new source-parameter/truth change is explained in the task's source-decisions evidence; no actual source document is opened.

At n=5 there are **410 paired cases / 820 stage evaluations**:

| Group | Conditions | Cases |
|---|---|---:|
| normal_baseline | original only | 25 |
| stress | monochrome, +5°, −5°, 90°, phone, layout_variant | 150 |
| quality_defect | 24% resolution, explicit 400px defect, severe upsampled blur | 75 |
| content_defect | early/future issue, mismatching identity, missing page, wrong upload slot, invalid bytes, and type-applicable missing dates/month | 160 |

Every applicable document/condition has five different inputs. The two type-specific missing-data conditions each have five relevant cases. Quality-defect FAIL is desired, not a false rejection. Case groups and expectations are authored before observing verdicts. A negative content case forbids PASS; production review policies are retained and reported rather than rewritten to force FAIL.

## Three stages and attribution

A obtains exact words and bounds from each synthetic PDF text layer. Its bounds are transformed with the same scaling, expanded rotation or phone homography as the submitted bitmap. A then substitutes those words into the **same image-source local reader** that B uses. The input PNG, image metadata, upload requirement, independent classifier, extractor and decision path are shared. No truth-selected extractor is used. A is explicitly marked `TEXT_LAYER_REFERENCE`; an internal adapter engine tag only keeps the unchanged image path active and never represents an own-model call.

B runs actual own OCR on that same image. Reference confidence is 1, while own supplies its measured confidence and word segmentation/bounds. C therefore measures paired operational OCR effects, including those differences, not a controlled glyph-only causal effect.

For classification, report A failures, B failures, A-correct→B-failed losses and A-failed→B-correct recoveries. For fields, report:

- An uncalled expected extractor yields `UNEXTRACTED_CLASSIFICATION`, null exact/CER metrics and a separate count. It is never a wrong field.
- A called extractor omitting a field yields `MISSING`, an accuracy opportunity and a wrong field. An expected empty string still differs from an absent field.
- Swallowed extractor/OCR exceptions yield explicit execution failure and `ERROR` fields, not a classification miss.
- A-called wrong/missing fields are baseline extraction errors. A-correct→B-called wrong/missing fields are additional OCR field losses. A-correct→B-uncalled fields are OCR-induced unextracted outcomes, counted separately. Recoveries are also separate.

Signed B−A differences are included but cannot replace paired loss/recovery counts when the called denominators change. The principal weakness/attribution tables use normal baseline and expected-valid stress only; deliberately corrupted content remains in verdict/condition tables and JSON rather than being interpreted as intrinsic classifier weakness.

## Raw and normalized metrics

Both figures are printed together. Raw compares typed semantic values, including original string formatting; date objects use ISO values. Structured JSON is parsed symmetrically, insurance geometry/confidence evidence is excluded and all reviewed semantic columns remain. Lists retain order.

Normalized applies the same field-aware rules to expected/observed values: NFKC, Unicode-whitespace handling, equivalent dash mapping, calendar-validated ISO date/month parsing, and grouped comma removal for numeric amount fields only. It preserves identifier leading zeros, meaningful address punctuation, type differences, missing/empty distinction and full structure. Normalization collisions remain visible rather than discarding a cell.

Raw and normalized CER each use their own value streams and micro-average summed edits / max(reference characters,1). Missing empty fields can have zero CER but still fail exact equality. Uncalled/error fields are excluded from field accuracy/CER denominators and always shown as separate possible/called/unextracted/error counts. Correct-field coverage over all authored opportunities is labeled coverage, never accuracy.

## Verdict rates and timing

Each group has its own numerator/denominator. Confirmed false rejection applies to expected-valid cases only: final FAIL plus an allowlisted FAIL-severity reupload code. False acceptance is PASS on a negative case. A group with no relevant population shows N/A, not 0%. Review is neither accepted nor confirmed rejected. All ten reupload codes are retained, including zero counts.

Condition tables show A/B processing seconds per physical page alongside both accuracies, classification and unextracted counts. Processing excludes rendering, PNG generation and metric/report calculations; the first own page includes model initialization. Invalid bytes have zero physical pages; their attempts/time are recorded separately and excluded from page-time numerators. This is a local diagnostic runtime measurement, not deployment capacity planning.

## Verification

New tests cover unique source/input generation, preserved geometry/labels, transform/reference geometry, raw/normalized symmetry, unextracted/missing/error denominators, exception/native-output/write guards, wrong-slot separation, groupwise rates, attribution and zero-page timing. Existing tests remain intact. Full engine/backend suites, all 18 scenario modules sequentially and frontend lint/build are required before the final review. Real-document mode is not executed by this command.
