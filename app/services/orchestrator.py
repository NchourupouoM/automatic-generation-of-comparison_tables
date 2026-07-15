import logging
import uuid
from pathlib import Path
from typing import Dict, List, Any, Literal, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

from pydantic import BaseModel, Field
import json
import re

from app.core.config import settings
from app.core.llm_factory import LLMFactory
from app.core.database import SessionLocal
from app.core.models import TemplateModel, ValidationTaskModel, ComparisonTableModel, ExtractedRowModel
from app.core.dynamic_loader import compile_dynamic_table_model, save_new_template_to_db
from app.core.schemas import ComparisonTable
from app.core.skills_loader import SkillLoader

# Importation des prompts isolés
from app.core.prompts import (
    CLASSIFIER_PROMPT,
    PROPOSE_PROPERTIES_PROMPT,
    SEGMENTER_CLUSTERER_PROMPT,
    ACADEMIC_EXTRACTION_PROMPT,
    RECOMMEND_TEMPLATE_PROMPT
)

from skills.structuralclustering.scripts.cluster_papers import SegmentationManifest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Structure de l'État du Graphe (GraphState)
# ---------------------------------------------------------------------------
class PaperTask(BaseModel):
    title: str
    authors: List[str] = []
    text_segment: str
    domain_hint: Optional[str] = None


class GraphState(TypedDict):
    raw_markdown: str
    manual_document_type: str
    document_type: Literal["single", "proceeding"]
    domain: str
    celery_task_id: str
    extraction_tasks: List[PaperTask]
    extracted_rows: List[Any]
    proposed_properties: List[Dict[str, str]]
    validated_schema_json: Dict[str, Any]
    consolidated_result: Dict[str, Any]


# ---------------------------------------------------------------------------
# 2. Modèles de routage intermédiaires
# ---------------------------------------------------------------------------
class DocumentClassification(BaseModel):
    document_type: Literal["single", "proceeding"]


class ProposedProperty(BaseModel):
    name: str = Field(..., description="Lowercase snake_case name.")
    description: str = Field(..., description="English description.")


class ProposedPropertiesList(BaseModel):
    properties: List[ProposedProperty]


class SuggestionProperty(BaseModel):
    name: str = Field(..., description="The property name in snake_case.")
    description: str = Field(..., description="English description/guideline.")
    type: str = Field(default="str", description="Data type: 'str', 'int', 'list_str', 'bool'")


class RecommendationResult(BaseModel):
    decision: Literal["match", "new"] = Field(..., description="Select 'match' or 'new'.")
    matched_template_id: Optional[str] = Field(default=None)
    proposed_domain_key: Optional[str] = Field(default=None)
    proposed_domain_name: Optional[str] = Field(default=None)
    proposed_properties: List[SuggestionProperty] = Field(default_factory=list)
    rationale: str = Field(..., description="Reasoning.")


# ---------------------------------------------------------------------------
# 3. Nœuds des Agents Coordonnés (Nodes)
# ---------------------------------------------------------------------------

def classify_document_node(state: GraphState) -> Dict[str, Any]:
    """Agent: Classifies whether the document is single or proceeding."""
    manual_type = state.get("manual_document_type", "auto")
    if manual_type in ["single", "proceeding"]:
        return {"document_type": manual_type}
        
    llm = LLMFactory.get_llm()
    structured_classifier = llm.with_structured_output(DocumentClassification)
    
    sample_text = state["raw_markdown"][:4000]
    prompt = CLASSIFIER_PROMPT.format(sample_text=sample_text)
    
    try:
        classification = structured_classifier.invoke(prompt)
        return {"document_type": classification.document_type}
    except Exception:
        return {"document_type": "single"}


def segmenter_and_clusterer_node(state: GraphState) -> Dict[str, Any]:
    """Agent: Splits proceedings into chunks."""
    logger.info("Agent: segmenter_and_clusterer_node running.")
    _, instructions = SkillLoader.load_skill(Path("skills/structuralclustering"))
    
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(SegmentationManifest, method="function_calling")
    
    prompt = SEGMENTER_CLUSTERER_PROMPT.format(
        instructions=instructions,
        raw_markdown=state["raw_markdown"][:60000]
    )
    manifest = structured_llm.invoke(prompt)
    
    tasks = []
    for paper in manifest.papers:
        tasks.append(PaperTask(
            title=paper.title,
            authors=paper.authors,
            text_segment=state["raw_markdown"][:15000],
            domain_hint=paper.research_problem
        ))
    return {"extraction_tasks": tasks}


