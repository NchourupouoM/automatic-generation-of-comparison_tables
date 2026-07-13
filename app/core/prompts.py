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
<role>
You are an expert scientific ontologist and domain coordinator.
</role>

<task>
Decide whether this paper's abstract matches an existing metadata schema, or
whether a new specialized schema must be generated for its domain.
</task>

<existing_schemas>
{existing_schemas_list}
</existing_schemas>

<matching_rule>
A schema counts as a match only if it targets the same specific sub-domain
and evaluation focus as the abstract — not merely the same broad field.
"Object detection" and "instance segmentation" both sit under "Computer
Vision" but are not a match for each other, because their comparative
metrics differ (mAP/IoU vs. panoptic quality). When unsure, prefer creating
a new schema over forcing a loose fit — a schema with the wrong metrics is
worse than one extra schema.
</matching_rule>

<thinking>
Identify the abstract's specific research problem and its likely evaluation
metrics first. Only then compare against each existing schema's stated
scope. Keep this reasoning private.
</thinking>

<output_format>
Return only this JSON object, no Markdown fences, no extra text:

{{
  "action": "use_existing" | "create_new",
  "schema_id": "string | null",       // set when action == use_existing, else null
  "domain_name": "string | null",     // set when action == create_new, else null
  "rationale": "one sentence, no more"
}}
</output_format>

<paper_abstract>
{abstract_text}
</paper_abstract>
"""

# ---------------------------------------------------------------------------
# 3. Prompt de Proposition de Propriétés (Template Proposer)
# ---------------------------------------------------------------------------
PROPOSE_PROPERTIES_PROMPT = """
<role>
You are an elite academic taxonomist.
</role>

<task>
Propose a comparative metadata schema for scientific publications in the
domain: '{domain_name}'.
</task>

<constraints>
- Exactly 5 to 7 properties — no more, no fewer.
- `name`: short, lowercase, snake_case (e.g. "detection_latency", "dataset_size").
- `description`: tells an extraction agent precisely what to look for and how
  to format the value (units, expected type, where in the paper it usually appears).
- Prefer metrics that are commonly reported across most papers in this
  domain over ones specific to a single method, so the schema stays
  comparable across many papers later.
</constraints>

<example>
Domain: "Acoustic Echo Cancellation"
Properties:
- name: "erle_db", description: "Echo Return Loss Enhancement (ERLE), reported in decibels (dB)."
- name: "real_time_factor", description: "Real-time factor or processing-speed metric reported, as a unitless ratio."
</example>

<output_format>
Return only this JSON array, no Markdown fences, no extra text:

[
  {{ "name": "snake_case_property", "description": "what to look for and how to format it" }},
  ...
]
</output_format>
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