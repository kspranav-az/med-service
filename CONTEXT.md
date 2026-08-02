# MedService Project Context

## Overview

MedService is a medical-domain AI toolkit built around a curated corpus of pediatric surgery and urology reference material. The project is organized as a multi-service codebase with shared infrastructure for ingestion, embeddings, retrieval, and entity extraction.

Active services:

- **RAG Chat Agent** — retrieval-augmented question-answering over the medical corpus with citations, hybrid search, two-tier reranking, Redis caching, request deduplication, and Langfuse tracing.
- **Semantic Autocomplete** — field-aware medical term autocomplete backed by a character-level trie, fuzzy matching, vector similarity over SciSpaCy-extracted entities, Redis caching, and per-IP rate limiting.
- **Dev Console** — a React + Vite + TypeScript + Tailwind frontend under `frontend/` for testing all backend services from the browser.

Additional services may be added under `services/` as the project grows.

## Repository Layout

```
med-service/
├── services/                  # Deployable service modules
│   ├── rag_chat_agent/        # RAG chat API and service logic
│   └── autocomplete/          # Semantic autocomplete API and service logic
├── shared/                    # Libraries shared across services
│   ├── cache/
│   ├── chunking/
│   ├── corpus_client.py
│   ├── cors.py                # CORS helpers for error responses
│   ├── dedup/
│   ├── embeddings/
│   ├── entities/              # SciSpaCy entity extraction provider
│   ├── fuzzy/                 # rapidfuzz-based typo tolerance
│   ├── fusion/                # Reciprocal Rank Fusion utilities
│   ├── ingestion/
│   ├── logging.py
│   ├── models/
│   ├── rate_limit/            # Redis token-bucket rate limiter
│   ├── reranker/
│   └── vector_store/          # Qdrant clients (rag_chunks + entities)
├── scripts/                   # Utility scripts
│   ├── extract_entities.py
│   ├── index_entities.py
│   ├── ingest_pdfs.py
│   ├── reindex_all.py
│   └── reindex_source.py
├── frontend/                  # React + Vite + TS + Tailwind dev console
├── notebooks/                 # Exploration notebooks
├── tests/                     # Pytest test suite
├── data/                      # NOT committed to Git
│   ├── corpus/
│   │   ├── manifest.json
│   │   └── books/pediatric/*.pdf
│   └── processed/
│       └── entities/scispacy_entities.json
├── docker-compose.yml         # Local Qdrant + Redis
├── docker-compose.override.yml.example  # Alternate ports for shared servers
├── README.md
├── PRD.md
├── DEPLOYMENT.md              # Deployment guide
├── CONTEXT.md                 # This file
└── AGENTS.md                  # AI-agent specific instructions
```

## Data Corpus

### Location

All source material lives in:

```
data/corpus/books/<domain>/
```

Currently all books are pediatric-focused:

```
data/corpus/books/pediatric/
```

### Manifest

`data/corpus/manifest.json` is the source of truth for the corpus. Each entry has:

```json
{
  "id": "arm_holschneider_2",
  "file": "arm_holschneider_2.pdf",
  "title": "ARM Holschneider (2nd ed.)",
  "pages": 477,
  "tags": ["pediatric-surgery", "colorectal", "anorectal-malformation"],
  "path": "books/pediatric/arm_holschneider_2.pdf",
  "domain": "pediatric"
}
```

### Current Stats

- **Books:** 24
- **Pages:** 19,714
- **Domain:** pediatric
- **Largest source:** Campbell-Walsh Urology (split into 4 parts, 4,899 pages total)

### Full Book List

