import shutil
import tempfile
import uuid
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import require_api_key

# Importation sécurisée des modèles relationnels
from app.core.models import (
    TemplateModel,
    ValidationTaskModel,
    ComparisonTableModel,
    ExtractedRowModel,
    ProceedingChunkModel,
    PaperEntityModel,
)

from app.core.parse_pdf import extract_pdf_to_markdown, split_proceeding_pdf
from app.core.dynamic_loader import save_new_template_to_db
from app.core.utils import slugify_domain, clamp_pagination
from app.services.tasks import run_extraction_task, run_schema_proposal_task
from app.services.orchestrator import recommend_template_for_paper

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schémas de requête d'API
# ---------------------------------------------------------------------------
class CustomFieldInput(BaseModel):
    name: str = Field(..., description="The dynamic property name in snake_case.")
    type: str = Field(default="str", description="Data type: 'str', 'int', 'list_str', 'bool'.")
    description: str = Field(..., description="English description of the property.")


class ValidateSchemaRequest(BaseModel):
    domain_display_name: str = Field(..., description="Friendly display name for the new domain.")
    properties: List[CustomFieldInput] = Field(..., description="Validated list of dynamic fields.")


class RecommendRequest(BaseModel):
    raw_markdown: str


# ---------------------------------------------------------------------------
# Endpoints de traitement des documents
# ---------------------------------------------------------------------------

@router.post("/ingest", status_code=202, dependencies=[Depends(require_api_key)])
async def ingest_document(
    file: UploadFile = File(...),
    document_type: str = Form(default="auto"),
    domain: str = Form(default="default")
):
    """
    Ingests a scientific PDF. Programmatically splits proceedings and persists
    every paper segment to PostgreSQL 'proceeding_chunks' to prevent data loss.
    """
    normalized_type = document_type.lower().strip()
    normalized_domain = domain.lower().strip()

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")

    try:
        temp_dir = Path(tempfile.gettempdir()) / "scientific_extractor"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dest_file_path = temp_dir / file.filename
        
        with dest_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

    tasks_payload = []
    
    # 1. Découpage déterministe immédiat sur l'API s'il s'agit d'un proceeding.
    # Le découpage n'est utilisé que s'il est CONFIANT (>= 2 segments, typiquement
    # via un sommaire PDF validé). Sinon, on ne devine pas au risque de couper un
    # article en deux : on transmet le document entier au segmenteur LLM.
    if normalized_type == "proceeding":
        temp_split_dir = temp_dir / f"split_{uuid.uuid4()}"
        split_paths = split_proceeding_pdf(str(dest_file_path), temp_split_dir)

        if len(split_paths) >= 2:
            for path in split_paths:
                try:
                    markdown_content = extract_pdf_to_markdown(str(path))
                    tasks_payload.append({
                        "title": path.stem.replace("_", " ").title(),
                        "authors": [],
                        "text_segment": markdown_content,
                        "domain_hint": "default"
                    })
                    path.unlink()
                except Exception as e:
                    shutil.rmtree(str(temp_split_dir), ignore_errors=True)
                    dest_file_path.unlink()
                    raise HTTPException(status_code=500, detail=f"Failed parsing proceeding chunks: {str(e)}")
            raw_markdown = ""
        else:
            # Pas de frontières fiables : on défère au segmenteur LLM (extraction_tasks vide).
            logger.info("No confident deterministic proceeding split; deferring to the LLM segmenter.")
            try:
                raw_markdown = extract_pdf_to_markdown(str(dest_file_path))
            except Exception as e:
                shutil.rmtree(str(temp_split_dir), ignore_errors=True)
                dest_file_path.unlink()
                raise HTTPException(status_code=500, detail=f"Failed parsing proceeding PDF: {str(e)}")

        shutil.rmtree(str(temp_split_dir), ignore_errors=True)
        dest_file_path.unlink()
    else:
        # Cas Single Paper classique
        try:
            raw_markdown = extract_pdf_to_markdown(str(dest_file_path))
            dest_file_path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed parsing single paper PDF: {str(e)}")

    # 2. Vérification s'il existe déjà un template pour ce domaine
    with SessionLocal() as db:
        domain_exists = db.query(TemplateModel).filter(
            TemplateModel.id == normalized_domain
        ).first() is not None

    # Branche A : Le domaine existe ET n'est pas "default" -> Extraction directe
    if normalized_domain != "default" and domain_exists:
        task = run_extraction_task.delay(
            raw_markdown, 
            normalized_type, 
            normalized_domain,
            extraction_tasks=tasks_payload
        )
        return {
            "task_id": task.id,
            "status": "PROCESSING",
            "detail": f"Direct extraction initiated for domain '{normalized_domain}'."
        }

    # Branche B (HITL) : Le domaine est "default" ou absent -> Création d'une tâche de validation
    validation_task_id = uuid.uuid4()
    
    with SessionLocal() as db:
        new_task = ValidationTaskModel(
            task_id=validation_task_id,
            status="PENDING_SCHEMA_PROPOSAL",
            raw_markdown=tasks_payload[0]["text_segment"] if tasks_payload else raw_markdown,
            domain=normalized_domain,
            document_type=normalized_type,
            proposed_properties=[]
        )
        db.add(new_task)
        db.flush()
        
        # Persistance physique de tous les fragments d'actes découpés
        if normalized_type == "proceeding":
            for chunk in tasks_payload:
                db_chunk = ProceedingChunkModel(
                    id=uuid.uuid4(),
                    task_id=validation_task_id,
                    title=chunk["title"],
                    authors=chunk["authors"],
                    text_segment=chunk["text_segment"],
                    domain_hint=chunk["domain_hint"]
                )
                db.add(db_chunk)
        db.commit()

    run_schema_proposal_task.delay(str(validation_task_id), tasks_payload[0]["text_segment"] if tasks_payload else raw_markdown, normalized_domain)

    return {
        "task_id": str(validation_task_id),
        "status": "PENDING_SCHEMA_PROPOSAL",
        "detail": f"Unregistered domain '{normalized_domain}'. Triggered AI proposals."
    }


