# Study slides and PDF delivery

Open Study Path creates a visual presentation for every materialized topic. The deck is derived from the reviewed lesson, uses static SVG diagrams generated from Mermaid source and is delivered to the learner only as PDF.

## Artifact contract

Each materialized topic uses:

```text
study/slides/TOPIC-000/
  index.html
  slides.css
  diagrams/
    *.mmd
    *.svg
  slides.pdf
  slides.meta.json
state/slide-reviews/TOPIC-000.yml
```

The topic contract records `slides`, `slides_pdf` and `slides_review`. HTML, CSS, Mermaid, SVG and metadata remain internal. The learner receives `slides.pdf`.

The module contains one visible **Slides da aula** link:

> Baixe os slides da aula em PDF. Use o PDF para revisão; esta aula continua sendo a fonte principal.

Task projections show resources in this order: slides, complete lesson, optional separate practice and assessment. Do not link source HTML, CSS, Mermaid, SVG, metadata or review evidence.

## Pedagogical quality bar

Deck size follows the estimated study effort: normally 12 slides for 45–60 minutes, about 15 for 75 minutes and about 18 for 90 minutes, with a hard maximum of 24. Slide count is not a quota: every page must carry a real explanatory move.

Required narrative roles are `title`, `map`, `concept`, `diagram`, `example`, `misconception`, `application`, `recap` and `summary`; at least two worked examples appear before learner application.

Slides with substantive roles identify the reviewed lesson section through `data-lesson-section`. Every approved outcome appears on at least two substantive slides through honest `data-outcome-ids`.

Every required concept from the topic contract must appear in visible copy or Mermaid source. Use at least six canonical layout types. Keep one main idea per page and no more than 120 visible words. The complete deck must contain enough explanation to remain useful without turning into a duplicate textbook.

Reject generic filler such as “defina a ideia central”, “aplique a um caso novo” or instructions that could be copied unchanged to another topic. Examples, comparisons and limits must be specific to the lesson.

## Static diagram boundary

Author diagrams as `diagrams/*.mmd`. HTML references the corresponding generated SVG:

```html
<img
  class="osp-diagram-image"
  src="diagrams/generation-cycle.svg"
  data-mermaid-source="diagrams/generation-cycle.mmd"
  alt="Descrição completa do diagrama"
>
```

The CI renderer loads the pinned local Mermaid package through a restricted localhost page and writes SVG before opening the slide HTML. The learner PDF contains no Mermaid runtime and executes no JavaScript. PNG diagrams and full-slide raster images are outside the contract.

Generated SVGs must contain no script or external asset. Each diagram needs alternative text and an explanatory caption that states both interpretation and relevant limit.

## PDF renderer

The renderer:

1. converts each `.mmd` file to SVG with the pinned local Mermaid package;
2. serves only the generated local build tree and renderer dependencies from localhost;
3. blocks external requests and records browser errors;
4. waits for fonts and SVG images;
5. checks overflow at 1280×720;
6. embeds SVG data into a deterministic isolated-page snapshot;
7. renders each slide as an isolated PDF page;
8. merges pages with fixed metadata and provenance;
9. writes `slides.pdf` and `slides.meta.json`;
10. verifies that committed artifacts match current sources.

The learner-facing URL is:

```text
https://github.com/OWNER/REPOSITORY/raw/HEAD/study/slides/TOPIC-000/slides.pdf
```

## CI handoff

The curriculum agent authors sources but does not install Chromium in chat. GitHub Actions renders missing or stale SVG/PDF artifacts and uploads the internal artifact `study-slide-render-output`. The agent downloads that artifact, visually inspects the PDF and commits generated files in one batch.

The artifact is not published to the learner. A missing PDF, stale source digest, missing SVG, external request, browser error, overflow or page-count mismatch prevents merge.

## Independent review

Run `instructions/37-review-study-slides.md` after the lesson passes course-content review and before final rendering. The review artifact uses version 4. A changed lesson, HTML, CSS or Mermaid source invalidates the review and generated output.
