import pytest
from fastapi import HTTPException

from app.core import security
from app.core.config import settings


def test_no_key_configured_is_open(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", None)
    # Should not raise regardless of header presence.
    assert security.require_api_key(None) is None
    assert security.require_api_key("anything") is None


def test_configured_key_accepts_match(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret-123")
    assert security.require_api_key("secret-123") is None


def test_configured_key_rejects_missing(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret-123")
    with pytest.raises(HTTPException) as exc:
        security.require_api_key(None)
    assert exc.value.status_code == 401


def test_configured_key_rejects_wrong(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret-123")
    with pytest.raises(HTTPException) as exc:
        security.require_api_key("wrong")
    assert exc.value.status_code == 401
