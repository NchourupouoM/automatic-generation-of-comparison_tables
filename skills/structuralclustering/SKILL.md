---
name: structuralclustering
description: Segment an Academic Proceeding PDF into individual papers and cluster them by their core research problem. Use this skill when the input is a multi-paper document, conference proceeding, or raw bulk text.
compatibility: Requires Python 3.10+, LangChain, and structured extraction schema.
metadata: 
  - version: 1.0.0
---

# Skill: Structural Clustering of Academic Proceedings

## 1. Overview & Operational Goal
This skill solves the problem of high-context, multi-paper scientific proceedings ($D_{proc}$). It guides an agent to segment a bulk document stream into distinct individual papers ($p_1 ... p_n$) and group those papers into semantically coherent clusters ($C_1 ... C_m$) based on their primary targeted "research_problem".

## 2. Default Methodology
*   **Segmentation**: Use Markdown headers (extracted via `pdf-extraction`) to identify title transitions. Every new paper is defined by a clear transition of title, authors, abstract, and introduction.
*   **Clustering Key**: The semantic grouping must center strictly around the "research_problem". Do not cluster by broad disciplines (e.g., "Deep Learning" is too generic; "Low-resource Machine Translation" is a valid research problem).

## 3. Step-by-Step Procedure
1.  **Read Input Stream**: Accept the parsed markdown content from the upstream PDF extraction skill.
2.  **Identify Boundary Patterns**: Look for recurring structures signifying paper beginnings (e.g., Titles in Title Case followed by Author names, Emails, Institutional affiliations, and an "Abstract" section).
3.  **Generate Paper Indexes**: Create a manifest of individual papers containing:
    *   `estimated_start_page` and `estimated_end_page`
    *   `extracted_title`
    *   `extracted_authors`
4.  **Semantic Inference**: For each segmented paper, extract a concise summary of the primary "research_problem" addressed.
5.  **Cluster Synthesis**: Apply a semantic grouping algorithm (or recursive LLM classification loop) to merge similar research problems into exactly $m$ unique clusters.

## 4. Quality Gates & Red Flags

### Red Flags (What to Avoid)
*   🚩 **Over-segmentation**: Splitting a single paper's sections (e.g., treating "Method" or "References" as separate papers).
*   🚩 **Broad Clustering**: Putting all papers into a single generic cluster like "Artificial Intelligence". If a cluster has more than 5 papers, check if the "research_problem" definition can be made more specific.
*   🚩 **Empty/Orphan Segments**: Extracting text blocks without assigning them to a parent paper.

### Verification Steps
*   [ ] Verify that the sum of pages of all segmented papers matches or closely approximates the total pages of the input PDF.
*   [ ] Confirm that every paper has at least a Title, an Author list, and a defined Research Problem.
*   [ ] Ensure that every cluster has a name that represents a specific scientific problem, not a technology stack.