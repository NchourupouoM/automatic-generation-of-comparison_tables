# app/services/tasks.py
import logging
from celery import Task
from app.core.celery_app import celery_app
from app.services.orchestrator import orchestrator_graph

logger = logging.getLogger(__name__)


class ExtractionTask(Task):
    """
    Custom task class to log lifecycle events of the extraction pipeline.
    """
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed. Arguments: {args}. Error: {str(exc)}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True, 
    base=ExtractionTask, 
    name="app.services.tasks.run_extraction"
)
def run_extraction_task(self, pdf_path: str,  manual_document_type: str = "auto", domain: str = "default") -> dict:
    """
    Asynchronous task wrapper that executes the LangGraph state machine.
    """
    logger.info(f"Task initiated: {self.request.id} for file {pdf_path}")
    
    # Mise à jour préliminaire du statut pour l'utilisateur
    self.update_state(
        state="PROCESSING", 
        meta={"progress_status": "Extracting document layout and classifying scale"}
    )
    
    try:
        # Initialisation de l'état du graphe
        state_input = {
            "pdf_path": pdf_path,
            "raw_markdown": "",
            "manual_document_type": manual_document_type,
            "document_type": "single",
            "domain": domain,
            "extraction_tasks": [],
            "extracted_rows": [],
            "consolidated_result": {}
        }
        
        # Invocation synchrone au sein du worker Celery
        final_state = orchestrator_graph.invoke(state_input)
        
        logger.info(f"Task completed successfully: {self.request.id}")
        return final_state["consolidated_result"]
        
    except Exception as e:
        logger.error(f"Execution error in orchestration pipeline: {str(e)}")
        # Nous levons l'exception pour permettre à Celery de marquer la tâche en statut FAILURE
        raise e