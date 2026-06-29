# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.endpoints import router as api_router

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