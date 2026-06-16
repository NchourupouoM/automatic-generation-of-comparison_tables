import logging
from pathlib import Path
from typing import Dict, List, Any, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.llm_factory import LLMFactory
from app.core.parse_pdf import extract_pdf_to_markdown
from app.core.schemas import ComparisonRow, ComparativeResult, ConsolidatedComparisonTable, ConsolidatedComparisonRow
from app.core.skills_loader import SkillLoader

from skills.structuralclustering.scripts.cluster_papers import SegmentationManifest
from app.core.domains_registry import DOMAINS_REGISTRY

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
    manual_document_type: str
    document_type: Literal["single", "proceeding"]
    
    # Liste de tâches individuelles d'extraction à réaliser (Pour le domaine par défaut)
    extraction_tasks: List[PaperTask]
    
    # Résultats d'extractions individuelles accumulées (ComparisonRow - Domaine par défaut)
    extracted_rows: List[ComparisonRow]
    
    # Résultat final structuré (S'adapte dynamiquement au domaine sélectionné)
    consolidated_result: Dict[str, Any]

    domain: str  # e.g., "default", "infectious-disease"


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
    """
    Agent: Classifies document scale or applies manual override to save LLM tokens.
    """
    # 1. Vérification si un override manuel a été fourni
    manual_type = state.get("manual_document_type", "auto")
    
    if manual_type in ["single", "proceeding"]:
        logger.info(
            f"Node: classify_document_node bypassed. "
            f"Applying manual override classification: '{manual_type}' to save tokens."
        )
        return {"document_type": manual_type}
        
    # 2. Exécution de la détection automatique sémantique si 'auto'
    logger.info("Node: classify_document_node running automatic LLM classification.")
    llm = LLMFactory.get_llm()
    structured_classifier = llm.with_structured_output(DocumentClassification)
    
    sample_text = state["raw_markdown"][:4000]
    
    prompt = f"""
    Analyze the introduction of this scientific document and classify if it is:
    - A 'single' research paper (focusing on one main contribution, method, and evaluation).
    - A 'proceeding' (acts, table of contents, or book volume containing multiple distinct research papers).
    
    Document sample:
    ---
    {sample_text}
    ---
    """
    try:
        classification = structured_classifier.invoke(prompt)
        logger.info(f"Auto-detection classified as: {classification.document_type}")
        return {"document_type": classification.document_type}
    except Exception as e:
        logger.warning(f"Auto-classification failed, defaulting to 'single'. Error: {str(e)}")
        return {"document_type": "single"}


# --- BRANCHE PAPIER UNIQUE SPÉCIALISÉ PAR DOMAINE (Nouveau Nœud) ---

def process_domain_single_paper_node(state: GraphState) -> Dict[str, Any]:
    """
    Agent: Specialized Single Paper Extractor.
    Extracts highly specific clinical or scientific variables for non-default domains (e.g., 'infectious-disease').
    Loads instructions dynamically from the target domain's SKILL.md.
    """
    target_domain = state.get("domain", "default")
    domain_config = DOMAINS_REGISTRY.get(target_domain, DOMAINS_REGISTRY["default"])
    
    logger.info(f"Agent: process_domain_single_paper_node started for domain '{target_domain}'")
    
    # Chargement dynamique des instructions de la compétence du domaine
    _, instructions = SkillLoader.load_skill(domain_config.skill_path)
    
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(domain_config.schema_class, method="function_calling")
    
    prompt = f"""
    SYSTEM SKILL INSTRUCTIONS (Loaded dynamically from {domain_config.skill_path}):
    =======================================================
    {instructions}
    =======================================================
    
    TASK INPUT:
    Extract the structured representation of the target paper.
    Ensure all domain-specific variables are populated accurately and formatted cleanly.
    
    Paper Content:
    ---
    {state["raw_markdown"][:50000]}
    ---
    """
    try:
        extracted_data = structured_llm.invoke(prompt)
        
        # Structure de retour standardisée pour l'API
        payload = {
            "domain": target_domain,
            "data": extracted_data.model_dump()
        }
        return {"consolidated_result": payload}
    except Exception as e:
        logger.error(f"Failed specialized extraction for domain '{target_domain}': {str(e)}")
        raise e


# --- BRANCHE PAPIER UNIQUE PAR DÉFAUT (Case A) ---

def baseline_identifier_agent(state: GraphState) -> Dict[str, Any]:
    """
    Agent 1 (Case A): Baseline Identifier.
    Job: Read the paper and identify only the main proposed method and the list of compared baselines.
    """
    logger.info("Agent: baseline_identifier_agent running.")
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(BaselineList, method="function_calling")
    
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


# --- BRANCHE RECUEIL D'ACTES PAR DÉFAUT (Case B) ---

