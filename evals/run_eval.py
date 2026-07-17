"""
End-to-end evaluation runner.

Two modes:

    # Score every PDF that has a golden file, print per-paper + aggregate metrics
    python -m evals.run_eval

    # Also run structural invariants across the whole PDF corpus (no golden needed)
    python -m evals.run_eval --smoke

This driver calls the REAL pipeline (PDF -> markdown -> LangGraph extraction),
so it needs a configured LLM provider and database, exactly like production.
It is intentionally NOT part of the unit-test suite (which stays offline and
deterministic); run it manually or in a nightly job with credentials present.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from evals.invariants import check_table_invariants
from evals.scoring import score_document, _first_table

EVAL_DIR = Path(__file__).parent
PDF_DIR = EVAL_DIR / "pdfs"
GOLDEN_DIR = EVAL_DIR / "golden"


def _extract(pdf_path: Path, domain: str = "default") -> Dict[str, Any]:
    """Runs the pipeline in-process and returns the consolidated result."""
    # Imported lazily so `--help` and offline unit tests never require the
    # heavy LLM / DB stack.
    from app.core.parse_pdf import extract_pdf_to_markdown
    from app.services.orchestrator import get_orchestrator_graph
    from app.services.orchestrator import PaperTask  # noqa: F401

    raw_markdown = extract_pdf_to_markdown(str(pdf_path))
    graph = get_orchestrator_graph()
    state = {
        "raw_markdown": raw_markdown,
        "manual_document_type": "single",
        "document_type": "single",
        "domain": domain,
        "celery_task_id": "",
        "extraction_tasks": [],
        "extracted_rows": [],
        "proposed_properties": [],
        "validated_schema_json": {},
        "consolidated_result": {},
    }
    config = {"configurable": {"thread_id": f"eval-{pdf_path.stem}"}}
    final = graph.invoke(state, config)
    return final.get("consolidated_result", {})


def run_scored(cache_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    results = []
    for golden_path in sorted(GOLDEN_DIR.glob("*.json")):
        stem = golden_path.stem
        pdf_path = PDF_DIR / f"{stem}.pdf"
        if not pdf_path.exists():
            print(f"[skip] no PDF for golden {stem}")
            continue

        golden = json.loads(golden_path.read_text())
        domain = golden.get("domain", "default")
        predicted = _extract(pdf_path, domain=domain)

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / f"{stem}.json").write_text(json.dumps(predicted, indent=2))

        report = score_document(golden, predicted)
        report["paper"] = stem
        results.append(report)
        print(
            f"[{stem}] field_f1={report['field_f1']:.2f} "
            f"row_recall={report['row_recall']:.2f} "
            f"domain={report['domain_predicted']!r} (want {report['domain_expected']!r})"
        )
    return results


def run_smoke() -> List[Dict[str, Any]]:
    results = []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        try:
            predicted = _extract(pdf_path)
            table = _first_table(predicted)
            violations = check_table_invariants(table)
            status = "ok" if not violations else "VIOLATIONS"
            print(f"[{pdf_path.stem}] {status} {violations if violations else ''}")
            results.append({"paper": pdf_path.stem, "violations": violations})
        except Exception as e:  # noqa: BLE001 - report and continue the sweep
            print(f"[{pdf_path.stem}] ERROR {e}")
            results.append({"paper": pdf_path.stem, "error": str(e)})
    return results


def _aggregate(results: List[Dict[str, Any]]) -> Dict[str, float]:
    scored = [r for r in results if "field_f1" in r]
    if not scored:
        return {}
    n = len(scored)
    return {
        "papers_scored": n,
        "mean_field_f1": round(sum(r["field_f1"] for r in scored) / n, 3),
        "mean_field_precision": round(sum(r["field_precision"] for r in scored) / n, 3),
        "mean_field_recall": round(sum(r["field_recall"] for r in scored) / n, 3),
        "mean_row_recall": round(sum(r["row_recall"] for r in scored) / n, 3),
        "domain_accuracy": round(
            sum(1 for r in scored if (r["domain_predicted"] or "") == (r["domain_expected"] or "")) / n, 3
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the comparison-table extraction evaluation.")
    parser.add_argument("--smoke", action="store_true",
                        help="Run structural invariants across the whole PDF corpus (no golden needed).")
    parser.add_argument("--cache", type=str, default=None,
                        help="Directory to cache raw predictions for offline inspection.")
    args = parser.parse_args()

    if args.smoke:
        run_smoke()
        return

    results = run_scored(Path(args.cache) if args.cache else None)
    summary = _aggregate(results)
    print("\n=== Aggregate ===")
    print(json.dumps(summary, indent=2) if summary else "No golden files scored.")


if __name__ == "__main__":
    main()
