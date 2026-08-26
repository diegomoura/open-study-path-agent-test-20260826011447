# Independent study-slide review

Run this review after the complete lesson, practice and assessment pass `instructions/36-review-course-content.md` and after semantic slide HTML and Mermaid sources have been authored. It is separate from lesson authorship and PDF rendering.

## Role

Act as the **study-slides reviewer**. Re-read the approved topic contract, reviewed lesson and complete visual deck. Do not approve because files, headings or outcome IDs merely exist.

The reviewer answers:

> Does this presentation preserve the lesson's real explanatory depth as a coherent visual explanation, with static diagrams and a reliable learner-facing PDF?

## Review sequence

1. Confirm the current lesson version has an approved course-content review.
2. Confirm `slides.css` matches the canonical template and the HTML contains no script.
3. Compare every approved required concept with visible slide copy or a Mermaid source.
4. Inspect every slide at 1280×720 and read the complete deck as a narrative.
5. Verify that every generated diagram is a local SVG bound to a reviewed `.mmd` source.
6. Verify at least two complete, topic-specific worked examples.
7. Reject generic wording that could be copied unchanged to an unrelated lesson.
8. Verify every outcome appears on at least two substantive slides.
9. Correct all blocking findings in HTML or `.mmd` sources.
10. Record evidence in `state/slide-reviews/TOPIC-000.yml` using review version 4.
11. Render and visually inspect `slides.pdf`, then run deterministic validation.

## Required dimensions

- `lesson_fidelity`: no unsupported facts, sources or recommendations;
- `outcome_coverage`: every outcome is genuinely represented more than once;
- `required_concept_coverage`: every required concept is explained or visualized;
- `narrative_arc`: useful result, early map, concepts, diagram, two examples, misconception, application, recall and synthesis;
- `worked_example_quality`: both examples include situation, reasoning, result and verification;
- `content_density`: the deck is a useful visual summary, not a set of slogans;
- `topic_specificity`: wording, examples and decisions are recognizably tied to this lesson;
- `summary_quality`: concise but explanatory;
- `visual_variety`: at least six canonical composition patterns;
- `visual_hierarchy`: readable at 1280×720 with no overflow;
- `static_svg_quality`: diagrams are focused, explained, safe, static and legible;
- `accessibility`: semantic headings, contrast, alternative text and no color-only meaning;
- `link_consistency`: PDF is the only learner-facing slide artifact;
- `pdf_delivery`: one page per slide, current provenance and no missing content.

## Learner-facing boundary

The module and tasks link only to:

```text
https://github.com/OWNER/REPOSITORY/raw/HEAD/study/slides/TOPIC-000/slides.pdf
```

Never link `index.html`, `slides.css`, `.mmd`, `.svg`, `slides.meta.json` or review evidence. Do not mention ZIP extraction or browser execution.

## Durable review evidence

Approve only when every check is `passed`, every outcome is reviewed and no blocking finding remains. A technically valid but visually thin, generic, clipped or stale deck must not be approved.
