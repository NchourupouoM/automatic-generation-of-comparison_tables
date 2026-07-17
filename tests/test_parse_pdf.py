from pathlib import Path

import pytest

from app.core.parse_pdf import extract_pdf_to_markdown, split_proceeding_pdf


def test_extract_markdown_returns_text(sample_pdf: Path):
    md = extract_pdf_to_markdown(str(sample_pdf))
    assert isinstance(md, str)
    assert len(md.strip()) > 100


def test_extract_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        extract_pdf_to_markdown("/no/such/file.pdf")


def test_split_single_paper_yields_at_least_one_segment(sample_pdf: Path, tmp_path: Path):
    # A single arXiv paper has no per-paper bookmarks, so the splitter should
    # fall back to treating it as one segment rather than crashing.
    segments = split_proceeding_pdf(str(sample_pdf), tmp_path / "out")
    assert len(segments) >= 1
    assert all(p.exists() for p in segments)
