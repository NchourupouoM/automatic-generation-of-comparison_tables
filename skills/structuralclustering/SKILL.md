---
name: structuralclustering
description: Segment multi-paper scientific documents (conference proceedings, workshop compilations, or bulk academic text) into distinct papers and semantically cluster them by their specific research problem. This skill serves as the mandatory pre-requisite step before calling 'academicextraction' on multi-paper inputs. Trigger when users ask to "process a proceeding", "extract tables from a conference compilation", "group papers by topic", or "split this book of articles".
compatibility: Requires Python 3.10+ and a layout-preserving PDF-to-Markdown extraction utility.
metadata:
  - version: 1.0.0
---

# Skill: Structural Clustering of Academic Proceedings

## 1. Overview & Operational Goal
This skill solves the problem of processing high-context, multi-paper scientific proceedings. It guides an agent to segment a continuous document stream into distinct individual papers and group those papers into semantically coherent clusters based on their primary targeted research problem. 

This process guarantees that downstream extraction tasks receive clean, isolated text segments, preventing context pollution and cross-paper hallucinations.

## 2. Input / Output Contract

### 2.1 Input Specification
The skill expects a single UTF-8 encoded string containing the layout-preserved raw Markdown output of a PDF extraction utility (e.g., PyMuPDF4LLM).
*   **Source**: Programmatic PDF parser (non-agentic utility).
*   **Format**: Raw Markdown.
*   **State Dependency**: Must contain structural headers (`#`, `##`), page break hints, and the complete text body of all papers.

### 2.2 Output Specification
The skill must produce a validated JSON payload adhering to the `ProceedingsManifest` schema.
```json
{
  "$schema": "https://agentskills.io/schemas/proceedings_manifest.v1.json",
  "papers": [
    {
      "title": "A Clean Title of Paper 1",
      "authors": ["Author A", "Author B"],
      "research_problem": "Specific Inferred Research Problem",
      "text_segment": "A clean cut segment of the paper content including its references..."
    }
  ]
}
```

## 3. Detailed Step-by-Step Procedure

### Step 3.1: Document Stream Ingestion & Layout Inspection
1. Read the parsed layout-preserved Markdown text.
2. Inspect the first 4,000 characters to identify document markers:
   - Scan for a Table of Contents (TOC) or Conference Preface. If present, record the titles listed in the TOC to use as a semantic reference map during segmentation.
   - Detect header patterns. Determine whether major article titles are designated by `#` (Heading 1), `##` (Heading 2), or standard paragraphs formatted in bold.

### Step 3.2: Heuristic-Based Paper Segmentation (The Boundary Detection Loop)
Scan the Markdown document linearly from beginning to end. Locate transition boundaries by detecting the end of a paper's References section and the start of the next paper's header.

#### Transition Boundary Heuristic (Strong vs. Weak Signals)
```text
[End of Paper A]
...
[12] Vaswani, A., et al. "Attention is all you need." NeurIPS 2017.
------------------ BOUNDARY DETECTED ------------------
[Start of Paper B]
# Improving Low-Resource Machine Translation via Dynamic Sampling
Author One, Author Two
Department of Computer Science, University of Technology
{author1, author2}@university.edu

Abstract
Low-resource machine translation remains a significant challenge...
```

*   **Strong Termination Signal**: The presence of a `References`, `Bibliography`, or `Works Cited` header followed by numbered or alphabetical citations.
*   **Strong Initiation Signal**: A new section beginning with a title in Title Case, followed immediately by a block containing email addresses (`@`), university/corporate affiliations, and an **Abstract** header.
*   **Boundary Execution**: 
    - Cut the text segment immediately before the new Title header.
    - All bibliography entries belong to the preceding paper segment. Do not allow a bibliography to spill over into the next paper's Title block.

### Step 3.3: In-Context Feature Extraction per Segment
For each isolated paper text segment:
1. Extract the parsed title and author list.
2. Read the Abstract and Introduction sections to infer the precise research problem.
3. Apply the **Task-Oriented Definition** to formulate the problem:
   - **Formula**: `[Action/Objective] + in + [Domain/Context]`
   - *Correct*: "Acoustic Echo Cancellation in low-latency communication systems"
   - *Incorrect*: "Signal Processing" (Discipline, too broad), "Deep Learning" (Methodology, not a problem).

### Step 3.4: Semantic Clustering
1. Compare the extracted research problems. Group papers together if and only if they target the exact same core task and domain, even if phrased differently by different authors.
2. **Semantic Primacy Rule**: A cluster represents a specific, coherent research problem. Do not enforce numerical quotas on cluster sizes. If a compilation contains 4 papers on 4 entirely different subjects, generate exactly 4 clusters. Clusters of size 1 (orphan papers) are valid and must be preserved to prevent artificial semantic dilution.
3. Write the finalized standardized research problem name to the `research_problem` field of all papers in that cluster. This value acts as the authoritative `research_problem_hint` for downstream extraction agents.

## 4. Quality Gates & Red Flags

### Red Flags (What to Avoid)
*   🚩 **Over-segmentation**: Treating sections within a single paper (e.g., "Method" or "References") as separate articles.
*   🚩 **Artificial Clustering**: Forcing unrelated papers into a single generic cluster (like "Machine Learning") to satisfy a quota.
*   🚩 **Boundary Spillover**: Including the title and author block of the next paper inside the references list of the previous paper.

### Verification Steps
*   [ ] Verify that the sum of characters of all segmented papers equals the character length of the raw input text (excluding preface or index tables).
*   [ ] Confirm that every paper has at least a Title, an Author list, and a defined Research Problem.
*   [ ] Ensure that every cluster has a specific name representing a precise scientific problem, not a broad technology stack or discipline.