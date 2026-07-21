"""Shared pytest configuration.

Ensures the repo root is importable and provides a dummy DATABASE_URL so that
importing ``app`` modules (whose settings require one) does not fail during
collection. No real database connection is opened unless a test actually uses
the session — the pure scoring tests never do.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Satisfy app.core.config's mandatory settings for import-time only.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-placeholder-not-used")