# ---------------------------------------------------------------------------
# Endpoint de Polling et d'État de Tâche
# ---------------------------------------------------------------------------
@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Fetches the status and results of either an active Celery extraction 
    or a pending Human-In-The-Loop schema validation.
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        task_result = AsyncResult(task_id, app=celery_app)
        response = {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result if task_result.status == "SUCCESS" else None
        }
        if task_result.status == "FAILURE":
            response["error"] = str(task_result.result)
        return response

    with SessionLocal() as db:
        task_record = db.query(ValidationTaskModel).filter(
            ValidationTaskModel.task_id == task_uuid
        ).first()
        
        if task_record:
            status_in_db = task_record.status
            proposed = task_record.proposed_properties
            
            if status_in_db == "PENDING_SCHEMA_VALIDATION":
                return {
                    "task_id": task_id,
                    "status": "PENDING_SCHEMA_VALIDATION",
                    "proposed_properties": proposed,
                    "domain": task_record.domain,  # Retourne le véritable domaine extrait sémantiquement [3]
                    "raw_markdown": task_record.raw_markdown,
                    "detail": "AI has generated schema proposals. Waiting for human verification."
                }
            elif status_in_db == "PENDING_SCHEMA_PROPOSAL":
                return {
                    "task_id": task_id,
                    "status": "PENDING_SCHEMA_PROPOSAL",
                    "detail": "AI is generating extraction suggestions."
                }

    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": task_result.status
    }
    
    if task_result.status == "SUCCESS":
        response["result"] = task_result.result
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.result)
        
    return response


