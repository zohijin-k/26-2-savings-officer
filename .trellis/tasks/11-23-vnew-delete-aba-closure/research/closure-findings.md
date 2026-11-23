# Findings
Independent review identified parent id reuse and application_no conflict replacement; all seven guards are required. Youth officer reason projection differs and must be wired separately. Existing full first-submit fixture deleted a Review; replace that setup with an unreviewed fixture. No append-only audit model exists in builtin Application/Review. Original administrative reason for erasing memo/decision was only a code comment, with no approval or restoration path. No intake round is modelled.

SQLite official conflict documentation confirms REPLACE victim deletion and recursive-trigger dependency. Actual 0/1 PRAGMA combinations are tested, not assumed.
