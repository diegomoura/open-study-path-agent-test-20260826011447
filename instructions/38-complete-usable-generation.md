# Complete the usable learning window before visual finishing

Apply this contract during initial curriculum generation and every rolling-window materialization.

The learner-facing operation has two independent completion dimensions:

1. **pedagogical readiness** — lesson, practice, assessment, flashcards, content review and curriculum review are current;
2. **visual readiness** — slide source is reviewed and the committed PDF plus metadata are current.

## Durable states

For every materialized topic, persist these states in the active operation record:

- `lesson_ready`: `pending | ready | failed`;
- `slides_source_ready`: `pending | ready | failed | disabled`;
- `slides_pdf_status`: `pending | ready | failed | disabled`.

Persist the checkpoint `learning_window_usable` as soon as every eligible topic in the active window has `lesson_ready: ready`. Record its timestamp and the exact topic IDs.

PDF generation must never erase or downgrade this checkpoint. A missing, stale or failed PDF changes only `slides_pdf_status`.

## Required order

1. Generate all pedagogical artifacts for the active window.
2. Run content and curriculum review.
3. Refresh every affected generated-artifact fingerprint in one deterministic batch.
4. Run the fast pedagogical validation without installing Playwright or Chromium.
5. Persist `learning_window_usable` when it passes.
6. Generate and review slide sources.
7. Render PDFs and metadata.
8. Run the visual validation separately.
9. Publish external task resources only according to the selected backend's required resource policy.

Do not create one commit per repaired fingerprint. Do not stop after reporting a known deterministic mismatch. Repair all mismatches of the same class before the next push.

## Learner-facing response

When `learning_window_usable` exists, never reply only that creation is incomplete.

Report:

- which lessons are already usable;
- whether slide HTML is ready;
- whether PDFs are ready, pending or failed;
- whether external publication is complete or still pending;
- the exact blocking stage when one remains.

A visual failure must be phrased as an optional or configured-resource failure, not as loss of the completed lessons.

When PDFs are required by the selected publication policy, keep the same operation, branch and pull request recoverable until visual validation succeeds. Do not create a competing recovery branch.

## Timing

Record stage timestamps and durations for at least:

- pedagogical generation;
- review refresh;
- pedagogical validation;
- `learning_window_usable`;
- slide-source generation;
- PDF rendering;
- visual validation;
- external publication.
