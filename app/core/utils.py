import re


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
