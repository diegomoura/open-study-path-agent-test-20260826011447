#!/usr/bin/env python3
"""Validate repository-contract intake discovery and course-title semantics."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from intake_resolution import CURRENT_MARKER

ROOT = Path(__file__).resolve().parents[1]
NATURAL_COMMAND = "Preenchi o formulário. Pode continuar."


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def text(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        fail(f"missing intake-resolution contract: {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, terms: list[str]) -> None:
    content = text(path)
    for term in terms:
        if term not in content:
            fail(f"{path} is missing deterministic-intake term: {term}")


def load_yaml(path: str) -> Any:
    return yaml.safe_load(text(path))


def main() -> None:
    require("instructions/05-configure-intake.md", [
        "https://github.com/OWNER/REPOSITORY/issues/new?template=create-study-path.yml",
        CURRENT_MARKER,
        "Add a title",
        "course name",
        "study-request",
        "intake:imported",
        "Do not require an issue number",
        "current repository form contract",
        "submitted issue does not contain the form marker",
        "never ask the learner to edit technical markers",
    ])
    require("instructions/10-intake.md", [
        "scripts/intake_resolution.py",
        CURRENT_MARKER,
        "issue title",
        "`issue_title`",
        "`path.name`",
        "Do not rewrite the issue title",
        "Matching headings alone",
        "exactly one valid candidate",
        "When none remain",
        "more than one remains",
        "never select an arbitrary newest repository issue",
        "state/intake-summary.json.source_reference",
        "intake:imported",
        "path.learning_request",
        "path.subject",
        "instructions/20-diagnostic.md",
        "required checked consent",
        "technical marker belongs to the repository form",
        "never ask the learner to edit a marker",
    ])
    require("instructions/phase-completion.md", [
        "Return the direct intake link",
        NATURAL_COMMAND,
        "Do not ask for an issue or submission number",
        "multiple valid candidates",
    ])
    require("AGENTS.md", [
        "course name comes from the issue title",
        "current repository form contract",
        "Matching headings alone",
        "Never ask the learner to edit an issue to add a technical marker",
    ])

    issue_form = load_yaml(".github/ISSUE_TEMPLATE/create-study-path.yml")
    if issue_form.get("name") != "Criar meu curso":
        fail("new intake form must use learner-facing course language")
    if issue_form.get("title") not in (None, ""):
        fail("the native issue title must not be prefilled")
    issue_blocks = [block for block in issue_form.get("body", []) if isinstance(block, dict)]
    if any(block.get("id") == "path_name" for block in issue_blocks):
        fail("GitHub Issue Form must not duplicate the course name in path_name")
    markdown = "\n".join(
        str(block.get("attributes", {}).get("value", ""))
        for block in issue_blocks
        if block.get("type") == "markdown"
    )
    if markdown.count(CURRENT_MARKER) != 1:
        fail("intake Issue Form must contain exactly one current hidden form marker")
    for term in ["Add a title", "nome do curso", "Esse campo é obrigatório"]:
        if term not in markdown:
            fail(f"intake title guidance is missing: {term}")

    resolver = text("scripts/intake_resolution.py")
    for forbidden in [
        "missing_current_marker",
        "unsupported_or_ambiguous_marker",
        "INTAKE_MARKER_RE",
        "ANY_MARKER_RE",
    ]:
        if forbidden in resolver:
            fail(f"rendered issue resolution must not depend on body marker logic: {forbidden}")
    for required in [
        "missing_discovery_label",
        "missing_checked_consent",
        "missing_required_response",
        "current_form_contract",
        "unexpected_author",
    ]:
        if required not in resolver:
            fail(f"rendered issue resolution is missing identity check: {required}")

    regression = text("scripts/test_intake_resolution.py")
    for term in [
        "markdown-only form marker is intentionally absent",
        "missing_discovery_label",
        "missing_checked_consent",
        "unexpected_author",
        "current_form_contract",
    ]:
        if term not in regression:
            fail(f"rendered intake regression is missing: {term}")

    mapping = load_yaml("intake/field-mapping.yml")
    github_issue = mapping.get("github_issue", {})
    if github_issue.get("current_form_version") != 4:
        fail("GitHub intake mapping must identify form version 4")
    if github_issue.get("current_mappings", {}).get("issue_title") != "path.name":
        fail("GitHub issue title must map to path.name")
    if github_issue.get("compatible_versions"):
        fail("unused intake compatibility versions must not remain configured")
    mappings = mapping.get("mappings", {})
    if mappings.get("subject") != "path.learning_request":
        fail("the main learning request must be preserved in path.learning_request")
    derived_subject = mapping.get("derived_fields", {}).get("path.subject", {})
    if derived_subject.get("from") != "path.learning_request":
        fail("path.subject must be derived from the preserved learning request")

    for path in [
        "scripts/intake_resolution.py",
        "scripts/test_intake_resolution.py",
        "scripts/ensure_repository_labels.py",
        "scripts/test_repository_labels.py",
    ]:
        if not (ROOT / path).is_file():
            fail(f"missing intake regression asset: {path}")

    workflow = text(".github/workflows/validate-template.yml")
    for command in [
        "python scripts/test_intake_resolution.py",
        "python scripts/test_repository_labels.py",
    ]:
        if command not in workflow:
            fail(f"validation workflow is missing: {command}")

    manifest = load_yaml("instructions/manifest.yml")
    phases = {
        phase.get("id"): phase
        for phase in manifest.get("phases", [])
        if isinstance(phase, dict)
    }
    intake = phases.get("intake", {})
    if intake.get("allow_explicit_chain_to") != "diagnostic":
        fail("intake phase must allow validated diagnostic chaining")
    if intake.get("stop_after_phase") is not True:
        fail("intake must stop by default when chaining was not requested")

    print("Repository-contract intake resolution and course-title semantics passed.")


if __name__ == "__main__":
    main()
