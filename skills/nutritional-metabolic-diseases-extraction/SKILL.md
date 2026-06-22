---
name: nutritional-metabolic-diseases-extraction
description: >
  Extract clinical, metabolic, and nutritional intervention metadata from
  scientific papers targeting nutritional and metabolic diseases. Populates the
  specialized NutritionalMetabolicComparisonTable with both the proposed study
  (Row 1) and all compared baseline studies (Rows 2..K+1). Enforces strict
  non-inheritance and cause/treatment disambiguation rules.
---

# Skill: Specialized Extraction — Nutritional & Metabolic Diseases

---

## 1. Overview & Operational Goal

Produce a structured `NutritionalMetabolicComparisonTable` in which the **proposed
study (Row 1)** and **all compared clinical/dietary baseline studies (Rows 2 to
K+1)** are aligned under the same nutritional and metabolic parameters. The table
must be internally consistent: field semantics, units, and naming conventions must
be uniform across every row.

---

## 2. Input / Output Contract

| Direction | Type               | Description |
|-----------|--------------------|-------------|
| Input     | `text/markdown`    | Full Markdown of the research paper |
| Output    | `application/json` | One `NutritionalMetabolicComparisonTable` object |

### 2.1 Top-level Output Structure

```json
{
  "research_problem": "<shared research problem for all rows>",
  "rows": [ /* NutritionalMetabolicRow × (1 + K) */ ]
}
```

---

## 3. Schema Reference

### 3.1 `NutritionalMetabolicRow` — Field Catalogue

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `paper_title` | `str` | ✅ | Title of the paper or named baseline study |
| `authors` | `List[str]` | ✅ | Authors of **this specific** row's study |
| `disease_name` | `str \| null` | — | Target disease (e.g., *Obesity*, *Scurvy*, *Type 2 Diabetes*) |
| `geographical_area` | `str \| null` | — | Country or region where the study was conducted |
| `nutritional_deficiency_associated_to_the_disease` | `str \| null` | — | Deficiencies associated with the disease (e.g., *Vitamin C deficiency*, *Zinc deficiency*) |
| `type_of_diet` | `str \| null` | — | Dietary intervention analyzed (e.g., *Ketogenic diet*, *Mediterranean diet*) |
| `duration_of_intervention` | `str \| null` | — | Active timeframe of the therapeutic or dietary intervention |
| `mechanism_of_action` | `str \| null` | — | Biological or biochemical pathway described |
| `causes` | `str \| null` | — | Etiology, primary causes, triggers, or risk factors of the disease |
| `research_problem` | `str \| null` | — | Overarching scientific gap addressed by the study |
| `has_symptom` | `List[str]` | ✅ | Clinical signs and symptoms observed in the study population |
| `medical_treatment` | `str \| null` | — | Pharmacological or clinical treatments administered |
| `biomarkers` | `List[str]` | ✅ | Biological/chemical indicators monitored (e.g., HbA1c, lipid profile, blood glucose) |
| `has_outcome` | `str \| null` | — | Clinical effectiveness or physiological outcome of the intervention |
| `study_population` | `str \| null` | — | Cohort description: size, age range, inclusion criteria |
| `food_component` | `str \| null` | — | Specific nutrients, food components, or supplements evaluated |
| `follow_up_period` | `str \| null` | — | Post-intervention observation duration |
| `contribution` | `ContributionDetails \| null` | ✅ Row 1 only | Core empirical contribution — **Row 1 only**, `null` for all baselines |

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

1. **Paper title**: extract the full title from the document header.
2. **Authors**: list only the true authors of *this* paper.
3. **Clinical fields**: populate all applicable fields from the Methods, Results,
   and Abstract sections, including:
   - `disease_name`, `geographical_area`, `type_of_diet`, `duration_of_intervention`
   - `mechanism_of_action`, `causes`, `has_symptom`, `medical_treatment`
   - `biomarkers`, `has_outcome`, `study_population`, `food_component`
   - `nutritional_deficiency_associated_to_the_disease`, `follow_up_period`
4. **Contribution block**: populate `contribution.research_problem` (specific
   hypothesis) and `contribution.result` (key quantitative finding).

### Step 4.2 — Extract Baseline / Prior Studies (Rows 2..K+1)

1. Scan the **Evaluation**, **Results**, **Discussion**, and **Related Work**
   sections for studies compared side-by-side with the current paper.
2. For each identified baseline study:
   - Create one `NutritionalMetabolicRow`.
   - Populate fields exclusively from what is explicitly stated about *that*
     study in the source text.
   - Set `contribution` to `null`.
3. **Strict Non-Inheritance Rule**:
   - ❌ Do **not** copy the primary paper's `authors`, DOI, URL, or venue into
     any baseline row unless the text explicitly attributes them to that baseline.
   - ❌ Do **not** infer or fabricate field values for baseline rows.

### Step 4.3 — Align Cross-Row Metabolic Parameters

The following fields require special disambiguation attention:

#### `causes`
- Extract the **etiology, primary risk factors, or triggers** of the disease
  (e.g., *"genetic predisposition"*, *"high-fructose diet"*, *"sedentary lifestyle"*).
- ⚠️ **Do not confuse with `medical_treatment`**: treatments administered to
  address the disease are **not** causes of the disease.

