# skills/structural-clustering/scripts/cluster_papers.py
from pathlib import Path
from pydantic import BaseModel, Field
from app.core.llm_factory import LLMFactory
from app.core.skills_loader import SkillLoader


class SegmentedPaperMetadata(BaseModel):
    title: str = Field(..., description="The inferred title of the individual paper.")
    authors: list[str] = Field(default_factory=list, description="Extracted authors of the paper.")
    abstract_summary: str = Field(..., description="Brief summary of the paper's abstract.")
    research_problem: str = Field(..., description="The specific, granular research problem addressed.")


class SegmentationManifest(BaseModel):
    papers: list[SegmentedPaperMetadata] = Field(..., description="List of all individual papers extracted from the proceeding.")


def run_clustering_and_segmentation(markdown_text: str) -> SegmentationManifest:
    """
    Segments a proceeding document by loading and executing instructions 
    dynamically defined in the SKILL.md file.
    """
    # 1. Résolution dynamique des instructions du Skill parent
    skill_dir = Path(__file__).parent.parent
    _, instructions = SkillLoader.load_skill(skill_dir)
    
    # 2. Configuration du modèle
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(SegmentationManifest)
    
    # 3. Injection dynamique de la spécification de la compétence dans le prompt
    prompt = f"""
    SYSTEM INSTRUCTIONS (Loaded dynamically from SKILL.md):
    =======================================================
    {instructions}
    =======================================================
    
    TASK RUNTIME INPUT:
    Analyze the following scientific text segment:
    ---
    {markdown_text[:60000]}
    ---
    """
    
    try:
        manifest = structured_llm.invoke(prompt)
        return manifest
    except Exception as e:
        raise RuntimeError(f"Failsafe triggered. Structured clustering failed: {str(e)}")