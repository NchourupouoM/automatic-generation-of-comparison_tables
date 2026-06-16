import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.services.tasks import run_extraction_task

router = APIRouter()


# app/api/endpoints.py (Mise à jour ciblée)

@router.post("/ingest", status_code=202)
async def ingest_document(
    file: UploadFile = File(...),
    document_type: str = Form(
        default="auto",
        description="Override document scale classification. Allowed values: 'auto', 'single', 'proceeding'"
    ),
    domain: str = Form(
        default="default",
        description="Target scientific domain template. e.g., 'default', 'infectious-disease'"
    )
):
    """
    Ingests a scientific PDF document with optional domain-specific and scale overrides.
    """
    normalized_type = document_type.lower().strip()
    normalized_domain = domain.lower().strip()
    
    # Validation du domaine par rapport au registre
    from app.core.domains_registry import DOMAINS_REGISTRY
    if normalized_domain not in DOMAINS_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported domain '{normalized_domain}'. Supported domains: {list(DOMAINS_REGISTRY.keys())}"
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    try:
        temp_dir = Path(tempfile.gettempdir()) / "scientific_extractor"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dest_file_path = temp_dir / file.filename
        
        with dest_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save error: {str(e)}")
    finally:
        await file.close()

    # Transmission du domaine et du type de document à Celery
    task = run_extraction_task.delay(str(dest_file_path), normalized_type, normalized_domain)
    
    return {
        "task_id": task.id,
        "status": "PENDING",
        "detail": f"Processing in domain '{normalized_domain}' started."
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