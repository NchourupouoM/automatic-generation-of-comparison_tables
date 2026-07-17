# Scientific Content Extractor

A modular, domain-driven agentic framework designed to parse and extract structured comparative data from scientific literature. 

The system leverages **LangGraph** for granular multi-agent orchestration, **FastAPI** for REST endpoints, **Celery/Redis** for resilient asynchronous task queuing, **PostgreSQL** for persistence (templates, tasks, and results), and a **vanilla-JS single-page UI** served as static files. It natively conforms to the open **agentskills.io** specification for dynamic, file-based skill injection.

---

## 1. Architectural Blueprint & Core Philosophy

The system's core objective is to extract comparative matrices from scientific texts. Instead of relying on a monolithic extraction prompt (which frequently suffers from context leakage, baseline misattribution, and metrics halluncinations), this project splits tasks across highly specialized, atomic agents.

```mermaid
flowchart TD
    %% Nodes Definition
    A[PDF Ingestion <br> PyMuPDF4LLM]
    B[Scale Classification]
    
    C[Proceeding <br> D_proc]
    D[Single Paper <br> D_single]
    
    E[Segment & Cluster]
    F[Domain Registry Routing]
    
    G[Default Domain <br> Baseline Extraction]
    H[Custom Domain <br> e.g., Infectious Disease]
    
    I[Map-Reduce <br> Parallel Extraction]
    J[Joint Academic <br> Feature Extraction]
    
    K[Dynamic Table <br> Synthesis & CSV]

    %% Connections
    A --> B
    
    B --> C
    B --> D
    
    C --> E
    E --> I
    
    D --> F
    
    F --> G
    F --> H
    
    G --> J
    H --> J
    
    I --> K
    J --> K

    %% Styling
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style K fill:#bbf,stroke:#333,stroke-width:2px
    style B fill:#ffd27f,stroke:#333,stroke-width:1px
    style F fill:#ffd27f,stroke:#333,stroke-width:1px
```

### Key Design Principles

1. **One Task per Agent**: Each node in the execution graph has a single, isolated cognitive responsibility (e.g., identifying baseline names, extracting tabular row data, or grouping papers).
2. **Dynamic Domain Customization (The Template Pattern)**: The system is easily extensible. You can define a target scientific domain (e.g., `infectious-disease`) by registering a specific Pydantic schema and writing a markdown instruction set (`SKILL.md`). The orchestrator dynamically routes and loads these files at runtime.
3. **Strict Non-Inheritance**: To avoid context leakage, baseline rows do not inherit metadata (authors, DOIs, URLs, or venues) from the primary proposed paper unless explicitly cited.
4. **Model-Agnostic LLM Interface**: Through LangChain integrations, the backend is decoupled from any specific model provider. It supports OpenAI, Anthropic, or local LLMs (via Ollama) interchangeably.

---

## 2. Directory Structure

This project follows Clean Code and Domain-Driven Design (DDD) principles:

