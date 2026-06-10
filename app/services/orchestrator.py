# app/services/orchestrator.py
import logging
from pathlib import Path
from typing import Dict, List, Any, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.llm_factory import LLMFactory
from app.core.parse_pdf import extract_pdf_to_markdown
from app.core.schemas import ComparisonRow, ComparisonTable, ComparativeResult
from app.core.skills_loader import SkillLoader

from skills.structuralclustering.scripts.cluster_papers import SegmentationManifest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Définition de l'état du Graphe
# ---------------------------------------------------------------------------
class PaperTask(BaseModel):
    """Represents a micro-task for extracting one specific paper's row."""
    title: str
    authors: List[str] = []
    text_segment: str


class GraphState(TypedDict):
    pdf_path: str
    raw_markdown: str
    document_type: Literal["single", "proceeding"]
    
    # Liste de tâches individuelles d'extraction à réaliser
    extraction_tasks: List[PaperTask]
    
    # Résultats d'extractions individuelles accumulées (ComparisonRow)
    extracted_rows: List[ComparisonRow]
    
    # Résultat final structuré
    consolidated_result: Dict[str, Any]


# ---------------------------------------------------------------------------
# 2. Modèles intermédiaires pour les agents spécialisés
# ---------------------------------------------------------------------------
class BaselineList(BaseModel):
    """Schema for the Baseline Identifier Agent."""
    proposed_method_title: str = Field(..., description="The main contribution title of the paper.")
    baselines: List[str] = Field(
        default_factory=list, 
        description="List of baseline model names or previous works compared in the paper's evaluation."
    )


class DocumentClassification(BaseModel):
    document_type: Literal["single", "proceeding"]


# ---------------------------------------------------------------------------
# 3. Nœuds des Agents Granulaires (Nodes)
# ---------------------------------------------------------------------------

def extract_text_node(state: GraphState) -> Dict[str, Any]:
    """Deterministic step: calls programmatic utility to read PDF."""
    markdown_content = extract_pdf_to_markdown(state["pdf_path"])
    return {"raw_markdown": markdown_content}


def classify_document_node(state: GraphState) -> Dict[str, Any]:
    """Agent: Classifies document scale."""
    llm = LLMFactory.get_llm()
    structured_classifier = llm.with_structured_output(DocumentClassification)
    
    prompt = f"Analyze the introduction and determine if this is a 'single' paper or a 'proceeding':\n{state['raw_markdown'][:4000]}"
    try:
        classification = structured_classifier.invoke(prompt)
        return {"document_type": classification.document_type}
    except Exception:
        return {"document_type": "single"}


# --- BRANCHE PAPIER UNIQUE (D_single) ---

def baseline_identifier_agent(state: GraphState) -> Dict[str, Any]:
    """
    Agent 1 (Case A): Baseline Identifier.
    Job: Read the paper and identify only the main proposed method and the list of compared baselines.
    """
    logger.info("Agent: baseline_identifier_agent running.")
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(BaselineList)
    
    prompt = f"""
    Analyze the following research paper. Identify:
    1. The exact name of the Proposed Method or contribution of this paper.
    2. The names of the Related Baselines/Methods this paper compares itself against in the evaluation section.
    
    Paper Content:
    ---
    {state['raw_markdown'][:30000]}
    ---
    """
    result = structured_llm.invoke(prompt)
    
    # On crée une liste de micro-tâches d'extraction : le papier principal + les baselines
    tasks = [PaperTask(title=result.proposed_method_title, text_segment=state["raw_markdown"])]
    for baseline in result.baselines:
        tasks.append(PaperTask(title=baseline, text_segment=state["raw_markdown"]))
        
    return {"extraction_tasks": tasks}


# --- BRANCHE RECUEIL D'ACTES (D_proc) ---

def segmenter_and_clusterer_agent(state: GraphState) -> Dict[str, Any]:
    """
    Agent 1 (Case B): Segmenter and Clusterer.
    Job: Split proceeding and group papers by research problem.
    """
    logger.info("Agent: segmenter_and_clusterer_agent running.")
    # On charge la compétence d'extraction/clustering sémantique UNE SEULE FOIS
    _, instructions = SkillLoader.load_skill(Path("skills/structural-clustering"))
    
    # Pour l'étape intermédiaire, on réutilise le modèle de manifeste précédent

    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(SegmentationManifest)
    
    prompt = f"""
    SYSTEM SKILL INSTRUCTIONS:
    {instructions}
    
    Input proceeding text:
    ---
    {state['raw_markdown'][:60000]}
    ---
    """
    manifest = structured_llm.invoke(prompt)
    
    # On convertit le manifeste en micro-tâches individuelles d'extraction
    tasks = []
    for paper in manifest.papers:
        tasks.append(PaperTask(
            title=paper.title,
            authors=paper.authors,
            text_segment=state["raw_markdown"][:15000]  # Segment approximatif
        ))
    return {"extraction_tasks": tasks}


