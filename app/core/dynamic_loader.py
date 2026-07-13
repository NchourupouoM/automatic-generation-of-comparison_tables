# app/core/dynamic_loader.py
import logging
from typing import List, Dict, Any, Type, Optional
from pydantic import BaseModel, create_model, Field
from sqlalchemy.orm import Session
import re
from app.core.models import TemplateModel

logger = logging.getLogger(__name__)


def map_metadata_type_to_python(type_str: str) -> Any:
    """
    Maps string-based type definitions from the database 
    to physical Python types, wrapping them as Optional to avoid parsing crashes.
    """
    mapping = {
        "str": Optional[str],
        "int": Optional[int],
        "list_str": List[str],
        "bool": Optional[bool]
    }
    # Par défaut, nous retournons un type optionnel String si le type est inconnu
    return mapping.get(type_str.lower().strip(), Optional[str])


def compile_dynamic_table_model(template_id: str, db: Session) -> Type[BaseModel]:
    """
    Loads a template definition from the PostgreSQL 'templates' table
    and dynamically compiles a validated wrapping Pydantic Comparison Table model 
    compatible with LLM structured output.
    """
    # 1. Recherche du gabarit enregistré dans PostgreSQL
    template_record = db.query(TemplateModel).filter(TemplateModel.id == template_id).first()
    if not template_record:
        logger.error(f"Template with ID '{template_id}' was not found in the database registry.")
        raise ValueError(f"Template ID '{template_id}' not found in persistent Template Registry.")

    schema_meta = template_record.schema_json
    fields_meta = schema_meta.get("fields", [])

    # 2. Définition des coordonnées d'identification de base de chaque ligne
    dynamic_row_fields = {
        "paper_title": (str, Field(..., description="The official title of the research paper.")),
        "authors": (List[str], Field(default_factory=list, description="List of paper authors.")),
        "publication_month": (Optional[str], Field(default=None, description="Month of publication.")),
        "publication_year": (Optional[int], Field(default=None, description="Calendar year of publication.")),
        "venue": (Optional[str], Field(default=None, description="Venue or journal of publication.")),
        "research_field": (Optional[str], Field(default=None, description="The primary academic discipline.")),
        "doi": (Optional[str], Field(default=None, description="The Digital Object Identifier (DOI).")),
        "url": (Optional[str], Field(default=None, description="The direct online URL link.")),
        "research_problem": (str, Field(..., description="The exact scientific problem addressed.")),
        "research_method": (Optional[str], Field(default=None, description="The primary research methodology used.")),
    }

    # 3. Injection des caractéristiques sémantiques spécifiques au domaine (La liste Phi)
    for field in fields_meta:
        field_name = field["name"].strip().lower().replace(" ", "_")
        field_type = map_metadata_type_to_python(field.get("type", "str"))
        field_desc = field.get("description", "")
        
        dynamic_row_fields[field_name] = (
            field_type, 
            Field(default=None, description=field_desc)
        )

    # ---------------------------------------------------------------------------
    # CORRECTION : Nettoyage strict (Sanitization) pour satisfaire les APIs de LLM
    # ---------------------------------------------------------------------------
    # On élimine tous les caractères non-alphanumériques (parenthèses, ponctuations...)
    raw_suffix = template_id.replace("-", " ").title().replace(" ", "")
    clean_suffix = re.sub(r'[^a-zA-Z0-9_]', '', raw_suffix)
    
    # Barrière de sécurité : Troncature à 80 caractères pour éviter de dépasser la limite de 128
    class_name_suffix = clean_suffix[:80] if len(clean_suffix) > 80 else clean_suffix

    # 4. Compilation de la classe de ligne
    DynamicRowClass = create_model(
        f"Dynamic{class_name_suffix}Row",
        **dynamic_row_fields
    )

    # 5. Compilation de l'enveloppe finale du tableau comparatif
    DynamicTableClass = create_model(
        f"Dynamic{class_name_suffix}Table",
        research_problem=(str, Field(..., description="The shared research problem of this custom table.")),
        rows=(List[DynamicRowClass], Field(..., description="The list of comparative rows including the proposed study and its compared baseline/prior works."))
    )

    logger.info(f"Successfully compiled Pydantic dynamic comparison model: '{DynamicTableClass.__name__}'")
    return DynamicTableClass


def save_new_template_to_db(
    template_id: str, 
    name: str, 
    properties: List[Dict[str, str]], 
    db: Session
) -> TemplateModel:
    """
    Saves a validated custom domain schema metadata to the PostgreSQL 'templates' registry.
    Properties format example: [{'name': 'causes', 'description': 'Primary etiology', 'type': 'str'}]
    """
    schema_payload = {
        "domain_key": template_id,
        "domain_name": name,
        "fields": properties
    }

    # Vérification d'existence préalable pour mise à jour (Upsert pattern)
    existing_template = db.query(TemplateModel).filter(TemplateModel.id == template_id).first()
    if existing_template:
        logger.info(f"Updating existing template schema for: '{template_id}'")
        existing_template.name = name
        existing_template.schema_json = schema_payload
        db.commit()
        db.refresh(existing_template)
        return existing_template

    logger.info(f"Persisting new template schema into database for: '{template_id}'")
    new_template = TemplateModel(
        id=template_id,
        name=name,
        schema_json=schema_payload
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    return new_template