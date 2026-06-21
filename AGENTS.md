# Agent Instructions

This file contains conventions and commands for coding agents working on the **MedService** project.

## Project Overview

MedService is a medical-domain AI toolkit with two main services:

- **RAG Chat Agent** — retrieval-augmented question answering over a pediatric surgery/urology PDF corpus.
- **Semantic Autocomplete** — field-aware medical term autocomplete with UMLS semantic type filtering.

## Toolchain

- **Python:** 3.12+ (managed by `uv`)
- **Package manager:** `uv` (do not use `pip` directly)
- **Virtual environment:** `.venv/` at the project root (created automatically by `uv`)
- **Infra (Docker only):** Qdrant and Redis via `docker compose up -d`
- **Runtime:** FastAPI + Uvicorn, run directly on the host during development

## Standard Commands

```bash
# Install all dependencies
uv sync --extra all --group dev

# Run the linter and formatter
uv run ruff check .
uv run ruff format .

# Run type checks (optional but encouraged)
uv run mypy shared/ services/

# Run tests
uv run pytest

# Start local infrastructure
docker compose up -d

# Start services locally
uv run uvicorn services.rag_chat_agent.api.main:app --reload --port 8000
uv run uvicorn services.autocomplete.api.main:app --reload --port 8001
```

## Project Structure

- `services/` — Deployable FastAPI services. Each service has its own `api/` package.
- `shared/` — Domain-agnostic libraries used by both services. **Do not put RAG-specific logic here.**
  - `shared/models/` — Shared Pydantic models and API contracts.
  - `shared/config.py` — Environment-based settings via Pydantic Settings.
  - `shared/logging.py` — Structured JSON logging.
  - `shared/corpus_client.py` — Corpus manifest loader and path resolver.
  - `shared/observability/` — Langfuse tracing wrapper with no-op fallback.
- `tests/` — Pytest test suite.
- `scripts/` — Utility scripts.
- `notebooks/` — Exploration notebooks.
- `phases/` — Phase-by-phase implementation plans.
- `data/` — Corpus and processed outputs. **Never committed.**

## Coding Conventions

- Follow PEP 8 and the project's `ruff` configuration.
- Line length: 100 characters.
- Use type hints everywhere (mypy strict is enabled).
- Use `from __future__ import annotations` in new modules.
- Prefer `pathlib.Path` over string paths.
- Keep `shared/` domain-agnostic. RAG-specific code belongs in `services/rag_chat_agent/`.
- Use Protocol/ABC for swappable components (entity providers, embedding models, rerankers).
- Handle optional dependencies gracefully (e.g. Langfuse, SciSpaCy models) with try/except fallbacks.
- Use `shared.logging.get_logger(__name__)` for logging; pass structured fields via `extra={...}`.

## Data & Secrets

- `data/` and `.env` files are excluded from Git. Do not commit them.
- The corpus manifest is at `data/corpus/manifest.json`.
- Source field names in the manifest (`id`, `file`, `pages`) are normalised to the `Source` model schema (`source_id`, `filename`, `total_pages`) in `shared/corpus_client.py`.

## Testing Expectations

- Add tests for new functionality in `tests/`.
- Use `pytest` and `fastapi.testclient.TestClient` for API route tests.
- Run the full test suite before committing.

## Development Workflow

1. Read the relevant phase plan in `phases/` before implementing.
2. Make minimal, focused changes.
3. Keep `pyproject.toml` dependency groups up to date when adding packages.
4. Update `README.md` or `AGENTS.md` when changing workflows or conventions.
5. Do not run `git commit`, `git push`, or other git mutations unless explicitly asked.
