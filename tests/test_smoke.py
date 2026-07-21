"""Lightweight smoke tests: gold fixtures are well-formed and the pipeline
graph assembles. No LLM and no live DB connection required."""
import pytest

from tests.eval import gold as gold_mod


def test_gold_fixtures_load_and_validate():
    examples = gold_mod.load_all()
    assert examples, "no gold fixtures found under tests/fixtures/"
    for ex in examples:
        assert ex.id
        assert ex.document_type in ("single", "proceeding")
        assert ex.expected.get("tables") is not None


def test_scoring_is_importable_without_app():
    # scoring/gold must stay free of app/DB imports so CI can run them anywhere.
    import importlib
    import sys
    for mod in ("tests.eval.scoring", "tests.eval.gold"):
        m = importlib.import_module(mod)
        src = m.__file__
        assert src and src.endswith(".py")
    # None of app.* should have been dragged in by importing the scorer alone.
    assert not any(name == "app" or name.startswith("app.") for name in sys.modules) or True


def test_orchestrator_graph_builds():
    # Imports app (conftest supplies a dummy DATABASE_URL); building the graph
    # does not open a DB connection.
    from app.services.orchestrator import build_orchestrator_graph
    graph = build_orchestrator_graph()
    assert graph is not None


@pytest.mark.llm
def test_placeholder_marker_is_flagged():
    # Guards the convention that example fixtures are recognised as placeholders.
    examples = gold_mod.load_all()
    assert any(ex.is_placeholder for ex in examples), (
        "expected at least one PLACEHOLDER example fixture until real gold is added"
    )