#### `nutritional_deficiency_associated_to_the_disease`
- Extract **deficiencies caused by or strongly associated with** the disease
  (e.g., *"Zinc deficiency"*, *"Vitamin D3 deficiency"*).
- Distinguish from `food_component`, which refers to the ingredient being
  tested or supplemented.

#### `has_outcome`
- Capture the **clinical effectiveness or physiological result** of the
  supplement or intervention, with quantitative precision where available.

#### `follow_up_period`
- Extract the **post-intervention observation timeframe** separately from
  `duration_of_intervention` (which covers the active treatment period).

#### Cross-row alignment
- Use a **consistent naming convention** for all list fields across rows.
  - Example: if Row 1 uses `["HbA1c", "fasting blood glucose"]` for `biomarkers`,
    use the same terminology in baseline rows when the same markers are referenced.
- Verify that `disease_name` is consistent where the paper implies all compared
  studies address the same condition.

---

## 5. Quality Gates

### ✅ Acceptance Criteria

- [ ] `rows[0]` is the proposed study and has a non-null `contribution` block.
- [ ] All baseline rows (`rows[1..n]`) have `contribution = null`.
- [ ] No baseline row shares `authors` with Row 1 unless explicitly stated in the text.
- [ ] `causes` contains only disease etiologies, not treatments.
- [ ] `biomarkers` and `has_symptom` use consistent terminology across all rows.
- [ ] `follow_up_period` and `duration_of_intervention` are not conflated.

### 🚩 Red Flags — Hard Blocks

| ID | Red Flag | Consequence |
|----|----------|-------------|
| RF-01 | **Bibliographic Leakage** — primary paper's authors assigned to baseline rows | Invalid output; re-extract |
| RF-02 | **Baseline Omission** — only Row 1 present, no baselines captured | Incomplete table; re-scan Discussion/Results |
| RF-03 | **Contribution Pollution** — `contribution` set on a baseline row | Schema violation; set to `null` |
| RF-04 | **Cause/Treatment Confusion** — medical treatments listed under `causes` | Semantic violation; move to `medical_treatment` |
| RF-05 | **Deficiency/Component Confusion** — supplemented ingredient listed under `nutritional_deficiency_associated_to_the_disease` | Semantic violation; move to `food_component` |
| RF-06 | **Terminology Drift** — same biomarker named differently across rows | Alignment failure; normalise labels |
| RF-07 | **Field Fabrication** — values invented for missing baseline fields | Data integrity violation; use `null` |

---

## 6. Output Example (Minimal)

```json
{
  "research_problem": "Effect of ketogenic diet on glycaemic control in adults with Type 2 Diabetes",
  "rows": [
    {
      "paper_title": "Ketogenic Diet Improves Glycaemic Control in Overweight Adults with T2D: A 12-Week RCT",
      "authors": ["Martinez, L.", "Chen, W.", "Dupont, F."],
      "disease_name": "Type 2 Diabetes",
      "geographical_area": "France",
      "nutritional_deficiency_associated_to_the_disease": "Vitamin D deficiency",
      "type_of_diet": "Ketogenic diet (<20g carbohydrates/day)",
      "duration_of_intervention": "12 weeks",
      "mechanism_of_action": "Reduction of insulin resistance via hepatic ketogenesis and improved mitochondrial function",
      "causes": "Obesity, sedentary lifestyle, genetic predisposition",
      "research_problem": "Does a ketogenic diet improve HbA1c in overweight T2D patients compared to standard low-fat diet?",
      "has_symptom": ["hyperglycaemia", "fatigue", "polydipsia"],
      "medical_treatment": "Metformin 500 mg/day (maintained stable throughout trial)",
      "biomarkers": ["HbA1c", "fasting blood glucose", "LDL cholesterol", "triglycerides"],
      "has_outcome": "HbA1c reduced by 1.2% vs 0.4% in control group (p < 0.001) after 12 weeks",
      "study_population": "120 overweight adults (BMI 27–35), aged 40–65, diagnosed T2D for ≥2 years",
      "food_component": "Dietary fat (70%), protein (25%), carbohydrates (5%)",
      "follow_up_period": "6 months post-intervention",
      "contribution": {
        "research_problem": "Does a strict ketogenic diet outperform a standard low-fat diet for HbA1c reduction in overweight T2D adults on stable Metformin?",
        "result": "KD achieved a 1.2% HbA1c reduction vs 0.4% for low-fat diet (p < 0.001), with 65% of KD participants reaching HbA1c < 7% at 12 weeks."
      }
    },
    {
      "paper_title": "Low-Fat Diet and T2D Glycaemic Outcomes (Johnson et al., 2020)",
      "authors": ["Johnson, R.", "Patel, S."],
      "disease_name": "Type 2 Diabetes",
      "geographical_area": "United Kingdom",
      "type_of_diet": "Low-fat diet (<30% energy from fat)",
      "duration_of_intervention": "12 weeks",
      "biomarkers": ["HbA1c", "fasting blood glucose"],
      "has_symptom": ["hyperglycaemia"],
      "has_outcome": "HbA1c reduced by 0.4% over 12 weeks",
      "study_population": "115 adults with T2D, aged 35–70",
      "follow_up_period": "3 months post-intervention",
      "contribution": null
    }
  ]
}
```