```text
automatic-generation-of-comparison_tables/
├── app/
│   ├── api/
│   │   └── endpoints.py         # FastAPI routes (/ingest, /tasks, /templates, ...)
│   ├── core/
│   │   ├── celery_app.py        # Celery client initialization
│   │   ├── config.py            # Environment validation (pydantic-settings)
│   │   ├── database.py          # SQLAlchemy engine, session factory, Base
│   │   ├── models.py            # Relational models (templates, tasks, tables, rows)
│   │   ├── dynamic_loader.py    # Compiles Pydantic table models from DB templates
│   │   ├── llm_factory.py       # Model-agnostic LLM initializer (lazy provider imports)
│   │   ├── parse_pdf.py         # Programmatic PDF extraction & proceeding splitting
│   │   ├── prompts.py           # Isolated agent prompt templates
│   │   ├── schemas.py           # Core Pydantic output schemas
│   │   ├── skills_loader.py     # agentskills.io metadata parser
│   │   └── utils.py             # Shared helpers (domain slugification)
│   ├── services/
│   │   ├── orchestrator.py      # LangGraph state machine & node agents
│   │   └── tasks.py             # Celery task entrypoints
│   ├── static/                  # Vanilla-JS single-page UI (index.html, app.js, style.css)
│   └── main.py                  # FastAPI entrypoint + static mount
├── skills/                      # agentskills.io dynamic skills (SKILL.md per domain)
├── evals/                       # Evaluation harness
│   ├── pdfs/                    # 26-paper regression corpus
│   ├── golden/                  # Hand-verified ground-truth tables (+ _TEMPLATE.json)
│   ├── scoring.py               # Field-level precision/recall/F1 scoring
│   ├── invariants.py            # Structural correctness checks (no golden needed)
│   └── run_eval.py              # End-to-end runner (--smoke for corpus-wide invariants)
├── tests/                       # Offline, deterministic pytest suite
├── .github/workflows/
│   ├── ci.yml                   # Lint + tests on PRs and feature branches
│   └── gcp-deploy.yml           # Test-gated build & deploy to Cloud Run on main
└── requirements.txt             # Project dependencies
```

---

## 3. Dynamic Domain Extensibility

Domains are **data, not code**. Their schemas live in the PostgreSQL `templates`
table and are compiled into validated Pydantic models at runtime by
`app/core/dynamic_loader.py` — there is no code registry to edit. There are two
ways to add a domain:

### Path A: Human-in-the-Loop (no code, the default)
Ingest a paper with `domain=default`. The pipeline infers the scientific domain,
the **Template Proposer** agent suggests comparative properties, and the API
returns them for human review (`PENDING_SCHEMA_VALIDATION`). Approving them via
`POST /api/v1/tasks/{id}/validate-schema` persists the new template, which is
then reused automatically for every future paper in that domain.

### Path B: Author an extraction Skill (optional, for domain heuristics)
To give the extractor domain-specific guidance, add an agentskills.io skill:
create `skills/<your-domain>/SKILL.md` with YAML frontmatter and step-by-step
instructions. The extractor resolves `skills/{domain}` at runtime and falls back
to `skills/academicextraction` when no matching skill exists.

```markdown
---
name: yourdomainextraction
description: Explain when to trigger this domain skill.
metadata:
  - version: 1.0.0
---
# Skill: Your Domain Extraction Guidelines
Provide detailed clinical/scientific heuristics for parsing.
```

Both the orchestrator and the web UI pick up new templates and skills without
any further code changes.

---

## 4. Setup & Local Installation

### Prerequisites
*   Python 3.11 or 3.12
*   Docker (recommended for running Redis)
*   An API key for your chosen LLM provider (or a running Ollama instance)

### 1. Environment Activation
```bash
# Clone the repository and navigate to its root directory
git clone https://github.com/NchourupouoM/automatic-generation-of-comparison_tables.git
cd scientific-paper-content-extractor

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Variables
Create a local `.env` file at the project root with your configuration:
```env
DATABASE_URL=postgresql://user:pass@localhost:5432/extractor
REDIS_URL=redis://localhost:6379/0
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o
# LLM_PROVIDER=ollama
# LLM_MODEL_NAME=llama
OPENAI_API_KEY=your-openai-api-key
```
`DATABASE_URL` is required (the app validates it at startup); the tables are
auto-created on first boot via `Base.metadata.create_all`.

### 4. Start Services (Requires 3 Terminals)

#### Terminal 1: Run Redis
```bash
docker run --name redis-extractor -p 6379:6379 -d redis
```

#### Terminal 2: Run Celery Worker
```bash
celery -A app.core.celery_app:celery_app worker --loglevel=info
# On Windows, add '-P solo' if you experience execution loops:
# celery -A app.core.celery_app:celery_app worker --loglevel=info -P solo
```

#### Terminal 3: Run FastAPI App
```bash
uvicorn app.main:app --reload --port 8000
```

---

## 5. Running and Testing the Pipeline

### Testing with the Web UI
Once the FastAPI app is running, open `http://localhost:8000/` — the vanilla-JS
single-page UI is served directly from `app/static`.
*   Drop a PDF of a paper or a proceeding.
*   Pick a registered **Domain Template**, or leave it on **default** to trigger
    the human-in-the-loop schema proposal flow.