def segmenter_and_clusterer_agent(state: GraphState) -> Dict[str, Any]:
    """
    Agent 1 (Case B): Segmenter and Clusterer.
    Job: Split proceeding and group papers by research problem.
    """
    logger.info("Agent: segmenter_and_clusterer_agent running.")
    _, instructions = SkillLoader.load_skill(Path("skills/structuralclustering"))
    
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(SegmentationManifest, method="function_calling")
    
    prompt = f"""
    SYSTEM SKILL INSTRUCTIONS:
    {instructions}
    
    Input proceeding text:
    ---
    {state['raw_markdown'][:60000]}
    ---
    """
    manifest = structured_llm.invoke(prompt)
    
    tasks = []
    for paper in manifest.papers:
        tasks.append(PaperTask(
            title=paper.title,
            authors=paper.authors,
            text_segment=state["raw_markdown"][:15000]
        ))
    return {"extraction_tasks": tasks}


# --- NŒUDS COMMUNS ---

def feature_extractor_agent(state: GraphState) -> Dict[str, Any]:
    """
    Agent 2 (Common): Academic Feature Extractor.
    Job: Extract properties for ONE paper task at a time.
    """
    logger.info("Agent: feature_extractor_agent running.")
    _, instructions = SkillLoader.load_skill(Path("skills/academicextraction"))
    
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(ComparisonRow, method="function_calling")
    
    rows: List[ComparisonRow] = []
    
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
    Job: Consolidate extracted rows, transform List[CustomProperty] back to Dict[str, Any],
    and construct the final validated API output structure.
    """
    logger.info("Agent: table_synthesizer_agent running.")
    raw_rows = state["extracted_rows"]
    
    consolidated_rows: List[ConsolidatedComparisonRow] = []
    for row in raw_rows:
        dict_properties = {
            prop.property_name: prop.property_value 
            for prop in row.domain_specific_properties
        }
        
        consolidated_rows.append(
            ConsolidatedComparisonRow(
                proceeding_title=row.proceeding_title,
                paper_title=row.paper_title,
                authors=row.authors,
                publication_month=row.publication_month,
                publication_year=row.publication_year,
                venue=row.venue,
                research_field=row.research_field,
                doi=row.doi,
                url=row.url,
                research_problem=row.research_problem,
                research_method=row.research_method,
                domain_specific_properties=dict_properties
            )
        )
    
    if state["document_type"] == "proceeding":
        clusters: Dict[str, List[ConsolidatedComparisonRow]] = {}
        for row in consolidated_rows:
            prob = row.research_problem or "General Research"
            if prob not in clusters:
                clusters[prob] = []
            clusters[prob].append(row)
            
        tables = [
            ConsolidatedComparisonTable(research_problem=p, rows=r) 
            for p, r in clusters.items()
        ]
    else:
        common_problem = consolidated_rows[0].research_problem if consolidated_rows else "General Research"
        tables = [
            ConsolidatedComparisonTable(research_problem=common_problem, rows=consolidated_rows)
        ]
        
    result = ComparativeResult(tables=tables)
    
    # Format de retour unifié
    response_payload = {
        "domain": "default",
        "data": result.model_dump()
    }
    return {"consolidated_result": response_payload}


# ---------------------------------------------------------------------------
# 4. Construction et Compilation du Graphe
# ---------------------------------------------------------------------------
def route_by_scale_and_domain(state: GraphState) -> Literal["single_default_flow", "single_domain_flow", "proceeding_flow"]:
    """
    Routes the execution graph dynamically.
    - Proceeds to 'proceeding_flow' if dealing with proceedings.
    - Proceeds to 'single_domain_flow' if it's a single paper targeting a specialized domain (e.g., 'infectious-disease').
    - Otherwise, routes to 'single_default_flow' for the classic comparative pipeline.
    """
    if state.get("document_type") == "proceeding":
        return "proceeding_flow"
        
    domain = state.get("domain", "default")
    if domain != "default":
        return "single_domain_flow"
        
    return "single_default_flow"


def build_orchestrator_graph() -> StateGraph:
    workflow = StateGraph(GraphState)
    
    # Déclaration des nœuds
    workflow.add_node("extract_text", extract_text_node)
    workflow.add_node("classify_document", classify_document_node)
    workflow.add_node("baseline_identifier", baseline_identifier_agent)
    workflow.add_node("segment_and_cluster", segmenter_and_clusterer_agent)
    workflow.add_node("feature_extractor", feature_extractor_agent)
    workflow.add_node("table_synthesizer", table_synthesizer_agent)
    
    # Enregistrement du nouveau nœud dynamique
    workflow.add_node("process_domain_single_paper", process_domain_single_paper_node)
    
    # Tracé des flux de contrôle
    workflow.set_entry_point("extract_text")
    workflow.add_edge("extract_text", "classify_document")
    
    # Routage conditionnel enrichi
    workflow.add_conditional_edges(
        "classify_document",
        route_by_scale_and_domain,
        {
            "single_default_flow": "baseline_identifier",
            "single_domain_flow": "process_domain_single_paper",
            "proceeding_flow": "segment_and_cluster"
        }
    )
    
    workflow.add_edge("baseline_identifier", "feature_extractor")
    workflow.add_edge("segment_and_cluster", "feature_extractor")
    workflow.add_edge("feature_extractor", "table_synthesizer")
    
    # Points terminaux
    workflow.add_edge("table_synthesizer", END)
    workflow.add_edge("process_domain_single_paper", END)
    
    return workflow.compile()


orchestrator_graph = build_orchestrator_graph()