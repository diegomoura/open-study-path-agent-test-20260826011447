#!/usr/bin/env python3
"""Validate semantic slide sources, static Mermaid SVGs and learner-facing PDFs."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json
import math
import re
import unicodedata
from typing import Any, Mapping
from xml.etree import ElementTree

import yaml
from pypdf import PdfReader

OUTCOME_ID = re.compile(r"^LO-[1-9][0-9]*$")
TOPIC_ID = re.compile(r"^TOPIC-[0-9]{3,}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
SLIDES_LINK_START = "<!-- open-study-path:slides-link:start -->"
SLIDES_LINK_END = "<!-- open-study-path:slides-link:end -->"
THEME_NAME = "canonical-v3"
CONTRACT_VERSION = 3
RENDERER_ID = "open-study-path-html-svg-pdf-v3"
PDF_PRODUCER = "Open Study Path static SVG PDF renderer v3"
CSS_MARKER = "open-study-path:study-slides-theme version=3"
MIN_SLIDES_FLOOR = 12
MAX_SLIDES = 24
REQUIRED_ROLES = (
    "title", "map", "concept", "diagram", "example", "misconception", "application", "recap", "summary"
)
TRACEABLE_ROLES = {"concept", "diagram", "example", "misconception", "application", "recap"}
SUBSTANTIVE_ROLES = TRACEABLE_ROLES
LAYOUT_CLASSES = {
    "osp-title-layout", "osp-grid", "osp-compare", "osp-diagram", "osp-case", "osp-steps",
    "osp-challenge", "osp-checklist", "osp-prompt-grid", "osp-summary-layout", "osp-code-layout",
    "osp-process", "osp-matrix", "osp-stack", "osp-spectrum",
}
REQUIRED_REVIEW_CHECKS = (
    "lesson_fidelity", "outcome_coverage", "required_concept_coverage", "narrative_arc",
    "worked_example_quality", "content_density", "topic_specificity", "summary_quality",
    "visual_variety", "visual_hierarchy", "static_svg_quality", "accessibility",
    "link_consistency", "pdf_delivery",
)
FORBIDDEN_GENERIC_PHRASES = (
    "use a definição para explicar uma decisão concreta",
    "relacione o objeto com o restante do fluxo",
    "defina a transformação esperada",
    "separe o que precisa ser validado",
    "mostre como confirmar o resultado",
    "defina a ideia central",
    "aplique a um caso novo",
    "o controle externo continua necessário",
    "cada seta representa uma responsabilidade que pode ser explicada e testada",
    "construa um modelo mental que possa ser explicado, testado e usado nas próximas etapas",
)


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_marks.lower()).strip()


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing YAML frontmatter: {path}")
    try:
        _, raw, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"malformed YAML frontmatter: {path}") from exc
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter must be an object: {path}")
    return data, body


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def aggregate_source_sha256(paths: list[Path], root: Path) -> str:
    digest = sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def slides_contract(instance: Mapping[str, Any]) -> int:
    contract = _mapping(instance.get("study_slides"))
    try:
        return int(contract.get("contract_version", 0))
    except (TypeError, ValueError):
        return 0


def slides_enabled(instance: Mapping[str, Any]) -> bool:
    contract = _mapping(instance.get("study_slides"))
    return (
        slides_contract(instance) == CONTRACT_VERSION
        and contract.get("enabled") is True
        and contract.get("required_for_materialized_topics") is True
        and _text(contract.get("source_format")) == "html"
        and _text(contract.get("learner_format")) == "pdf"
        and _text(contract.get("document_name")) == "slides.pdf"
        and _text(contract.get("html_visibility")) == "internal_only"
        and _text(contract.get("diagram_source_format")) == "mermaid"
        and _text(contract.get("diagram_render_format")) == "svg"
        and contract.get("generated_images_enabled") is False
        and contract.get("mermaid_required") is True
    )


def slides_deliberately_disabled(instance: Mapping[str, Any]) -> bool:
    """True only when the instance explicitly turned study_slides off.

    `enabled: False` is the one field an instance sets to make a considered,
    all-or-nothing decision not to produce slides at all (see the Etapa 5b
    agent-pilot toggle, docs/claude-agent-pilot-etapa5.md) -- distinct from
    every other way `slides_enabled()` can return False, which is a
    misconfiguration (wrong contract_version, a required field left unset or
    wrong) that must still fail loudly. Any other field is irrelevant once
    `enabled` is explicitly False: there is nothing left to validate.
    """
    contract = _mapping(instance.get("study_slides"))
    return contract.get("enabled") is False


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class SlideHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.topic_id = ""
        self.content_version: int | None = None
        self.theme = ""
        self.slides: list[dict[str, Any]] = []
        self.stylesheet = ""
        self.script_count = 0
        self.inline_style_count = 0
        self.external_runtime_urls: list[str] = []
        self._slide_depth = 0
        self._current: dict[str, Any] | None = None
        self._heading_depth = 0

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self._attrs(attrs)
        classes = set(values.get("class", "").split())
        if tag == "meta":
            name = values.get("name")
            content = values.get("content", "")
            if name == "open-study-path:topic-id":
                self.topic_id = content
            elif name == "open-study-path:content-version":
                try:
                    self.content_version = int(content)
                except ValueError:
                    self.content_version = None
            elif name == "open-study-path:slide-theme":
                self.theme = content
        elif tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheet = values.get("href", "")
            if self.stylesheet.startswith(("http://", "https://", "//")):
                self.external_runtime_urls.append(self.stylesheet)
        elif tag == "script":
            self.script_count += 1
        elif tag == "style":
            self.inline_style_count += 1

        if tag in {"img", "source", "video", "audio", "iframe"}:
            url = values.get("src", "")
            if url.startswith(("http://", "https://", "//")):
                self.external_runtime_urls.append(url)

        if tag == "section" and "osp-slide" in classes:
            self._current = {
                "outcomes": [value for value in values.get("data-outcome-ids", "").split() if value],
                "heading": "",
                "text": [],
                "role": values.get("data-slide-role", ""),
                "lesson_section": values.get("data-lesson-section", ""),
                "layouts": set(classes & LAYOUT_CLASSES),
                "diagram_images": [],
                "has_caption": False,
            }
            self.slides.append(self._current)
            self._slide_depth = 1
            return

        if self._slide_depth and self._current is not None:
            if tag not in VOID_TAGS:
                self._slide_depth += 1
            self._current["layouts"].update(classes & LAYOUT_CLASSES)
            if "osp-caption" in classes:
                self._current["has_caption"] = True
            if tag == "img" and "osp-diagram-image" in classes:
                self._current["diagram_images"].append({
                    "src": values.get("src", ""),
                    "source": values.get("data-mermaid-source", ""),
                    "alt": values.get("alt", ""),
                })
            if tag in {"h1", "h2"}:
                self._heading_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._slide_depth:
            return
        if tag in {"h1", "h2"} and self._heading_depth:
            self._heading_depth -= 1
        self._slide_depth -= 1
        if self._slide_depth == 0:
            self._current = None

    def handle_data(self, data: str) -> None:
        if not self._current:
            return
        text = " ".join(data.split())
        if not text:
            return
        self._current["text"].append(text)
        if self._heading_depth:
            self._current["heading"] = f"{self._current['heading']} {text}".strip()


def parse_slide_html(path: Path) -> SlideHTMLParser:
    parser = SlideHTMLParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def expected_pdf_url(repository: str, pdf_path: str) -> str:
    return f"https://github.com/{repository}/raw/HEAD/{pdf_path}"


def source_paths(topic_dir: Path) -> list[Path]:
    return [topic_dir / "index.html", topic_dir / "slides.css", *sorted((topic_dir / "diagrams").glob("*.mmd"))]


def generated_svg_paths(topic_dir: Path) -> list[Path]:
    return sorted((topic_dir / "diagrams").glob("*.svg"))


def _validate_svg(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        content = path.read_text(encoding="utf-8")
        root = ElementTree.fromstring(content)
    except (OSError, UnicodeDecodeError, ElementTree.ParseError) as exc:
        return [f"invalid generated SVG {path}: {exc}"]
    if not root.tag.lower().endswith("svg"):
        errors.append(f"generated diagram is not an SVG root: {path}")
    lowered = content.lower()
    if "<script" in lowered:
        errors.append(f"generated SVG contains script content: {path}")
    if re.search(r"(?:href|src)\s*=\s*[\"'](?:https?:)?//", lowered):
        errors.append(f"generated SVG contains an external resource: {path}")
    if re.search(r"url\(\s*[\"']?(?:https?:)?//", lowered):
        errors.append(f"generated SVG contains an external CSS resource: {path}")
    return errors


def minimum_slide_count(estimated_hours: Any) -> int:
    try:
        hours = float(estimated_hours)
    except (TypeError, ValueError):
        hours = 1.0
    return max(MIN_SLIDES_FLOOR, min(MAX_SLIDES, math.ceil(hours * 12)))


def _validate_assets(root: Path, topic_id: str, css_path: Path) -> list[str]:
    errors: list[str] = []
    template = root / "templates/study-slides/slides.css"
    content = css_path.read_text(encoding="utf-8")
    if CSS_MARKER not in content:
        errors.append(f"{topic_id} slide CSS is missing the canonical-v3 marker")
    if template.is_file() and css_path.read_bytes() != template.read_bytes():
        errors.append(f"{topic_id} slide CSS must use the canonical-v3 template unchanged")
    return errors


def _validate_deck_structure(topic: Mapping[str, Any], parser: SlideHTMLParser, mmd_text: str) -> list[str]:
    errors: list[str] = []
    topic_id = _text(topic.get("id"))
    expected_min = minimum_slide_count(topic.get("estimated_hours"))
    if parser.theme != THEME_NAME:
        errors.append(f"{topic_id} slide HTML must declare theme {THEME_NAME}")
    if not expected_min <= len(parser.slides) <= MAX_SLIDES:
        errors.append(f"{topic_id} must contain between {expected_min} and {MAX_SLIDES} slides for its estimated effort")
    roles = [_text(slide.get("role")) for slide in parser.slides]
    for role in REQUIRED_ROLES:
        if role not in roles:
            errors.append(f"{topic_id} slide deck is missing required narrative role: {role}")
    if roles:
        if roles[0] != "title":
            errors.append(f"{topic_id} first slide role must be title")
        if roles[-1] != "summary":
            errors.append(f"{topic_id} final slide role must be summary")
        if "map" in roles and roles.index("map") > 2:
            errors.append(f"{topic_id} map slide must appear within the first three slides")
        if roles.count("example") < 2:
            errors.append(f"{topic_id} must contain at least two topic-specific worked examples")
        if "example" in roles and "application" in roles and roles.index("example") > roles.index("application"):
            errors.append(f"{topic_id} worked examples must appear before learner application")

    layouts: set[str] = set()
    all_visible_text: list[str] = []
    represented: dict[str, int] = {}
    diagram_count = 0
    for slide in parser.slides:
        layouts.update(slide.get("layouts", set()))
        role = _text(slide.get("role"))
        if role in TRACEABLE_ROLES and not _text(slide.get("lesson_section")):
            errors.append(f"{topic_id} {role} slide is missing data-lesson-section")
        words = " ".join(slide.get("text", [])).split()
        all_visible_text.extend(words)
        if len(words) > 120:
            errors.append(f"{topic_id} slide '{slide.get('heading')}' exceeds 120 visible words")
        if role in SUBSTANTIVE_ROLES:
            for outcome in slide.get("outcomes", []):
                represented[outcome] = represented.get(outcome, 0) + 1
        diagrams = slide.get("diagram_images", [])
        diagram_count += len(diagrams)
        for diagram in diagrams:
            if not _text(diagram.get("src")).endswith(".svg"):
                errors.append(f"{topic_id} diagram image must use a local SVG")
            if not _text(diagram.get("source")).endswith(".mmd"):
                errors.append(f"{topic_id} diagram image must declare its Mermaid source")
            if not _text(diagram.get("alt")):
                errors.append(f"{topic_id} diagram image is missing alternative text")
            if not slide.get("has_caption"):
                errors.append(f"{topic_id} diagram slide is missing an osp-caption interpretation")

    if len(layouts) < 6:
        errors.append(f"{topic_id} must use at least six canonical layout types; got {sorted(layouts)}")
    if diagram_count < 1:
        errors.append(f"{topic_id} slide deck must reference at least one generated Mermaid SVG")
    if len(all_visible_text) < len(parser.slides) * 24:
        errors.append(f"{topic_id} slide deck is too thin: {len(all_visible_text)} visible words for {len(parser.slides)} slides")

    outcomes = [_text(_mapping(value).get("id")) for value in _list(topic.get("learning_outcomes"))]
    for outcome in outcomes:
        if represented.get(outcome, 0) < 2:
            errors.append(f"{topic_id} outcome {outcome} must appear on at least two substantive slides")
    if any(not OUTCOME_ID.fullmatch(value) for value in represented):
        errors.append(f"{topic_id} slides contain invalid outcome IDs")

    combined = normalize_text(" ".join(all_visible_text) + " " + mmd_text)
    for outcome in _list(topic.get("learning_outcomes")):
        for concept in _list(_mapping(outcome).get("required_concepts")):
            normalized = normalize_text(_text(concept))
            if normalized and normalized not in combined:
                errors.append(f"{topic_id} slides do not visibly cover required concept: {_text(concept)}")
    for phrase in FORBIDDEN_GENERIC_PHRASES:
        if normalize_text(phrase) in combined:
            errors.append(f"{topic_id} slide deck contains generic placeholder copy: {phrase}")
    return errors


def _validate_review(root: Path, topic: Mapping[str, Any], lesson: Path, sources: list[Path], review: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    topic_id = _text(topic.get("id"))
    outcomes = [_text(_mapping(value).get("id")) for value in _list(topic.get("learning_outcomes"))]
    if review.get("version") != 4:
        errors.append(f"{topic_id} slide review must use version 4")
    if _text(review.get("topic_id")) != topic_id:
        errors.append(f"{topic_id} slide review topic_id mismatch")
    if review.get("content_version") != topic.get("content_version"):
        errors.append(f"{topic_id} slide review is stale")
    if _text(review.get("reviewer_role")) != "study_slides_reviewer":
        errors.append(f"{topic_id} slide review must use study_slides_reviewer")
    if _text(review.get("review_mode")) != "independent_pass":
        errors.append(f"{topic_id} slide review must use independent_pass")
    if _text(review.get("status")) != "approved":
        errors.append(f"{topic_id} slide review status must be approved")
    if not _text(review.get("reviewed_at")):
        errors.append(f"{topic_id} slide review is missing reviewed_at")
    checks = _mapping(review.get("checks"))
    for check in REQUIRED_REVIEW_CHECKS:
        if _text(checks.get(check)) != "passed":
            errors.append(f"{topic_id} slide review check must pass: {check}")
    if _text(review.get("source_lesson")) != lesson.relative_to(root).as_posix():
        errors.append(f"{topic_id} slide review source_lesson mismatch")
    if _text(review.get("source_lesson_sha256")) != file_sha256(lesson):
        errors.append(f"{topic_id} slide review lesson hash is stale")
    if _text(review.get("slides_source")) != sources[0].relative_to(root).as_posix():
        errors.append(f"{topic_id} slide review slides_source mismatch")
    if _text(review.get("slides_source_sha256")) != aggregate_source_sha256(sources, root):
        errors.append(f"{topic_id} slide review source hash is stale")
    reviewed = [_text(value) for value in _list(review.get("outcomes_reviewed"))]
    if reviewed != outcomes:
        errors.append(f"{topic_id} slide review outcomes mismatch: expected {outcomes}, got {reviewed}")
    if _list(review.get("blocking_findings")):
        errors.append(f"{topic_id} slide review has blocking findings")
    return errors


def _validate_pdf(topic_id: str, pdf_path: Path, meta_path: Path, sources: list[Path], svgs: list[Path], root: Path, slide_count: int) -> list[str]:
    errors: list[str] = []
    try:
        pdf_bytes = pdf_path.read_bytes()
        if not pdf_bytes.startswith(b"%PDF-"):
            errors.append(f"{topic_id} slides.pdf does not start with a PDF header")
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        return [f"{topic_id} slides.pdf cannot be read: {exc}"]
    if len(reader.pages) != slide_count:
        errors.append(f"{topic_id} PDF page count mismatch: expected {slide_count}, got {len(reader.pages)}")
    metadata = reader.metadata or {}
    producer = _text(metadata.get("/Producer"))
    title = _text(metadata.get("/Title"))
    subject = _text(metadata.get("/Subject"))
    if producer != PDF_PRODUCER:
        errors.append(f"{topic_id} PDF producer mismatch")
    if title != f"{topic_id} study slides":
        errors.append(f"{topic_id} PDF title metadata mismatch")

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return errors + [f"{topic_id} slides.meta.json is invalid: {exc}"]
    if meta.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"{topic_id} slides metadata must use contract_version {CONTRACT_VERSION}")
    if _text(_mapping(meta.get("renderer")).get("id")) != RENDERER_ID:
        errors.append(f"{topic_id} slides metadata renderer mismatch")
    expected_digest = aggregate_source_sha256(sources, root)
    if _text(meta.get("source_digest")) != expected_digest:
        errors.append(f"{topic_id} slides metadata source_digest is stale")
    source_hashes = _mapping(meta.get("source_sha256"))
    for source in sources:
        relative = source.relative_to(root).as_posix()
        if _text(source_hashes.get(relative)) != file_sha256(source):
            errors.append(f"{topic_id} slides metadata source hash is stale: {relative}")
    svg_hashes = _mapping(meta.get("svg_sha256"))
    for svg in svgs:
        relative = svg.relative_to(root).as_posix()
        if _text(svg_hashes.get(relative)) != file_sha256(svg):
            errors.append(f"{topic_id} slides metadata SVG hash is stale: {relative}")
    pdf_meta = _mapping(meta.get("pdf"))
    if pdf_meta.get("pages") != slide_count:
        errors.append(f"{topic_id} slides metadata page count mismatch")
    if pdf_meta.get("bytes") != len(pdf_bytes):
        errors.append(f"{topic_id} slides metadata PDF byte count mismatch")
    if _text(pdf_meta.get("sha256")) != sha256(pdf_bytes).hexdigest():
        errors.append(f"{topic_id} slides metadata PDF hash is stale")
    snapshot = _text(meta.get("rendered_snapshot_sha256"))
    if not SHA256_HEX.fullmatch(snapshot):
        errors.append(f"{topic_id} rendered snapshot hash is invalid")
    expected_subject = f"open-study-path-renderer:{RENDERER_ID};source:{expected_digest};snapshot:{snapshot}"
    if subject != expected_subject:
        errors.append(f"{topic_id} PDF provenance metadata mismatch")
    diagnostics = _mapping(meta.get("diagnostics"))
    for key in ("console_errors", "overflow_slides", "external_requests", "missing_diagrams"):
        if _list(diagnostics.get(key)):
            errors.append(f"{topic_id} renderer diagnostics are not clean: {key}")
    return errors


def validate_materialized_topic(root: Path, repository: str, topic: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    topic_id = _text(topic.get("id"))
    if not TOPIC_ID.fullmatch(topic_id):
        return [f"invalid materialized topic id: {topic_id!r}"]
    required_paths = {
        "module": _text(topic.get("module")),
        "slides": _text(topic.get("slides")),
        "slides_pdf": _text(topic.get("slides_pdf")),
        "slides_review": _text(topic.get("slides_review")),
    }
    for key, relative in required_paths.items():
        if not relative:
            errors.append(f"{topic_id} is missing {key}")
        elif not (root / relative).is_file():
            errors.append(f"{topic_id} {key} is missing: {relative}")
    if _text(topic.get("slides_package")):
        errors.append(f"{topic_id} still declares the removed slides_package field")
    if errors:
        return errors

    lesson = root / required_paths["module"]
    topic_dir = (root / required_paths["slides"]).parent
    sources = source_paths(topic_dir)
    if not sources[0].is_file() or not sources[1].is_file() or len(sources) < 3:
        return [f"{topic_id} slide sources must include index.html, slides.css and at least one diagrams/*.mmd"]
    parser = parse_slide_html(sources[0])
    if parser.topic_id != topic_id:
        errors.append(f"{topic_id} source HTML topic metadata mismatch")
    if parser.content_version != topic.get("content_version"):
        errors.append(f"{topic_id} source HTML content version mismatch")
    if parser.stylesheet != "slides.css":
        errors.append(f"{topic_id} source HTML must reference local slides.css")
    if parser.script_count:
        errors.append(f"{topic_id} source HTML must not execute JavaScript")
    if parser.external_runtime_urls:
        errors.append(f"{topic_id} source HTML has external runtime assets")
    errors.extend(_validate_assets(root, topic_id, sources[1]))

    mmd_text = "\n".join(path.read_text(encoding="utf-8") for path in sources[2:])
    errors.extend(_validate_deck_structure(topic, parser, mmd_text))

    referenced_svgs: set[Path] = set()
    referenced_mmds: set[Path] = set()
    for slide in parser.slides:
        for diagram in slide.get("diagram_images", []):
            referenced_svgs.add(topic_dir / _text(diagram.get("src")))
            referenced_mmds.add(topic_dir / _text(diagram.get("source")))
    for path in sorted(referenced_mmds):
        if path not in sources:
            errors.append(f"{topic_id} HTML references unknown Mermaid source: {path.relative_to(root)}")
    for path in sorted(referenced_svgs):
        if not path.is_file():
            errors.append(f"{topic_id} generated SVG is missing: {path.relative_to(root)}")
        else:
            errors.extend(_validate_svg(path))
    svgs = generated_svg_paths(topic_dir)
    if set(svgs) != referenced_svgs:
        errors.append(f"{topic_id} generated SVG set must exactly match diagrams referenced by HTML")
    if any(path.suffix.lower() == ".png" for path in topic_dir.rglob("*")):
        errors.append(f"{topic_id} must not contain generated PNG slide assets")
    if (topic_dir / "slides.zip").exists() or (topic_dir / "slides.js").exists():
        errors.append(f"{topic_id} retains removed ZIP or JavaScript slide artifacts")

    meta_path = topic_dir / "slides.meta.json"
    if not meta_path.is_file():
        errors.append(f"{topic_id} slides metadata is missing")
    else:
        errors.extend(_validate_pdf(topic_id, root / required_paths["slides_pdf"], meta_path, sources, svgs, root, len(parser.slides)))
    review = _mapping(load_yaml(root / required_paths["slides_review"]))
    errors.extend(_validate_review(root, topic, lesson, sources, review))

    expected_url = expected_pdf_url(repository, required_paths["slides_pdf"])
    lesson_text = lesson.read_text(encoding="utf-8")
    if lesson_text.count(SLIDES_LINK_START) != 1 or lesson_text.count(SLIDES_LINK_END) != 1:
        errors.append(f"{topic_id} lesson must contain exactly one managed slides-link block")
    if expected_url not in lesson_text:
        errors.append(f"{topic_id} lesson is missing the current PDF slides link")
    if "slides.zip" in lesson_text.lower() or "slides.html" in lesson_text.lower():
        errors.append(f"{topic_id} lesson still exposes removed ZIP/HTML slide instructions")
    return errors


def validate_repository(root: Path) -> ValidationResult:
    instance_path = root / ".open-study-path/instance.yml"
    if not instance_path.is_file():
        instance_path = root / "templates/instance.yml"
    instance = _mapping(load_yaml(instance_path)) if instance_path.is_file() else {}
    if slides_deliberately_disabled(instance):
        # A genuine, explicit opt-out (study_slides.enabled: false) is not a
        # misconfiguration -- nothing to check, pass silently. Materialized
        # topics are allowed to exist without slides in this mode; the
        # per-topic loop below is simply never reached.
        return ValidationResult(())
    contract = slides_contract(instance)
    if contract == 2:
        from study_slides_legacy import validate_repository as validate_legacy
        return validate_legacy(root)
    errors: list[str] = []
    if not slides_enabled(instance):
        errors.append("study_slides must use contract_version 3 with PDF delivery and static Mermaid SVG")
        return ValidationResult(tuple(errors))
    repository = _text(instance.get("repository")) or "OWNER/REPOSITORY"
    topics_dir = root / "study/topics"
    if topics_dir.is_dir():
        for path in sorted(topics_dir.glob("TOPIC-*.md")):
            try:
                topic, _ = parse_frontmatter(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if _text(topic.get("content_status")) == "materialized":
                errors.extend(validate_materialized_topic(root, repository, topic))
    return ValidationResult(tuple(errors))
