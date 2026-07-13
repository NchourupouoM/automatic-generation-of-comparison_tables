import logging
from typing import Generator
from sqlalchemy import create_engine
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
# 4. Dépendance d'injection de session (Dependency Injection)
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