@router.post("/tasks/{task_id}/validate-schema", status_code=202, dependencies=[Depends(require_api_key)])
async def validate_schema_and_extract(task_id: str, payload: ValidateSchemaRequest):
    """
    Saves the validated schema to templates registry, retrieves ALL persisted 
    proceeding chunks from PostgreSQL, and triggers final parallel extraction.
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task ID format '{task_id}'. Must be a valid hexadecimal UUID string."
        )
    
    domain_display_name = payload.domain_display_name.strip()

    new_template_id = slugify_domain(domain_display_name)

    if not new_template_id or new_template_id == "default":
        new_template_id = f"custom-default-{uuid.uuid4().hex[:4]}"
        
    logger.info(f"Registering validated dynamic template under ID: '{new_template_id}'")

    with SessionLocal() as db:
        task_record = db.query(ValidationTaskModel).filter(ValidationTaskModel.task_id == task_uuid).first()
        if not task_record:
            raise HTTPException(status_code=404, detail="Validation task not found.")
            
        raw_markdown = task_record.raw_markdown
        original_type = task_record.document_type or "single"
        
        properties_list = [prop.model_dump() for prop in payload.properties]
        save_new_template_to_db(
            template_id=new_template_id,
            name=domain_display_name,
            properties=properties_list,
            db=db
        )
        
        chunks_payload = []
        if original_type == "proceeding":
            chunks = db.query(ProceedingChunkModel).filter(ProceedingChunkModel.task_id == task_uuid).all()
            for chunk in chunks:
                chunks_payload.append({
                    "title": chunk.title,
                    "authors": chunk.authors or [],
                    "text_segment": chunk.text_segment,
                    "domain_hint": new_template_id
                })
        
        task_record.status = "SUCCESS"
        db.commit()
    
    # Le template validé par l'humain s'applique au document entier, y compris
    # pour un proceeding : le passer en "default" ferait perdre le schéma validé.
    celery_task = run_extraction_task.delay(
        raw_markdown,
        original_type,
        new_template_id,
        extraction_tasks=chunks_payload
    )

    return {
        "task_id": celery_task.id,
        "status": "PROCESSING"
    }


# ---------------------------------------------------------------------------
# PATH CORRECTIF : Reprise d'extraction robuste avec Template recommandé existant [3]
# ---------------------------------------------------------------------------
@router.post("/tasks/{task_id}/resume-with-existing-template", status_code=202, dependencies=[Depends(require_api_key)])
async def resume_with_existing_template(task_id: str, template_id: str = Form(...)):
    """
    Deletes the temporary validation task and immediately triggers the final 
    extraction Celery task using an existing registered template schema [3].
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format.")
        
    with SessionLocal() as db:
        task_record = db.query(ValidationTaskModel).filter(ValidationTaskModel.task_id == task_uuid).first()
        if not task_record:
            raise HTTPException(status_code=404, detail="Validation task not found.")
            
        raw_markdown = task_record.raw_markdown
        original_type = task_record.document_type or "single"
        
        # 1. Récupération des fragments sémantiques enfants AVANT la suppression parente [3]
        chunks_payload = []
        if original_type == "proceeding":
            chunks = db.query(ProceedingChunkModel).filter(ProceedingChunkModel.task_id == task_uuid).all()
            for chunk in chunks:
                chunks_payload.append({
                    "title": chunk.title,
                    "authors": chunk.authors or [],
                    "text_segment": chunk.text_segment,
                    "domain_hint": template_id
                })
        
        # 2. Suppression propre de la tâche temporaire de validation
        db.delete(task_record)
        db.commit()
                
    # 3. Déclenchement de la tâche finale d'extraction Celery unifiée [3]
    celery_task = run_extraction_task.delay(
        raw_markdown,
        original_type,
        template_id,
        extraction_tasks=chunks_payload
    )
    
    return {
        "task_id": celery_task.id,
        "status": "PROCESSING",
        "detail": "Resuming extraction with existing template."
    }