| File | Title | Pages | Domain |
|------|-------|-------|--------|
| `arm_holschneider_2.pdf` | ARM Holschneider (2nd ed.) | 477 | pediatric |
| `campbell_walsh_urology_11e_part_1.pdf` | Campbell-Walsh Urology 11E - Part 1 | 1,224 | pediatric |
| `campbell_walsh_urology_11e_part_2.pdf` | Campbell-Walsh Urology 11E - Part 2 | 1,224 | pediatric |
| `campbell_walsh_urology_11e_part_3.pdf` | Campbell-Walsh Urology 11E - Part 3 | 1,224 | pediatric |
| `campbell_walsh_urology_11e_part_4.pdf` | Campbell-Walsh Urology 11E - Part 4 | 1,227 | pediatric |
| `coran_pediatric_surgery_part_1.pdf` | Coran Pediatric Surgery - Part 1 | 628 | pediatric |
| `coran_pediatric_surgery_part_2.pdf` | Coran Pediatric Surgery - Part 2 | 628 | pediatric |
| `coran_pediatric_surgery_part_3.pdf` | Coran Pediatric Surgery - Part 3 | 629 | pediatric |
| `dk_gupta_pediatric_surgery_vol_1.pdf` | DK Gupta Pediatric Surgery Vol. 1 | 858 | pediatric |
| `dk_gupta_pediatric_surgery_vol_5.pdf` | DK Gupta Pediatric Surgery Vol. 5 | 681 | pediatric |
| `hadidi_hypospadias.pdf` | Hadidi - Hypospadias | 372 | pediatric |
| `harriet_lane_handbook.pdf` | The Harriet Lane Handbook | 893 | pediatric |
| `hinmans_atlas_pediatric_urologic_surgery_2e.pdf` | Hinman's Atlas of Pediatric Urologic Surgery 2nd ed. | 949 | pediatric |
| `kelalis_king_belman_clinical_pediatric_urology_part_1.pdf` | Kelalis-King-Belman Clinical Pediatric Urology - Part 1 | 739 | pediatric |
| `kelalis_king_belman_clinical_pediatric_urology_part_2.pdf` | Kelalis-King-Belman Clinical Pediatric Urology - Part 2 | 738 | pediatric |
| `meherbaan_singh.pdf` | Meherbaan Singh | 109 | pediatric |
| `nelson_essentials_pediatrics_2018.pdf` | Nelson Essentials of Pediatrics (2018) | 2,301 | pediatric |
| `neofax_2014.pdf` | Neofax 2014 | 869 | pediatric |
| `nephrology_bagga.pdf` | Nephrology Bagga | 598 | pediatric |
| `operative_pediatric_surgery_7e_rob_smith.pdf` | Operative Pediatric Surgery 7th ed. (Rob & Smith) | 1,128 | pediatric |
| `pena_colorectal_surgery.pdf` | Pena - Colorectal Surgery | 510 | pediatric |
| `rickhams_neonatal_surgery_2018.pdf` | Rickham's Neonatal Surgery 1st ed. (2018) | 1,307 | pediatric |
| `roy_chaudhary_handbook_pediatric_surgery.pdf` | Roy Chaudhary - Handbook of Pediatric Surgery | 393 | pediatric |
| `urodynamics_iaps.pdf` | Urodynamics IAPS | 8 | pediatric |

## Conventions

### File Naming

- All PDFs use `snake_case`.
- No spaces, brackets, or special characters in filenames.
- Split books are named `<title>_part_<N>.pdf`.

### Domain Organization

- Books are grouped under `data/corpus/books/<domain>/`.
- The manifest must reflect the actual path with `path` and `domain` fields.
- When adding a new domain, create a new folder and update the manifest.

### Code Organization

- Services live under `services/` and should be independently runnable.
- Shared logic lives under `shared/` and must not depend on a specific service.
- Each service can have its own `Dockerfile`; the root `pyproject.toml` manages all dependencies.

### Git Rules

- `data/` is **never** committed to Git.
- `manifest.json` is also kept outside Git by project decision.
- The repository should contain code, configs, scripts, tests, and documentation only.

## Environment

A Python virtual environment exists at `.venv/` managed by `uv`. Install all extras for development:

```bash
uv sync --extra all --group dev
```

Qdrant and Redis are run via Docker Compose for local development:

```bash
docker compose up -d
```

## Python Version

- **Python 3.12** (narrowed to `<3.13` because `qdrant-client==1.18.0` pulls incompatible NumPy 2.x on Python 3.13+).

## Frontend Dev Console

A browser-based testing UI lives in `frontend/`. It communicates with the running backend services.

```bash
cd frontend
npm install
npm run dev
```

The console opens at `http://localhost:5173` and expects the chat service on `http://localhost:8000` and the autocomplete service on `http://localhost:8001`.

To use custom URLs, copy the example file and edit it before running the dev server:

```bash
cp frontend/.env.example frontend/.env
```

## CORS

Both FastAPI services use `CORSMiddleware` plus custom exception handlers so that error responses also include CORS headers. Allowed origins are controlled by the `CORS_ORIGINS` environment variable (comma-separated). The default includes common Vite dev origins; production deployments must set this to the real frontend origin(s).

## Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for server deployment instructions, including:

- deploying on the shared Prime World CRM VPS via Traefik (`docker-compose.med-service.deploy.yml`),
- copying Qdrant storage and entity data without reindexing,
- port planning for shared servers,
- subdomain vs path-based routing trade-offs,
- systemd and Nginx examples,
- integration with an existing Traefik or Nginx reverse proxy.

## Notes for Future Work

- The corpus is currently pediatric-only. Future domains (e.g., cardiology, radiology, oncology) should follow the same folder + manifest pattern.
- The RAG and autocomplete services read from `data/corpus/manifest.json` and resolve PDF paths relative to `data/corpus/`.
- Any ingestion pipeline should handle page-range splits and large PDFs gracefully.
- Autocomplete currently uses SciSpaCy-extracted entities with internal placeholder TUIs. Phase 5 will replace this with a UMLS-backed provider that exposes true CUIs and all 127 TUIs without changing the API contract.
