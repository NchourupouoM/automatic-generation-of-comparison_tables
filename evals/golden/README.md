# Golden dataset

Each file here is the **hand-verified correct comparison table** for one PDF in
`../pdfs/`. The runner matches them by filename:

```
evals/pdfs/arxiv_0708.2121v1.pdf   <->   evals/golden/arxiv_0708.2121v1.json
```

Only papers with a golden file are *scored* for accuracy. Every PDF (golden or
not) is still checked for structural invariants by `run_eval.py --smoke`, so the
whole 26-paper corpus works as a regression suite from day one.

## How to annotate a paper

1. Open the PDF and find the paper's main comparison/results table (the one that
   compares the proposed method against prior work).
2. Copy `_TEMPLATE.json` to `<pdf-stem>.json`.
3. Fill in:
   - `domain` — the machine key you'd expect (`protein-classification`, etc.).
   - `research_problem` — one sentence.
   - `rows` — row 0 is the paper's own method (`is_proposed_method: true`), the
     rest are the baselines it compares against. Put domain-specific columns in
     `properties`. Leave a field out (or `null`) if the paper doesn't report it —
     do **not** invent values.
4. Aim for ~10–15 annotated papers spanning your domains and at least one messy
   two-column / scanned PDF. Diversity matters more than volume.

## Scoring

`fields` = the paper title plus every key in `properties`, per row. The runner
reports field-level precision/recall/F1 and row recall, using fuzzy string
matching (85% similarity) so trivial whitespace/casing differences don't count
as misses. See `../scoring.py`.