# ---------------------------------------------------------------------------
# PATH CORRECTIF : Refus et suppression transactionnelle de la queue [3]
# ---------------------------------------------------------------------------
@router.post("/tasks/{task_id}/decline", status_code=200, dependencies=[Depends(require_api_key)])
async def decline_validation_task(task_id: str):
    """
    Deletes the validation task and its associated fragments from PostgreSQL 
    when declined by the human validator, instantly clearing the queue [3].
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task ID format. Must be a valid UUID."
        )
        
    with SessionLocal() as db:
        task_record = db.query(ValidationTaskModel).filter(
            ValidationTaskModel.task_id == task_uuid
        ).first()
        
        if not task_record:
            raise HTTPException(status_code=404, detail="Validation task not found.")
        
        db.delete(task_record)
        db.commit()
        
    return {
        "status": "DECLINED",
        "detail": "Validation task successfully declined and deleted from registry."
    }


# ---------------------------------------------------------------------------
# Endpoints de Lecture Base de Données (Dashboard sémantique)
# ---------------------------------------------------------------------------

@router.get("/templates")
async def list_templates(
    limit: Optional[int] = Query(default=None, ge=1),
    offset: Optional[int] = Query(default=None, ge=0),
):
    safe_limit, safe_offset = clamp_pagination(limit, offset, settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    with SessionLocal() as db:
        total = db.query(TemplateModel).count()
        templates = (
            db.query(TemplateModel)
            .order_by(TemplateModel.created_at.desc())
            .offset(safe_offset).limit(safe_limit).all()
        )
        return {
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "properties": t.schema_json.get("fields", [])
                } for t in templates
            ]
        }


@router.get("/validation-tasks")
async def list_pending_validation_tasks(
    limit: Optional[int] = Query(default=None, ge=1),
    offset: Optional[int] = Query(default=None, ge=0),
):
    safe_limit, safe_offset = clamp_pagination(limit, offset, settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    with SessionLocal() as db:
        base = db.query(ValidationTaskModel).filter(
            ValidationTaskModel.status == "PENDING_SCHEMA_VALIDATION"
        )
        total = base.count()
        tasks = base.order_by(ValidationTaskModel.created_at.desc()).offset(safe_offset).limit(safe_limit).all()
        return {
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "tasks": [
                {
                    "task_id": str(t.task_id),
                    "domain": t.domain,
                    "proposed_properties": t.proposed_properties,
                    "created_at": t.created_at.isoformat()
                } for t in tasks
            ]
        }


@router.get("/comparisons")
async def list_finalized_comparisons(
    limit: Optional[int] = Query(default=None, ge=1),
    offset: Optional[int] = Query(default=None, ge=0),
):
    safe_limit, safe_offset = clamp_pagination(limit, offset, settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    with SessionLocal() as db:
        total = db.query(ComparisonTableModel).count()
        tables = (
            db.query(ComparisonTableModel)
            .order_by(ComparisonTableModel.created_at.desc())
            .offset(safe_offset).limit(safe_limit).all()
        )
        return {
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "comparisons": [
                {
                    "id": str(t.id),
                    "research_problem": t.research_problem,
                    "domain": t.domain or "default",
                    "rows_count": len(t.rows),
                    "created_at": t.created_at.isoformat()
                } for t in tables
            ]
        }


@router.get("/comparisons/{table_id}")
async def get_finalized_comparison(table_id: str):
    """
    Retrieves a specific comparative table and its rows from the PostgreSQL database,
    returning a unified payload structure identical to active Celery tasks [3].
    """
    import uuid
    try:
        table_uuid = uuid.UUID(table_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid table ID format.")

    with SessionLocal() as db:
        table = db.query(ComparisonTableModel).filter(
            ComparisonTableModel.id == table_uuid
        ).first()
        
        if not table:
            raise HTTPException(status_code=404, detail="Comparison table not found.")
        
        rows_payload = []
        for row in table.rows:
            rows_payload.append({
                "paper_title": row.paper_title,
                "authors": row.authors or [],
                "is_proposed_method": row.is_proposed_method,
                "domain_specific_properties": row.domain_properties,
                "evidence": row.evidence or [],
                "entity_id": str(row.entity_id) if row.entity_id else None,
                **(row.bibliographic_metadata or {})
            })
            
        # CORRECTIF UNIFIÉ : Retourne le format attendu par le moteur de rendu JavaScript [3]
        return {
            "consolidated_result": {
                "domain": table.domain or "default",
                "document_type": "single",  # Forcer le rendu horizontal plat parfait pour l'inspection unitaire [3]
                "tables": [
                    {
                        "table_id": str(table.id),
                        "research_problem": table.research_problem,
                        "rows": rows_payload
                    }
                ]
            }
        }


# ---------------------------------------------------------------------------
# Entity Resolution : papiers canoniques dé-dupliqués et leurs occurrences
# ---------------------------------------------------------------------------
@router.get("/entities")
async def list_paper_entities(
    limit: Optional[int] = Query(default=None, ge=1),
    offset: Optional[int] = Query(default=None, ge=0),
):
    """Lists canonical papers, most-referenced first. A single entity here may be
    cited as a baseline across many comparison tables."""
    safe_limit, safe_offset = clamp_pagination(limit, offset, settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    with SessionLocal() as db:
        total = db.query(PaperEntityModel).count()
        entities = (
            db.query(PaperEntityModel)
            .order_by(PaperEntityModel.mention_count.desc(), PaperEntityModel.created_at.desc())
            .offset(safe_offset).limit(safe_limit).all()
        )
        return {
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "entities": [
                {
                    "id": str(e.id),
                    "canonical_title": e.canonical_title,
                    "authors": e.authors or [],
                    "doi": e.doi,
                    "mention_count": e.mention_count,
                }
                for e in entities
            ],
        }


@router.get("/entities/{entity_id}")
async def get_paper_entity(entity_id: str):
    """Returns a canonical paper and every place it appears (which comparison
    table, and whether it was the proposed method or a baseline there)."""
    try:
        entity_uuid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entity ID format.")

    with SessionLocal() as db:
        entity = db.query(PaperEntityModel).filter(PaperEntityModel.id == entity_uuid).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found.")

        mentions = (
            db.query(ExtractedRowModel, ComparisonTableModel)
            .join(ComparisonTableModel, ExtractedRowModel.table_id == ComparisonTableModel.id)
            .filter(ExtractedRowModel.entity_id == entity_uuid)
            .order_by(ComparisonTableModel.created_at.desc())
            .all()
        )
        return {
            "id": str(entity.id),
            "canonical_title": entity.canonical_title,
            "authors": entity.authors or [],
            "doi": entity.doi,
            "mention_count": entity.mention_count,
            "mentions": [
                {
                    "table_id": str(tbl.id),
                    "research_problem": tbl.research_problem,
                    "domain": tbl.domain or "default",
                    "paper_title": row.paper_title,
                    "is_proposed_method": row.is_proposed_method,
                }
                for row, tbl in mentions
            ],
        }


@router.post("/recommend-template")
async def recommend_schema_for_paper(request: RecommendRequest):
    if not request.raw_markdown.strip():
        raise HTTPException(status_code=400, detail="Document content cannot be empty.")
    
    recommendation = recommend_template_for_paper(request.raw_markdown)
    return recommendation


@router.get("/templates/{template_id}")
async def get_template_details(template_id: str):
    with SessionLocal() as db:
        template = db.query(TemplateModel).filter(TemplateModel.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found.")
        return {
            "id": template.id,
            "name": template.name,
            "properties": template.schema_json.get("fields", [])
        }