---
name: infectious-disease-extraction
description: >
  Jointly extract the primary infectious disease study (proposed method) and its
  cited prior clinical/dietary baseline studies into a single, cohesive
  InfectiousDiseaseComparisonTable. Enforces strict non-inheritance rules to
  prevent bibliographic leakage across rows.
---

# Skill: Joint Comparative Extraction — Infectious Disease & Nutritional Interventions

---

## 1. Overview & Operational Goal

Produce a structured `InfectiousDiseaseComparisonTable` in which the **proposed
study (Row 1)** and **all compared clinical/dietary baseline studies (Rows 2 to
K+1)** are aligned under identical clinical parameters. The table must be
self-consistent: field labels, units, and naming conventions must be uniform
across every row.

---

## 2. Input / Output Contract

| Direction | Type              | Description |
|-----------|-------------------|-------------|
| Input     | `text/markdown`   | Full Markdown of the research paper |
| Output    | `application/json`| One `InfectiousDiseaseComparisonTable` object |

### 2.1 Top-level Output Structure

```json
{
  "research_problem": "<shared research problem for all rows>",
  "rows": [ /* InfectiousDiseaseRow × (1 + K) */ ]
}
```

---

## 3. Schema Reference

### 3.1 `InfectiousDiseaseRow` — Field Catalogue

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `paper_title` | `str` | ✅ | Official title of the paper or baseline study |
| `authors` | `List[str]` | ✅ | Authors of **this specific** row's study |
| `disease_name` | `str \| null` | — | Target infectious disease (e.g., *Malaria*, *COVID-19*, *Tuberculosis*) |
| `geographical_area` | `str \| null` | — | Country or region where the study was conducted |
| `type_of_diet` | `str \| null` | — | Dietary regime or nutritional intervention analyzed |
| `duration_of_intervention` | `str \| null` | — | Active timeframe of the clinical or nutritional intervention |
| `nutritional_deficiency_associated_to_the_disease` | `str \| null` | — | Nutritional deficiencies explicitly linked to disease severity |
| `pathogen` | `str \| null` | — | Causative microorganism (e.g., *Plasmodium falciparum*, *Vibrio cholerae*) |
| `research_problem` | `str \| null` | — | Overarching scientific gap addressed by the study |
| `mechanism_of_action` | `str \| null` | — | Biological, immunological, or pharmacological pathway described |
| `medical_treatment` | `str \| null` | — | Pharmacological or clinical treatments administered |
| `biomarkers` | `List[str]` | ✅ | Biological/chemical indicators monitored (e.g., viral load, CRP) |
| `has_symptom` | `List[str]` | ✅ | Clinical symptoms observed in the study population |
| `study_population` | `str \| null` | — | Cohort description: sample size, age range, inclusion criteria |
| `food_component` | `str \| null` | — | Macro/micronutrients or bioactive ingredients evaluated |
| `has_outcome` | `str \| null` | — | Clinical or physiological outcome after intervention |
| `material` | `str \| null` | — | Lab tools, assays, reagents, or materials used |
| `follow_up_period` | `str \| null` | — | Post-intervention observation duration |
| `method` | `str \| null` | — | Experimental design (e.g., double-blind RCT, in-vitro study) |
| `contribution` | `ContributionDetails` | ✅ Row 1 only | Core empirical contribution — **Row 1 only** |

### 3.2 `ContributionDetails` — Sub-schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `research_problem` | `str` | ✅ | Specific hypothesis addressed by the paper's main contribution |
| `result` | `str` | ✅ | Core empirical result or quantitative finding |

> **Rule**: `contribution` is **required and non-null for Row 1** (proposed study).
> It **must be `null`** for all baseline rows (Rows 2..K+1).

---

## 4. Extraction Protocol

### Step 4.1 — Extract the Primary Study (Row 1)

1. **Identify the paper title**: extract the full title from the document header.
2. **Authors**: list only the true authors of *this* paper (not editors or reviewers).
3. **Clinical fields**: populate `disease_name`, `pathogen`, `geographical_area`,
   `type_of_diet`, `medical_treatment`, `biomarkers`, `has_symptom`, `has_outcome`,
   `study_population`, `mechanism_of_action`, `method`, `material`, `follow_up_period`,
   `duration_of_intervention`, `nutritional_deficiency_associated_to_the_disease`,
   `food_component`, and `research_problem` from the Methods, Results, and Abstract.
4. **Contribution block**: populate `contribution.research_problem` (specific hypothesis)
   and `contribution.result` (key quantitative finding).

