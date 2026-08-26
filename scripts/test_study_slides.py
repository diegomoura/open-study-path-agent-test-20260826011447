#!/usr/bin/env python3
"""Regression tests for static SVG slide sources and learner-facing PDFs."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

from pypdf import PdfWriter
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from study_slides import (  # noqa: E402
    PDF_PRODUCER,
    RENDERER_ID,
    REQUIRED_REVIEW_CHECKS,
    aggregate_source_sha256,
    expected_pdf_url,
    file_sha256,
    slides_deliberately_disabled,
    validate_materialized_topic,
    validate_repository,
)


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content, encoding="utf-8")


def canonical_css() -> str:
    return """/* open-study-path:study-slides-theme version=3 */
.osp-slide{width:1280px;height:720px}.osp-title-layout{}.osp-grid{}.osp-compare{}.osp-diagram{}.osp-case{}.osp-steps{}.osp-challenge{}.osp-checklist{}.osp-prompt-grid{}.osp-summary-layout{}.osp-matrix{}
"""


def valid_html() -> str:
    specs = [
        ("title", "LO-1 LO-2", "", "osp-title-layout", "Tokens, contexto e geração com resultado observável e verificação externa claramente declarada."),
        ("map", "LO-1 LO-2", "", "osp-grid", "O percurso conecta tokenização, contexto, distribuição de probabilidades, aplicação e evidência."),
        ("concept", "LO-1", "Começando do zero", "osp-compare", "Token é uma unidade processada; contexto reúne instruções e texto já produzido."),
        ("concept", "LO-1", "Conteúdo essencial", "osp-matrix", "O modelo calcula alternativas prováveis e acrescenta cada token selecionado ao contexto seguinte."),
        ("diagram", "LO-1 LO-2", "Mapa visual", "osp-diagram", "O fluxo mostra contexto, probabilidades, seleção do token e uma etapa externa de verificação."),
        ("example", "LO-1", "Exemplos trabalhados", "osp-case", "Um resumo usa apenas texto fornecido e é comparado ao original antes de ser aceito."),
        ("example", "LO-2", "Exemplos trabalhados", "osp-steps", "Uma política recente exige documento autorizado; reduzir temperatura não substitui a fonte vigente."),
        ("misconception", "LO-2", "Erros comuns e como corrigir", "osp-compare", "Temperatura altera variação de amostragem, mas não transforma uma continuação provável em verdade."),
        ("concept", "LO-2", "Conteúdo essencial", "osp-grid", "Conhecimento paramétrico difere de consulta atual; a aplicação controla ferramentas e permissões."),
        ("application", "LO-1 LO-2", "Prática guiada", "osp-challenge osp-checklist", "A pessoa desenha um fluxo com fonte oficial, recuperação, contexto, resposta citada e revisão."),
        ("recap", "LO-1 LO-2", "Confira sem consultar", "osp-prompt-grid", "As perguntas recuperam token, contexto, previsão do próximo token, temperatura e verificação externa."),
        ("summary", "LO-1 LO-2", "", "osp-summary-layout", "A resposta emerge token a token; parâmetros mudam amostragem e afirmações importantes precisam de evidência."),
    ]
    sections = []
    for index, (role, outcomes, lesson_section, layout, text) in enumerate(specs, start=1):
        section_attr = f' data-lesson-section="{lesson_section}"' if lesson_section else ""
        diagram = ""
        if role == "diagram":
            diagram = '<figure class="osp-diagram"><img class="osp-diagram-image" src="diagrams/flow.svg" data-mermaid-source="diagrams/flow.mmd" alt="Ciclo de geração token a token com verificação externa"></figure><p class="osp-caption">O ciclo gera texto; a aplicação decide quando verificar.</p>'
        sections.append(
            f'<section class="osp-slide {layout}" data-slide-role="{role}" data-outcome-ids="{outcomes}"{section_attr}>'
            f'<h2>Slide {index}</h2><div class="{layout}"><p>{text} Esta explicação contém detalhes específicos suficientes para sustentar a leitura sem depender de frases genéricas.</p>{diagram}</div></section>'
        )
    return f"""<!doctype html><html lang="pt-BR"><head>
