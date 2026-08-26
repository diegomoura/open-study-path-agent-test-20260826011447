#!/usr/bin/env python3
"""Validate semantic slide sources, static SVG diagrams and learner-facing PDFs."""
from pathlib import Path
import sys
from study_slides import validate_repository

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    result = validate_repository(ROOT)
    if not result.ok:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Study-slide HTML, static Mermaid SVG, independent review and PDF contract passed.")


if __name__ == "__main__":
    main()
