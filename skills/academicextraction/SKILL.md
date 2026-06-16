---
name: academicextraction
description: >
  Extract bibliographic metadata, the proposed method (primary contribution),
  and all compared baselines from a scientific paper into a single validated
  ComparisonTable. Trigger when users ask to "compare this paper", "extract
  the baselines", "analyze the results compared to other models", "extract the
  performance metrics of the proposed method and its competitors", "add this
  paper to my table", or "what did they benchmark against". Also trigger when
  receiving a clean paper segment from the structuralclustering skill. For
  multi-paper inputs (proceedings, bulk PDFs), always run structuralclustering
  first, then call this skill once per segment.
compatibility: >
  Python 3.10+. Requires a structured JSON-mode LLM output to guarantee schema
  compliance. No external libraries required beyond schemas.py.
metadata:
  - version: 3.0.0
---

# Skill: High-Precision Joint Comparative Academic Extraction

## 1. Overview & Operational Goal

The primary failure mode of standard academic extraction is **metadata
contamination**: copying bibliographic fields (authors, venue, DOI, year,
proceeding title) from the source paper onto baseline rows. This is **always
wrong**. Every baseline is an independent published work with its own authors,
venue, and year. Those values must come exclusively from the citation entry of
that baseline in the source paper's bibliography — never from the source paper
itself.

The final output is a single `ComparisonTable` object: one `research_problem`
shared by all rows, and one `ComparisonRow` per method (proposed + each baseline).

---

## 2. The Metadata Firewall Rule (Critical — Read First)

> ⛔ **METADATA FIREWALL**: Fields `authors`, `venue`, `publication_year`,
> `publication_month`, `doi`, `url`, and `proceeding_title` are
> **bibliographically scoped**. They describe the publication where a method
> was first presented — not the paper you are currently reading.
>
> For Row 1 (proposed method): populate from the source paper's own header.
> For Rows 2..K (baselines): populate **exclusively** from the corresponding
> bibliography entry in the source paper. If the bibliography entry does not
> provide a field, set it to `null`. Never copy Row 1's values into any
> baseline row.

This rule supersedes any instruction to "fill in" missing fields. A `null`
is always correct. A copied value from the wrong paper is always wrong.

**Concrete example of the violation to avoid:**

The paper "Attention Is All You Need" (Vaswani et al., NIPS 2017) compares
against ConvS2S (Gehring et al., ICML 2017). The following is **forbidden**:

```
❌ WRONG — metadata from source paper copied to baseline row
ConvS2S row: authors = ["Vaswani", "Shazeer", ...], venue = "NIPS", year = 2017
```

```
✅ CORRECT — metadata from ConvS2S's own bibliography entry
ConvS2S row: authors = ["Jonas Gehring", "Michael Auli", ...], venue = "ICML", year = 2017
```

---

## 3. Input / Output Contract

### 3.1 Input

| Field | Type | Description |
|---|---|---|
| `paper_text` | `str` | UTF-8 Markdown text of a single paper or clean segment from `structuralclustering` |
| `research_problem_hint` | `str \| null` | Authoritative problem string from upstream clustering. If provided, use it verbatim — do not re-infer. |

### 3.2 Output — `ComparisonTable`

The skill must return exactly **one** `ComparisonTable` object. No other
wrapping or list structure is permitted.

```json
{
  "research_problem": "string — shared across all rows",
  "rows": [
    {
      "proceeding_title":           "string | null",
      "paper_title":                "string (required)",
      "authors":                    ["string"],
      "publication_month":          "string | null",
      "publication_year":           "integer | null",
      "venue":                      "string | null",
      "research_field":             "string | null",
      "doi":                        "string | null",
      "url":                        "string | null",
      "research_problem":           "string (required) — identical to table-level field",
      "research_method":            "string | null",
      "domain_specific_properties": [
        { "property_name": "snake_case_key", "property_value": "exact string from paper" }
      ]
    }
  ]
}
```

> ⚠️ `domain_specific_properties` is **always a list of `{property_name, property_value}`
> objects** — never a flat dict `{"key": "value"}`. Required for strict JSON Schema compliance.

