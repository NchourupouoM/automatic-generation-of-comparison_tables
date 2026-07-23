from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.endpoints import router as api_router

from app.core.database import engine, Base, ensure_additive_upgrades
import app.core.models
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. INITIALISATION AUTOMATIQUE DES TABLES DANS CLOUD SQL [3]
# ---------------------------------------------------------------------------
# 'create_all' crée les tables manquantes mais n'altère jamais une table
# existante. 'ensure_additive_upgrades' complète ce comportement en ajoutant, de
# façon idempotente et non destructive, les nouvelles colonnes nullables à une
# base de données déjà en production — évitant toute erreur au déploiement.
try:
    logger.info("Initializing Google Cloud SQL tables if missing...")
    Base.metadata.create_all(bind=engine)
    ensure_additive_upgrades()
    logger.info("Database schema successfully checked, initialized, and upgraded in PostgreSQL.")
except Exception as e:
    logger.error(f"❌ Failed to auto-create/upgrade database schema on startup: {str(e)}")


app = FastAPI(
    title="Scientific Content Extractor API",
    description="Asynchronous comparative matrix extraction from scientific publications.",
    version="1.0.0"
)

# 1. Enregistrement prioritaire du routeur d'API
app.include_router(api_router, prefix="/api/v1")

# 2. Montage du dossier d'interface statique
# Le paramètre html=True redirige automatiquement l'appel de "/" vers "index.html"
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")