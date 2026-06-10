---
name: academicextraction
description: Extract bibliographic metadata and domain-specific comparison properties (Phi) from a research paper or a set of related baselines. Conforms output strictly to the ComparisonRow schema.
compatibility: Requires Python 3.10+, schemas.py, and a structured LLM.
metadata: 
  - version: 1.0.0
---

# Skill: High-Precision Structured Academic Extraction

## 1. Overview & Operational Goal
This skill extracts standard bibliographic metadata and domain-specific comparative features ($\Phi$) from an individual scientific publication ($D_{single}$ or segmented $p_i$) [2.1]. The output is strictly formatted as a relational row adhering to the unified target schema [2.1].

## 2. Default Methodology
*   **Property Mapping ($\Phi$)**: Do not hardcode comparison axes. The agent must dynamically discover up to 5 key comparison properties (e.g., "Accuracy", "Dataset Size", "Inference Speed", "Hardware Requirements") mentioned in the paper's comparison or evaluation sections.
*   **Strict Grounding**: Every extracted parameter must be grounded in the source text. Do not hallucinate metrics. If a value is unknown, explicitly set it to `null`.

## 3. Step-by-Step Procedure
1.  **Identify Paper Coordinates**: Extract the paper title, authors, venue, publication date, DOI, and URL from the first pages of the text.
2.  **Determine Research Problem & Method**: Extract a concise definition of the targeted research problem and the primary methodology used.
3.  **Perform Dynamic Semantic Profiling ($\Phi$)**:
    *   Scan the "Evaluation", "Results", or "Discussion" section of the paper.
    *   Identify the key performance metrics or structural properties used to evaluate the work.
    *   Represent these metrics as key-value pairs inside the `domain_specific_properties` dictionary.
4.  **Format Constraints**: Verify that the generated output strictly validates against the `ComparisonRow` schema definition.

## 4. Quality Gates & Red Flags

### Red Flags (What to Avoid)
*   🚩 **Invented Values**: Do not guess numeric values (e.g., writing "98% Accuracy" if the paper only describes the result as "state-of-the-art"). Use empty/null fields or textual descriptions when uncertain.
*   🚩 **Mismatched Baselines**: Mixing up the performance values of the *proposed method* with those of its *baselines*. Ensure values are mapped to the correct paper entity.
*   🚩 **Overloaded Phi Dictionary**: Creating an excessively large `domain_specific_properties` map (> 10 items) that dilutes focus. Keep to the most essential comparative criteria.

### Verification Steps
*   [ ] Check that `paper_title` is not empty.
*   [ ] Check that `research_problem` is represented as a specific problem domain.
*   [ ] Confirm that all keys within the `domain_specific_properties` dictionary are in snake_case or clean title formatting (e.g., `inference_latency_ms`).