def domain_detector_node(state: GraphState) -> Dict[str, Any]:
    """
    Agent: Domain Detector.
    Queries PostgreSQL template registry. If the schema is missing OR is 'default',
    system forces a dynamic schema validation flow.
    """
    target_domain = state.get("domain", "default")
    
    if target_domain == "default" and state.get("extraction_tasks"):
        detected_domain = state["extraction_tasks"][0].domain_hint or "default"
        target_domain = detected_domain.lower().replace(" ", "-")
        target_domain = re.sub(r'[^a-z0-9\-]', '', target_domain)

    logger.info(f"Agent: Detecting schema validation registry for domain: '{target_domain}'")
    
    with SessionLocal() as db:
        template_record = db.query(TemplateModel).filter(TemplateModel.id == target_domain).first()
        
        # S'il y a un template en base ET que le domaine n'est pas "default" -> Direct Extraction
        if template_record and target_domain != "default":
            logger.info(f"Domain '{target_domain}' detected in database registry. Proceeding to extraction.")
            tasks = state.get("extraction_tasks", [])
            if not tasks:
                tasks = [PaperTask(title="Proposed Study", text_segment=state["raw_markdown"])]
            return {"domain": target_domain, "extraction_tasks": tasks}
        else:
            logger.warning(f"Domain '{target_domain}' requires dynamic schema proposal. Redirecting to Proposer.")
            return {"domain": target_domain, "extraction_tasks": []}


def recommend_template_for_paper(sample_text: str) -> dict:
    with SessionLocal() as db:
        templates = db.query(TemplateModel).all()
        existing_schemas = [
            {"id": t.id, "name": t.name, "properties": [p["name"] for p in t.schema_json.get("fields", [])]}
            for t in templates
        ]

    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(RecommendationResult, method="function_calling")
    
    prompt = RECOMMEND_TEMPLATE_PROMPT.format(
        existing_schemas_list=json.dumps(existing_schemas, indent=2) if existing_schemas else "No existing schemas.",
        abstract_text=sample_text[:5000]
    )
    
    try:
        recommendation = structured_llm.invoke(prompt)
        return recommendation.model_dump()
    except Exception as e:
        return {
            "decision": "new",
            "proposed_domain_key": "custom-domain",
            "proposed_domain_name": "Custom Domain",
            "proposed_properties": [{"name": "key_metric", "type": "str", "description": "The primary outcome measure."}],
            "rationale": f"Recommendation failed: {str(e)}"
        }


def template_proposer_node(state: GraphState) -> Dict[str, Any]:
    target_domain = state.get("domain", "custom_domain")
    logger.info(f"Agent: Formulating suggested properties for domain '{target_domain}'")
    
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(ProposedPropertiesList, method="function_calling")
    prompt = PROPOSE_PROPERTIES_PROMPT.format(domain_name=target_domain)
    
    try:
        suggestions = structured_llm.invoke(prompt)
        properties = [prop.model_dump() for prop in suggestions.properties]
        
        celery_id = state.get("celery_task_id")
        if celery_id:
            import uuid
            with SessionLocal() as db:
                task_uuid = uuid.UUID(celery_id)
                existing = db.query(ValidationTaskModel).filter(ValidationTaskModel.task_id == task_uuid).first()
                if not existing:
                    new_task = ValidationTaskModel(
                        task_id=task_uuid,
                        status="PENDING_SCHEMA_VALIDATION",
                        proposed_properties=properties,
                        raw_markdown=state["raw_markdown"],
                        domain=target_domain,
                        document_type=state.get("document_type", "single")
                    )
                    db.add(new_task)
                    db.commit()
                    logger.info(f"Successfully registered active HITL interrupt in PostgreSQL: {celery_id}")
                    
        return {"proposed_properties": properties}
    except Exception as e:
        logger.error(f"Failed to propose properties: {str(e)}")
        return {"proposed_properties": []}