### Step 4.2 — Extract Baseline / Prior Studies (Rows 2..K+1)

1. Scan the **Evaluation**, **Results**, **Discussion**, and **Related Work**
   sections for studies compared side-by-side with the current paper.
2. For each identified baseline study:
   - Create one `InfectiousDiseaseRow`.
   - Populate fields exclusively from what is explicitly stated about *that* study
     in the source text.
   - Set `contribution` to `null`.
3. **Strict Non-Inheritance Rule**:
   - ❌ Do **not** copy the primary paper's `authors`, DOI, URL, or venue into
     any baseline row unless the text explicitly attributes them to that baseline.
   - ❌ Do **not** infer or fabricate field values for baseline rows.

### Step 4.3 — Align Cross-Row Parameters

1. Use a **consistent naming convention** for all list fields across rows.
   - Example: if Row 1 uses `["viral load", "CRP"]` for `biomarkers`, use
     the same terminology in baseline rows when referring to the same markers.
2. Verify that `disease_name` and `pathogen` are consistent where the paper
   implies the same disease context applies to all compared studies.
3. Set the top-level `research_problem` to the overarching scientific question
   that motivates the entire comparison table.

---

## 5. Quality Gates

### ✅ Acceptance Criteria

- [ ] `rows[0]` is the proposed study and has a non-null `contribution` block.
- [ ] All baseline rows (`rows[1..n]`) have `contribution = null`.
- [ ] No baseline row shares `authors` with Row 1 unless the text explicitly
      lists the same authors for that baseline.
- [ ] `biomarkers` and `has_symptom` use consistent terminology across all rows.
- [ ] The top-level `research_problem` captures the shared scientific question.

### 🚩 Red Flags — Hard Blocks

| ID | Red Flag | Consequence |
|----|----------|-------------|
| RF-01 | **Bibliographic Leakage** — primary paper's authors assigned to baseline rows | Invalid output; re-extract |
| RF-02 | **Baseline Omission** — only Row 1 present, no baselines captured | Incomplete table; re-scan Discussion/Results |
| RF-03 | **Contribution Pollution** — `contribution` set on a baseline row | Schema violation; set to `null` |
| RF-04 | **Terminology Drift** — same biomarker named differently across rows | Alignment failure; normalise labels |
| RF-05 | **Field Fabrication** — values invented for missing baseline fields | Data integrity violation; use `null` |

---

## 6. Output Example (Minimal)

```json
{
  "research_problem": "Effect of micronutrient supplementation on malaria severity in sub-Saharan Africa",
  "rows": [
    {
      "paper_title": "Zinc Supplementation Reduces Malaria Morbidity in Burkina Faso Children",
      "authors": ["Ouedraogo, A.", "Traoré, B.", "Müller, O."],
      "disease_name": "Malaria",
      "pathogen": "Plasmodium falciparum",
      "geographical_area": "Burkina Faso",
      "type_of_diet": "Zinc-supplemented diet",
      "duration_of_intervention": "6 months",
      "nutritional_deficiency_associated_to_the_disease": "Zinc deficiency",
      "medical_treatment": "Artemisinin-based combination therapy (ACT)",
      "biomarkers": ["parasitaemia", "serum zinc", "haemoglobin"],
      "has_symptom": ["fever", "anaemia", "splenomegaly"],
      "study_population": "450 children aged 6–59 months",
      "food_component": "Zinc (10 mg/day)",
      "has_outcome": "30% reduction in clinical malaria episodes",
      "method": "Double-blind RCT",
      "follow_up_period": "12 months",
      "contribution": {
        "research_problem": "Does daily zinc supplementation reduce Plasmodium falciparum malaria incidence in zinc-deficient children?",
        "result": "Zinc supplementation reduced uncomplicated malaria episodes by 30% (p < 0.01) over 6 months."
      }
    },
    {
      "paper_title": "Iron Supplementation in Malaria-Endemic Regions (Smith et al., 2021)",
      "authors": ["Smith, J.", "Koné, M."],
      "disease_name": "Malaria",
      "pathogen": "Plasmodium falciparum",
      "geographical_area": "Ghana",
      "type_of_diet": "Iron-supplemented diet",
      "duration_of_intervention": "3 months",
      "biomarkers": ["haemoglobin", "ferritin"],
      "has_symptom": ["anaemia", "fatigue"],
      "has_outcome": "Modest improvement in haemoglobin; no significant change in parasitaemia",
      "contribution": null
    }
  ]
}
```