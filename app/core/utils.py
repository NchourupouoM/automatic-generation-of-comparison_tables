import re
from typing import Optional


def clamp_pagination(limit: Optional[int], offset: Optional[int],
                     default: int, maximum: int) -> tuple[int, int]:
    """
    Normalizes user-supplied pagination params into a safe (limit, offset)
    pair: limit falls back to `default`, is floored at 1 and capped at
    `maximum`; offset is floored at 0.
    """
    safe_limit = default if not limit or limit < 1 else min(limit, maximum)
    safe_offset = 0 if not offset or offset < 0 else offset
    return safe_limit, safe_offset


def slugify_domain(value: str) -> str:
    """
    Normalizes a human-readable domain name into the machine key used as
    the templates registry primary key.
    e.g. "Malaria-Induced Bone Loss" -> "malaria-induced-bone-loss"
    """
    slug = value.strip().lower().replace("_", " ")
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug
