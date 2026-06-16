# app/core/domains_registry.py
from pathlib import Path
from typing import Dict, Type
from pydantic import BaseModel

# Import des schémas de validation
from app.domains.infectious_disease.schemas import InfectiousDiseaseComparisonTable
from app.core.schemas import ComparisonTable


class DomainConfig:
    """ Holds the dynamic configurations for a specific extraction domain. """
    def __init__(self, schema_class: Type[BaseModel], skill_path: Path):
        self.schema_class = schema_class
        self.skill_path = skill_path


# Enregistrement des configurations par domaine
DOMAINS_REGISTRY: Dict[str, DomainConfig] = {
    "infectious-disease": DomainConfig(
        schema_class=InfectiousDiseaseComparisonTable,
        skill_path=Path("skills/infectious-disease-extraction")
    ),
    "default": DomainConfig(
        schema_class=ComparisonTable,
        skill_path=Path("skills/academicextraction")
    )
}