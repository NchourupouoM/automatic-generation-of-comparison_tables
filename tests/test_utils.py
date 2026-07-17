from app.core.utils import slugify_domain


def test_slugify_basic():
    assert slugify_domain("Malaria-Induced Bone Loss") == "malaria-induced-bone-loss"


def test_slugify_underscores_and_case():
    assert slugify_domain("Colorectal_Cancer Dietetics") == "colorectal-cancer-dietetics"


def test_slugify_strips_punctuation():
    assert slugify_domain("Protein (Structure) Prediction!") == "protein-structure-prediction"


def test_slugify_collapses_and_trims_dashes():
    assert slugify_domain("  --Deep  Learning--  ") == "deep-learning"


def test_slugify_empty():
    assert slugify_domain("   ") == ""