*   Start the extraction; the page polls the task and renders the final
    comparative matrix as a flat table.

### Testing with cURL (API Mode)

1. **Ingest a Paper** (Example for Infectious Disease):
   ```bash
   curl -X POST "http://localhost:8000/api/v1/ingest" \
     -F "file=@/path/to/your/infectious_disease_paper.pdf" \
     -F "document_type=single" \
     -F "domain=infectious-disease"
   ```
   **Response**:
   ```json
   {
     "task_id": "84a37bde-3456-4cde-a12e-1234567890ab",
     "status": "PROCESSING",
     "detail": "Direct extraction initiated for domain 'infectious-disease'."
   }
   ```

2. **Poll for the Status & Consolidated Results**:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/tasks/84a37bde-3456-4cde-a12e-1234567890ab"
   ```

### API security (optional)
Set `API_KEY` in your environment to require an `X-API-Key` header on all
mutating endpoints (`/ingest`, `/validate-schema`, `/resume-with-existing-template`,
`/decline`). When unset, the API stays open for local development.
```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "X-API-Key: $API_KEY" -F "file=@paper.pdf" -F "domain=default"
```

### Pagination
List endpoints (`/comparisons`, `/templates`, `/validation-tasks`) accept
`?limit=&offset=` and return `{total, limit, offset, ...}`. `limit` defaults to
`DEFAULT_PAGE_SIZE` and is capped at `MAX_PAGE_SIZE`.

---

## 6. Quality: Tests & Evaluation

The project ships with two independent quality layers.

### Unit tests (offline, deterministic — no LLM/DB/network)
```bash
pip install pytest ruff
ruff check app evals tests
pytest -q
```
These cover PDF splitting, the skills loader, dynamic model compilation, domain
slugification, proceeding-segment boundary logic, and the eval scoring/invariant
libraries. They run on every push and pull request via `.github/workflows/ci.yml`,
and gate the production deploy in `gcp-deploy.yml`.

### Evaluation harness (measures extraction quality)
`evals/` contains a 26-paper regression corpus (`evals/pdfs/`) and a scoring
framework that turns "the prompts seem to work" into a measured number.

```bash
# Structural invariants across the whole corpus (needs LLM creds + DB, no golden):
python -m evals.run_eval --smoke

# Field-level precision/recall/F1 against hand-verified golden tables:
python -m evals.run_eval
```

To score accuracy, annotate papers by copying `evals/golden/_TEMPLATE.json` to
`evals/golden/<pdf-stem>.json` and filling in the correct table — see
`evals/golden/README.md`. Papers without a golden file are still checked for
structural correctness (exactly one proposed row, no author leakage onto
baselines, well-formed DOIs, non-empty titles).

---

## 7. Contribution Standards & Code Quality

To keep the project maintainable and robust, contributors must adhere to the following rules:
*   **Strong Typing**: All payloads must be strictly validated using Pydantic. Avoid arbitrary `dict` returns.
*   **Strict Non-Inheritance**: Ensure that any new extraction skill strictly instructs the agent not to copy coordinates of the main paper onto baselines.
*   **Agnostic LLM Binding**: Do not instantiate LLM clients directly inside the skills or services. Always request them from `LLMFactory.get_llm()` to ensure interoperability across model providers.
*   **Green CI**: New code must pass `ruff check` and `pytest`. Add tests for any new deterministic logic, and an eval golden file when you add a domain you can verify.