from fastapi import FastAPI
from app.api.endpoints import router as api_router

app = FastAPI(
    title="Scientific Content Extractor API",
    description="Asynchronous comparative matrix extraction from scientific publications.",
    version="1.0.0"
)

# Intégration des routes API
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root():
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "Scientific Content Extractor API"
    }