"""Evaluation runner: drive the real extraction pipeline over the gold
fixtures and score the output.

Unlike ``scoring.py`` and ``gold.py`` (which are pure), this module imports
``app`` and therefore needs the project's environment (``DATABASE_URL`` etc.)
and — for a real evaluation — a configured LLM provider/API key. It reuses the
production extraction code path (``_extract_single_paper`` + the real prompts
and skills), so the numbers reflect the actual system, not a reimplementation.

Usage::

    # Real evaluation against the configured LLM provider:
    python -m tests.eval.runner

    # Smoke run with a stub LLM (no API key needed) — proves the harness wiring,
    # NOT extraction quality:
    python -m tests.eval.runner --fake

Exit code is non-zero if cell-F1 falls below --min-f1 (default 0.0), so this
can gate CI once real gold data and a model are wired up.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests.eval import gold as gold_mod
from tests.eval import scoring


def _tasks_for(example: gold_mod.GoldExample) -> List[Any]:
    """Build the pipeline's PaperTask list for a gold example, mirroring how
    the API layer prepares work (deterministic split for proceedings)."""
    from app.services.orchestrator import PaperTask
    from app.core.parse_pdf import extract_pdf_to_markdown, split_proceeding_pdf

    inp = example.input
    if "pdf" in inp:
        pdf_path = str((gold_mod.FIXTURES_DIR.parent / inp["pdf"]).resolve()
                       if not Path(inp["pdf"]).is_absolute() else inp["pdf"])
        if example.document_type == "proceeding":
            import tempfile
            out = Path(tempfile.mkdtemp(prefix="eval_split_"))
            segs = split_proceeding_pdf(pdf_path, out)
            return [PaperTask(title=p.stem, authors=[],
                              text_segment=extract_pdf_to_markdown(str(p)),
                              domain_hint=example.domain) for p in segs]
        return [PaperTask(title=example.id, authors=[],
                          text_segment=extract_pdf_to_markdown(pdf_path),
                          domain_hint=example.domain)]

    md = inp["raw_markdown"]
    # For raw_markdown proceedings the caller is expected to pre-split into a
    # list; a single blob is treated as one paper.
    if isinstance(md, list):
        return [PaperTask(title=f"{example.id}-{i}", authors=[],
                          text_segment=seg, domain_hint=example.domain)
                for i, seg in enumerate(md)]
    return [PaperTask(title=example.id, authors=[], text_segment=md,
                      domain_hint=example.domain)]


def _table_to_dict(table: Any) -> Dict[str, Any]:
    """Convert an extracted pydantic ComparisonTable into the gold-shaped dict."""
    STANDARD = {"paper_title", "authors", "publication_month", "publication_year",
                "venue", "research_field", "doi", "url", "research_problem",
                "research_method"}
    rows_out = []
    for idx, row in enumerate(table.rows):
        row_dict = row.model_dump()
        props = {k: v for k, v in row_dict.items() if k not in STANDARD}
        biblio = {k: v for k, v in row_dict.items() if k in STANDARD}
        rows_out.append({
            "paper_title": row.paper_title,
            "authors": getattr(row, "authors", []) or [],
            "is_proposed_method": idx == 0,
            "domain_specific_properties": props,
            **biblio,
        })
    return {"research_problem": getattr(table, "research_problem", ""), "rows": rows_out}


def predict(example: gold_mod.GoldExample) -> Dict[str, Any]:
    """Run the real extraction node logic on a gold example and return a
    consolidated_result-shaped prediction."""
    from pathlib import Path as _P
    from app.core.llm_factory import LLMFactory
    from app.core.skills_loader import SkillLoader
    from app.core.schemas import ComparisonTable
    from app.core.dynamic_loader import compile_dynamic_table_model
    from app.core.database import SessionLocal
    from app.services.orchestrator import _extract_single_paper

    domain = example.domain or "default"
    skill_dir = _P(f"skills/{domain}")
    if not skill_dir.exists():
        skill_dir = _P("skills/academicextraction")
    _, instructions = SkillLoader.load_skill(skill_dir)

    if domain == "default":
        schema = ComparisonTable
    else:
        with SessionLocal() as db:
            schema = compile_dynamic_table_model(domain, db)

    structured_llm = LLMFactory.get_llm().with_structured_output(schema, method="function_calling")

    tables = []
    for task in _tasks_for(example):
        extracted = _extract_single_paper(task, instructions, structured_llm)
        if extracted is not None:
            tables.append(_table_to_dict(extracted))
    return {"tables": tables}


def run(min_f1: float = 0.0, only: Optional[str] = None,
        fixtures_dir: Path = gold_mod.FIXTURES_DIR) -> int:
    examples = gold_mod.load_all(fixtures_dir)
    if only:
        examples = [e for e in examples if e.id == only]
    if not examples:
        print("No gold fixtures found.", file=sys.stderr)
        return 1

    scores = []
    placeholder_ids = []
    for ex in examples:
        if ex.is_placeholder:
            placeholder_ids.append(ex.id)
        pred = predict(ex)
        scores.append(scoring.score_example(ex.expected, pred, example_id=ex.id))

    total = scoring.aggregate(scores)
    summary = total.summary()

    print("\n=== Extraction evaluation ===")
    print(f"{'example':40s} {'row_f1':>7s} {'cell_f1':>7s} {'leak':>5s}")
    print("-" * 62)
    for row in total.per_example:
        print(f"{row['id'][:40]:40s} {row['row_f1']:>7.3f} "
              f"{row['cell_f1']:>7.3f} {row['leakage_violations']:>5d}")
    print("-" * 62)
    print(json.dumps(summary, indent=2))

    if placeholder_ids:
        print(f"\n⚠  {len(placeholder_ids)} PLACEHOLDER fixture(s) still in use: "
              f"{', '.join(placeholder_ids)}")
        print("   Replace them with real hand-verified gold before trusting these numbers.")

    if summary["cell_f1"] < min_f1:
        print(f"\nFAIL: cell_f1 {summary['cell_f1']} < required {min_f1}", file=sys.stderr)
        return 2
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate extraction against gold fixtures.")
    parser.add_argument("--min-f1", type=float, default=0.0,
                        help="Fail (exit 2) if aggregate cell_f1 is below this.")
    parser.add_argument("--only", type=str, default=None, help="Run a single fixture by id.")
    parser.add_argument("--fake", action="store_true",
                        help="Use a stub LLM (no API key). Smoke-tests wiring, not quality.")
    args = parser.parse_args(argv)

    if args.fake:
        _install_fake_llm()

    return run(min_f1=args.min_f1, only=args.only)


def _install_fake_llm() -> None:
    """Patch LLMFactory with a deterministic stub so the harness can run with
    no API key. Produces trivially wrong output — for wiring smoke tests only."""
    from types import SimpleNamespace
    from app.core import llm_factory

    class _Struct:
        def __init__(self, schema):
            self.schema = schema
        def invoke(self, _prompt):
            row_model = self.schema.model_fields["rows"].annotation.__args__[0]
            kwargs = {"paper_title": "Stub Paper", "authors": ["Stub Author"],
                      "research_problem": "stub"}
            for name, info in row_model.model_fields.items():
                if name not in kwargs and info.is_required():
                    kwargs[name] = "x"
            return self.schema(research_problem="stub", rows=[row_model(**kwargs)])

    class _Fake:
        def invoke(self, _p):
            return SimpleNamespace(content="Stub Domain")
        def with_structured_output(self, schema, method=None):
            return _Struct(schema)

    llm_factory.LLMFactory.get_llm = staticmethod(lambda: _Fake())


if __name__ == "__main__":
    raise SystemExit(main())
