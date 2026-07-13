import logging
from pathlib import Path
import pymupdf4llm
import fitz  # PyMuPDF
import re
from typing import List

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

def split_proceeding_pdf(pdf_path: str, output_dir: Path) -> List[Path]:
    """
    Programmatically splits a multi-paper proceeding PDF into individual paper PDFs
    using PDF outlines (bookmarks) or structural text markers (Abstract keyword).
    No LLMs used, completely deterministic, offline and ultra-fast.
    """
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()  # Récupère la table des matières/signets du PDF
    
    paper_start_pages = []
    
    # Mots-clés de sections de métadonnées générales à ignorer
    ignore_keywords = {
        "preface", "table of contents", "contents", "index", "introduction", 
        "foreword", "acknowledgment", "author index", "program committee",
        "keynote", "welcome", "sponsor", "organizer", "committee", "session"
    }
    
    # 1. Tentative de découpage par les signets officiels (Level-1 bookmarks)
    for level, title, page in toc:
        if level == 1:
            title_lower = title.lower()
            if not any(kw in title_lower for kw in ignore_keywords):
                paper_start_pages.append(page - 1)  # fitz utilise l'indexation 0
                
    # Déduplication et tri
    paper_start_pages = sorted(list(set(paper_start_pages)))
    
    # 2. Repli : Scan structurel des en-têtes de pages si aucun signet n'est trouvé
    if not paper_start_pages:
        logger.info("No PDF outlines found. Falling back to structural 'Abstract' page scanning.")
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")[:1000].lower() # Scan du haut de page
            
            if "abstract" in text or "abstract:" in text:
                paper_start_pages.append(page_num)
                
    # Si aucun signal n'est trouvé, on traite le document entier comme un seul bloc
    if not paper_start_pages:
        logger.warning("Could not programmatically detect paper boundaries. Treating entire PDF as a single paper.")
        paper_start_pages = [0]
        
    # 3. Création physique des segments PDF découpés
    output_dir.mkdir(parents=True, exist_ok=True)
    split_pdf_paths = []
    total_pages = len(doc)
    
    for i, start_page in enumerate(paper_start_pages):
        end_page = paper_start_pages[i + 1] - 1 if i + 1 < len(paper_start_pages) else total_pages - 1
        
        # Filtre de sécurité : On ignore les segments de moins de 2 pages (pages d'index, préfaces)
        if (end_page - start_page + 1) < 2 and len(paper_start_pages) > 1:
            continue
            
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
        
        out_path = output_dir / f"paper_segment_{start_page + 1}_{end_page + 1}.pdf"
        new_doc.save(str(out_path))
        new_doc.close()
        
        split_pdf_paths.append(out_path)
        
    doc.close()
    logger.info(f"Programmatic split completed. Generated {len(split_pdf_paths)} paper segments.")
    return split_pdf_paths