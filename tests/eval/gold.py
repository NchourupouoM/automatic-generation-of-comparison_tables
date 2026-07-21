"""Loading and light validation of gold (ground-truth) fixtures.

A gold fixture is a JSON file under ``tests/fixtures/`` describing one input
document and its hand-verified expected comparison result. Pure module: no
``app`` imports, no DB, no network.

Fixture schema::

    {
      "id": "unique-slug",
      "description": "free text — cite the source paper here",
      "document_type": "single" | "proceeding",
      "domain": "default" | "<registered-template-id>",
      "input": {
        "raw_markdown": "…full text…"     # OR
        "pdf": "tests/fixtures/pdfs/foo.pdf"
      },
      "expected": { "tables": [ … ] }      # same shape as consolidated_result
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@dataclass
class GoldExample:
    id: str
    description: str
    document_type: str
    domain: str
    input: Dict[str, Any]
    expected: Dict[str, Any]
    source_path: Path

    @property
    def is_placeholder(self) -> bool:
        """Placeholder fixtures ship as scaffolding and must be replaced with
        real hand-verified data before their scores mean anything."""
        return "PLACEHOLDER" in (self.description or "").upper()


def _validate(data: Dict[str, Any], path: Path) -> None:
    required = ["id", "document_type", "input", "expected"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"{path.name}: missing required keys {missing}")
    if data["document_type"] not in ("single", "proceeding"):
        raise ValueError(f"{path.name}: document_type must be 'single' or 'proceeding'")
    if "raw_markdown" not in data["input"] and "pdf" not in data["input"]:
        raise ValueError(f"{path.name}: input must contain 'raw_markdown' or 'pdf'")
    if "tables" not in data["expected"]:
        raise ValueError(f"{path.name}: expected must contain 'tables'")


def load_example(path: Path) -> GoldExample:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate(data, Path(path))
    return GoldExample(
        id=data["id"],
        description=data.get("description", ""),
        document_type=data["document_type"],
        domain=data.get("domain", "default"),
        input=data["input"],
        expected=data["expected"],
        source_path=Path(path),
    )


def load_all(fixtures_dir: Path = FIXTURES_DIR) -> List[GoldExample]:
    fixtures_dir = Path(fixtures_dir)
    examples: List[GoldExample] = []
    for path in sorted(fixtures_dir.glob("*.json")):
        examples.append(load_example(path))
    return examples