def template_validator_node(state: GraphState) -> Dict[str, Any]:
    logger.info("Agent: Human checkpoint validated. Resuming pipeline execution.")
    target_domain = state.get("domain", "custom")
    
    with SessionLocal() as db:
        template_record = db.query(TemplateModel).filter(TemplateModel.id == target_domain).first()
        if not template_record:
            raise ValueError(f"Resumed failed: No validated template found for '{target_domain}'.")
            
    tasks = [PaperTask(title="Proposed Study", text_segment=state["raw_markdown"])]
    return {"extraction_tasks": tasks}


def academic_features_extraction_node(state: GraphState) -> Dict[str, Any]:
    """
    Agent: Academic Features Extraction.
    Resolves the Skill instructions and dynamic validation schemas.
    """
    target_domain = state.get("domain", "default")
    logger.info(f"Agent: Academic Features Extractor running for domain '{target_domain}'")
    
    # ---------------------------------------------------------------------------
    # CORRECTIF : Résolution dynamique du chemin du Skill sémantique [3]
    # ---------------------------------------------------------------------------
    skill_dir = Path(f"skills/{target_domain}")
    if not skill_dir.exists():
        # Fallback de sécurité vers la compétence générique d'extraction si non-référencée
        logger.info(f"Skill directory 'skills/{target_domain}' not found. Falling back to 'academicextraction'.")
        skill_dir = Path("skills/academicextraction")
        
    _, instructions = SkillLoader.load_skill(skill_dir)
    
    # 2. Résolution du modèle de validation
    if target_domain == "default":
        target_schema = ComparisonTable
    else:
        with SessionLocal() as db:
            target_schema = compile_dynamic_table_model(target_domain, db)
        
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(target_schema, method="function_calling")
    
    rows = []
    
    # 3. Traitement de chaque segment de document
    for task in state["extraction_tasks"]:
        prompt = ACADEMIC_EXTRACTION_PROMPT.format(
            instructions=instructions,
            paper_content=task.text_segment
        )
        
        # Boucle d'auto-correction sémantique de Deep Agent (Quality Gate)
        max_attempts = 3
        extracted_table = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f" -> Extraction attempt {attempt}/{max_attempts} for paper '{task.title}'")
                extracted_table = structured_llm.invoke(prompt)
                
                for index, row in enumerate(extracted_table.rows):
                    if index > 0 and len(row.authors) > 0 and set(row.authors) == set(task.authors):
                        raise ValueError(
                            f"Context Leakage Detected: Baseline row '{row.paper_title}' incorrectly inherited "
                            f"the primary paper's author list {task.authors}. Baselines are independent papers."
                        )
                break
                
            except Exception as e:
                logger.warning(f" -> Quality Gate Rejected attempt {attempt} for '{task.title}': {str(e)}")
                if attempt == max_attempts:
                    logger.error(f" -> Deep Agent auto-correction exhausted. Abandoning.")
                    break
                
                prompt = f"""
                PREVIOUS ATTEMPT FAILED WITH ERROR:
                {str(e)}
                
                Please strictly correct your JSON payload. Make sure baseline rows do NOT inherit the primary paper's authors, DOI, or URL.
                
                {ACADEMIC_EXTRACTION_PROMPT.format(instructions=instructions, paper_content=task.text_segment)}
                """
        
        if extracted_table:
            rows.append(extracted_table)
            
    return {"extracted_rows": rows}


def table_synthesizer_node(state: GraphState) -> Dict[str, Any]:
    logger.info("Agent: Synthetizer running database persistence.")
    extracted_tables = state["extracted_rows"]
    target_domain = state.get("domain", "default")
    
    STANDARD_FIELDS = {
        "paper_title", "authors", "publication_month", "publication_year", 
        "venue", "research_field", "doi", "url", "research_problem", "research_method"
    }
    
    persisted_tables_payload = []
    
    with SessionLocal() as db:
        for table_data in extracted_tables:
            research_prob = table_data.research_problem
            
            db_table = ComparisonTableModel(
                id=uuid.uuid4(),
                research_problem=research_prob,
                domain=target_domain if target_domain != "default" else None
            )
            db.add(db_table)
            db.flush()
            
            rows_payload = []
            for index, row in enumerate(table_data.rows):
                row_dict = row.model_dump()
                
                bibliographic_meta = {}
                domain_specific_phi = {}
                
                for key, val in row_dict.items():
                    if key in STANDARD_FIELDS:
                        bibliographic_meta[key] = val
                    else:
                        domain_specific_phi[key] = val
                
                is_proposed = (index == 0)
                
                db_row = ExtractedRowModel(
                    id=uuid.uuid4(),
                    table_id=db_table.id,
                    paper_title=row.paper_title,
                    authors=row.authors,
                    is_proposed_method=is_proposed,
                    bibliographic_metadata=bibliographic_meta,
                    domain_properties=domain_specific_phi
                )
                db.add(db_row)
                
                rows_payload.append({
                    "paper_title": row.paper_title,
                    "authors": row.authors,
                    "is_proposed_method": is_proposed,
                    "domain_specific_properties": domain_specific_phi,
                    **bibliographic_meta
                })
            
            db.commit()
            
            persisted_tables_payload.append({
                "table_id": str(db_table.id),
                "research_problem": research_prob,
                "rows": rows_payload
            })
            
    return {
        "consolidated_result": {
            "domain": target_domain,
            "document_type": state.get("document_type", "single"),
            "tables": persisted_tables_payload
        }
    }


