# MedService

Medical-domain AI toolkit built around a curated pediatric surgery and urology corpus.

## Planned Services

- **RAG Chat Agent** — question-answering over medical textbook PDFs with cited sources
- **Semantic Autocomplete** — field-aware medical term autocomplete with UMLS semantic type filtering

## Repository Structure

```
med-service/
├── services/              # Deployable service modules
│   ├── rag_chat_agent/
│   └── autocomplete/
├── shared/                # Libraries shared across services
├── scripts/               # Utility scripts
├── notebooks/             # Exploration notebooks
├── tests/                 # Tests
├── phases/                # Phase-by-phase implementation plans
├── data/                  # Corpus and processed outputs (NOT committed)
├── docker-compose.yml     # Qdrant + Redis only
└── pyproject.toml         # uv-managed Python 3.12 dependencies
```

## Quick Start

### 1. Environment

```bash
uv sync --extra all --group dev
```

### 2. Start local infrastructure

```bash
docker compose up -d
```

This starts Qdrant on port `6333` and Redis on port `6379`.

### 3. Verify

```bash
uv run python --version              # Python 3.12.x
uv run python -c "from shared.corpus_client import load_manifest; print(len(load_manifest()))"  # 24
uv run pytest                        # should pass
uv run ruff check .                  # should pass
```

### 4. Index the corpus (long-running)

```bash
# Test with one small source first
uv run reindex-source --source urodynamics_iaps --parser pymupdf --batch-size 32

# Index the full corpus (resume supported)
uv run reindex-all --parser pymupdf --batch-size 32
```

### 5. Configure API keys

Copy the example environment file and add your keys:

```bash
cp .env.example .env
# Edit .env and set at least one LLM key
```

### 6. Run services locally

```bash
# RAG Chat Agent (requires OPENAI_API_KEY, ANTHROPIC_API_KEY, or KIMI_API_KEY)
uv run uvicorn services.rag_chat_agent.api.main:app --reload --port 8000

# Semantic Autocomplete
uv run uvicorn services.autocomplete.api.main:app --reload --port 8001
```

Example requests:

```bash
curl http://localhost:8000/api/v1/health

# With OpenAI
OPENAI_API_KEY=sk-... curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"What are the first-line treatments for Type 2 Diabetes?"}'

# With Kimi Code
KIMI_API_KEY=Your_Kimi_Code_API_Key curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"What are the first-line treatments for Type 2 Diabetes?","model":"kimi-for-coding"}'

curl http://localhost:8001/api/v1/health

curl -X POST http://localhost:8001/api/v1/autocomplete \
  -H 'Content-Type: application/json' \
  -d '{"query":"myo","field_types":"T047,T191"}'
```

## Development Notes

- Python **3.12** managed by `uv`
- Local processing for PDF parsing, embedding, and NER
- Docker used only for Qdrant, Redis, and API integration testing
- Data under `data/` is never committed to Git
- PDF parsing uses **PyMuPDF** by default; **Marker** is included as an optional layout-preserving parser
- See `phases/` for detailed implementation plans
- See `AGENTS.md` for coding conventions and agent instructions

## Documentation

- `PRD.md` — Product Requirements Document
- `CONTEXT.md` — Project context and conventions
- `AGENTS.md` — Coding conventions and commands for agents
- `phases/phase_01_foundation.md` — Phase 1 plan