<meta name="open-study-path:topic-id" content="TOPIC-001"><meta name="open-study-path:content-version" content="2"><meta name="open-study-path:slide-theme" content="canonical-v3">
<link rel="stylesheet" href="slides.css"></head><body><main>{''.join(sections)}</main></body></html>"""


def make_pdf(path: Path, pages: int, source_digest: str, snapshot: str) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=1280, height=720)
    writer.add_metadata({
        "/Producer": PDF_PRODUCER,
        "/Creator": PDF_PRODUCER,
        "/Title": "TOPIC-001 study slides",
        "/Subject": f"open-study-path-renderer:{RENDERER_ID};source:{source_digest};snapshot:{snapshot}",
    })
    with path.open("wb") as handle:
        writer.write(handle)


def build_valid_tree(root: Path) -> tuple[dict, str]:
    repository = "example/private-study"
    topic = {
        "id": "TOPIC-001", "content_status": "materialized", "content_version": 2, "estimated_hours": 1.0,
        "module": "study/modules/TOPIC-001.md", "slides": "study/slides/TOPIC-001/index.html",
        "slides_pdf": "study/slides/TOPIC-001/slides.pdf", "slides_review": "state/slide-reviews/TOPIC-001.yml",
        "learning_outcomes": [
            {"id": "LO-1", "statement": "Explain generation", "required_concepts": ["token", "contexto", "previsão do próximo token"]},
            {"id": "LO-2", "statement": "Recognize limits", "required_concepts": ["temperatura", "conhecimento paramétrico", "verificação externa"]},
        ],
    }
    css = canonical_css()
    write(root / "templates/study-slides/slides.css", css)
    topic_dir = root / "study/slides/TOPIC-001"
    write(topic_dir / "index.html", valid_html())
    write(topic_dir / "slides.css", css)
    write(topic_dir / "diagrams/flow.mmd", "flowchart LR\n A[contexto] --> B[distribuição de probabilidades]\n B --> C[previsão do próximo token]\n C --> A\n C --> D[verificação externa]\n")
    write(topic_dir / "diagrams/flow.svg", '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="300"><text x="20" y="40">token contexto temperatura conhecimento paramétrico verificação externa</text></svg>')
    lesson = root / "study/modules/TOPIC-001.md"
    pdf_url = expected_pdf_url(repository, topic["slides_pdf"])
    write(lesson, f"# Aula\n\n<!-- open-study-path:slides-link:start -->\n## Slides da aula\n\n[Baixe os slides da aula em PDF]({pdf_url}). Use o PDF para revisão; esta aula continua sendo a fonte principal.\n<!-- open-study-path:slides-link:end -->\n")
    sources = [topic_dir / "index.html", topic_dir / "slides.css", topic_dir / "diagrams/flow.mmd"]
    source_digest = aggregate_source_sha256(sources, root)
    snapshot = "a" * 64
    pdf_path = topic_dir / "slides.pdf"
    make_pdf(pdf_path, 12, source_digest, snapshot)
    meta = {
        "contract_version": 3, "topic_id": "TOPIC-001", "content_version": 2,
        "renderer": {"id": RENDERER_ID}, "slide_count": 12, "diagram_count": 1,
        "outcome_ids": ["LO-1", "LO-2"],
        "source_sha256": {path.relative_to(root).as_posix(): file_sha256(path) for path in sources},
        "source_digest": source_digest,
        "svg_sha256": {"study/slides/TOPIC-001/diagrams/flow.svg": file_sha256(topic_dir / "diagrams/flow.svg")},
        "rendered_snapshot_sha256": snapshot,
        "pdf": {"pages": 12, "bytes": pdf_path.stat().st_size, "sha256": file_sha256(pdf_path), "producer": PDF_PRODUCER},
        "diagnostics": {"console_errors": [], "overflow_slides": [], "external_requests": [], "missing_diagrams": []},
    }
    write(topic_dir / "slides.meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    review = {
        "version": 4, "topic_id": "TOPIC-001", "content_version": 2,
        "reviewed_at": "2026-08-03T10:00:00Z", "reviewer_role": "study_slides_reviewer",
        "review_mode": "independent_pass", "status": "approved",
        "source_lesson": "study/modules/TOPIC-001.md", "source_lesson_sha256": file_sha256(lesson),
        "slides_source": "study/slides/TOPIC-001/index.html", "slides_source_sha256": aggregate_source_sha256(sources, root),
        "checks": {name: "passed" for name in REQUIRED_REVIEW_CHECKS},
        "outcomes_reviewed": ["LO-1", "LO-2"], "blocking_findings": [], "non_blocking_findings": [],
    }
    write(root / "state/slide-reviews/TOPIC-001.yml", yaml.safe_dump(review, sort_keys=False, allow_unicode=True))
    return topic, repository


def test_valid_topic() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory); topic, repository = build_valid_tree(root)
        assert validate_materialized_topic(root, repository, topic) == []


def test_generic_placeholder_is_rejected() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory); topic, repository = build_valid_tree(root)
        index = root / topic["slides"]
        index.write_text(index.read_text(encoding="utf-8").replace("Tokens, contexto", "Defina a ideia central. Tokens, contexto"), encoding="utf-8")
        errors = validate_materialized_topic(root, repository, topic)
        assert any("generic placeholder" in error for error in errors)


def test_missing_svg_is_rejected() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory); topic, repository = build_valid_tree(root)
        (root / "study/slides/TOPIC-001/diagrams/flow.svg").unlink()
        errors = validate_materialized_topic(root, repository, topic)
        assert any("generated SVG is missing" in error for error in errors)


def test_zip_instruction_is_rejected() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory); topic, repository = build_valid_tree(root)
        lesson = root / topic["module"]
        lesson.write_text(lesson.read_text(encoding="utf-8") + "\nAbra slides.zip e slides.html.\n", encoding="utf-8")
        errors = validate_materialized_topic(root, repository, topic)
        assert any("ZIP/HTML" in error for error in errors)


def test_thin_deck_is_rejected() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory); topic, repository = build_valid_tree(root)
        index = root / topic["slides"]
        index.write_text(index.read_text(encoding="utf-8").replace(" Esta explicação contém detalhes específicos suficientes para sustentar a leitura sem depender de frases genéricas.", ""), encoding="utf-8")
        errors = validate_materialized_topic(root, repository, topic)
        assert any("too thin" in error for error in errors)


def test_slides_deliberately_disabled_requires_explicit_false() -> None:
    assert slides_deliberately_disabled({"study_slides": {"enabled": False}})
    # Absent config is a misconfiguration to catch, not an opt-out --
    # otherwise every repository that simply never configured study_slides
    # would silently skip validation instead of erroring.
    assert not slides_deliberately_disabled({})
    assert not slides_deliberately_disabled({"study_slides": {}})
    assert not slides_deliberately_disabled({"study_slides": {"enabled": None}})


def test_validate_repository_passes_when_deliberately_disabled_even_with_materialized_topics() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            yaml.safe_dump({"repository": "example/private-study", "study_slides": {"enabled": False}}),
        )
        # A materialized topic with zero slide artifacts anywhere -- this is
        # exactly the state the Etapa 5b agent-pilot toggle (docs/claude-
        # agent-pilot-etapa5.md) produces when slides are off.
        write(
            root / "study/topics/TOPIC-001.md",
            "---\nid: TOPIC-001\ncontent_status: materialized\ncontent_version: 1\n---\n\nConteudo.\n",
        )
        result = validate_repository(root)
        assert result.ok, result.errors


def test_validate_repository_still_errors_when_slides_config_is_missing_not_disabled() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / ".open-study-path/instance.yml", yaml.safe_dump({"repository": "example/private-study"}))
        result = validate_repository(root)
        assert not result.ok
        assert any("contract_version 3" in error for error in result.errors)



def main() -> None:
    tests = [
        test_valid_topic,
        test_generic_placeholder_is_rejected,
        test_missing_svg_is_rejected,
        test_zip_instruction_is_rejected,
        test_thin_deck_is_rejected,
        test_slides_deliberately_disabled_requires_explicit_false,
        test_validate_repository_passes_when_deliberately_disabled_even_with_materialized_topics,
        test_validate_repository_still_errors_when_slides_config_is_missing_not_disabled,
    ]
    for test in tests:
        test()
    print(f"Static SVG/PDF study-slide regression tests passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
