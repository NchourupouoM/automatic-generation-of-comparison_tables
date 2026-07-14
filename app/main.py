# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.endpoints import router as api_router

from app.core.database import engine, Base
import app.core.models
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. INITIALISATION AUTOMATIQUE DES TABLES DANS CLOUD SQL [3]
# ---------------------------------------------------------------------------
# La méthode 'create_all' est totalement idempotente : elle va créer les tables 
# manquantes lors du premier démarrage, mais n'écrasera pas les données existantes 
# lors des redémarrages ultérieurs du serveur [3].
try:
    logger.info("Initializing Google Cloud SQL tables if missing...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables successfully checked and initialized in PostgreSQL.")
except Exception as e:
    logger.error(f"❌ Failed to auto-create database tables on startup: {str(e)}")


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