---

## 4. Step-by-Step Procedure

### Step 4.1 — Identify the Source Paper's Full Title

Before any extraction, locate the **full bibliographic title** of the source
paper at the top of page 1. This is the complete sentence-length title of the
work (e.g., *"Attention Is All You Need"*), not the name of the architecture
or method it proposes (e.g., *"Transformer"*).

> 🔑 **Title vs. Method Name**: The paper's title and the name of its proposed
> method are often different. "Attention Is All You Need" proposes the
> "Transformer". "EfficientDet: Scalable and Efficient Object Detection"
> proposes "EfficientDet". The `paper_title` field in Row 1 must contain
> the full paper title. The `research_method` field contains the method name.

### Step 4.2 — Establish the Research Problem Context

1. Check whether a `research_problem_hint` is provided in the input.
2. **Authority Rule**: If a hint is supplied, assign it verbatim to the table's
   `research_problem` and to every row. Do not re-infer or rewrite it.
3. If no hint is provided, infer the research problem from Abstract and
   Introduction. Apply the Task-Oriented Definition:
   - **Formula**: `[Action/Objective] + in + [Domain/Context]`
   - ✅ `"Neural Machine Translation for English-German language pairs"`
   - ✅ `"Acoustic Echo Cancellation in low-latency communication systems"`
   - ❌ `"Signal Processing"` — discipline, too broad
   - ❌ `"Deep Learning"` — methodology, not a problem
   - ❌ `"Transformer fine-tuning"` — describes the solution, not the problem

### Step 4.3 — Extract the Proposed Method (Row 1)

Locate the paper's primary contribution. Look for phrases such as:
*"We propose…"*, *"Our method, named…"*, *"In this work, we introduce…"*.

Populate Row 1 **exclusively from the source paper's own header and metadata**:

| Field | Where to find it |
|---|---|
| `paper_title` | Page 1 header — **full title of the paper**, not the method name |
| `authors` | Page 1, after title — one string per person |
| `proceeding_title` | Cover page or running header — parent volume name |
| `venue` | Header, footer, or acknowledgements — e.g. `"NIPS"`, `"CVPR"` |
| `publication_year` | Date line or copyright — integer |
| `publication_month` | Date line — e.g. `"June"` or null if absent |
| `doi` | First page or bibliography — prefer over URL |
| `url` | First page — fallback if no DOI |
| `research_field` | Keywords or abstract — broad discipline |
| `research_method` | Abstract + Method section — architecture or approach name |

### Step 4.4 — Build the Bibliography Index

Before extracting any baseline, **parse the entire References / Bibliography
section** of the source paper into an index:

```
bibliography_index = {
  "[1]": { authors: [...], title: "...", venue: "...", year: ..., doi: "...", url: "..." },
  "[2]": { ... },
  ...
}
```

This index is the **sole authorised source** for baseline bibliographic data.
Any field not present in a bibliography entry must be set to `null` — do not
infer, guess, or borrow from other rows.

### Step 4.5 — Identify and Extract Baselines (Rows 2 to K+1)

Navigate to sections labeled **Experiments**, **Evaluation**, **Results**,
**Baselines**, or **Comparative Study**. For each named model evaluated
side-by-side with the proposed method:

1. **Note its citation key** (e.g., `[14]`, `[Gehring et al., 2017]`).
2. **Look up `bibliography_index[citation_key]`** to retrieve its metadata.
3. Populate the baseline row using **only** data from that bibliography entry.

Apply the **Baseline Data Protocol**:

| Scenario | `paper_title` | `authors` | `venue` / `year` |
|---|---|---|---|
| Cited baseline with bibliography entry | Title from bib entry | Authors from bib entry | Venue and year from bib entry |
| Cited baseline — bib entry has partial info | Title from bib | Available fields only | Missing fields → `null` |
| Informal/uncited baseline (e.g. "vanilla LSTM") | Descriptive label e.g. `"Vanilla LSTM baseline"` | `[]` | `null` / `null` |

