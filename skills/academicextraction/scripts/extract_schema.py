# skills/academic-extraction/scripts/extract_schema.py
from pathlib import Path
from typing import Optional
from app.core.schemas import ComparisonRow
from app.core.llm_factory import LLMFactory
from app.core.skills_loader import SkillLoader


def run_academic_extraction(
    paper_text: str, 
    proceeding_title: Optional[str] = None
) -> ComparisonRow:
    """
    Extracts structured academic metadata by loading and injecting instructions
    dynamically defined in the SKILL.md file.
    """
    # 1. Résolution dynamique des instructions du Skill parent
    skill_dir = Path(__file__).parent.parent
    _, instructions = SkillLoader.load_skill(skill_dir)
    
    # 2. Configuration du modèle
    llm = LLMFactory.get_llm()
    structured_llm = llm.with_structured_output(ComparisonRow)
    
    # 3. Injection dynamique du corps d'instructions dans le contexte d'exécution
    prompt = f"""
    SYSTEM INSTRUCTIONS :
    =======================================================
    {instructions}
    =======================================================
    
    TASK RUNTIME INPUT:
    {"Proceeding context: " + proceeding_title if proceeding_title else ""}
    
    Paper Content:
    ---
    {paper_text[:40000]}
    ---
    """
    
    try:
        row_data = structured_llm.invoke(prompt)
        if proceeding_title and not row_data.proceeding_title:
            row_data.proceeding_title = proceeding_title
        return row_data
    except Exception as e:
        raise RuntimeError(f"Failsafe triggered. Structured academic extraction failed: {str(e)}")