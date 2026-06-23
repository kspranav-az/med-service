# Phase 1: Foundation

## Goal
Set up the local development environment and project skeleton so that RAG and autocomplete development can proceed cleanly.

## Duration
Week 1

## Prerequisites
- MacBook Air M5 16GB
- `uv` installed
- Python 3.12 available
- Docker Desktop installed (for Qdrant + Redis only)
- `data/corpus/` contains 24 pediatric PDFs and `manifest.json`

## Tasks

### 1. Environment Setup
- Remove old Python 3.9 `.venv`
- Initialize `uv` project with Python 3.12
- Create root `pyproject.toml` with core dependencies:
  - FastAPI, Uvicorn, Pydantic
  - Qdrant client, Redis client
  - sentence-transformers, transformers, torch
  - pypdf / pymupdf
  - SciSpaCy models (`en_ner_bc5cdr_md`, `en_core_sci_lg`)
  - Langfuse, RAGAS
  - pytest, ruff, mypy

### 2. Repository Structure
Create the following layout:

```
med-service/
├── services/
│   ├── rag_chat_agent/
│   │   ├── api/
│   │   ├── service/
│   │   └── tests/
│   └── autocomplete/
│       ├── api/
│       ├── service/
│       └── tests/
├── shared/
│   ├── ingestion/
│   ├── chunking/
│   ├── embeddings/
│   ├── vector_store/
│   ├── cache/
│   ├── models/
│   ├── rate_limit/
│   ├── observability/
│   └── corpus_client.py
├── scripts/
├── tests/
├── notebooks/
├── phases/
├── docker-compose.yml
├── pyproject.toml
├── .gitignore
├── README.md
├── CONTEXT.md
├── PRD.md
└── AGENTS.md
```

### 3. Docker Compose
Create `docker-compose.yml` with:
- Qdrant (port 6333, persisted volume)
- Redis (port 6379)
- No Python/FastAPI services in Docker yet

### 4. Shared Components
- Manifest loader (`data/corpus/manifest.json`)
- Config management (pydantic-settings)
- Logging setup (structured JSON logs)
- Shared Pydantic models:
  - `Source`, `Chunk`, `Entity`, `Citation`
  - `ChatRequest`, `ChatResponse`
  - `AutocompleteRequest`, `AutocompleteResponse` (with nullable `cui`/`tuis`)

### 5. Observability Setup
- Create Langfuse project (Cloud free tier)
- Add Langfuse client wrapper in `shared/observability/`
- Add basic tracing decorator

### 6. Documentation
- Update `AGENTS.md` with project conventions
- Update `README.md` with setup instructions

## Key Considerations

- **Keep `shared/` domain-agnostic.** Do not put RAG-specific logic there.
- **Data is never committed.** `data/` is already in `.gitignore`.
- **Use Protocol/ABC for swappable components** (e.g., entity provider, embedding model).
- **MPS is optional.** Test that CPU fallback works before relying on MPS.
- **Docker is only for infra.** Do not put preprocessing or embedding workers in Docker yet.

## Status

✅ Completed.

## Verification Checklist

- [x] `uv run python --version` returns Python 3.12
- [x] `docker compose up` starts Qdrant and Redis successfully
- [x] `python -c "from shared.corpus_client import load_manifest; print(len(load_manifest()))"` prints 24
- [x] Qdrant is reachable at `http://localhost:6333`
- [x] Redis is reachable at `redis://localhost:6379`
- [x] `pytest` runs without import errors
- [x] `ruff check .` passes on new code
- [x] `.gitignore` excludes `data/`, `.venv/`, `.DS_Store`, and local infra volumes

## Outputs / Deliverables

1. `pyproject.toml`
2. `docker-compose.yml`
3. `shared/` module skeleton
4. `services/rag_chat_agent/` and `services/autocomplete/` skeletons
5. Updated `AGENTS.md` and `README.md`
6. Working Qdrant + Redis local stack
