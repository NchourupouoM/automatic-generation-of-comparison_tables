"""Cross-paper entity resolution.

The same baseline paper is often cited across many comparison tables. This module
maps each extracted row to a single canonical `PaperEntityModel`, so those scattered
mentions collapse into one linked identity.

Matching is deterministic and cheap (no LLM): a normalized DOI wins when present,
otherwise a slug of the title. This is intentionally conservative — it never merges
two papers that don't share a DOI or a near-identical title.
"""
from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.models import PaperEntityModel

# Common stop-words dropped from the title slug so trivial wording differences
# ("A Study of..." vs "Study of...") still resolve to the same key.
_STOP = {"a", "an", "the", "of", "for", "on", "in", "and", "to", "with", "using", "via"}


def _normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    d = doi.strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = d.replace("doi:", "").strip()
    return d or None


def _slug_title(title: Optional[str]) -> str:
    words = re.sub(r"[^a-z0-9\s]", " ", (title or "").lower()).split()
    kept = [w for w in words if w not in _STOP]
    return "-".join(kept)[:200]


def canonical_key(title: Optional[str], doi: Optional[str]) -> Optional[str]:
    """Deterministic identity key for a paper, or None if it can't be keyed."""
    ndoi = _normalize_doi(doi)
    if ndoi:
        return f"doi:{ndoi}"
    slug = _slug_title(title)
    return f"title:{slug}" if slug else None


def resolve_entity(
    db: Session,
    title: Optional[str],
    authors: Optional[List[str]],
    doi: Optional[str] = None,
) -> Optional[PaperEntityModel]:
    """Find or create the canonical entity for a paper and count this mention.

    Returns the entity, or None when the paper cannot be keyed (e.g. no title).
    The caller is responsible for committing the surrounding transaction.
    """
    key = canonical_key(title, doi)
    if not key:
        return None

    entity = db.query(PaperEntityModel).filter(PaperEntityModel.canonical_key == key).first()
    if entity is None:
        entity = PaperEntityModel(
            canonical_key=key,
            canonical_title=(title or "").strip() or "Untitled",
            authors=authors or [],
            doi=_normalize_doi(doi),
            mention_count=0,
        )
        db.add(entity)
        db.flush()  # assign id
    else:
        # Enrich a title-keyed entity if a later mention supplies richer metadata.
        if not entity.doi and _normalize_doi(doi):
            entity.doi = _normalize_doi(doi)
        if (not entity.authors) and authors:
            entity.authors = authors

    entity.mention_count = (entity.mention_count or 0) + 1
    return entity
