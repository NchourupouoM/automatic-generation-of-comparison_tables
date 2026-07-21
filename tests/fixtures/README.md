# Gold fixtures — the ground-truth benchmark

Each `*.json` file here is **one input document plus its hand-verified correct
comparison table**. Together they form the benchmark the evaluation harness
scores the pipeline against.

> The files shipped with a `.example.json` name (and a `PLACEHOLDER` note in
> their description) are **scaffolding**. They exist so the harness runs on day
> one. Replace them with real, hand-verified examples — that curation *is* the
> valuable part of this contribution.

## How to add a real gold example

1. Pick a real paper (or proceeding PDF). Note its title and DOI.
2. Get its text: either drop the PDF under `tests/fixtures/pdfs/` and point
   `input.pdf` at it, or paste the extracted markdown into `input.raw_markdown`.
3. **By hand**, write the correct comparison table under `expected.tables` —
   the proposed method as the first row (`is_proposed_method: true`), then one
   row per baseline it is compared against. Fill only the fields you can verify
   from the paper; leave the rest out (a missing field counts as "no value").
4. Save as `tests/fixtures/<slug>.json` (drop the `.example` marker).

## Schema

```jsonc
{
  "id": "unique-slug",
  "description": "cite the source paper: title + DOI",
  "document_type": "single" | "proceeding",
  "domain": "default" | "<registered-template-id>",
  "input": {
    "raw_markdown": "…full text…"        // OR
    // "pdf": "tests/fixtures/pdfs/foo.pdf"
    // for a raw_markdown proceeding, raw_markdown may be a list of per-paper strings
  },
  "expected": {
    "tables": [
      {
        "research_problem": "…",
        "rows": [
          {
            "paper_title": "…",
            "is_proposed_method": true,
            "authors": ["…"],
            "publication_year": 2023,
            "venue": "…", "doi": "…",
            "domain_specific_properties": { "your_column": "value" }
          }
        ]
      }
    ]
  }
}
```

## Running the evaluation

```bash
# Real run — needs a configured LLM provider + API key in .env
python -m tests.eval.runner

# Wiring smoke test — no API key (produces deliberately wrong output)
python -m tests.eval.runner --fake

# Gate on a minimum aggregate cell-F1 (use in CI once real gold exists)
python -m tests.eval.runner --min-f1 0.7
```

The scorer itself (`tests/eval/scoring.py`) is pure and unit-tested in
`tests/test_scoring.py`, so metric definitions stay trustworthy.
