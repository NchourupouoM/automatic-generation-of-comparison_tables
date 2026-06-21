---
name: nutritional-metabolic-diseases-extraction
description: Extract clinical, metabolic, and nutritional intervention metadata from scientific papers targeting nutritional and metabolic diseases. Bypasses general schemas to populate the specialized Nutritional and Metabolic Diseases Template. Trigger when processing papers on Obesity, Type 2 Diabetes, metabolic syndrome, associated dietary treatments, nutritional deficiencies, causes, and biomarkers.
compatibility: Requires Python 3.10+ and the app/domains/nutritional_metabolic_diseases/schemas.py template.
metadata: 
  - version: 1.0.0
---

# Skill: Specialized Extraction for Nutritional and Metabolic Diseases

## 1. Overview & Operational Goal
The objective is to produce a structured comparative table (`NutritionalMetabolicComparisonTable`) where the proposed study (Row 1) and all compared clinical/dietary baseline studies cited in the paper (Rows 2 to K+1) are structured under the exact same nutritional and metabolic parameters [2.1].

## 2. Input / Output Contract
*   **Input**: Raw Markdown of a nutritional or metabolic disease research paper.
*   **Output**: A single `NutritionalMetabolicComparisonTable` JSON object [2.1].

## 3. Extraction Protocol and Field Semantics

### Step 3.1: Extract the Primary Study (Row 1)
1. **Paper Title**: Extract the paper's full title from the top of the first page.
2. Extract the true primary authors, venue, year, disease, pathogen, dietary and medical interventions, biomarkers, and outcomes.
3. Populate the `contribution` block with the specific research problem and results.

### Step 3.2: Extract Compared baseline Studies (Rows 2 to K+1)
1. Scan the **Evaluation**, **Results**, or **Discussion** sections to identify the previous studies or control/baseline trials compared side-by-side with the current study.
2. For each prior study identified:
   - Create a distinct `NutritionalMetabolicRow` entry.
   - **The Strict Non-Inheritance Rule**: Baseline rows **MUST NOT** copy the main paper's authors, DOI, URL, or Proceeding Title unless explicitly cited in the text.
   - **Contribution Block**: Set the `contribution` block for all baseline rows to `null`/None (it is reserved exclusively for the primary study).

### Step 3.3: Align Comparative Metabolic Parameters
1. **Causes**: Identify the primary etiology, causes, or triggers of the disease (e.g., "genetic predisposition", "high-fructose diet").
2. **Nutritional Deficiency associated to the disease**: Extract the deficiency caused by or associated with this disease (e.g., "Zinc deficiency", "Vitamin D3 deficiency").
3. **Has Outcome**: Identify the clinical effectiveness of the supplement or intervention.
4. **Follow-up Period**: Extract the post-intervention follow-up observation timeframe.

## 4. Quality Gates & Red Flags

### Red Flags (What to Avoid)
*   🚩 **Bibliographic Leakage**: Copying the main study's authors or coordinates into the baseline rows.
*   🚩 **Confusing Cause and Treatment**: Do not list medical treatments as the 'causes' of the disease.