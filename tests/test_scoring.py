"""Unit tests for the pure scorer. No app import, no DB, no LLM — these run
anywhere (CI included) and pin down what the accuracy numbers actually mean."""
from tests.eval import scoring


def _row(title, proposed=False, authors=None, props=None, **biblio):
    return {
        "paper_title": title,
        "is_proposed_method": proposed,
        "authors": authors or [],
        "domain_specific_properties": props or {},
        **biblio,
    }


def _result(rows, problem="p"):
    return {"tables": [{"research_problem": problem, "rows": rows}]}


def test_perfect_match_scores_one():
    rows = [
        _row("Our Method", proposed=True, authors=["A", "B"],
             publication_year=2023, props={"acc": "95%"}),
        _row("Baseline X", authors=["C"], publication_year=2020, props={"acc": "88%"}),
    ]
    gold = _result(rows)
    pred = _result([dict(r) for r in rows])  # identical
    s = scoring.score_example(gold, pred)
    out = s.summary()
    assert out["row_f1"] == 1.0
    assert out["cell_f1"] == 1.0
    assert out["leakage_violations"] == 0
    assert out["proposed_identified"] == "1/1"


def test_missing_value_hurts_recall():
    gold = _result([_row("Our Method", proposed=True, props={"acc": "95%", "auc": "0.9"})])
    pred = _result([_row("Our Method", proposed=True, props={"acc": "95%"})])  # dropped auc
    s = scoring.score_example(gold, pred).summary()
    assert s["cell_recall"] < 1.0
    assert s["cell_precision"] == 1.0   # nothing wrong was produced


def test_wrong_value_hurts_precision_and_recall():
    gold = _result([_row("Our Method", proposed=True, props={"acc": "95%"})])
    pred = _result([_row("Our Method", proposed=True, props={"acc": "50%"})])  # wrong
    s = scoring.score_example(gold, pred).summary()
    assert s["cell_precision"] == 0.0
    assert s["cell_recall"] == 0.0


def test_missing_row_hurts_row_recall():
    gold = _result([
        _row("Our Method", proposed=True, props={"acc": "95%"}),
        _row("Baseline X", props={"acc": "88%"}),
    ])
    pred = _result([_row("Our Method", proposed=True, props={"acc": "95%"})])  # baseline lost
    s = scoring.score_example(gold, pred).summary()
    assert s["row_recall"] == 0.5
    assert s["row_precision"] == 1.0


def test_leakage_violation_detected():
    # Baseline row copied the proposed paper's authors — a firewall violation.
    pred = _result([
        _row("Our Method", proposed=True, authors=["Jane Doe", "Alan Smith"]),
        _row("Baseline X", authors=["Jane Doe", "Alan Smith"]),
    ])
    gold = _result([
        _row("Our Method", proposed=True, authors=["Jane Doe", "Alan Smith"]),
        _row("Baseline X", authors=["Other Person"]),
    ])
    s = scoring.score_example(gold, pred).summary()
    assert s["leakage_violations"] == 1


def test_normalisation_treats_na_as_empty():
    gold = _result([_row("Our Method", proposed=True, props={"acc": "95%"})])
    # "N/A" should count as no value, so nothing is scored wrong or extra here.
    pred = _result([_row("Our Method", proposed=True,
                         props={"acc": "95%", "auc": "N/A"})])
    s = scoring.score_example(gold, pred).summary()
    assert s["cell_precision"] == 1.0
    assert s["cell_recall"] == 1.0


def test_author_order_does_not_matter():
    gold = _result([_row("M", proposed=True, authors=["Alice", "Bob"])])
    pred = _result([_row("M", proposed=True, authors=["Bob", "Alice"])])
    s = scoring.score_example(gold, pred).summary()
    assert s["cell_f1"] == 1.0


def test_aggregate_micro_averages():
    a = scoring.score_example(
        _result([_row("M", proposed=True, props={"x": "1"})]),
        _result([_row("M", proposed=True, props={"x": "1"})]))
    b = scoring.score_example(
        _result([_row("N", proposed=True, props={"y": "2"})]),
        _result([_row("N", proposed=True, props={"y": "9"})]))  # wrong
    total = scoring.aggregate([a, b]).summary()
    assert total["examples"] == 2
    assert 0.0 < total["cell_f1"] < 1.0


def test_fuzzy_title_still_matches_row():
    gold = _result([_row("A Novel Method for Malaria Detection", proposed=True, props={"acc": "9"})])
    pred = _result([_row("Novel Method for Malaria Detection", proposed=True, props={"acc": "9"})])
    s = scoring.score_example(gold, pred).summary()
    assert s["row_f1"] == 1.0