> ⛔ **Isolation Enforcement**: After populating a baseline row from its
> bibliography entry, verify that **none** of its bibliographic fields
> (`authors`, `venue`, `publication_year`, `doi`, `proceeding_title`) match
> Row 1 identically unless the baseline was genuinely published in the same
> paper (co-contribution). If they do match, treat it as a contamination error
> and re-extract from the bibliography.

### Step 4.6 — Extract and Align Domain-Specific Properties

Identify evaluation metrics from the paper's results tables and figures
(e.g., BLEU, F1-Score, Latency, Parameters, mAP).

For each row, populate `domain_specific_properties` as a list of
`{property_name, property_value}` objects. The **Strict Alignment Rule**:
every row must use the **exact same `property_name` spelling, casing, and
unit format**.

✅ Aligned (correct):
```json
Row 1: { "property_name": "BLEU_En-De", "property_value": "28.4" }
Row 2: { "property_name": "BLEU_En-De", "property_value": "26.36" }
```

❌ Misaligned (forbidden):
```json
Row 1: { "property_name": "Bleu_en_de", "property_value": "28.4" }
Row 2: { "property_name": "bleu_ende",  "property_value": "26.36" }
```

**Rules for `property_value`:**
- Copy verbatim from the paper: `"28.4"`, `"3.5 days on 8 P100 GPUs"`
- If a baseline's value for a metric is not reported, set `property_value` to
  `"N/A"` — do not omit the property or invent a number
- Aim for 3–8 properties per row; cap at 10
- Use the paper's results table as the authoritative source over the abstract

---

## 5. Worked Example — "Attention Is All You Need"

**Source paper**: Vaswani et al., "Attention Is All You Need", NIPS 2017.
Baselines include ConvS2S (Gehring et al., ICML 2017) and GNMT+RL (Wu et al., 2016).

```json
{
  "research_problem": "Neural Machine Translation for English-German and English-French",
  "rows": [
    {
      "proceeding_title": "31st Conference on Neural Information Processing Systems (NIPS 2017)",
      "paper_title": "Attention Is All You Need",
      "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit",
                  "Llion Jones", "Aidan N. Gomez", "Łukasz Kaiser", "Illia Polosukhin"],
      "publication_month": null,
      "publication_year": 2017,
      "venue": "NIPS",
      "research_field": "Natural Language Processing",
      "doi": null,
      "url": "https://arxiv.org/abs/1706.03762",
      "research_problem": "Neural Machine Translation for English-German and English-French",
      "research_method": "Transformer — encoder-decoder with multi-head self-attention and no recurrence",
      "domain_specific_properties": [
        { "property_name": "BLEU_En-De", "property_value": "28.4" },
        { "property_name": "BLEU_En-Fr", "property_value": "41.8" },
        { "property_name": "training_time", "property_value": "3.5 days on 8 P100 GPUs" },
        { "property_name": "training_cost_FLOPs", "property_value": "3.3 · 10^18" },
        { "property_name": "parallelizable", "property_value": "Yes — no sequential dependency" },
        { "property_name": "...", "property_value": "..." }
      ]
    },
    {
      "proceeding_title": null,
      "paper_title": "Convolutional Sequence to Sequence Learning",
      "authors": ["Jonas Gehring", "Michael Auli", "David Grangier", "Denis Yarats", "Yann N. Dauphin"],
      "publication_month": null,
      "publication_year": 2017,
      "venue": "ICML",
      "research_field": "Natural Language Processing",
      "doi": null,
      "url": "https://arxiv.org/abs/1705.03122",
      "research_problem": "Neural Machine Translation for English-German and English-French",
      "research_method": "Convolutional sequence-to-sequence model (ConvS2S)",
      "domain_specific_properties": [
        { "property_name": "BLEU_En-De", "property_value": "26.36" },
        { "property_name": "BLEU_En-Fr", "property_value": "40.46" },
        { "property_name": "training_time", "property_value": "9.5 days on 32 GPUs" },
        { "property_name": "training_cost_FLOPs", "property_value": "1.5 · 10^20" },
        { "property_name": "parallelizable", "property_value": "Yes" },
        { "property_name": "...", "property_value": "..." }
      ]
    },
    {
      "proceeding_title": null,
      "paper_title": "Google's Neural Machine Translation System: Bridging the Gap between Human and Machine Translation",
      "authors": ["Yonghui Wu", "Mike Schuster", "Zhifeng Chen", "Quoc V. Le", "Mohammad Norouzi"],
      "publication_month": null,
      "publication_year": 2016,
      "venue": "arXiv",
      "research_field": "Natural Language Processing",
      "doi": null,
      "url": "https://arxiv.org/abs/1609.08144",
      "research_problem": "Neural Machine Translation for English-German and English-French",
      "research_method": "GNMT — LSTM-based encoder-decoder with RL fine-tuning",
      "domain_specific_properties": [
        { "property_name": "BLEU_En-De", "property_value": "26.30" },
        { "property_name": "BLEU_En-Fr", "property_value": "41.16" },
        { "property_name": "training_time", "property_value": "N/A" },
        { "property_name": "training_cost_FLOPs", "property_value": "3.3 · 10^18" },
        { "property_name": "parallelizable", "property_value": "Limited — sequential recurrence" },
        { "property_name": "...", "property_value": "..." }
      ]
    }
  ]
}
```

