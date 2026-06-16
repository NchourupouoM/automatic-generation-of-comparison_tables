from celery import Celery
from app.core.config import settings

# Initialisation de l'instance Celery
celery_app = Celery(
    "scientific_extractor",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configurations pour des exécutions sérialisables et stables en production
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Force les tâches Celery à être importées pour être découvertes automatiquement
    imports=["app.services.tasks"]
)