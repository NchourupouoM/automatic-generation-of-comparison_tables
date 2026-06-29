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


# app/services/tasks.py (Mise à jour ciblée)

@celery_app.task(bind=True, name="app.services.tasks.run_extraction")
def run_extraction_task(
    self, 
    raw_markdown: str,  # Devient directement la chaîne Markdown
    manual_document_type: str = "auto", 
    domain: str = "default"
) -> dict:
    self.update_state(
        state="PROCESSING", 
        meta={"progress_status": f"Initializing execution for domain: '{domain}'"}
    )
    
    try:
        # Initialisation de l'état du graphe avec le Markdown déjà présent
        state_input = {
            "raw_markdown": raw_markdown,  # Injecté directement
            "manual_document_type": manual_document_type,
            "document_type": "single",
            "domain": domain,
            "extraction_tasks": [],
            "extracted_rows": [],
            "consolidated_result": {}
        }
        
        final_state = orchestrator_graph.invoke(state_input)
        return final_state["consolidated_result"]
        
    except Exception as e:
        raise e