#!/usr/bin/env python3
"""Validate semantic study-slide sources, review evidence and offline ZIP delivery."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import json
import re
from typing import Any, Mapping
from zipfile import ZipFile, BadZipFile

import yaml

OUTCOME_ID = re.compile(r"^LO-[1-9][0-9]*$")
TOPIC_ID = re.compile(r"^TOPIC-[0-9]{3,}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
SLIDES_LINK_START = "<!-- open-study-path:slides-link:start -->"
SLIDES_LINK_END = "<!-- open-study-path:slides-link:end -->"
MIN_SLIDES = 8
MAX_SLIDES = 18
THEME_NAME = "canonical-v2"
PACKAGE_BUILDER_ID = "open-study-path-html-zip-v1"
PACKAGE_ENTRYPOINT = "slides.html"
CSS_MARKER = "open-study-path:study-slides-theme version=2"
JS_MARKER = "open-study-path:study-slides-runtime version=3"
PACKAGE_MARKER = "open-study-path:packaged-slides version=1"
REQUIRED_ROLES = (
    "title", "map", "diagram", "example", "misconception", "application", "summary"
)
TRACEABLE_ROLES = {"concept", "diagram", "example", "misconception", "application", "recap"}
LAYOUT_CLASSES = {
    "osp-title-layout", "osp-grid", "osp-compare", "osp-diagram", "osp-case",
    "osp-steps", "osp-challenge", "osp-checklist", "osp-prompt-grid", "osp-summary-layout",
}
REQUIRED_REVIEW_CHECKS = (
    "lesson_fidelity", "outcome_coverage", "narrative_arc", "worked_example_quality",
    "summary_quality", "visual_variety", "visual_hierarchy", "mermaid_quality",
    "accessibility", "link_consistency", "offline_delivery",
)
SOURCE_FILENAMES = ("index.html", "slides.css", "slides.js")


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


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing YAML frontmatter: {path}")
    _, raw, body = text.split("---", 2)
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


def slides_enabled(instance: Mapping[str, Any]) -> bool:
    contract = _mapping(instance.get("study_slides"))
    return (
        contract.get("contract_version") == 2
        and contract.get("enabled") is True
        and contract.get("required_for_materialized_topics") is True
        and _text(contract.get("source_format")) == "html"
        and _text(contract.get("learner_format")) == "zip_html"
        and _text(contract.get("archive_entrypoint")) == PACKAGE_ENTRYPOINT
    )


class SlideHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.topic_id = ""
        self.content_version: int | None = None
        self.theme = ""
        self.slides: list[dict[str, Any]] = []
        self.mermaid_count = 0
        self.image_count = 0
        self.external_runtime_urls: list[str] = []
        self.stylesheet = ""
        self.script = ""
        self.inline_style_count = 0
        self.inline_script_count = 0
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
        if tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheet = values.get("href", "")
            if self.stylesheet.startswith(("http://", "https://", "//")):
                self.external_runtime_urls.append(self.stylesheet)
        if tag == "script":
            if values.get("src"):
                self.script = values["src"]
                if self.script.startswith(("http://", "https://", "//")):
                    self.external_runtime_urls.append(self.script)
            else:
                self.inline_script_count += 1
        if tag == "style":
            self.inline_style_count += 1
        if tag in {"img", "source", "video", "audio", "iframe"}:
            url = values.get("src", "")
            if tag == "img":
                self.image_count += 1
            if url.startswith(("http://", "https://", "//")):
                self.external_runtime_urls.append(url)
        if tag == "section" and "osp-slide" in classes:
            outcomes = [v for v in values.get("data-outcome-ids", "").split() if v]
            self._current = {
                "outcomes": outcomes,
                "heading": "",
                "text": [],
                "role": values.get("data-slide-role", ""),
                "lesson_section": values.get("data-lesson-section", ""),
                "layouts": set(classes & LAYOUT_CLASSES),
                "has_mermaid": False,
                "has_caption": False,
            }
            self.slides.append(self._current)
            self._slide_depth = 1
            return
        if self._slide_depth and self._current is not None:
            self._slide_depth += 1
            self._current["layouts"].update(classes & LAYOUT_CLASSES)
            if "mermaid" in classes:
                self.mermaid_count += 1
                self._current["has_mermaid"] = True
            if "osp-caption" in classes:
                self._current["has_caption"] = True
            if tag in {"h1", "h2"}:
                self._heading_depth = 1
        elif "mermaid" in classes:
            self.mermaid_count += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._slide_depth:
            return
        if self._heading_depth:
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


def parse_slide_html_text(text: str) -> SlideHTMLParser:
    parser = SlideHTMLParser()
    parser.feed(text)
    return parser


def parse_slide_html(path: Path) -> SlideHTMLParser:
    return parse_slide_html_text(path.read_text(encoding="utf-8"))


def expected_package_url(repository: str, package_path: str) -> str:
    return f"https://github.com/{repository}/raw/HEAD/{package_path}"


def _validate_assets(root: Path, topic_id: str, source_paths: list[Path]) -> list[str]:
    errors: list[str] = []
    template_dir = root / "templates" / "study-slides"
    css_template = template_dir / "slides.css"
    js_template = template_dir / "slides.js"
    css_path, js_path = source_paths[1], source_paths[2]
    if CSS_MARKER not in css_path.read_text(encoding="utf-8"):
        errors.append(f"{topic_id} slide CSS is missing the canonical-v2 theme marker")
    if JS_MARKER not in js_path.read_text(encoding="utf-8"):
        errors.append(f"{topic_id} slide runtime is missing the version=3 marker")
    if css_template.is_file() and css_path.read_bytes() != css_template.read_bytes():
        errors.append(f"{topic_id} slide CSS must use the canonical-v2 template unchanged")
    if js_template.is_file() and js_path.read_bytes() != js_template.read_bytes():
        errors.append(f"{topic_id} slide runtime must use the canonical template unchanged")
    return errors


def _validate_deck_structure(topic_id: str, parser: SlideHTMLParser) -> list[str]:
    errors: list[str] = []
    if parser.theme != THEME_NAME:
        errors.append(f"{topic_id} slide HTML must declare theme {THEME_NAME}")
    if not MIN_SLIDES <= len(parser.slides) <= MAX_SLIDES:
        errors.append(f"{topic_id} must contain between {MIN_SLIDES} and {MAX_SLIDES} slides")
    if parser.mermaid_count < 1:
        errors.append(f"{topic_id} slide deck must contain at least one Mermaid diagram")
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
        if "example" in roles and "application" in roles and roles.index("example") > roles.index("application"):
            errors.append(f"{topic_id} worked example must appear before learner application")
    layouts: set[str] = set()
    for slide in parser.slides:
        layouts.update(slide.get("layouts", set()))
        if slide.get("role") in TRACEABLE_ROLES and not _text(slide.get("lesson_section")):
            errors.append(f"{topic_id} {slide.get('role')} slide is missing data-lesson-section")
        words = " ".join(slide.get("text", [])).split()
        if len(words) > 120:
            errors.append(f"{topic_id} slide '{slide.get('heading')}' exceeds 120 words")
        if slide.get("has_mermaid") and not slide.get("has_caption"):
            errors.append(f"{topic_id} Mermaid slide is missing an osp-caption interpretation")
    if len(layouts) < 5:
        errors.append(f"{topic_id} must use at least five canonical layout types; got {sorted(layouts)}")
    return errors


def _validate_review(root: Path, topic: Mapping[str, Any], lesson: Path, sources: list[Path], review: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    topic_id = _text(topic.get("id"))
    outcomes = [_text(_mapping(v).get("id")) for v in _list(topic.get("learning_outcomes")) if _text(_mapping(v).get("id"))]
    if review.get("version") != 3:
        errors.append(f"{topic_id} slide review must use version 3")
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
    reviewed = [_text(v) for v in _list(review.get("outcomes_reviewed")) if _text(v)]
    if reviewed != outcomes:
        errors.append(f"{topic_id} slide review outcomes mismatch: expected {outcomes}, got {reviewed}")
    if _list(review.get("blocking_findings")):
        errors.append(f"{topic_id} slide review has blocking findings")
    return errors


def _safe_zip_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _validate_package(topic_id: str, package_path: Path, meta_path: Path, source_paths: list[Path], root: Path) -> tuple[list[str], str]:
    errors: list[str] = []
    packaged_html = ""
    try:
        with ZipFile(package_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != [PACKAGE_ENTRYPOINT]:
                errors.append(f"{topic_id} ZIP must contain exactly {PACKAGE_ENTRYPOINT}; got {names}")
            for info in infos:
                if not _safe_zip_name(info.filename):
                    errors.append(f"{topic_id} ZIP contains an unsafe path: {info.filename}")
                if info.flag_bits & 0x1:
                    errors.append(f"{topic_id} ZIP must not encrypt files")
                if info.date_time != (1980, 1, 1, 0, 0, 0):
                    errors.append(f"{topic_id} ZIP timestamp is not deterministic for {info.filename}")
            if PACKAGE_ENTRYPOINT in names:
                packaged_html = archive.read(PACKAGE_ENTRYPOINT).decode("utf-8")
    except (BadZipFile, UnicodeDecodeError) as exc:
        errors.append(f"{topic_id} slides package is invalid: {exc}")
        return errors, packaged_html

    parser = parse_slide_html_text(packaged_html)
    if PACKAGE_MARKER not in packaged_html:
        errors.append(f"{topic_id} packaged HTML is missing the package marker")
    if parser.stylesheet or parser.script:
        errors.append(f"{topic_id} packaged HTML must not depend on external CSS or JavaScript files")
    if parser.inline_style_count < 1 or parser.inline_script_count < 1:
        errors.append(f"{topic_id} packaged HTML must inline CSS and JavaScript")
    if parser.external_runtime_urls:
        errors.append(f"{topic_id} packaged HTML has external runtime assets: {parser.external_runtime_urls}")
    if parser.topic_id != topic_id:
        errors.append(f"{topic_id} packaged HTML topic metadata mismatch")

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{topic_id} slides.meta.json is invalid: {exc}")
        return errors, packaged_html
    if meta.get("contract_version") != 2:
        errors.append(f"{topic_id} slides metadata must use contract_version 2")
    if _text(_mapping(meta.get("builder")).get("id")) != PACKAGE_BUILDER_ID:
        errors.append(f"{topic_id} slides metadata builder mismatch")
    if _text(meta.get("entrypoint")) != PACKAGE_ENTRYPOINT:
        errors.append(f"{topic_id} slides metadata entrypoint mismatch")
    expected_digest = aggregate_source_sha256(source_paths, root)
    if _text(meta.get("source_digest")) != expected_digest:
        errors.append(f"{topic_id} slides metadata source_digest is stale")
    source_hashes = _mapping(meta.get("source_sha256"))
    for source in source_paths:
        relative = source.relative_to(root).as_posix()
        if _text(source_hashes.get(relative)) != file_sha256(source):
            errors.append(f"{topic_id} slides metadata source hash is stale: {relative}")
    package_meta = _mapping(meta.get("package"))
    if _text(package_meta.get("sha256")) != file_sha256(package_path):
        errors.append(f"{topic_id} slides package hash is stale")
    if package_meta.get("bytes") != package_path.stat().st_size:
        errors.append(f"{topic_id} slides package byte count mismatch")
    html_meta = _mapping(meta.get("html"))
    html_bytes = packaged_html.encode("utf-8")
    if _text(html_meta.get("sha256")) != sha256(html_bytes).hexdigest():
        errors.append(f"{topic_id} packaged HTML hash is stale")
    if html_meta.get("bytes") != len(html_bytes):
        errors.append(f"{topic_id} packaged HTML byte count mismatch")
    return errors, packaged_html


def validate_materialized_topic(root: Path, repository: str, topic: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    topic_id = _text(topic.get("id"))
    if not TOPIC_ID.fullmatch(topic_id):
        return [f"invalid materialized topic id: {topic_id!r}"]
    content_version = topic.get("content_version")
    if not isinstance(content_version, int) or content_version <= 0:
        errors.append(f"{topic_id} content_version must be positive")

    required_paths = {
        "module": _text(topic.get("module")),
        "slides": _text(topic.get("slides")),
        "slides_package": _text(topic.get("slides_package")),
        "slides_review": _text(topic.get("slides_review")),
    }
    for key, relative in required_paths.items():
        if not relative:
            errors.append(f"{topic_id} is missing {key}")
        elif not (root / relative).is_file():
            errors.append(f"{topic_id} {key} is missing: {relative}")
    if errors:
        return errors

    lesson = root / required_paths["module"]
    source_dir = (root / required_paths["slides"]).parent
    sources = [source_dir / name for name in SOURCE_FILENAMES]
    missing_sources = [p.relative_to(root).as_posix() for p in sources if not p.is_file()]
    if missing_sources:
        return [f"{topic_id} slide sources are missing: {missing_sources}"]
    package_path = root / required_paths["slides_package"]
    meta_path = source_dir / "slides.meta.json"
    if not meta_path.is_file():
        errors.append(f"{topic_id} slides metadata is missing: {meta_path.relative_to(root)}")
        return errors

    parser = parse_slide_html(sources[0])
    if parser.topic_id != topic_id:
        errors.append(f"{topic_id} source HTML topic metadata mismatch")
    if parser.content_version != content_version:
        errors.append(f"{topic_id} source HTML content version mismatch")
    if parser.stylesheet != "slides.css" or parser.script != "slides.js":
        errors.append(f"{topic_id} source HTML must reference local slides.css and slides.js")
    if parser.external_runtime_urls:
        errors.append(f"{topic_id} source HTML has external runtime assets")
    errors.extend(_validate_assets(root, topic_id, sources))
    errors.extend(_validate_deck_structure(topic_id, parser))

    outcomes = [_text(_mapping(v).get("id")) for v in _list(topic.get("learning_outcomes")) if _text(_mapping(v).get("id"))]
    represented = []
    for slide in parser.slides:
        for outcome in slide.get("outcomes", []):
            if outcome not in represented:
                represented.append(outcome)
    if represented != outcomes:
        errors.append(f"{topic_id} slide outcome coverage mismatch: expected {outcomes}, got {represented}")
    if any(not OUTCOME_ID.fullmatch(value) for value in represented):
        errors.append(f"{topic_id} slides contain invalid outcome IDs")

    package_errors, _ = _validate_package(topic_id, package_path, meta_path, sources, root)
    errors.extend(package_errors)

    review = load_yaml(root / required_paths["slides_review"])
    errors.extend(_validate_review(root, topic, lesson, sources, _mapping(review)))

    expected_url = expected_package_url(repository, required_paths["slides_package"])
    lesson_text = lesson.read_text(encoding="utf-8")
    if lesson_text.count(SLIDES_LINK_START) != 1 or lesson_text.count(SLIDES_LINK_END) != 1:
        errors.append(f"{topic_id} lesson must contain exactly one managed slides-link block")
    if expected_url not in lesson_text:
        errors.append(f"{topic_id} lesson is missing the current ZIP slides link")
    if PACKAGE_ENTRYPOINT not in lesson_text:
        errors.append(f"{topic_id} lesson must explain that the learner opens {PACKAGE_ENTRYPOINT}")
    if "slides.pdf" in lesson_text.lower():
        errors.append(f"{topic_id} lesson still exposes a PDF slide link")
    return errors


def validate_repository(root: Path) -> ValidationResult:
    errors: list[str] = []
    instance_path = root / ".open-study-path" / "instance.yml"
    if not instance_path.is_file():
        instance_path = root / "templates" / "instance.yml"
    instance = _mapping(load_yaml(instance_path)) if instance_path.is_file() else {}
    if not slides_enabled(instance):
        errors.append("study_slides must use contract_version 2 and learner_format zip_html")
    repository = _text(instance.get("repository")) or "OWNER/REPOSITORY"
    topics_dir = root / "study" / "topics"
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
