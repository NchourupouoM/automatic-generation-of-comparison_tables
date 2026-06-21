from typing import List, Optional
from pydantic import BaseModel, Field


class ContributionDetails(BaseModel):
    """
    Subgroup capturing the core empirical contribution of the scientific paper.
    """
    research_problem: str = Field(
        ...,
        description="The specific research problem or hypothesis addressed directly by this paper's main contribution."
    )
    result: str = Field(
        ...,
        description="The core empirical result or quantitative finding achieved by this contribution."
    )


class NutritionalMetabolicRow(BaseModel):
    """
    Represents a single row in the comparative matrix for the Nutritional and Metabolic Diseases domain.
    Used for both the primary proposed study and the compared prior works/related studies.
    """
    paper_title: str = Field(
        ..., 
        description="The title of the research paper (or the named prior study/baseline model)."
    )
    authors: List[str] = Field(
        default_factory=list, 
        description="List of authors who published the paper."
    )
    
    # Properties extracted from the Nutritional and Metabolic Diseases template
    disease_name: Optional[str] = Field(
        default=None, 
        description="Name of the nutritional or metabolic disease studied (e.g., Obesity, Scurvy, Type 2 Diabetes)."
    )
    geographical_area: Optional[str] = Field(
        default=None, 
        description="The geographical region, country, or location where the study or trial took place."
    )
    nutritional_deficiency_associated_to_the_disease: Optional[str] = Field(
        default=None, 
        description="Specific nutritional deficiencies associated with the disease (e.g., Vitamin C deficiency, Zinc deficiency)."
    )
    type_of_diet: Optional[str] = Field(
        default=None, 
        description="Type of dietary intervention or food regime analyzed (e.g., Ketogenic diet, Mediterranean diet)."
    )
    duration_of_intervention: Optional[str] = Field(
        default=None, 
        description="The active timeframe or duration of the therapeutic, dietary, or nutritional intervention."
    )
    mechanism_of_action: Optional[str] = Field(
        default=None, 
        description="The biological, physiological, or biochemical pathway/mechanism of action described."
    )
    causes: Optional[str] = Field(
        default=None, 
        description="The etiology, primary causes, triggers, or risk factors of the nutritional or metabolic disease."
    )
    research_problem: Optional[str] = Field(
        default=None, 
        description="The general, overarching research problem or scientific gap addressed by the study."
    )
    has_symptom: List[str] = Field(
        default_factory=list, 
        description="Clinical signs and symptoms associated with the disease or observed in the study population."
    )
    medical_treatment: Optional[str] = Field(
        default=None, 
        description="Any pharmacological, medical, or clinical treatments administered to the subjects."
    )
    biomarkers: List[str] = Field(
        default_factory=list, 
        description="Biological or chemical indicators monitored in the study (e.g., HbA1c, lipid profile, blood glucose)."
    )
    has_outcome: Optional[str] = Field(
        default=None, 
        description="The clinical effectiveness, physiological, or therapeutic outcome of the supplement or intervention."
    )
    study_population: Optional[str] = Field(
        default=None, 
        description="Detailed description of the target study cohort (size, age range, inclusion criteria)."
    )
    food_component: Optional[str] = Field(
        default=None, 
        description="Specific food components, nutrients, or supplementary active ingredients evaluated."
    )
    follow_up_period: Optional[str] = Field(
        default=None, 
        description="The duration of the post-intervention follow-up observation period."
    )
    
    # La contribution est spécifique à l'étude proposée (Row 1). Elle sera nulle pour les études antérieures citées.
    contribution: Optional[ContributionDetails] = Field(
        default=None, 
        description="The specific empirical contribution and key outcomes. Populate ONLY for the primary proposed study (Row 1). Set to null/None for baseline rows."
    )


class NutritionalMetabolicComparisonTable(BaseModel):
    """
    The final comparison table matching the Nutritional and Metabolic Diseases domain.
    Contains the proposed study (Row 1) and all compared related works/baselines (Rows 2 to K+1).
    """
    research_problem: str = Field(
        ...,
        description="The shared research problem that groups all the comparative rows in this table together."
    )
    rows: List[NutritionalMetabolicRow] = Field(
        ...,
        description="The collection of comparison entries (rows) including the proposed study and its compared baseline/prior works."
    )