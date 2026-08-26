#!/usr/bin/env python3
"""Apply the one-time textual migration from browser Mermaid/PDF to static SVG/PDF."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "AGENTS.md",
    "README.md",
    "instructions/30-generate-path.md",
    "instructions/36-review-course-content.md",
    "instructions/38-complete-usable-generation.md",
    "instructions/40-publish-tasks.md",
    "instructions/57-materialize-next-content.md",
    "templates/module.md",
    "templates/topic.md",
)

REPLACEMENTS = (
    ("semantic HTML/CSS/JavaScript", "semantic HTML/CSS and Mermaid source files"),
    ("semantic HTML, CSS and JavaScript", "semantic HTML/CSS and Mermaid source files"),
    ("semantic HTML, CSS, JavaScript", "semantic HTML, CSS and Mermaid source files"),
    ("HTML, CSS, JavaScript and render metadata", "HTML, CSS, Mermaid source, generated SVG and render metadata"),
    ("HTML, CSS, JavaScript, render metadata", "HTML, CSS, Mermaid source, generated SVG and render metadata"),
    ("HTML, CSS, JavaScript", "HTML, CSS, Mermaid source files and generated SVG"),
    ("HTML, CSS and JavaScript", "HTML, CSS, Mermaid source files and generated SVG"),
    ("six to eighteen concise 16:9 slides", "twelve to twenty-four topic-specific 16:9 slides according to estimated effort"),
    ("six to eighteen focused 16:9 slides", "twelve to twenty-four topic-specific 16:9 slides according to estimated effort"),
    ("6–18 concise 16:9 slides", "12–24 topic-specific 16:9 slides according to estimated effort"),
    ("six to eighteen", "twelve to twenty-four"),
    ("Mermaid stays as text in HTML and renders to SVG.", "Mermaid is authored in `.mmd` files and rendered to static SVG before HTML inspection and PDF generation."),
    ("include at least one focused Mermaid diagram rendered as SVG", "include at least one focused Mermaid source rendered to static SVG before PDF generation"),
    ("include Mermaid, run slide review, render `slides.pdf`", "include Mermaid source, render it to static SVG, run slide review and render `slides.pdf`"),
    ("include Mermaid, run slide review and build", "include Mermaid source rendered to static SVG, run slide review and build"),
    ("include at least one useful Mermaid diagram", "include at least one useful Mermaid source rendered to static SVG"),
    ("Every slide deck also contains at least one useful Mermaid diagram. Reuse or simplify a reviewed lesson model when it fits the visual narrative.", "Every slide deck also contains at least one useful Mermaid source under `diagrams/`. Reuse or simplify a reviewed lesson model, then render it to static SVG before browser inspection."),
    ("The HTML exists only to build the PDF.", "HTML, CSS, Mermaid sources and generated SVG exist only to build the PDF."),
    ("HTML is build input only.", "HTML, CSS, Mermaid sources and generated SVG are build inputs only."),
    ("A failed render, stale source hash, overflow, Mermaid error, page mismatch or missing PDF", "A failed render, stale source hash, missing SVG, overflow, page mismatch or missing PDF"),
    ("A missing PDF, stale source hash, Mermaid error, overflow, wrong page count", "A missing PDF, stale source hash, missing SVG, overflow, wrong page count"),
    ("do not generate raster illustrations or an image of each slide", "do not generate PNG diagrams, raster illustrations or an image of each slide"),
    ("Do not generate raster illustrations or complete-slide images", "Do not generate PNG diagrams, raster illustrations or complete-slide images"),
    ("rendered as SVG", "rendered to static SVG"),
)


def replace_unmigrated(text: str, old: str, new: str) -> str:
    """Replace old occurrences while preserving occurrences already expanded to new.

    Some migrations append text to an existing sentence, so ``old`` can be a
    prefix of ``new``. A plain ``str.replace`` would expand that sentence on
    every run. This scanner skips complete ``new`` occurrences and migrates
    only the remaining ``old`` occurrences.
    """
    if old == new or old not in text:
        return text
    output: list[str] = []
    cursor = 0
    while True:
        index = text.find(old, cursor)
        if index < 0:
            output.append(text[cursor:])
            return "".join(output)
        output.append(text[cursor:index])
        if text.startswith(new, index):
            output.append(new)
            cursor = index + len(new)
        else:
            output.append(new)
            cursor = index + len(old)


def main() -> None:
    changed: list[str] = []
    for relative in TARGETS:
        path = ROOT / relative
        if not path.is_file():
            continue
        before = path.read_text(encoding="utf-8")
        after = before
        for old, new in REPLACEMENTS:
            after = replace_unmigrated(after, old, new)
        if relative in {"AGENTS.md", "instructions/30-generate-path.md"}:
            after = replace_unmigrated(
                after,
                "Create semantic HTML/CSS and Mermaid source files under `study/slides/TOPIC-000/`, derive concise slides",
                "Create semantic HTML/CSS and Mermaid source files under `study/slides/TOPIC-000/`, derive 12–24 topic-specific slides according to estimated effort",
            )
            after = replace_unmigrated(
                after,
                "The slide deck inherits these reviewed claims. It does not run a second research pass or introduce unsupported claims.",
                "The slide deck inherits these reviewed claims. It does not run a second research pass or introduce unsupported claims. It must preserve every required concept and at least two worked examples instead of compressing the lesson into a generic shell.",
            )
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append(relative)
    print(f"Static SVG/PDF contract text migration updated {len(changed)} file(s).")


if __name__ == "__main__":
    main()
