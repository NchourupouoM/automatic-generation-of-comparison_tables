from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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
        description="The month of publication (e.g., 'June', 'December')."
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
        description="The exact scientific or technical problem the paper addresses. This is used as the key for clustering and comparing papers."
    )
    
    research_method: Optional[str] = Field(
        default=None,
        description="The primary research methodology employed by the authors (e.g., 'empirical evaluation', 'simulation', 'theoretical proof', 'extraction')."
    )
    
    domain_specific_properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="A dictionary capturing custom semantic properties (Phi) extracted for domain comparison (e.g., dataset used, accuracy, latency, model size)."
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


class ComparativeResult(BaseModel):
    """
    The consolidated output returned by the Agentic Orchestrator.
    It can contain one table (for single paper mode) or multiple tables (for conference proceedings).
    """
    
    tables: List[ComparisonTable] = Field(
        default_factory=list,
        description="A list containing one or more comparison tables generated from the processed document(s)."
    )