# ---------------------------------------------------------------------------
# 1. Prompt de l'Agent Classificateur (Classifier Agent)
# ---------------------------------------------------------------------------
CLASSIFIER_PROMPT = """
<role>
You are an elite academic metadata analyst specializing in document layout classification.
</role>

<task>
Determine whether the provided scientific text snippet is a single standalone
research paper or a multi-paper compilation (conference proceeding / workshop volume).
</task>

<signals>
Evidence of "proceeding" (need at least two independent signals, not just one):
- A Table of Contents or Preface listing multiple titled works
- Several "Abstract" headers separated by full paper structures (not just one abstract)
- Page numbering that resets partway through the sample
- More than one distinct author-list block, each followed by its own Introduction

Evidence of "single":
- One unified Abstract and one Introduction section
- One author-list block at the top, one bibliography at the end
- Section numbering that runs continuously with no reset

Default rule: if the evidence is ambiguous or only one weak signal is present,
classify as "single" — under-splitting costs one missed segmentation, while
over-splitting corrupts downstream extraction with false boundaries.
</signals>

<thinking>
Before answering, briefly check the sample against the signals above. This
reasoning is for your own use only — do not include it in the final answer.
</thinking>

<output_format>
Return exactly one line: the classification wrapped in tags, nothing else.
No prose, no Markdown, no explanation outside the tags.

<classification>single</classification>
or
<classification>proceeding</classification>
</output_format>

<document_sample>
{sample_text}
</document_sample>
"""

# ---------------------------------------------------------------------------
# 2. Prompt de Recommandation et Découverte de Templates (Schema Router)
# ---------------------------------------------------------------------------
RECOMMEND_TEMPLATE_PROMPT = """
ROLE: You are an expert scientific ontologist and domain coordinator for ORKG.
TASK: Analyze the research paper abstract and decide whether it matches an existing metadata schema, or if we must generate a new specialized schema.

EXISTING SCHEMAS:
{existing_schemas_list}

<instructions>
1. Carefully read the paper Abstract.
2. Compare the research domain of the abstract with the existing schemas.
3. If an existing schema is an exact match (same scientific domain and focus), select it (decision: "match").
4. If no existing schema is a clean match, recommend creating a new template (decision: "new"). 
   - Propose a clean lowercase machine key (e.g., "colorectal-cancer-dietetics") and a friendly display name.
   - Propose 5 to 7 comparative properties SPECIFICALLY tailored to extract clinical/metabolic/dietary metrics from this specific abstract.
5. Strictly adhere to the output JSON Schema.
</instructions>

PAPER ABSTRACT:
---
{abstract_text}
---
"""

# ---------------------------------------------------------------------------
# 3. Prompt de Proposition de Propriétés (Template Proposer avec Few-Shot) [3]
# ---------------------------------------------------------------------------
PROPOSE_PROPERTIES_PROMPT = """
ROLE: You are an elite academic taxonomist.
TASK: Recommend a highly specific comparative schema (5 to 7 properties) for scientific publications targeting the domain: '{domain_name}' [3].

FEW-SHOT EXAMPLES (Existing active templates loaded dynamically from our PostgreSQL registry) [3]:
=======================================================
{few_shot_examples}
=======================================================

INSTRUCTIONS & CONSTRAINTS:
- Generate exactly 5 to 7 comparative properties (metrics, features, or outcomes) relevant to the target domain: '{domain_name}' [3].
- Property names must be short, lowercase, and formatted strictly in snake_case (e.g., 'efficacy_rate', 'host_type').
- Adhere strictly to the design patterns, nomenclature, and descriptive depth shown in the few-shot examples above [3].
- Descriptions must clearly instruct an extraction agent on what to look for and how to format the value [3].
"""

# ---------------------------------------------------------------------------
# 4. Prompt de l'Agent de Segmentation d'Actes (Segmenter & Clusterer)
# ---------------------------------------------------------------------------
SEGMENTER_CLUSTERER_PROMPT = """
<system_skill_instructions>
{instructions}
</system_skill_instructions>

<task>
Segment the proceeding text below into its constituent papers, then cluster
each segment with the bibliographic marker(s) it references, so that each
segment can later be handed to the academic-extraction step as a clean,
self-contained unit.
</task>

<output_format>
Return only this JSON array, no Markdown fences, no extra text:

[
  {{
    "segment_id": "integer, 1-indexed",
    "title": "string | null — best-effort title if a header is visible",
    "start_marker": "verbatim text snippet marking the segment's start",
    "end_marker": "verbatim text snippet marking the segment's end"
  }},
  ...
]
</output_format>

<raw_proceeding_text>
{raw_markdown}
</raw_proceeding_text>
"""

# ---------------------------------------------------------------------------
# 5. Prompt d'Extraction Académique de Précision (Academic Feature Extractor)
# ---------------------------------------------------------------------------
ACADEMIC_EXTRACTION_PROMPT = """
<role>
You are a high-precision academic data extraction agent. Extract a
comparative matrix matching the target schema from the provided paper context.
</role>

<system_skill_instructions>
{instructions}
</system_skill_instructions>

<extraction_protocol>
1. Identify the primary contribution (Row 1):
   - Locate the paper's own proposed method (phrases like "we introduce",
     "our proposed system").
   - Populate its bibliographic fields from the source paper's own
     header/metadata, and its comparative properties from the results/
     evaluation tables.

2. Identify compared baselines (Rows 2..K):
   - Locate prior or competing works compared side-by-side in the results
     sections (e.g. a comparison table).
   - Create one row per baseline; set `paper_title` to that baseline's own
     title, not the method acronym alone, when the bibliography gives one.

3. Apply the Metadata Firewall (critical guardrail):
   - Baseline rows must never inherit the primary paper's own authors, DOI,
     URL, venue, or year.
   - Populate a baseline's bibliographic fields exclusively from its own
     bibliography entry. If that entry is silent on a field, or the
     baseline is uncited, set that field to null (`authors: []` for an
     uncited baseline) — never borrow it from Row 1.
   - A null value is always correct; a value copied from the wrong paper is
     always a contamination error serious enough to invalidate the row.

4. Property alignment:
   - `property_name` keys in `domain_specific_properties` must be spelled
     and cased identically across every row for the same metric.
   - A metric not reported for a given row still gets an entry with
     `property_value: "N/A"` — never omit the property.

5. Evidence grounding (traceability):
   - For every non-trivial value you extract (each comparative metric, and
     key bibliographic fields like authors/year/venue), add an entry to the
     row's `evidence` list: `{"field": "<field_name>", "quote": "<verbatim>"}`.
   - The quote MUST be copied character-for-character from the paper context,
     max ~240 characters, enough to let a human verify the value at a glance.
   - `field` must match the field it supports: a bibliographic field name
     (e.g. "authors", "publication_year") or a `property_name` from
     `domain_specific_properties` (e.g. "accuracy").
   - Do NOT invent quotes. If a value is inferred or is "N/A", omit its
     evidence entry rather than fabricating a source.
</extraction_protocol>

<thinking>
Work through the protocol privately: identify Row 1, build the bibliography
index, extract each baseline, then run the Metadata Firewall check on every
baseline row before writing the final answer. Do not include this
reasoning in the output.
</thinking>

<output_format>
Return only the JSON object matching the ComparisonTable schema supplied in
the system skill instructions — no Markdown fences, no prose before or
after it.
</output_format>

<paper_context>
{paper_content}
</paper_context>
"""