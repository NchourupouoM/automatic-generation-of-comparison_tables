"""
Field-level scoring for extracted comparison tables against golden truth.

The harness runs the real pipeline on a PDF, then compares the produced table
to a hand-verified golden JSON file of the same shape. Scoring is deliberately
simple and explainable — no LLM-as-judge — so a regression is always traceable
to a concrete field.

Golden / prediction JSON shape (per table)::

    {
      "domain": "protein-structure-prediction",
      "research_problem": "...",
      "rows": [
        {
          "paper_title": "...",
          "authors": ["..."],
          "is_proposed_method": true,
          "properties": {"accuracy": "0.92", "dataset": "CASP7"}
        },
        ...
      ]
    }

`properties` collects the domain-specific comparative columns; any extra
top-level keys on a row are folded into it, so predictions coming straight from
the API (which flatten `domain_specific_properties`) can be scored as-is.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List

# Bibliographic keys are matched separately from domain properties.
BIBLIOGRAPHIC_KEYS = {
    "paper_title", "authors", "publication_month", "publication_year",
    "venue", "research_field", "doi", "url", "research_problem",
    "research_method", "is_proposed_method",
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _similar(a: Any, b: Any, threshold: float = 0.85) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na and not nb:
        return True
    if not na or not nb:
        return False
    if na == nb:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def _row_properties(row: Dict[str, Any]) -> Dict[str, Any]:
    """Collects domain properties whether nested under `properties`/
    `domain_specific_properties` or flattened onto the row."""
    props: Dict[str, Any] = {}
    for key in ("properties", "domain_specific_properties"):
        nested = row.get(key)
        if isinstance(nested, dict):
            props.update(nested)
    for key, val in row.items():
        if key not in BIBLIOGRAPHIC_KEYS and key not in ("properties", "domain_specific_properties"):
            props[key] = val
    return props


@dataclass
class TableScore:
    matched_rows: int = 0
    golden_rows: int = 0
    predicted_rows: int = 0
    field_true_positives: int = 0
    field_false_positives: int = 0
    field_false_negatives: int = 0
    notes: List[str] = field(default_factory=list)

    @property
    def row_recall(self) -> float:
        return self.matched_rows / self.golden_rows if self.golden_rows else 0.0

    @property
    def row_precision(self) -> float:
        return self.matched_rows / self.predicted_rows if self.predicted_rows else 0.0

    @property
    def field_precision(self) -> float:
        denom = self.field_true_positives + self.field_false_positives
        return self.field_true_positives / denom if denom else 0.0

    @property
    def field_recall(self) -> float:
        denom = self.field_true_positives + self.field_false_negatives
        return self.field_true_positives / denom if denom else 0.0

    @property
    def field_f1(self) -> float:
        p, r = self.field_precision, self.field_recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "row_recall": round(self.row_recall, 3),
            "row_precision": round(self.row_precision, 3),
            "field_precision": round(self.field_precision, 3),
            "field_recall": round(self.field_recall, 3),
            "field_f1": round(self.field_f1, 3),
            "matched_rows": self.matched_rows,
            "golden_rows": self.golden_rows,
            "predicted_rows": self.predicted_rows,
            "notes": self.notes,
        }


def _match_rows(golden_rows: List[Dict], pred_rows: List[Dict]) -> List[tuple]:
    """Greedy best-match of golden rows to predicted rows on paper_title."""
    pairs = []
    used = set()
    for g in golden_rows:
        best_idx, best_ratio = None, 0.0
        for i, p in enumerate(pred_rows):
            if i in used:
                continue
            ratio = SequenceMatcher(None, _norm(g.get("paper_title")), _norm(p.get("paper_title"))).ratio()
            if ratio > best_ratio:
                best_idx, best_ratio = i, ratio
        if best_idx is not None and best_ratio >= 0.6:
            used.add(best_idx)
            pairs.append((g, pred_rows[best_idx]))
        else:
            pairs.append((g, None))
    return pairs


def score_table(golden: Dict[str, Any], predicted: Dict[str, Any]) -> TableScore:
    """Scores a single predicted comparison table against its golden truth."""
    score = TableScore()
    golden_rows = golden.get("rows", []) or []
    pred_rows = predicted.get("rows", []) or []
    score.golden_rows = len(golden_rows)
    score.predicted_rows = len(pred_rows)

    for g_row, p_row in _match_rows(golden_rows, pred_rows):
        if p_row is None:
            g_props = _row_properties(g_row)
            score.field_false_negatives += len(g_props) + 1  # +1 for the title itself
            score.notes.append(f"missing row: {g_row.get('paper_title')!r}")
            continue

        score.matched_rows += 1
        # Title counts as a field.
        if _similar(g_row.get("paper_title"), p_row.get("paper_title")):
            score.field_true_positives += 1
        else:
            score.field_false_negatives += 1

        g_props = _row_properties(g_row)
        p_props = _row_properties(p_row)
        for key, g_val in g_props.items():
            match = None
            for p_key, p_val in p_props.items():
                if _norm(p_key) == _norm(key):
                    match = p_val
                    break
            if match is not None and _similar(g_val, match):
                score.field_true_positives += 1
            else:
                score.field_false_negatives += 1
        # Predicted properties with no golden counterpart are false positives.
        golden_keys = {_norm(k) for k in g_props}
        for p_key in p_props:
            if _norm(p_key) not in golden_keys:
                score.field_false_positives += 1

    return score


def score_document(golden_doc: Dict[str, Any], predicted_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scores a full document result. Accepts either a bare table dict or the
    API's `{"consolidated_result": {"tables": [...]}}` envelope on either side.
    Golden files are expected to be a single table; the first predicted table
    is scored against it.
    """
    golden_table = _first_table(golden_doc)
    predicted_table = _first_table(predicted_doc)
    result = score_table(golden_table, predicted_table).as_dict()
    result["domain_expected"] = golden_table.get("domain")
    result["domain_predicted"] = predicted_table.get("domain") or predicted_doc.get(
        "consolidated_result", {}
    ).get("domain")
    return result


def _first_table(doc: Dict[str, Any]) -> Dict[str, Any]:
    if "consolidated_result" in doc:
        tables = doc["consolidated_result"].get("tables", [])
        return tables[0] if tables else {"rows": []}
    if "tables" in doc:
        tables = doc.get("tables", [])
        return tables[0] if tables else {"rows": []}
    return doc
