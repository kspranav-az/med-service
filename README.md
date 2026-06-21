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
uv sync --extra all
```

### 2. Start local infrastructure

```bash
docker compose up -d
```

This starts Qdrant on port `6333` and Redis on port `6379`.

### 3. Verify

```bash
uv run python --version  # Python 3.12.x
```

## Development Notes

- Python **3.12** managed by `uv`
- Local processing for PDF parsing, embedding, and NER
- Docker used only for Qdrant, Redis, and API integration testing
- Data under `data/` is never committed to Git
- See `phases/` for detailed implementation plans

## Documentation

- `PRD.md` — Product Requirements Document
- `CONTEXT.md` — Project context and conventions
- `phases/phase_01_foundation.md` — Phase 1 plan
