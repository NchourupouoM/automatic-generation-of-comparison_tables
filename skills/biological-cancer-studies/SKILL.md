---
name: biological-cancer-studies
description: Extract pathological, epidemiological, clinical, and preventative metadata from scientific papers on biological-based cancer studies. Trigger when processing oncology research, clinical trials on breast, colon, or lung cancers, risk factor analyses, and chemotherapy evaluations.
compatibility: Requires Python 3.10+ and the app/domains/biological_cancer_studies/schemas.py template.
metadata:
  - version: 1.0.0
---

# Skill: High-Precision Oncology and Biological Cancer Studies Extraction

## 1. Overview & Operational Goal
This specialized skill targets biological-based cancer studies. It extracts pathological tumor parameters (stages, subtypes), clinical therapies, and prevention strategies, organizing them into a unified, flat comparative matrix [2.1].

## 2. Input / Output Contract
*   **Input**: Raw Markdown text of an oncology paper.
*   **Output**: A single `ComparisonTable` containing `InfectiousDiseaseRow` compatible objects.

## 3. Extraction Protocol and Field Semantics

### Step 3.1: Pathological Characterization
1. **Problem (Cancer Tissue Origin)**: Identify the specific organ or tissue where the studied cancer starts in the body (e.g., "Breast tissue", "Epithelial tissue of the colon").
2. **Subtypes**: Extract the biological or molecular subtype of the cancer targeted (e.g. "Triple-Negative Breast Cancer (TNBC)", "HER2+ positive").
3. **Cancer Stages**: Locate the stage of cancer progression involved in the cohort (e.g. "Stage IV metastatic", "Early-stage local").

### Step 3.2: Epidemiology & Risk Factors
1. **Epidemiology**: Extract quantitative values representing the incidence, prevalence, or mortality of that cancer (e.g. "Over 2.3 million cases diagnosed globally in 2024").
2. **Risk Factor**: Identify carcinogens, genetics, or exposures that increase the likelihood of developing the studied cancer.

### Step 3.3: Therapeutic and Prevention Strategies
1. **Treatment Strategies**: Extract surgical, radiological, or chemotherapeutic strategies used to treat the cancer (e.g. "Adjuvant chemotherapy with doxorubicin").
2. **Prevention Strategies**: Identify behaviors, interventions, or drugs used to avoid cancer development or recurrence (e.g. "Prophylactic mastectomy", "selective estrogen receptor modulators").

## 4. Quality Gates & Red Flags

### Red Flags
*   🚩 **Confusing Treatment and Prevention**: Do not list active chemotherapy as a prevention strategy.
*   🚩 **Vague Cancer Subtypes**: Writing "cancer" as subtype. It must describe molecular or histology classifications.