# Dockerfile
FROM python:3.11-slim

# Éviter l'écriture de fichiers de cache Python (.pyc)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# Installation des dépendances systèmes légères
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'intégralité du code du projet (incluant app/static)
COPY . .

EXPOSE 8000

# Par défaut, l'image lance le serveur web API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]