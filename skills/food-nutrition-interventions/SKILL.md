---
name: food-nutrition-interventions
description: Extract clinical trials and dietary intervention parameters evaluating the role of specialized foods, macro/micronutrients, and supplements in disease management. Trigger when analyzing trials on dietary supplementations, therapeutic foods, nutrient focus, and clinical outcomes.
compatibility: Requires Python 3.10+ and the app/domains/food_nutrition_interventions/schemas.py template.
metadata:
  - version: 1.0.0
---

# Skill: Specialized Extraction for Food and Nutritional Interventions

## 1. Overview & Operational Goal
This skill structures clinical trials studying the therapeutic effects of foods, specialized diets, and macro/micronutrients in managing acute or chronic diseases [2.1].

## 2. Input / Output Contract
*   **Input**: Raw Markdown of a clinical nutrition trial paper.
*   **Output**: A single `ComparisonTable` containing consolidated rows [2.1].

## 3. Extraction Protocol and Field Semantics

### Step 3.1: Disease and Study Characterization
1. **Disease Name**: Extract the primary medical condition addressed (e.g., "Celiac Disease", "Non-alcoholic Fatty Liver Disease (NAFLD)").
2. **Disease Type**: Classify the condition to group and compare studies (e.g., "Autoimmune gastrointestinal", "Metabolic liver disease").
3. **Study Type**: Identify the research design (e.g., "Double-blind randomized controlled trial").

### Step 3.2: Nutritional Intervention Parameters
1. **Food/Diet Intervention**: Extract the specific food, dietary pattern, or supplement administered (e.g., "Gluten-free diet", "High-fiber supplementation").
2. **Nutrient Focus**: Identify the key nutrient emphasized (e.g. "Soluble fibers", "Omega-3 fatty acids").
3. **Duration of Intervention**: Extract the length of the trial (e.g., "12 weeks", "6 months").

### Step 3.3: Methodology & Outcomes
1. **Methodology**: Summarize how the study was conducted (e.g., "1:1 allocation, parallel-group trial with caloric restriction").
2. **Key Findings**: Extract the primary clinical results and statistical significance (e.g. "Significant decrease in hepatic steatosis (p = 0.02) compared to control").

## 4. Quality Gates & Red Flags

### Red Flags
*   🚩 **Over-generalizing the Intervention**: Writing "diet" instead of the specific pattern (e.g., "Low-FODMAP diet").
*   🚩 **Hallucinating Outcomes**: Creating positive statistical results if the authors reported no significant difference.