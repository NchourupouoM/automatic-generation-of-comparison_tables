from typing import get_args

from app.core.dynamic_loader import map_metadata_type_to_python


def test_known_type_mappings():
    assert map_metadata_type_to_python("int") is not None
    # list_str maps to a concrete List[str], not Optional
    assert map_metadata_type_to_python("list_str") == __import__("typing").List[str]


def test_unknown_type_defaults_to_optional_str():
    mapped = map_metadata_type_to_python("weird_unseen_type")
    assert str in get_args(mapped)


def test_case_insensitive():
    assert map_metadata_type_to_python("INT") == map_metadata_type_to_python("int")
