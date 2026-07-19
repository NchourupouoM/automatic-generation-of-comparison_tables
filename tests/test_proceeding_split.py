"""
Tests for proceeding boundary detection.

The cardinal rule (from the field): a single paper's text must NEVER be split
across two segments. These tests encode both directions — never over-split a
single paper, and correctly split a genuine multi-paper proceeding — using
synthetic PDFs plus a regression sweep over the real corpus.
"""
import fitz
import pytest

from app.core.parse_pdf import (
    _enforce_min_gap,
    _is_section_title,
    detect_paper_start_pages,
)


def _make_pdf(tmp_path, name, n_pages, toc=None, page_text=None):
    """Builds a small PDF with n_pages, an optional outline, and optional
    per-page text (dict {page_index: text})."""
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=612, height=792)
        text = (page_text or {}).get(i, f"Body content of page {i}.")
        page.insert_text((72, 72), text)
    if toc:
        doc.set_toc(toc)
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


# --- unit helpers --------------------------------------------------------
@pytest.mark.parametrize("title", [
    "Introduction", "1. Introduction", "2 Methods", "3.2 Results",
    "Materials and Methods", "References", "Bibliography", "Figure 3",
    "Appendix A", "Conclusions", "Acknowledgments", "  ",
])
def test_section_titles_detected(title):
    assert _is_section_title(title) is True


@pytest.mark.parametrize("title", [
    "Deep learning for protein folding prediction",
    "A sparse model for cancer survival analysis",
    "On the thermodynamics of RNA secondary structure",
])
def test_paper_titles_not_sections(title):
    assert _is_section_title(title) is False


def test_enforce_min_gap_collapses_close_starts():
    assert _enforce_min_gap([0, 1, 2, 8, 9, 20], 2) == [0, 2, 8, 20]
    assert _enforce_min_gap([5, 0, 3], 4) == [0, 5]


# --- never over-split a single paper -------------------------------------
def test_section_outline_is_not_split(tmp_path):
    # A single paper whose level-1 outline is its section list must stay whole.
    toc = [[1, "Introduction", 1], [1, "Methods", 3], [1, "Results", 5], [1, "References", 7]]
    pdf = _make_pdf(tmp_path, "sections.pdf", 8, toc=toc)
    assert detect_paper_start_pages(fitz.open(pdf)) == [0]


def test_granular_descriptive_subsections_not_split(tmp_path):
    # Descriptive (non-lexicon) subsection titles, closely spaced -> one paper.
    toc = [[1, f"Some detailed subsection about topic {i}", 1 + 2 * i] for i in range(6)]
    pdf = _make_pdf(tmp_path, "review.pdf", 13, toc=toc)
    assert detect_paper_start_pages(fitz.open(pdf)) == [0]


def test_no_outline_no_signal_is_single(tmp_path):
    pdf = _make_pdf(tmp_path, "plain.pdf", 6)
    assert detect_paper_start_pages(fitz.open(pdf)) == [0]


def test_structural_abstract_without_prior_references_does_not_split(tmp_path):
    # 'abstract' on an interior page but no references before it -> not a boundary.
    pdf = _make_pdf(tmp_path, "abs_only.pdf", 6, page_text={3: "Abstract of a subsection idea"})
    assert detect_paper_start_pages(fitz.open(pdf)) == [0]


# --- correctly split a genuine proceeding --------------------------------
def test_outlined_proceeding_is_split_at_boundaries(tmp_path):
    # 3 papers, 5 pages each, outline entries are paper titles at pages 1/6/11.
    toc = [
        [1, "A study of alpha effects in systems", 1],
        [1, "Understanding beta mechanisms in depth", 6],
        [1, "Gamma dynamics and their consequences", 11],
    ]
    pdf = _make_pdf(tmp_path, "proceeding.pdf", 15, toc=toc)
    assert detect_paper_start_pages(fitz.open(pdf)) == [0, 5, 10]


def test_structural_split_with_frontmatter_and_prior_references(tmp_path):
    # No outline; page 2 has references, page 3 begins with an Abstract -> boundary.
    text = {2: "... concluding remarks.\nReferences\n[1] ...", 3: "Abstract\nWe present a new method."}
    pdf = _make_pdf(tmp_path, "struct.pdf", 6, page_text=text)
    assert detect_paper_start_pages(fitz.open(pdf)) == [0, 3]


# --- regression sweep over the real corpus (all single papers) -----------
_PDFS = sorted((__import__("pathlib").Path(__file__).parent.parent / "evals" / "pdfs").glob("*.pdf"))


@pytest.mark.parametrize("pdf_path", _PDFS, ids=[p.stem for p in _PDFS])
def test_real_single_papers_are_never_over_split(pdf_path):
    doc = fitz.open(str(pdf_path))
    starts = detect_paper_start_pages(doc)
    doc.close()
    assert starts == [0], f"{pdf_path.name} was over-split into starts {starts}"