# ---------------------------------------------------------------------------
# 4. Routeurs et liaisons logiques du Graphe
# ---------------------------------------------------------------------------
def route_by_document_scale(state: GraphState) -> Literal["proceeding_flow", "single_flow"]:
    if state["document_type"] == "proceeding":
        return "proceeding_flow"
    return "single_flow"

def route_start_node(state: GraphState) -> Literal["classify_document", "segment_and_cluster", "domain_detector"]:
    manual_type = state.get("manual_document_type", "auto")
    if manual_type == "single":
        return "domain_detector"
    elif manual_type == "proceeding":
        return "segment_and_cluster"
    return "classify_document"

def route_by_domain_registry_presence(state: GraphState) -> Literal["has_schema_flow", "propose_schema_flow"]:
    if state.get("extraction_tasks"):
        return "has_schema_flow"
    return "propose_schema_flow"


def build_orchestrator_graph() -> StateGraph:
    workflow = StateGraph(GraphState)
    
    workflow.add_node("classify_document", classify_document_node)
    workflow.add_node("segment_and_cluster", segmenter_and_clusterer_node)
    workflow.add_node("domain_detector", domain_detector_node)
    workflow.add_node("template_proposer", template_proposer_node)
    workflow.add_node("template_validator", template_validator_node)
    workflow.add_node("academic_features_extraction", academic_features_extraction_node)
    workflow.add_node("synthesizer", table_synthesizer_node)
    
    workflow.set_conditional_entry_point(
        route_start_node,
        {
            "classify_document": "classify_document",
            "segment_and_cluster": "segment_and_cluster",
            "domain_detector": "domain_detector"
        }
    )
    
    workflow.add_conditional_edges(
        "classify_document",
        route_by_document_scale,
        {
            "proceeding_flow": "segment_and_cluster",
            "single_flow": "domain_detector"
        }
    )
    
    workflow.add_edge("segment_and_cluster", "domain_detector")
    
    workflow.add_conditional_edges(
        "domain_detector",
        route_by_domain_registry_presence,
        {
            "has_schema_flow": "academic_features_extraction",
            "propose_schema_flow": "template_proposer"
        }
    )
    
    workflow.add_edge("template_proposer", "template_validator")
    workflow.add_edge("template_validator", "academic_features_extraction")
    workflow.add_edge("academic_features_extraction", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    return workflow


# ---------------------------------------------------------------------------
# 5. CHARGEMENT DYNAMIQUE DU PERSISTEUR LANGGRAPH DANS LE WORKER (Lazy Loading) [3]
# ---------------------------------------------------------------------------
_orchestrator_graph = None

def get_orchestrator_graph():
    global _orchestrator_graph
    if _orchestrator_graph is None:
        logger.info("Compiling LangGraph StateMachine with dynamic PostgresSaver connection pool...")
        
        connection_pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            max_size=5,
            min_size=1,
            kwargs={
                "autocommit": True,
                "row_factory": dict_row
            }
        )
        
        checkpointer = PostgresSaver(connection_pool)
        checkpointer.setup()
        
        _orchestrator_graph = build_orchestrator_graph().compile(
            checkpointer=checkpointer,
            interrupt_before=["template_validator"]
        )
    return _orchestrator_graph

orchestrator_graph = build_orchestrator_graph()