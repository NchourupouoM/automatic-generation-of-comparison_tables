"""Unit tests for cross-paper entity resolution keys and the grounding schema.
Offline and deterministic — no DB, no LLM."""
from app.core.entities import canonical_key
from app.core.schemas import ComparisonRow, CustomProperty, EvidenceItem


# ---- canonical_key ----

def test_title_slug_is_case_and_punct_insensitive():
    a = canonical_key("An Elegant Solution to Protein Classification!", None)
    b = canonical_key("an elegant solution to protein classification", None)
    assert a == b
    assert a.startswith("title:")


def test_stopwords_do_not_split_identity():
    a = canonical_key("A Study of Malaria Detection", None)
    b = canonical_key("Study of Malaria Detection", None)
    assert a == b


def test_doi_wins_over_title():
    k = canonical_key("Totally Different Title", "10.1000/xyz")
    assert k == "doi:10.1000/xyz"


def test_doi_url_forms_normalize_equal():
    assert canonical_key("t", "https://doi.org/10.1/AbC") == canonical_key("t", "10.1/abc")
    assert canonical_key("t", "doi:10.1/abc") == "doi:10.1/abc"


def test_two_different_papers_get_different_keys():
    assert canonical_key("Malaria Detection Nets", None) != canonical_key("Bone Loss Cohort", None)


def test_untitled_paper_has_no_key():
    assert canonical_key("", None) is None
    assert canonical_key(None, None) is None


# ---- grounding schema ----

def test_comparison_row_accepts_evidence():
    row = ComparisonRow(
        paper_title="Our Method",
        research_problem="X",
        domain_specific_properties=[CustomProperty(property_name="accuracy", property_value="95%")],
        evidence=[EvidenceItem(field="accuracy", quote="we achieve 95% accuracy")],
    )
    assert row.evidence[0].field == "accuracy"
    dumped = row.model_dump()
    assert dumped["evidence"] == [{"field": "accuracy", "quote": "we achieve 95% accuracy"}]


def test_evidence_defaults_empty():
    row = ComparisonRow(paper_title="P", research_problem="X")
    assert row.evidence == []
