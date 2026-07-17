from evals.invariants import check_table_invariants


def _valid_table():
    return {
        "rows": [
            {"paper_title": "Our method", "authors": ["A. One"], "is_proposed_method": True,
             "properties": {"accuracy": "0.9"}},
            {"paper_title": "A baseline", "authors": ["B. Two"], "is_proposed_method": False,
             "properties": {"accuracy": "0.8"}},
        ]
    }


def test_valid_table_has_no_violations():
    assert check_table_invariants(_valid_table()) == []


def test_empty_table_flagged():
    assert "table has no rows" in check_table_invariants({"rows": []})


def test_missing_proposed_flagged():
    table = _valid_table()
    table["rows"][0]["is_proposed_method"] = False
    assert any("proposed method" in v for v in check_table_invariants(table))


def test_two_proposed_flagged():
    table = _valid_table()
    table["rows"][1]["is_proposed_method"] = True
    assert any("proposed method" in v for v in check_table_invariants(table))


def test_author_leakage_detected():
    table = _valid_table()
    table["rows"][1]["authors"] = ["A. One"]  # copied from the primary paper
    assert any("inherited the primary paper's authors" in v for v in check_table_invariants(table))


def test_empty_title_flagged():
    table = _valid_table()
    table["rows"][1]["paper_title"] = "  "
    assert any("empty paper_title" in v for v in check_table_invariants(table))


def test_malformed_doi_flagged():
    table = _valid_table()
    table["rows"][0]["doi"] = "not-a-doi"
    assert any("malformed DOI" in v for v in check_table_invariants(table))


def test_valid_doi_passes():
    table = _valid_table()
    table["rows"][0]["doi"] = "10.1038/nature12373"
    assert check_table_invariants(table) == []
