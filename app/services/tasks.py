import logging
import uuid
from celery import Task
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.models import ValidationTaskModel
# IMPORTATION DE LA FONCTION LAZY-LOADED [3]
from app.services.orchestrator import get_orchestrator_graph, PaperTask

logger = logging.getLogger(__name__)


class BaseExtractionTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed. Error: {str(exc)}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(bind=True, base=BaseExtractionTask, name="app.services.tasks.run_extraction")
def run_extraction_task(
    self, 
    raw_markdown: str, 
    manual_document_type: str = "auto", 
    domain: str = "default",
    extraction_tasks: list = []
) -> dict:
    """
    Asynchronous task executing the LangGraph agentic pipeline.
    """
    logger.info(f"Task {self.request.id} started. Domain: '{domain}'. Chunks count: {len(extraction_tasks)}")
    
    tasks = [PaperTask(**t) for t in extraction_tasks] if extraction_tasks else []
    
    state_input = {
        "raw_markdown": raw_markdown,
        "manual_document_type": manual_document_type,
        "document_type": "proceeding" if manual_document_type == "proceeding" else "single",
        "domain": domain,
        "celery_task_id": str(self.request.id),
        "extraction_tasks": tasks,
        "extracted_rows": [],
        "proposed_properties": [],
        "validated_schema_json": {},
        "consolidated_result": {}
    }
    
    config = {
        "configurable": {
            "thread_id": str(self.request.id)
        }
    }
    
    # RÉSOLUTION : Récupération dynamique du graphe compilé dans le worker actif [3]
    orchestrator_graph = get_orchestrator_graph()
    
    final_state = orchestrator_graph.invoke(state_input, config)
    return final_state["consolidated_result"]


@celery_app.task(bind=True, base=BaseExtractionTask, name="app.services.tasks.run_schema_proposal")
def run_schema_proposal_task(self, task_uuid_str: str, raw_markdown: str, domain: str) -> dict:
    """
    Executes the Template Proposer Agent to generate Suggested Properties for the User UI.
    """
    logger.info(f"Task {self.request.id} formulating schema proposals for domain: '{domain}'")
    
    state_input = {
        "raw_markdown": raw_markdown,
        "manual_document_type": "single",
        "document_type": "single",
        "domain": domain,
        "celery_task_id": task_uuid_str,
        "extraction_tasks": [],
        "extracted_rows": [],
        "proposed_properties": [],
        "validated_schema_json": {},
        "consolidated_result": {}
    }
    
    config = {
        "configurable": {
            "thread_id": str(task_uuid_str)
        }
    }
    
    # RÉSOLUTION : Récupération dynamique du graphe [3]
    orchestrator_graph = get_orchestrator_graph()
    
    final_state = orchestrator_graph.invoke(state_input, config)
    
    with SessionLocal() as db:
        task_record = db.query(ValidationTaskModel).filter(
            ValidationTaskModel.task_id == uuid.UUID(task_uuid_str)
        ).first()
        
        if task_record:
            task_record.proposed_properties = final_state.get("proposed_properties", [])
            task_record.status = "PENDING_SCHEMA_VALIDATION"
            db.commit()
            
    logger.info(f"Successfully saved AI suggested properties for task {task_uuid_str}")
    return {"proposed_properties": final_state.get("proposed_properties", [])}