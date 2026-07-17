"""
Shared test fixtures. Sets dummy env vars BEFORE any `app.*` import so that
`app.core.config.Settings` (which requires DATABASE_URL) can be constructed
without a real database or LLM credentials. These tests are fully offline and
deterministic — no network, no DB, no LLM calls.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("LLM_MODEL_NAME", "gpt-4o")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")

from pathlib import Path

import pytest

PDF_DIR = Path(__file__).parent.parent / "evals" / "pdfs"


@pytest.fixture
def sample_pdf() -> Path:
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        pytest.skip("no sample PDFs available in evals/pdfs")
    return pdfs[0]
