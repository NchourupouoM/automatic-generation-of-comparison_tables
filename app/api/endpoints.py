import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.services.tasks import run_extraction_task
from app.core.domains_registry import DOMAINS_REGISTRY
from app.core.parse_pdf import extract_pdf_to_markdown

router = APIRouter()

@router.post("/ingest", status_code=202)
async def ingest_document(
    file: UploadFile = File(...),
    document_type: str = Form(default="auto"),
    domain: str = Form(default="default")
):
    normalized_type = document_type.lower().strip()
    normalized_domain = domain.lower().strip()
    
    if normalized_domain not in DOMAINS_REGISTRY:
        raise HTTPException(status_code=400, detail="Unsupported domain.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    try:
        # Sauvegarde temporaire sur le conteneur API pour conversion
        temp_dir = Path(tempfile.gettempdir()) / "scientific_extractor"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dest_file_path = temp_dir / file.filename
        
        with dest_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 1. Extraction immédiate du PDF en Markdown sur le serveur API
        raw_markdown = extract_pdf_to_markdown(str(dest_file_path))
        
        # 2. Suppression immédiate du fichier physique pour libérer la mémoire du conteneur
        dest_file_path.unlink()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF parsing error: {str(e)}")
    finally:
        await file.close()

    # 3. Transmission de la chaîne de texte brute au lieu du chemin de fichier
    task = run_extraction_task.delay(raw_markdown, normalized_type, normalized_domain)
    
    return {
        "task_id": task.id,
        "status": "PENDING",
        "detail": f"Processing in domain '{normalized_domain}' started with in-memory parsing."
    }

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Fetches the processing state and final results of the extraction task.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.status
    }
    
    if task_result.status == "SUCCESS":
        response["result"] = task_result.result
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.result)
    elif task_result.status == "PROCESSING":
        # Récupération des informations d'état personnalisées fournies par update_state
        response["progress_info"] = task_result.info
        
    return response