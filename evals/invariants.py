"""
Structural invariants a valid extraction must satisfy, independent of any
golden truth. These let the whole 26-paper corpus act as a regression suite:
a table can be scored for *accuracy* only where a golden file exists, but every
document can be checked for these cheap correctness properties.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def check_table_invariants(table: Dict[str, Any]) -> List[str]:
    """Returns a list of violation messages; empty means the table is well-formed."""
    violations: List[str] = []
    rows = table.get("rows")

    if not isinstance(rows, list) or len(rows) == 0:
        violations.append("table has no rows")
        return violations

    proposed = [r for r in rows if r.get("is_proposed_method")]
    if len(proposed) == 0:
        violations.append("no row flagged as the proposed method")
    elif len(proposed) > 1:
        violations.append(f"{len(proposed)} rows flagged as proposed method (expected exactly 1)")

    primary_authors = set(_norm_list(proposed[0].get("authors"))) if proposed else set()

    for i, row in enumerate(rows):
        if not (row.get("paper_title") or "").strip():
            violations.append(f"row {i} has an empty paper_title")

        # Metadata firewall: a baseline must not copy the primary paper's authors.
        if i > 0 and not row.get("is_proposed_method"):
            row_authors = set(_norm_list(row.get("authors")))
            if row_authors and primary_authors and row_authors == primary_authors:
                violations.append(
                    f"row {i} ({row.get('paper_title')!r}) inherited the primary paper's authors"
                )

        doi = row.get("doi") or _nested(row).get("doi")
        if doi and not DOI_RE.match(str(doi).strip()):
            violations.append(f"row {i} has a malformed DOI: {doi!r}")

    return violations


def _nested(row: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("properties", "domain_specific_properties"):
        val = row.get(key)
        if isinstance(val, dict):
            return val
    return {}


def _norm_list(authors: Any) -> List[str]:
    if not isinstance(authors, list):
        return []
    return [" ".join(str(a).lower().split()) for a in authors if str(a).strip()]
