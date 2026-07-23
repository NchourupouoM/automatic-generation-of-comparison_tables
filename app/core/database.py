import logging
from typing import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Configuration du Moteur d'exécution (Engine)
# ---------------------------------------------------------------------------
# pool_pre_ping=True : Indispensable sur GCP Cloud Run. Il vérifie que la 
# connexion réseau vers Cloud SQL est toujours "vivante" avant d'exécuter une requête.
# Si la connexion a expiré à cause d'une mise à l'échelle (scale-to-zero), elle est recréée proprement.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      
    pool_size=5,             # Taille du pool de connexions simultanées par conteneur
    max_overflow=10,         # Connexions supplémentaires autorisées en cas de pic de charge
    pool_recycle=1800        # Recyclage des connexions après 30 minutes d'inactivité
)

# ---------------------------------------------------------------------------
# 2. Fabrique de Session locale (SessionLocal)
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# ---------------------------------------------------------------------------
# 3. Classe de Base Déclarative (Style SQLAlchemy 2.0)
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Unified declarative base representing the relational models.
    Supports modern Python typing annotations natively.
    """
    pass


# ---------------------------------------------------------------------------
# 4. Mises à niveau additives idempotentes (safe online migration)
# ---------------------------------------------------------------------------
# Registry of columns introduced after the initial schema. `create_all` creates
# MISSING TABLES but never ALTERS an existing one, so a database that predates a
# column would be missing it and the app would error on insert/read. We add such
# columns here — always NULLABLE and additive, so existing rows simply get NULL
# (which the app already treats as "empty"). Purely additive and idempotent:
# safe to run on every startup, and it never drops or rewrites anything.
_ADDITIVE_COLUMNS = {
    "extracted_rows": {
        "evidence": "JSONB",
        "entity_id": "UUID",
    },
}


def ensure_additive_upgrades() -> None:
    """Add any newly-introduced nullable columns that an older database lacks.

    This is a deliberately tiny, dependency-free alternative to a full migration
    tool: it only ever runs `ADD COLUMN IF NOT EXISTS` for columns listed in
    `_ADDITIVE_COLUMNS`. On a fresh database (where `create_all` already made the
    tables with every column) each statement is a no-op.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all will have built it complete
            present = {c["name"] for c in inspector.get_columns(table)}
            for column, sql_type in columns.items():
                if column in present:
                    continue
                logger.info(f"Additive upgrade: adding {table}.{column} ({sql_type}).")
                conn.execute(text(
                    f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sql_type}'
                ))


# ---------------------------------------------------------------------------
# 5. Dépendance d'injection de session (Dependency Injection)
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI and Task dependency generator.
    Guarantees that database connections are properly closed after each 
    request/task is resolved, preventing memory leaks in production.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session exception encountered: {str(e)}")
        raise e
    finally:
        db.close()