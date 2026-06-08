import logging
from pathlib import Path
import pymupdf4llm

# Configuration basique des logs
logger = logging.getLogger(__name__)


def run_extraction(pdf_path: str) -> str:
    """Prend un chemin de fichier PDF, extrait son contenu de manière structurée

    et renvoie une chaîne au format Markdown propre.
    """
    path_obj = Path(pdf_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Le fichier PDF à l'emplacement '{pdf_path}' est introuvable.")

    try:
        logger.info(f"Début de l'extraction de : {pdf_path}")

        # Utilisation de pymupdf4llm pour la conversion native Markdown
        # Cette bibliothèque gère nativement l'analyse de mise en page (Layout) sans GPU
        markdown_text = pymupdf4llm.to_markdown(str(path_obj))

        logger.info(f"Extraction terminée avec succès pour {pdf_path}.")
        return markdown_text

    except Exception as e:
        logger.error(
            f"Erreur lors de l'extraction du document PDF {pdf_path}: {str(e)}"
        )
        raise RuntimeError(
            f"Échec de l'extraction structurelle du PDF : {str(e)}"
        )