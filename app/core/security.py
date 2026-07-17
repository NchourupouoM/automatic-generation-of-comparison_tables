"""
Lightweight API-key authentication.

When `settings.API_KEY` is configured, protected endpoints require a matching
`X-API-Key` request header. When it is unset (the default), the dependency is a
no-op so local development and the existing open deployment keep working. This
keeps the security opt-in and backwards-compatible while giving production a
single switch to lock the API down.
"""
from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: enforce the configured API key, if any."""
    expected = settings.API_KEY
    if not expected:
        return  # Auth disabled — open API.
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
