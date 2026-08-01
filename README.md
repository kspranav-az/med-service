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
uv run mypy shared services scripts tests  # should pass
```

### 4. Index the corpus (long-running)

```bash
# Test with one small source first
uv run reindex-source --source urodynamics_iaps --parser pymupdf --batch-size 32

# Index the full corpus (resume supported)
uv run reindex-all --parser pymupdf --batch-size 32
```

### 5. Build the autocomplete entity index (long-running)

The autocomplete service needs extracted entities indexed in Qdrant.

```bash
# Install the SciSpaCy NER model (one-time; uv sync does not persist it)
uv pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz

# Extract entities from the corpus (~30-120 min depending on hardware)
uv run extract-entities

# Embed and index them in Qdrant
uv run index-entities
```

### 6. Configure API keys

Copy the example environment file and add your keys:

```bash
cp .env.example .env
# Edit .env and set at least one LLM key
```

### 7. Run services locally

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

# With Kimi Code (via Anthropic-compatible endpoint)
ANTHROPIC_API_KEY=Your_Kimi_Code_API_Key \
ANTHROPIC_BASE_URL=https://api.kimi.com/coding/ \
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"What are the first-line treatments for Type 2 Diabetes?","model":"claude-sonnet-4-20250514"}'

curl http://localhost:8001/api/v1/health

curl -X POST http://localhost:8001/api/v1/autocomplete \
  -H 'Content-Type: application/json' \
  -d '{"query":"myo","field_types":"T047,T191","limit":10,"fuzzy":true,"semantic_expansion":true}'
```

## Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for deploying to a server, including co-hosting with another project on the same machine without reindexing the corpus.

### Run the dev console (frontend)

A React + Vite + TypeScript + Tailwind dev console is available under `frontend/` for testing both services from the browser.

```bash
cd frontend
npm install
npm run dev
```

The console runs at `http://localhost:5173` and expects the backend services on their default ports (`8000` and `8001`).
To use custom URLs, copy the example environment file and edit it:

```bash
cp frontend/.env.example frontend/.env
# Update VITE_CHAT_API_URL and VITE_AUTOCOMPLETE_API_URL if needed
```

The console has three tabs:

- **Chat** — submit RAG questions with model, reranker, and cache overrides.
- **Autocomplete** — live debounced medical term suggestions with match-source badges.
- **Health** — verify that both backend services are reachable.

## Rate Limits

Both endpoints use Redis token-bucket rate limiters with separate limits per IP:

| Endpoint | Limit | Burst |
|----------|-------|-------|
| `POST /api/v1/chat` | 10 req / min | 3 |
| `POST /api/v1/autocomplete` | 60 req / min | 10 |

Configure limits via environment variables (see `shared/config.py`).

## Development Notes

- Python **3.12** managed by `uv`
- Local processing for PDF parsing, embedding, and NER
- Docker used only for Qdrant, Redis, and API integration testing
- Data under `data/` is never committed to Git
- PDF parsing uses **PyMuPDF** by default; **Marker** is included as an optional layout-preserving parser
- RAG pipeline includes hybrid search, a two-tier cross-encoder reranker, Redis result cache, request deduplication, confidence scoring, and Langfuse tracing
- Autocomplete uses a character-level trie for prefix matching, `rapidfuzz` for typo tolerance, BGE embeddings for semantic expansion, and reciprocal rank fusion (RRF) to merge result streams
- The autocomplete entity provider is currently SciSpaCy-only (`en_core_sci_md`) with placeholder TUIs; a UMLS-backed provider is planned for Phase 5
- See `phases/` for detailed implementation plans
- See `AGENTS.md` for coding conventions and agent instructions

## Documentation

- `PRD.md` — Product Requirements Document
- `CONTEXT.md` — Project context and conventions
- `AGENTS.md` — Coding conventions and commands for agents
- `phases/phase_01_foundation.md` — Phase 1 plan