> Notice: each baseline row has **distinct authors, venue, and year** sourced
> from the bibliography. No field from the Vaswani et al. row appears in
> baseline rows unless independently verified as correct.

---

## 6. Handling Missing or Ambiguous Data

| Situation | Action |
|---|---|
| Metric present in text but no numeric value | Use quoted text as `property_value` |
| Baseline metric not reported in the paper | `property_value: "N/A"` — never omit |
| Bibliography entry has no year | `publication_year: null` |
| No evaluation section (survey/position paper) | `domain_specific_properties: []`, `research_method: "Survey"` |
| Conflicting numbers between abstract and results table | Use results table value |
| Informal baseline with no citation | `authors: []`, `doi: null`, `publication_year: null` |
| Baseline cited but bibliography entry not found | Extract what is inferable from inline citation text; set remaining fields to `null` |

---

## 7. Quality Gates

### Pre-emission checklist
- [ ] Row 1 `paper_title` is the **full title of the paper**, not the method name
- [ ] Output is a single `ComparisonTable`, not a bare list of rows
- [ ] Row 1 represents the proposed contribution, not a baseline
- [ ] All rows share the exact same `research_problem` string
- [ ] Every baseline row's `authors`, `venue`, `year` come from its bibliography entry — verified against bibliography index built in Step 4.4
- [ ] No baseline row has fields identical to Row 1 unless confirmed co-authored (contamination check)
- [ ] `domain_specific_properties` is a list of `{property_name, property_value}` objects — never a flat dict
- [ ] All `property_name` values are identically spelled and cased across every row
- [ ] No `property_value` was invented — every number traces to the source text
- [ ] Informal baselines have `authors: []` and `doi: null`

### Red flags
- 🚩 **Metadata contamination**: baseline row has same `authors`/`venue`/`year` as Row 1 — re-extract from bibliography
- 🚩 **Title is method name**: `paper_title: "Transformer"` instead of `"Attention Is All You Need"`
- 🚩 **Flat dict in `domain_specific_properties`**: `{"Accuracy": "94%"}` instead of `[{"property_name": "Accuracy", "property_value": "94%"}]`
- 🚩 **Metric swapping**: proposed method score assigned to a baseline row
- 🚩 **Hallucinated coordinates**: invented DOIs, authors, or years for informal baselines
- 🚩 **Key drift**: `"BLEU_En-De"` in Row 1 becoming `"bleu_ende"` in Row 2
- 🚩 **Missing proposed method row**: extraction contains only baseline rows
- 🚩 **Identical `proceeding_title` across all rows**: proceedings belong to the source paper only; baselines published elsewhere will have different or null proceeding titles