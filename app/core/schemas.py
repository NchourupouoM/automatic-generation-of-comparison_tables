from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CustomProperty(BaseModel):
    """
    Represents a single custom comparison axis as a key-value pair.
    This replaces dynamic Dict[str, Any] to guarantee strict JSON Schema compliance.
    """
    property_name: str = Field(
        ..., 
        description="The clean name of the comparative metric or feature (e.g., 'accuracy', 'dataset_size', 'latency')."
    )
    property_value: str = Field(
        ..., 
        description="The exact extracted value corresponding to the property (e.g., '92.4%', '50k steps', '120ms')."
    )


class EvidenceItem(BaseModel):
    """
    Grounds a single extracted value in the source text: the field it supports
    and a short verbatim quote copied from the paper. Enables one-click human
    verification of every cell in the comparison table.
    """
    field: str = Field(
        ...,
        description="The name of the field this quote supports (e.g. 'authors', 'accuracy', 'publication_year')."
    )
    quote: str = Field(
        ...,
        description="A short, VERBATIM excerpt (max ~240 chars) copied exactly from the paper that supports the extracted value."
    )


class ComparisonRow(BaseModel):
    """
    Represents a single row in the comparative matrix, capturing bibliographic
    and domain-specific semantic properties of a research paper.
    """
    
    proceeding_title: Optional[str] = Field(
        default=None,
        description="The title of the conference proceeding or book volume where the paper was published, if applicable."
    )
    
    paper_title: str = Field(
        ...,
        description="The full, official title of the research paper."
    )
    
    authors: List[str] = Field(
        default_factory=list,
        description="A list of authors who wrote the paper (e.g., ['John Doe', 'Alice Smith'])."
    )
    
    publication_month: Optional[str] = Field(
        default=None,
        description="The month of publication (e.g., 'June' or '06')."
    )
    
    publication_year: Optional[int] = Field(
        default=None,
        description="The calendar year of publication (e.g., 2024)."
    )
    
    venue: Optional[str] = Field(
        default=None,
        description="The specific venue or platform where the paper was published (e.g., 'CVPR', 'ArXiv', 'Nature')."
    )
    
    research_field: Optional[str] = Field(
        default=None,
        description="The primary academic discipline or domain of research (e.g., 'Computer Vision', 'NLP', 'Bioinformatics')."
    )
    
    doi: Optional[str] = Field(
        default=None,
        description="The Digital Object Identifier (DOI) of the paper."
    )
    
    url: Optional[str] = Field(
        default=None,
        description="The direct online URL link to access the publication."
    )
    
    research_problem: str = Field(
        ...,
        description="The exact scientific or technical problem the paper addresses."
    )
    
    research_method: Optional[str] = Field(
        default=None,
        description="The primary research methodology employed by the authors."
    )
    
    # Utilisation de la liste fortement typée pour satisfaire les contraintes d'OpenAI
    domain_specific_properties: List[CustomProperty] = Field(
        default_factory=list,
        description="A list of custom domain-specific semantic properties (Phi) extracted for comparison."
    )

    evidence: List[EvidenceItem] = Field(
        default_factory=list,
        description="Grounding: for each important extracted value, a {field, quote} pair whose quote is copied verbatim from the paper."
    )


class ComparisonTable(BaseModel):
    """
    Represents a full comparative matrix aligned around a single unique research problem.
    """
    research_problem: str = Field(
        ...,
        description="The shared research problem that groups all the comparative rows in this table together."
    )
    rows: List[ComparisonRow] = Field(
        default_factory=list,
        description="The collection of comparison entries (rows) including the proposed contribution and its corresponding baseline methods."
    )


# ---------------------------------------------------------------------------
# Schémas de Sortie API (Formatés proprement pour l'utilisateur final)
# ---------------------------------------------------------------------------
class ConsolidatedComparisonRow(BaseModel):
    """
    Consolidated row for API consumers. Converts the list of properties 
    back into a clean dictionary.
    """
    proceeding_title: Optional[str]
    paper_title: str
    authors: List[str]
    publication_month: Optional[str]
    publication_year: Optional[int]
    venue: Optional[str]
    research_field: Optional[str]
    doi: Optional[str]
    url: Optional[str]
    research_problem: str
    research_method: Optional[str]
    domain_specific_properties: Dict[str, Any] 


class ConsolidatedComparisonTable(BaseModel):
    research_problem: str
    rows: List[ConsolidatedComparisonRow]


class ComparativeResult(BaseModel):
    """
    Final consolidated output Schema returned by the API.
    """
    tables: List[ConsolidatedComparisonTable] = Field(
        default_factory=list,
        description="A list containing one or more comparison tables formatted with clean key-value property dictionaries."
    )
