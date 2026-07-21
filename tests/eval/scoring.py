"""Pure, dependency-free scoring for comparison-table extraction.

This module compares a *predicted* comparison result against a hand-verified
*gold* result and produces interpretable accuracy metrics. It imports nothing
from ``app`` and touches no database or network, so it runs anywhere — in
particular in CI without an LLM API key.

Both `gold` and `pred` use the same shape the pipeline already emits
(``consolidated_result``)::

    {
      "tables": [
        {
          "research_problem": "…",
          "rows": [
            {
              "paper_title": "…",
              "is_proposed_method": true,
              "authors": ["…"],
              "publication_year": 2023,
              "venue": "…",
              "doi": "…",
              "domain_specific_properties": {"efficacy_rate": "95%"}
            },
            …
          ]
        }
      ]
    }

Metrics produced:
  * row  P/R/F1  — did we find the right papers (rows)?
  * cell P/R/F1  — of the values we should have filled, how many are correct?
  * leakage_violations — baseline rows that copied the proposed paper's authors
  * proposed_correct   — was the paper's own method identified as row-0/proposed?
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

# Values that should all be treated as "no value provided".
_EMPTY = {"", "n/a", "na", "none", "null", "-", "—", "unknown",
          "not reported", "not mentioned", "not available", "nan"}

# Standard bibliographic fields scored as ordinary scalar cells.
_BIBLIO_FIELDS = [
    "publication_year", "publication_month", "venue", "research_field",
    "doi", "url", "research_method", "research_problem",
]


def _norm(value: Any) -> Optional[str]:
    """Normalise a scalar to a comparable canonical string, or None if empty."""
    if value is None:
        return None
    s = re.sub(r"\s+", " ", str(value).strip().lower())
    return None if s in _EMPTY else s


def _norm_list(values: Any) -> Optional[str]:
    """Normalise a list (e.g. authors) to an order-independent canonical key."""
    if not isinstance(values, (list, tuple)):
        return _norm(values)
    parts = sorted(p for p in (_norm(v) for v in values) if p)
    return "|".join(parts) or None


def row_cells(row: Dict[str, Any]) -> Dict[str, str]:
    """Flatten one row into a {field_key: normalised_value} map of the cells
    that carry a value. The paper title is excluded — it is the identity used
    for row alignment, not a compared cell."""
    cells: Dict[str, str] = {}

    authors = _norm_list(row.get("authors"))
    if authors:
        cells["authors"] = authors

    for key in _BIBLIO_FIELDS:
        nv = _norm(row.get(key))
        if nv is not None:
            cells[key] = nv

    props = row.get("domain_specific_properties") or {}
    for key, val in props.items():
        nv = _norm_list(val) if isinstance(val, (list, tuple)) else _norm(val)
        if nv is not None:
            cells[f"prop::{key}"] = nv

    return cells


def _title(row: Dict[str, Any]) -> str:
    return _norm(row.get("paper_title")) or ""


def _title_sim(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return SequenceMatcher(None, _title(a), _title(b)).ratio()


def _all_rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for table in (result or {}).get("tables", []) or []:
        rows.extend(table.get("rows", []) or [])
    return rows


def match_rows(
    gold_rows: List[Dict[str, Any]],
    pred_rows: List[Dict[str, Any]],
    threshold: float = 0.6,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """Greedily align predicted rows to gold rows by title similarity.

    Returns (matched_pairs, unmatched_gold_idx, unmatched_pred_idx).
    A pair is only accepted when title similarity ≥ threshold. Rows that are
    both flagged as the proposed method get a small similarity bonus so a
    paper's own contribution aligns even if its title is phrased differently.
    """
    candidates: List[Tuple[float, int, int]] = []
    for gi, g in enumerate(gold_rows):
        for pi, p in enumerate(pred_rows):
            sim = _title_sim(g, p)
            if g.get("is_proposed_method") and p.get("is_proposed_method"):
                sim = min(1.0, sim + 0.15)
            candidates.append((sim, gi, pi))

    candidates.sort(reverse=True)
    used_g, used_p = set(), set()
    matched: List[Tuple[int, int]] = []
    for sim, gi, pi in candidates:
        if sim < threshold or gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        matched.append((gi, pi))

    unmatched_g = [i for i in range(len(gold_rows)) if i not in used_g]
    unmatched_p = [i for i in range(len(pred_rows)) if i not in used_p]
    return matched, unmatched_g, unmatched_p


def _proposed_row(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for r in rows:
        if r.get("is_proposed_method"):
            return r
    return rows[0] if rows else None


def leakage_violations(pred_rows: List[Dict[str, Any]]) -> int:
    """Count baseline rows that illegitimately inherited the proposed paper's
    author list — the 'Metadata Firewall' violation the pipeline guards against."""
    proposed = _proposed_row(pred_rows)
    if not proposed:
        return 0
    primary = _norm_list(proposed.get("authors"))
    if not primary:
        return 0
    violations = 0
    for r in pred_rows:
        if r is proposed:
            continue
        if _norm_list(r.get("authors")) == primary:
            violations += 1
    return violations


def f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fscore = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, fscore


@dataclass
class Score:
    """Accumulates counts across one or many examples so metrics can be
    aggregated micro-averaged (sum the counts, then divide)."""
    examples: int = 0
    # row-level
    row_tp: int = 0
    row_fp: int = 0
    row_fn: int = 0
    # cell-level
    cell_tp: int = 0
    cell_fp: int = 0
    cell_fn: int = 0
    # specialised
    leakage: int = 0
    proposed_total: int = 0
    proposed_correct: int = 0
    per_example: List[Dict[str, Any]] = field(default_factory=list)

    def __add__(self, other: "Score") -> "Score":
        merged = Score()
        for f_ in ("examples", "row_tp", "row_fp", "row_fn", "cell_tp",
                   "cell_fp", "cell_fn", "leakage", "proposed_total",
                   "proposed_correct"):
            setattr(merged, f_, getattr(self, f_) + getattr(other, f_))
        merged.per_example = self.per_example + other.per_example
        return merged

    def summary(self) -> Dict[str, Any]:
        rp, rr, rf = f1(self.row_tp, self.row_fp, self.row_fn)
        cp, cr, cf = f1(self.cell_tp, self.cell_fp, self.cell_fn)
        return {
            "examples": self.examples,
            "row_precision": round(rp, 4),
            "row_recall": round(rr, 4),
            "row_f1": round(rf, 4),
            "cell_precision": round(cp, 4),
            "cell_recall": round(cr, 4),
            "cell_f1": round(cf, 4),
            "leakage_violations": self.leakage,
            "proposed_identified": f"{self.proposed_correct}/{self.proposed_total}",
        }


def score_example(gold: Dict[str, Any], pred: Dict[str, Any],
                  threshold: float = 0.6, example_id: str = "") -> Score:
    """Score a single predicted result against its gold result."""
    gold_rows = _all_rows(gold)
    pred_rows = _all_rows(pred)

    matched, unmatched_g, unmatched_p = match_rows(gold_rows, pred_rows, threshold)

    s = Score(examples=1)
    s.row_tp = len(matched)
    s.row_fn = len(unmatched_g)   # gold rows we failed to produce
    s.row_fp = len(unmatched_p)   # rows we invented that gold doesn't have

    for gi, pi in matched:
        g_cells = row_cells(gold_rows[gi])
        p_cells = row_cells(pred_rows[pi])
        keys = set(g_cells) | set(p_cells)
        for k in keys:
            gv, pv = g_cells.get(k), p_cells.get(k)
            if gv is not None and pv is not None and gv == pv:
                s.cell_tp += 1
            elif gv is not None and (pv is None or pv != gv):
                s.cell_fn += 1          # missing or wrong value
                if pv is not None:
                    s.cell_fp += 1      # wrong value is also a false positive
            elif gv is None and pv is not None:
                s.cell_fp += 1          # value where gold expects none

    # proposed-method identification
    g_prop = _proposed_row(gold_rows)
    p_prop = _proposed_row(pred_rows)
    if g_prop is not None:
        s.proposed_total = 1
        if p_prop is not None and _title_sim(g_prop, p_prop) >= threshold:
            s.proposed_correct = 1

    s.leakage = leakage_violations(pred_rows)

    s.per_example.append({"id": example_id, **s.summary()})
    return s


def aggregate(scores: List[Score]) -> Score:
    total = Score()
    for s in scores:
        total = total + s
    return total
