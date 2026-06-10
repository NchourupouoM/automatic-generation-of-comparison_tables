import logging
from pathlib import Path
import pymupdf4llm

logger = logging.getLogger(__name__)


def extract_pdf_to_markdown(pdf_path: str) -> str:
    """
        Deterministic helper to extract raw layout-preserved markdown from PDF.
        This is a software tool, not an LLM-based cognitive skill.
    """
    path_obj = Path(pdf_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
    
    try:
        logger.info(f"Extracting raw markdown from: {pdf_path}")
        return pymupdf4llm.to_markdown(str(path_obj))
    except Exception as e:
        logger.error(f"Failed programmatic PDF extraction: {str(e)}")
        raise RuntimeError(f"PDF extraction utility failed: {str(e)}")