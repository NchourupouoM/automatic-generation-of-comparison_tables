from evals.scoring import score_document, _first_table


GOLDEN = {
    "domain": "protein-classification",
    "research_problem": "Classify proteins into folds",
    "rows": [
        {
            "paper_title": "An elegant solution to protein classification",
            "authors": ["Ashok Palaniappan"],
            "is_proposed_method": True,
            "properties": {"accuracy": "0.92", "dataset": "SCOP"},
        },
        {
            "paper_title": "Prior fold recognition method",
            "authors": ["Someone Else"],
            "is_proposed_method": False,
            "properties": {"accuracy": "0.85", "dataset": "SCOP"},
        },
    ],
}


def test_perfect_match_scores_one():
    report = score_document(GOLDEN, GOLDEN)
    assert report["field_f1"] == 1.0
    assert report["row_recall"] == 1.0
    assert report["matched_rows"] == 2


def test_missing_row_lowers_recall():
    pred = {"domain": "protein-classification", "rows": [GOLDEN["rows"][0]]}
    report = score_document(GOLDEN, pred)
    assert report["row_recall"] == 0.5
    assert report["field_recall"] < 1.0


def test_wrong_value_counts_as_miss():
    pred = {
        "rows": [
            {**GOLDEN["rows"][0], "properties": {"accuracy": "0.10", "dataset": "SCOP"}},
            GOLDEN["rows"][1],
        ]
    }
    report = score_document(GOLDEN, pred)
    assert report["field_f1"] < 1.0


def test_fuzzy_title_still_matches():
    pred = {
        "rows": [
            {**GOLDEN["rows"][0], "paper_title": "An Elegant Solution To Protein Classification."},
            GOLDEN["rows"][1],
        ]
    }
    report = score_document(GOLDEN, pred)
    assert report["matched_rows"] == 2


def test_extra_predicted_property_is_false_positive():
    pred = {
        "rows": [
            {**GOLDEN["rows"][0], "properties": {"accuracy": "0.92", "dataset": "SCOP", "junk": "x"}},
            GOLDEN["rows"][1],
        ]
    }
    report = score_document(GOLDEN, pred)
    assert report["field_precision"] < 1.0


def test_accepts_consolidated_envelope():
    envelope = {"consolidated_result": {"tables": [GOLDEN]}}
    assert _first_table(envelope)["domain"] == "protein-classification"
    report = score_document(GOLDEN, envelope)
    assert report["field_f1"] == 1.0


def test_flattened_api_rows_are_scored():
    # API rows put domain props under `domain_specific_properties` and flatten bib fields.
    pred = {
        "rows": [
            {
                "paper_title": GOLDEN["rows"][0]["paper_title"],
                "authors": ["Ashok Palaniappan"],
                "is_proposed_method": True,
                "domain_specific_properties": {"accuracy": "0.92", "dataset": "SCOP"},
            },
            {
                "paper_title": GOLDEN["rows"][1]["paper_title"],
                "is_proposed_method": False,
                "domain_specific_properties": {"accuracy": "0.85", "dataset": "SCOP"},
            },
        ]
    }
    report = score_document(GOLDEN, pred)
    assert report["field_f1"] == 1.0
