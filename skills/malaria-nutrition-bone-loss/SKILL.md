---
name: malaria-nutrition-bone-loss
description: Extract complex host-pathogen interactions, nutritional status, and bone remodeling/anemia outcomes from studies evaluating malaria-induced bone loss. Trigger when analyzing papers studying Plasmodium species, bone resorption, anemia pathophysiology, and dietary co-factors.
compatibility: Requires Python 3.10+ and the app/domains/malaria_nutrition_bone_loss/schemas.py template.
metadata:
  - version: 1.0.0
---

# Skill: Specialized Extraction for Malaria, Nutrition, and Skeletal Pathology

## 1. Overview & Operational Goal
This advanced skill parses the multi-system pathological interactions between malaria infection, host nutritional deficiencies, anemia, and metabolic bone loss.

## 2. Input / Output Contract
*   **Input**: Raw Markdown of a skeletal pathology/malaria paper.
*   **Output**: A single `ComparisonTable` containing the dynamic metrics.

## 3. Extraction Protocol and Field Semantics

### Step 3.1: Host and Pathogen Baseline Coordinates
1. **Plasmodium Species**: Identify the precise parasite species responsible for the infection (e.g., *Plasmodium berghei ANKA*, *Plasmodium falciparum*).
2. **Host Type**: Extract the biological system (e.g. "C57BL/6 mice", "Human pediatric cohort").
3. **Infection Pattern**: Identify the temporal pattern of infection (e.g., "acute infection", "chronic recrudescent").

### Step 3.2: Nutritional and Skeletal Pathology
1. **Nutritional Status**: Verify if direct dietary intake, caloric restriction, or specific micro-nutrient feeding was evaluated.
2. **Bone Compartment Affected**: Identify the specific skeletal regions evaluated (e.g. "trabecular bone of the distal femur metaphysis").
3. **Bone Remodeling Markers**: List molecular indicators of skeletal activity (e.g. "RANKL/OPG ratio", "Osteocalcin", "CTX-1").
4. **Bone Marrow Pathology**: Extract structural bone marrow alterations (e.g. "marrow hypoplasia", "parasitized erythrocyte accumulation").

### Step 3.3: Anemia and Inflammation
1. **Anemia Evaluation**: Extract indicators of iron status (e.g. "Hemoglobin (Hb) levels", "hematocrit").
2. **Anemia Mechanism**: Locate the biological pathways causing anemia (e.g., "bystander erythrocyte destruction", "erythropoiesis suppression").
3. **Inflammatory Mediators**: List cytokines measured (e.g., "TNF-alpha", "IFN-gamma", "IL-6").

## 4. Quality Gates & Red Flags

### Red Flags
*   🚩 **Confusing Host and Parasite**: Do not write *Plasmodium berghei* as the host. The host is the rodent or human.
*   🚩 **Omission of Molecular Markers**: Failing to capture specific scientific acronyms for bone markers (e.g., writing "bone loss" instead of "decreased OPG/RANKL ratio").