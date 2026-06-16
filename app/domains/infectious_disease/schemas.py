# app/domains/infectious_disease/schemas.py
from typing import List, Optional
from pydantic import BaseModel, Field


class ContributionDetails(BaseModel):
    """
    Subgroup capturing the core empirical contribution of the scientific paper.
    """
    research_problem: str = Field(
        ...,
        description="The specific research problem or hypothesis addressed directly by the paper's main contribution."
    )
    result: str = Field(
        ...,
        description="The core empirical result or quantitative finding achieved by the proposed contribution."
    )


class InfectiousDiseaseRow(BaseModel):
    """
    Standardized schema (Template) for the Infectious Disease domain.
    Maps clinical trials, pathogens, diets, interventions, and outcomes.
    """
    
    # ---------------------------------------------------------------------------
    # Basic Identification Coordinates
    # ---------------------------------------------------------------------------
    paper_title: str = Field(
        ..., 
        description="The official title of the research paper."
    )
    authors: List[str] = Field(
        default_factory=list, 
        description="List of authors who published the paper."
    )
    
    # ---------------------------------------------------------------------------
    # Domain Fields (From User Template Layout)
    # ---------------------------------------------------------------------------
    disease_name: Optional[str] = Field(
        default=None, 
        description="Name of the target infectious disease studied (e.g., Malaria, COVID-19, Tuberculosis)."
    )
    geographical_area: Optional[str] = Field(
        default=None, 
        description="The geographical region, country, or location where the study or trial took place."
    )
    type_of_diet: Optional[str] = Field(
        default=None, 
        description="Type of dietary regime or nutritional intervention analyzed in the study population."
    )
    duration_of_intervention: Optional[str] = Field(
        default=None, 
        description="The active timeframe or duration of the clinical, therapeutic, or nutritional intervention."
    )
    nutritional_deficiency_associated_to_the_disease: Optional[str] = Field(
        default=None, 
        description="Any specific nutritional deficiencies or malnutrition factors explicitly linked to the disease severity or occurrence."
    )
    pathogen: Optional[str] = Field(
        default=None, 
        description="The specific microbiological pathogen causing the disease (e.g., Plasmodium falciparum, Vibrio cholerae)."
    )
    research_problem: Optional[str] = Field(
        default=None, 
        description="The general, overarching research problem or scientific gap addressed by the paper."
    )
    mechanism_of_action: Optional[str] = Field(
        default=None, 
        description="The biological, immunological, or pharmacological pathway/mechanism of action described."
    )
    medical_treatment: Optional[str] = Field(
        default=None, 
        description="Any pharmacological, medical, or clinical treatments administered to the subjects."
    )
    biomarkers: List[str] = Field(
        default_factory=list, 
        description="Biological or chemical indicators monitored in the study (e.g., viral load, CRP, antibody titers)."
    )
    has_symptom: List[str] = Field(
        default_factory=list, 
        description="Symptoms and clinical manifestations observed in the host or patient population."
    )
    study_population: Optional[str] = Field(
        default=None, 
        description="Detailed description of the cohort (e.g., sample size, age range, inclusion criteria)."
    )
    food_component: Optional[str] = Field(
        default=None, 
        description="Specific macro/micronutrients, food components, or bioactive ingredients evaluated."
    )
    has_outcome: Optional[str] = Field(
        default=None, 
        description="The clinical, therapeutic, or physiological outcome observed after the intervention."
    )
    material: Optional[str] = Field(
        default=None, 
        description="Specific laboratory tools, assays, reagents, or materials used in the experiments."
    )
    follow_up_period: Optional[str] = Field(
        default=None, 
        description="The duration of the observation period after the primary intervention has ended."
    )
    method: Optional[str] = Field(
        default=None, 
        description="The overarching scientific methodology or experimental design (e.g., double-blind RCT, in-vitro study)."
    )
    
    # ---------------------------------------------------------------------------
    # Subgroup: Contribution
    # ---------------------------------------------------------------------------
    contribution: ContributionDetails = Field(
        ..., 
        description="The targeted empirical contribution and key outcomes of the paper."
    )

class InfectiousDiseaseComparisonTable(BaseModel):
    """
    The final comparison table matching the infectious disease domain.
    Contains the proposed study (Row 1) and all compared prior works/related studies (Rows 2 to K+1).
    """
    research_problem: str = Field(
        ...,
        description="The shared research problem that groups all the comparative rows in this table together."
    )
    rows: List[InfectiousDiseaseRow] = Field(
        ...,
        description="The collection of comparison entries (rows) including the proposed study and its compared baseline/prior works."
    )