# --- NŒUDS COMMUNS ---

def feature_extractor_agent(state: GraphState) -> Dict[str, Any]:
    """
    Agent 2 (Common): Academic Feature Extractor.
    Job: Extract properties for ONE paper task at a time.
    """
    logger.info("Agent: feature_extractor_agent running.")
    # Chargement unique de la compétence d'extraction
    _, instructions = SkillLoader.load_skill(Path("skills/academic-extraction"))
    
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(ComparisonRow)
    
    rows: List[ComparisonRow] = []
    
    # Pour chaque tâche d'extraction de papier identifiée, l'agent extrait ses caractéristiques de manière isolée
    for task in state["extraction_tasks"]:
        logger.info(f"Extracting features for paper: '{task.title}'")
        prompt = f"""
        SYSTEM SKILL INSTRUCTIONS:
        {instructions}
        
        TASK INSTRUCTIONS:
        Extract comparative features for the target paper: '{task.title}'
        If authors are provided, use them.
        
        Source Text segment:
        ---
        {task.text_segment}
        ---
        """
        try:
            row = structured_llm.invoke(prompt)
            # Alignement de sécurité
            row.paper_title = task.title
            if task.authors and not row.authors:
                row.authors = task.authors
            rows.append(row)
        except Exception as e:
            logger.warning(f"Failed feature extraction for paper '{task.title}': {str(e)}")
            
    return {"extracted_rows": rows}


def table_synthesizer_agent(state: GraphState) -> Dict[str, Any]:
    """
    Agent 3 (Common): Comparison Table Synthesizer.
    Job: Consolidate extracted rows, align key-value mismatches, and construct the final table.
    """
    logger.info("Agent: table_synthesizer_agent running.")
    rows = state["extracted_rows"]
    
    # Si nous sommes dans le cas proceeding, on groupe les lignes par problème de recherche commun
    if state["document_type"] == "proceeding":
        clusters: Dict[str, List[ComparisonRow]] = {}
        for row in rows:
            prob = row.research_problem or "General Research"
            if prob not in clusters:
                clusters[prob] = []
            clusters[prob].append(row)
            
        tables = [ComparisonTable(research_problem=p, rows=r) for p, r in clusters.items()]
    else:
        # Cas papier unique : une seule table regroupant le papier proposé et ses baselines
        common_problem = rows[0].research_problem if rows else "General Research"
        tables = [ComparisonTable(research_problem=common_problem, rows=rows)]
        
    result = ComparativeResult(tables=tables)
    return {"consolidated_result": result.model_dump()}


# ---------------------------------------------------------------------------
# 4. Construction et Compilation du Graphe
# ---------------------------------------------------------------------------
def route_by_document_scale(state: GraphState) -> Literal["single_flow", "proceeding_flow"]:
    if state["document_type"] == "proceeding":
        return "proceeding_flow"
    return "single_flow"


def build_orchestrator_graph() -> StateGraph:
    workflow = StateGraph(GraphState)
    
    workflow.add_node("extract_text", extract_text_node)
    workflow.add_node("classify_document", classify_document_node)
    workflow.add_node("baseline_identifier", baseline_identifier_agent)
    workflow.add_node("segment_and_cluster", segmenter_and_clusterer_agent)
    workflow.add_node("feature_extractor", feature_extractor_agent)
    workflow.add_node("table_synthesizer", table_synthesizer_agent)
    
    workflow.set_entry_point("extract_text")
    workflow.add_edge("extract_text", "classify_document")
    
    workflow.add_conditional_edges(
        "classify_document",
        route_by_document_scale,
        {
            "single_flow": "baseline_identifier",
            "proceeding_flow": "segment_and_cluster"
        }
    )
    
    workflow.add_edge("baseline_identifier", "feature_extractor")
    workflow.add_edge("segment_and_cluster", "feature_extractor")
    workflow.add_edge("feature_extractor", "table_synthesizer")
    workflow.add_edge("table_synthesizer", END)
    
    return workflow.compile()


orchestrator_graph = build_orchestrator_graph()