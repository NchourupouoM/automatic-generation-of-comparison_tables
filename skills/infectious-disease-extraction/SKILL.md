---
name: infectious-disease-extraction
description: Jointly extract the primary infectious disease study (proposed method) and its cited prior clinical/dietary baseline studies into a single, cohesive InfectiousDiseaseComparisonTable. Prevents context leakage by enforcing strict non-inheritance rules.
compatibility: Requires Python 3.10+ and the app/domains/infectious_disease/schemas.py template.
metadata: 
  - version: 1.1.0
---

# Skill: Joint Comparative Extraction for Infectious Disease and Nutritional Interventions

## 1. Overview & Operational Goal
The objective is to produce a structured comparative table (`InfectiousDiseaseComparisonTable`) where the proposed study (Row 1) and all compared clinical/dietary baseline studies cited in the paper (Rows 2 to K+1) are structured under the exact same clinical parameters [2.1].

## 2. Input / Output Contract
*   **Input**: Raw Markdown of an infectious disease research paper.
*   **Output**: A single `InfectiousDiseaseComparisonTable` JSON object [2.1].

## 3. Extraction Protocol and Field Semantics

### Step 3.1: Extract the Primary Study (Row 1)
1. **Paper Title**: Extract the paper's full title from the top of the first page.
2. Extract the true primary authors, venue, year, disease, pathogen, dietary and medical interventions, biomarkers, and outcomes.
3. Populate the `contribution` block with the specific research problem and results.

### Step 3.2: Extract Compared Baseline Studies (Rows 2 to K+1)
1. Scan the **Evaluation**, **Results**, or **Discussion** sections to identify the previous studies or control/baseline trials compared side-by-side with the current study.
2. For each prior study identified (e.g., "Smith et al. (2021) diet trial", "Standard-of-Care control cohort"):
   - Create a distinct `InfectiousDiseaseRow` entry.
   - **The Strict Non-Inheritance Rule**: Baseline rows **MUST NOT** copy the main paper's authors, DOI, URL, or Proceeding Title unless explicitly cited in the text.
   - **Contribution Block**: Set the `contribution` block for all baseline rows to `null`/None (it is reserved exclusively for the primary study).

### Step 3.3: Align Comparative Clinical Parameters
1. Ensure all extracted rows share compatible values in their clinical fields (disease, pathogen, diet, treatment, biomarkers) as compared in the original paper's comparative tables.
2. Ensure identical naming convention across rows for list items (e.g., if biomarkers are listed as `["viral load"]` on Row 1, use similar terminology for baseline rows).

## 4. Quality Gates & Red Flags

### Red Flags (What to Avoid)
*   🚩 **Bibliographic Leakage**: Assigning the authors of the primary paper to baseline clinical rows.
*   🚩 **Omission of Baselines**: Extracting only the current study and failing to capture the historical/baseline cohorts it compared itself against.