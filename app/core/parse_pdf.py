import logging
import re
from pathlib import Path
import pymupdf4llm
import fitz  # PyMuPDF
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Proceeding boundary detection helpers
# ---------------------------------------------------------------------------
# A real paper is at least this many pages; candidate starts closer than this are
# treated as the SAME paper (prevents cutting one paper into several).
MIN_PAPER_PAGES = 2
# Typical minimum spacing between whole papers in a proceeding. A smaller median
# spacing across many outline entries indicates subsections of one paper, not
# separate papers.
_MIN_PAPER_GAP = 4

# Section headings that must never be mistaken for the start of a new paper.
_SECTION_LEXICON = {
    "abstract", "summary", "introduction", "background", "background and preamble",
    "preamble", "related work", "preliminaries", "notation", "motivation",
    "methods", "method", "materials and methods", "models and methods",
    "experimental setup", "experiments", "evaluation", "results",
    "results and discussion", "discussion", "discussion and conclusion",
    "discussion and conclusions", "conclusion", "conclusions", "future work",
    "acknowledgment", "acknowledgments", "acknowledgement", "acknowledgements",
    "references", "bibliography", "appendix", "appendices", "competing interests",
    "author contributions", "funding", "start of article",
}
# Titles beginning with these words are structural, not paper titles.
_SECTIONISH_PREFIX = re.compile(
    r"^\s*(figure|fig\.?|table|tab\.?|appendix|section|chapter|part|"
    r"supplementary|supplemental|competing|acknowledg|references|bibliography)\b",
    re.IGNORECASE,
)
# Numbered section headings, e.g. "1. Introduction", "2 Methods", "3.2 Results".
_NUMBERED_SECTION = re.compile(r"^\s*\d+(\.\d+)*\.?\s+\S")
_REFERENCES = re.compile(r"\breferences\b|\bbibliography\b", re.IGNORECASE)


def _is_section_title(title: str) -> bool:
    """True when an outline entry names a section/figure rather than a paper."""
    normalized = " ".join((title or "").strip().lower().split())
    if not normalized:
        return True
    if _NUMBERED_SECTION.match(title or ""):
        return True
    if _SECTIONISH_PREFIX.match(title or ""):
        return True
    return normalized in _SECTION_LEXICON


def _begins_with_front_matter(page: "fitz.Page") -> bool:
    """
    Strict front-page signal: an 'abstract'/'summary' heading appears very near
    the top of the page. Deliberately narrow (first 600 chars) so an 'abstract'
    mention buried in body text on an interior page does not trigger a false
    split. arXiv identifiers are intentionally NOT used — they are stamped on
    every page margin and would over-split every document.
    """
    head = page.get_text("text")[:600].lower()
    return "abstract" in head or "summary" in head


def _has_references(page: "fitz.Page") -> bool:
    """True when a page contains a References/Bibliography section (a paper ending)."""
    return bool(_REFERENCES.search(page.get_text("text")))


def _enforce_min_gap(starts: List[int], min_gap: int) -> List[int]:
    """Collapses start pages closer than min_gap (keeps the earlier one), so a
    single paper's internal markers can never become multiple papers."""
    kept: List[int] = []
    for page in sorted(set(starts)):
        if not kept or page - kept[-1] >= min_gap:
            kept.append(page)
    return kept


def _starts_from_bookmarks(doc: "fitz.Document") -> Optional[List[int]]:
    """
    Derives paper start pages from the PDF outline, but only when the outline
    genuinely looks like a proceeding's per-paper table of contents. Returns
    None when the outline is really a single paper's section list.
    """
    toc = doc.get_toc()
    level1 = [(title, page) for level, title, page in toc if level == 1 and page >= 1]
    if len(level1) < 2:
        return None

    # If most level-1 entries are section names, this is one paper's TOC, not a
    # proceeding — refuse to split on it.
    section_like = sum(1 for title, _ in level1 if _is_section_title(title))
    if section_like / len(level1) >= 0.5:
        return None

    paper_pages = [page - 1 for title, page in level1 if not _is_section_title(title)]
    starts = _enforce_min_gap(paper_pages, MIN_PAPER_PAGES)
    if len(starts) < 2:
        return None

    # Distinguish a proceeding (papers spaced several pages apart) from a single
    # long paper/review whose outline lists many closely-spaced descriptive
    # subsections. Real papers run several pages; a small median gap means the
    # outline is subsections, not papers -> don't trust it for splitting.
    if len(starts) >= 3:
        gaps = sorted(starts[i + 1] - starts[i] for i in range(len(starts) - 1))
        median_gap = gaps[len(gaps) // 2]
        if median_gap < _MIN_PAPER_GAP:
            return None

    if starts[0] != 0:
        starts = _enforce_min_gap([0] + starts, 1)
    return starts


def _starts_from_structure(doc: "fitz.Document") -> List[int]:
    """
    High-precision fallback for documents without a usable outline. A new paper
    is recognised only when a page BOTH begins with front matter (abstract/summary
    heading at the very top) AND the previous page ends the prior paper (contains a
    References/Bibliography section). Requiring both signals means a single paper's
    internal 'abstract' mentions or section headings can never trigger a split.

    This is intentionally low-recall: when boundaries can't be proven it returns
    [0] (whole document), leaving multi-paper detection for the content-aware LLM
    segmenter. Over-splitting corrupts extraction; under-splitting does not.
    """
    starts = [0]
    for page_num in range(1, len(doc)):
        if page_num - starts[-1] < MIN_PAPER_PAGES:
            continue
        if _begins_with_front_matter(doc[page_num]) and _has_references(doc[page_num - 1]):
            starts.append(page_num)
    return starts


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

def detect_paper_start_pages(doc: "fitz.Document") -> List[int]:
    """
    Returns the 0-indexed start page of each paper in a (possibly multi-paper)
    document. Prefers a validated PDF outline; otherwise falls back to
    structural front-page detection. Always returns at least [0].

    The detection is deliberately conservative: it will never break a single
    paper into several (section headings and closely-spaced markers are merged),
    trading the occasional missed split for never corrupting a paper's text by
    cutting it in two.
    """
    starts = _starts_from_bookmarks(doc)
    if starts:
        logger.info(f"Proceeding split: using validated outline -> {len(starts)} paper(s).")
        return starts

    starts = _starts_from_structure(doc)
    if len(starts) > 1:
        logger.info(f"Proceeding split: using structural front-page signals -> {len(starts)} paper(s).")
    else:
        logger.info("Proceeding split: no reliable boundaries found; treating as a single paper.")
    return starts


def split_proceeding_pdf(pdf_path: str, output_dir: Path) -> List[Path]:
    """
    Splits a multi-paper proceeding PDF into individual paper PDFs at detected
    paper boundaries. Deterministic, offline, and LLM-free.
    """
    doc = fitz.open(pdf_path)
    paper_start_pages = detect_paper_start_pages(doc)

    output_dir.mkdir(parents=True, exist_ok=True)
    split_pdf_paths: List[Path] = []
    total_pages = len(doc)

    for i, start_page in enumerate(paper_start_pages):
        end_page = paper_start_pages[i + 1] - 1 if i + 1 < len(paper_start_pages) else total_pages - 1

        # Skip degenerate <2-page fragments only when we actually split into several
        # (a genuinely short single-paper document must still be returned whole).
        if (end_page - start_page + 1) < MIN_PAPER_PAGES and len(paper_start_pages) > 1:
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