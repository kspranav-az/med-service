# Product Requirements Document (PRD)
## Medical AI System: RAG Chat Agent + Semantic Autocomplete
**Version:** 1.2 (Updated)  
**Date:** June 21, 2026  
**Status:** Draft — Phase 4 implemented

---

## 1. Executive Summary

This PRD defines the requirements for a dual-purpose Medical AI system comprising:
1. **Medical PDF RAG Chat Agent** -- A retrieval-augmented generation system that answers clinical questions grounded in ~1.1GB of medical textbook PDFs (24 pediatric surgery/urology books), with **two-tier cross-encoder reranking** (fast MiniLM default + full BGE-Reranker quality mode), **request deduplication**, **cache invalidation on content updates**, automated evaluation, and full observability.
2. **Medical Semantic Autocomplete** -- A field-aware autocomplete system supporting all 127 UMLS semantic types (TUIs) with both filtered and non-filtered modes, backed by Redis caching for sub-10ms hot queries, **incremental entity index updates**, and **rate limiting**.

The system is designed for **development on a MacBook Air M5 16GB** and **production deployment on a cloud VPS**, using API-based LLMs with self-hosted vector storage for HIPAA-aligned data residency.

---

## 1.1 Project Decisions & Updates

The following decisions have been made since PRD v1.1:

| Decision | v1.1 Plan | Updated Plan | Rationale |
|----------|-----------|--------------|-----------|
| **Python environment** | Python 3.9 venv | **Python 3.12 + uv** | Modern toolchain; faster dependency resolution |
| **Development approach** | Docker Desktop for full stack | **Local processing + Docker only for Qdrant/Redis/API testing** | Avoid Docker overhead on MacBook Air M5; faster preprocessing |
| **NER / entity extraction** | QuickUMLS + GLiNER ensemble | **SciSpaCy-only initially**; QuickUMLS + GLiNER after UMLS license | UMLS license is pending |
| **Build order** | Parallel RAG + autocomplete | **RAG-first, then autocomplete skeleton, then UMLS integration** | RAG has no UMLS dependency; delivers value faster |
| **PDF parser** | Marker + Unstructured + Nougat | **pypdf / pymupdf** primary; optional Marker for layout | Lighter, faster, Python 3.12 compatible |
| **GPU usage (local)** | Not specified | **MPS for batch embeddings/reranker testing only** | Apple Silicon GPU accelerates Transformer batch inference |
| **Data size** | 5GB+ corpus | **~1.1GB actual corpus** (24 pediatric PDFs, 19,714 pages) | Matches actual `data/corpus/books/pediatric/` contents |

### Impact on Autocomplete
Until UMLS is approved, autocomplete will be built with a **pluggable entity provider**:
- **v1 placeholder:** SciSpaCy-extracted entities with internal type labels (no CUIs, limited TUIs)
- **v1.5 upgrade:** Swap to UMLS-backed provider with full CUIs + 127 TUIs

The API contract, trie structure, vector index, Redis cache, and frontend remain unchanged during this swap.

---

## 2. Goals & Objectives

| Goal | Success Metric |
|------|--------------|
| Provide accurate, cited medical answers from textbook corpus | >85% retrieval accuracy (nDCG@5), <2% hallucination rate |
| Reduce clinician form-completion time | >40% time reduction, >70% suggestion selection rate |
| Maintain data privacy for PHI | Self-hosted vector DB, encrypted at rest (AES-256), TLS 1.2+ |
| Enable rapid development on existing hardware | Full local dev stack runs on MacBook Air M5 16GB |
| Support all medical entity types | All 127 UMLS semantic types filterable + non-filtered mode |
| Ensure production reliability | 99.5% uptime, full request tracing, automated quality monitoring |
| Support content updates without full reindex | Incremental PDF add/update/delete (RAG-12, AC-13) |

---

## 3. User Personas

| Persona | Needs | Interaction |
|---------|-------|-------------|
| **Clinical Developer** | Build/test the system locally | MacBook Air, Docker, small PDF subset |
| **Clinician / Medical Student** | Ask questions about textbook content | Chat interface with cited answers |
| **EHR Data Entry Clerk** | Fast, accurate form completion | Autocomplete on diagnosis, medication, procedure fields |
| **System Administrator** | Deploy, monitor, scale, debug | Dashboard, traces, logs, cost metrics |
| **Quality Assurance Lead** | Monitor answer quality over time | Automated evaluation scores, drift alerts |

---

## 4. Functional Requirements

### 4.1 RAG Chat Agent

| ID | Requirement | Priority |
|----|-------------|----------|
| RAG-1 | Ingest medical PDFs (5GB+), extract text, tables, and layout-aware chunks | P0 |
| RAG-2 | Generate embeddings for ~935,000 chunks using medical-optimized model | P0 |
| RAG-3 | Store vectors in self-hosted Qdrant with scalar quantization (int8) | P0 |
| RAG-4 | Accept natural language queries, retrieve top-k relevant chunks via hybrid search (dense + sparse) | P0 |
| RAG-5 | **Rerank retrieved chunks using a two-tier cross-encoder system: (a) fast MiniLM-based reranker (~5ms/pair) as default, (b) full BGE-Reranker-v2-M3 (~20ms/pair) as optional "quality mode"** | P0 |
| RAG-6 | Synthesize answers using API LLM (GPT-4o / Claude / Kimi) with strict citation grounding | P0 |
| RAG-7 | Return answers with source identifiers linking back to PDF pages | P0 |
| RAG-8 | Support conversation history / multi-turn context | P1 |
| RAG-9 | Implement confidence thresholding; defer low-confidence queries with warning | P1 |
| RAG-10 | **Cache frequent RAG queries and their retrieved contexts; invalidate cache when source PDFs are updated or reindexed** | P1 |
| RAG-11 | Provide admin dashboard for indexing status, query logs, and feedback | P2 |
| **RAG-12** | **Support incremental indexing -- add, update, or remove individual PDFs without full reindex; store PDF-level metadata (source_id, filename, ingest_date, version) in Qdrant payload to enable selective deletion/update** | P1 |
| **RAG-13** | **Request deduplication -- if identical queries arrive simultaneously, only one proceeds through retrieval and LLM generation; subsequent identical requests wait for the same result via Redis in-flight lock with 5-second timeout** | P1 |

### 4.2 Semantic Autocomplete

| ID | Requirement | Priority |
|----|-------------|----------|
| AC-1 | Extract ~280,000 medical entities from PDFs using NER ensemble | P0 |
| AC-2 | Normalize all entities to UMLS CUIs with full semantic type (TUI) assignment | P0 |
| AC-3 | Build prefix trie (radix tree) for sub-millisecond prefix matching | P0 |
| AC-4 | Build HNSW vector index in Qdrant for semantic similarity search | P0 |
| AC-5 | Support **any combination of the 127 UMLS semantic types** as filter | P0 |
| AC-6 | Support **non-filtered mode** (search across all types via `"all"` string) | P0 |
| AC-7 | Implement fuzzy matching (Levenshtein distance <=2) for typo tolerance | P0 |
| AC-8 | Merge trie + vector results via Reciprocal Rank Fusion (RRF, alpha=0.7) | P0 |
| AC-9 | Return ranked suggestions with entity name, CUI, semantic type, and source | P0 |
| AC-10 | **Cache hot autocomplete queries in Redis for <10ms P50 response** | P1 |
| AC-11 | Achieve P50 latency <20ms (<10ms cached), P95 latency <50ms | P0 |
| **AC-12** | **Rate limiting -- 60 requests/minute per IP on autocomplete endpoint; Redis-based token bucket** | P1 |
| **AC-13** | **Support incremental entity index updates when new documents are ingested, without full trie rebuild** | P1 |

### 4.3 Evaluation & Observability

| ID | Requirement | Priority |
|----|-------------|----------|
| OBS-1 | Trace every RAG request end-to-end: query -> retrieval -> reranking -> generation -> response | P1 |
| OBS-2 | Record latency per component, token usage, API cost, and retrieval scores per request | P1 |
| OBS-3 | Run automated evaluation (faithfulness, answer relevance, context precision) on scheduled test set | P1 |
| OBS-4 | Alert on quality drift, latency spikes, or error rate thresholds | P1 |
| OBS-5 | Provide admin dashboard with query volume, cost trends, and evaluation metrics | P2 |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | RAG query response <3s end-to-end; Autocomplete <50ms (P95), <10ms cached (P50) |
| **Scalability** | Support 5-20 concurrent users on starter VPS; scale to 200+ on growth tier |
| **Reliability** | 99.5% uptime; graceful degradation if LLM API is unavailable; cached autocomplete survives DB restart |
| **Security** | HIPAA-aligned: encryption at rest/transit, RBAC, audit logs, BAAs |
| **Privacy** | No PHI sent to LLM APIs unless explicitly configured; vector DB self-hosted |
| **Portability** | Same codebase runs on MacBook Air (dev) and VPS/GCP (prod) |
| **Observability** | Structured logging, distributed tracing, query metrics, latency histograms, automated evaluation scores |

---

## 6. Technical Architecture

### 6.1 Shared Infrastructure (Both Systems)

```
+-------------------------------------------------------------+
|                    PDF Parsing Pipeline                      |
|         (Marker + Unstructured + Nougat + Post-proc)        |
+-------------------------------------------------------------+
                              |
        +---------------------+---------------------+
        |                     |                     |
        v                     v                     v
   +---------+          +----------+          +----------+
   | Chunking |          |   NER    |          | Entity   |
   |(400 tok, |          | Ensemble |          | Linking  |
   |200 overlap|         |QuickUMLS |          |  UMLS    |
   |Dynamic) |          |+ GLiNER  |          |          |
   +----+----+          +-----+----+          +-----+----+
        |                     |                     |
        v                     v                     v
   +---------+          +----------+          +----------+
   |Embedding|          |  Trie    |          | Vector   |
   |BGE-Base |          | (Radix)  |          | Index    |
   |768-dim  |          |          |          | Qdrant   |
   |int8     |          |          |          | entities |
   +----+----+          +-----+----+          +-----+----+
        |                     |                     |
        +---------------------+---------------------+
                              |
                              v
                    +------------------+
                    |   Qdrant Vector  |
                    |     Database     |
                    |  + rag_chunks    |
                    |  + entities      |
                    +------------------+
                              |
        +---------------------+---------------------+
        |                     |                     |
        v                     v                     v
   +----------+       +--------------+      +--------------+
   |  Redis   |       |  FastAPI     |      |  FastAPI     |
   |  Cache   |       |  /chat       |      |/autocomplete |
   |(Hot AC + |       |  (RAG)       |      |  (AC)        |
   |RAG ctx)  |       |              |      |              |
   +-----+----+       +------+-------+      +------+-------+
         |                     |                     |
         |              +------+------+             |
         |              |             |             |
         |       +------v------+ +----v----+        |
         |       |  Reranker   | |Langfuse |        |
         |       |(Two-Tier:  | |Tracing  |        |
         |       |MiniLM fast | |         |        |
         |       |+ BGE full) | +---------+        |
         |       +------+------+                    |
         |              |                           |
         +--------------+---------------------------+
                        |
                        v
                +------------------+
                |   API LLM        |
                | (GPT-4o/Claude)  |
                |   (RAG only)     |
                +------------------+
                        |
                        v
                +------------------+
                |  RAGAS Evaluator |
                |(Faithfulness,   |
                |Relevance, etc.)  |
                +------------------+
```

### 6.2 Component Specifications

| Component | Technology | Dev Spec | Prod Spec |
|-----------|------------|----------|-----------|
| PDF Parser | pypdf / pymupdf; optional Marker | Local batch | Cloud batch |
| Chunking | Dynamic token (LlamaIndex) | Full 24-book corpus | Full corpus |
| Embedding (RAG) | BGE-Base-v1.5 | CPU/MPS, batch 32-64 | CPU, batch 32-64 |
| Embedding (AC) | SapBERT | CPU/MPS | CPU |
| Vector DB | Qdrant (self-hosted) | 1GB RAM, full corpus | 4GB RAM, full |
| NER | **SciSpaCy-only initially**; QuickUMLS + GLiNER after UMLS license | Local batch | Cloud batch |
| Trie | Python radix tree / pygtrie | In-memory | In-memory / Redis |
| **Reranker (Tier 1)** | **MiniLM cross-encoder (~5ms/pair)** | **CPU, default** | **CPU, default** |
| **Reranker (Tier 2)** | **BGE-Reranker-v2-M3 (~20ms/pair)** | **CPU, quality mode** | **CPU, quality mode** |
| **Cache** | **Redis** | **Langfuse Cloud (dev)** | **Redis Cloud / self-hosted** |
| **Observability** | **Langfuse** | **Cloud free tier (10k traces)** | **Self-hosted / Cloud** |
| **Evaluation** | **RAGAS + custom test suite** | **Local CI** | **Scheduled prod job** |
| API Framework | FastAPI (Python) | Uvicorn single process | Uvicorn 4+ workers |
| LLM | OpenAI GPT-4o / Claude / Kimi API | API calls | API calls |
| Frontend | React/Vue | Local dev server | Static CDN |
| Deployment | Docker Compose | Docker Desktop | VPS / GCP |

---

## 7. UMLS Semantic Type System (Full Coverage)

The autocomplete system must support **all 127 UMLS Semantic Network types** (TUIs).

### 7.1 Filterable Type Categories

| Category | Example TUIs | Example Entities |
|----------|-------------|------------------|
| **Disease/Disorder** | T047, T048, T049, T191 | pneumonia, diabetes, depression |
| **Medication/Substance** | T121, T125, T129, T196 | metformin, insulin, aspirin |
| **Procedure** | T060, T061 | colonoscopy, appendectomy |
| **Anatomy** | T017, T018, T023, T030 | liver, left ventricle, femur |
| **Finding** | T184, T185 | fever, chest pain, dyspnea |
| **Organism** | T001, T004, T008 | bacteria, virus, fungi |
| **Conceptual Entity** | T078, T080, T081 | statistical concept, classification |
| **All 127 types** | T001-T197 | Full UMLS Metathesaurus coverage |

### 7.2 Filter Modes

| Mode | API Parameter | Behavior |
|------|--------------|----------|
| **Single Type** | `["T047"]` | Restrict to one semantic type |
| **Multi-Type Union** | `["T047", "T048", "T191"]` | OR logic across specified types |
| **Non-Filtered** | `"all"` | Search across all 127 types (default) |

### 7.3 Frontend Contract

HTML inputs declare accepted types via `data-entity-types`:

```html
<!-- Single type -->
<input data-entity-types="T047" placeholder="Diagnosis" />

<!-- Multiple types -->
<input data-entity-types="T121,T125" placeholder="Medications" />

<!-- No filter (general search) -->
<input data-entity-types="all" placeholder="Search any medical term..." />
```

---

## 8. API Specifications

### 8.1 RAG Chat Endpoint

```http
POST /api/v1/chat
Content-Type: application/json

{
  "query": "What are the first-line treatments for Type 2 Diabetes?",
  "conversation_id": "conv_123",
  "model": "gpt-4o",
  "top_k": 20,
  "rerank_top_k": 5,
  "reranker": "minilm",
  "require_citations": true,
  "confidence_threshold": 0.75,
  "use_cache": true
}
```

**Response:**
```json
{
  "answer": "First-line treatments for Type 2 Diabetes include...",
  "citations": [
    {"chunk_id": "chunk_48291", "source": "Harrison's Internal Medicine", "page": 2847, "score": 0.89}
  ],
  "confidence": 0.91,
  "tokens_used": 1240,
  "trace_id": "trace_abc123",
  "reranker_used": "minilm",
  "cached": false
}
```

**Quality mode reranker:** Set `"reranker": "bge-reranker-v2-m3"` for full cross-encoder accuracy.

### 8.2 Autocomplete Endpoint

```http
POST /api/v1/autocomplete
Content-Type: application/json

{
  "query": "myo",
  "field_types": "T047,T191",
  "limit": 10,
  "fuzzy": true,
  "semantic_expansion": true
}
```

**Response:**
```json
{
  "query": "myo",
  "field_types": "T047,T191",
  "results": [
    {
      "term": "myocardial infarction",
      "cui": "C0027051",
      "tuis": ["T047", "T191"],
      "aliases": ["heart attack", "MI"],
      "match_type": "prefix",
      "score": 0.95
    }
  ],
  "latency_ms": 12,
  "cached": false
}
```

---

## 9. Core Enhancement Modules

### 9.1 Reranking (Two-Tier Cross-Encoder)

**Purpose:** Improve retrieval accuracy by scoring query-chunk relevance beyond vector similarity, with a fast default and an optional high-accuracy mode.

**Tier 1 -- Fast (Default):**
- Model: **MiniLM-based cross-encoder** (~5ms per pair on CPU)
- Latency: ~100ms for 20 chunks (reranking phase)
- Use case: Standard queries, high-traffic scenarios

**Tier 2 -- Quality (Optional):**
- Model: **BGE-Reranker-v2-M3** (~20ms per pair on CPU)
- Latency: ~400ms for 20 chunks (reranking phase)
- Use case: Complex medical queries, low-confidence retrievals, quality-critical deployments
- API selection via `reranker` parameter (`"minilm"` or `"bge-reranker-v2-m3"`)

**Pipeline:**
1. Retrieve top-20 chunks from Qdrant via hybrid search
2. Pass `(query, chunk_text)` pairs through selected cross-encoder
3. Select top-5 reranked chunks for LLM context
4. **Expected improvement:** +10-15% nDCG@10 over vector-only retrieval

### 9.2 Caching Layer (Redis)

**Purpose:** Eliminate redundant computation and reduce API costs.

**Autocomplete Cache:**
- Key: `ac:{field_types_hash}:{query_prefix}:{fuzzy_flag}`
- TTL: 24 hours
- Impact: P50 latency drops from ~12ms to **<2ms** for repeated queries

**RAG Context Cache:**
- Key: `rag_ctx:{query_hash}:{top_k}:{reranker}`
- Value: Pre-retrieved chunk IDs and reranked scores
- TTL: 1 hour (medical content may update)
- Impact: Reduces Qdrant load and reranker compute; API cost savings of 20-40% for common questions

**Cache Invalidation:**
- On PDF reindex/update: clear all cache entries sourced from that PDF
- Cache version key bumped on any reindex; checked on every cache read
- Implementation:
```python
def invalidate_source_cache(source_id: str):
    redis.delete(f"rag_ctx:*:{source_id}:*")
    redis.incr("cache_version")
```

### 9.3 Incremental Indexing (RAG-12, AC-13)

**Purpose:** Add, update, or remove individual PDFs without full reindex.

**Qdrant Payload Schema (per point):**
```json
{
  "source_id": "harrisons_21st_ed",
  "filename": "harrisons_internal_medicine.pdf",
  "ingest_date": "2026-06-21T00:00:00Z",
  "version": 2,
  "chunk_index": 48291,
  "page_number": 2847
}
```

**Operations:**
- **Add new PDF:** Parse, chunk, embed, insert with new source_id
- **Update PDF:** Increment version, delete old points by source_id, insert new
- **Delete PDF:** Delete all points matching source_id; invalidate cache

**AC-13 -- Incremental Entity Updates:**
- Extract entities from new PDFs via NER pipeline
- Merge new entities into existing trie (radix tree supports insertion)
- Update Qdrant entities collection with new vectors
- No full trie rebuild required

### 9.4 Request Deduplication (RAG-13)

**Purpose:** Prevent multiple simultaneous identical queries from each generating separate LLM API calls.

**Mechanism:**
1. Query arrives -> compute query hash
2. Check Redis for `inflight:{query_hash}` lock key
3. If lock exists: subscribe to completion channel, wait for result
4. If no lock: acquire lock (5-second TTL), process full RAG pipeline, store result, publish to channel, release lock
5. Lock auto-expires after 5 seconds if processor crashes

### 9.5 Rate Limiting (AC-12)

**Purpose:** Protect API endpoints from abuse while allowing different traffic profiles for chat and autocomplete.

**Rules:**
- Redis token-bucket algorithm per IP address
- Exceeded limit: HTTP 429 with `Retry-After` header

| Endpoint | Requests / window | Burst |
|----------|-------------------|-------|
| `POST /api/v1/autocomplete` | 60 / min | 10 |
| `POST /api/v1/chat` | 10 / min | 3 |

### 9.6 Observability (Langfuse)

**Purpose:** Full visibility into every request.

**Traced Spans per RAG Request:**
1. `query_preprocessing` -- Normalization, expansion
2. `vector_retrieval` -- Qdrant hybrid search latency and result count
3. `reranking` -- Cross-encoder selection, scores, top-k selection
4. `llm_generation` -- Model, tokens, cost, response time
5. `post_processing` -- Citation formatting, confidence scoring

**Development:** Langfuse Cloud free tier (10k traces/month) -- no local resources needed.

### 9.7 Evaluation Framework (RAGAS)

**Metrics:**
| Metric | Target | Description |
|--------|--------|-------------|
| Faithfulness | >0.90 | Answer claims supported by retrieved context |
| Answer Relevance | >0.85 | Answer directly addresses the query |
| Context Precision | >0.85 | Retrieved chunks are relevant |
| Context Recall | >0.80 | All necessary information was retrieved |

**Test Set:** 100-200 manually curated medical QA pairs. Run nightly in production.

---

## 10. Future Enhancements (Deferred to v2.0)

### 10.1 Query Expansion (HyDE)

**Description:** Generate hypothetical ideal answer from query, embed it, use for retrieval.
**Deferral Reason:** Adds latency; current retrieval accuracy (nDCG@5 ~0.87) sufficient for v1.0.
**v2.0 Trigger:** Context recall consistently <0.80 for complex multi-concept queries.

### 10.2 GraphRAG

**Description:** Integrate structured medical knowledge graphs alongside vector retrieval.
**Deferral Reason:** Requires significant knowledge graph construction infrastructure.
**v2.0 Trigger:** User demand for relationship-based reasoning beyond document retrieval.

---

## 11. Deployment Strategy

### 11.1 Development Environment (MacBook Air M5 16GB)

| Service | Memory | Notes |
|---------|--------|-------|
| macOS + Apps | ~4GB | Base overhead |
| Docker (Qdrant + Redis only) | ~1.5GB | Docker Desktop limited to ~2GB |
| Qdrant | ~1GB | Full 24-book corpus |
| Redis | ~256MB | Cache layer |
| FastAPI | ~512MB | Both endpoints (Uvicorn) |
| React dev server | ~256MB | Hot reload |
| Embedding worker | ~1GB | MPS batch when available; batch size 32-64 |
| Langfuse | ~0MB | **Cloud free tier (10k traces)** |
| **Total used** | **~9.5GB** | **Fits comfortably in 16GB** |

**Dev workflow:**
- Use **uv** with **Python 3.12** for local package management.
- Run all preprocessing (PDF parsing, chunking, embedding, NER) **directly on macOS**, not in Docker.
- Use Docker only for **Qdrant**, **Redis**, and integration testing of APIs.
- Process the full **~1.1GB / 24-book pediatric corpus** locally.

**NER pipeline note:** Use **SciSpaCy-only** (`en_ner_bc5cdr_md`, `en_core_sci_lg`, etc.) for initial development until UMLS license is approved. Add QuickUMLS + GLiNER once license is obtained.

**GPU note:** Use Apple Silicon **MPS** backend for batch embedding and reranker benchmarking only. Runtime API serving remains CPU-bound.

**Embedding batch size:** Use **batch size 32-64** for CPU/MPS embedding. Batch 1 achieves ~50 chunks/sec; batch 32 achieves ~200-500 chunks/sec due to amortized overhead (higher on MPS).

### 11.2 Production Environment (Recommended: VPS)

| Tier | Specs | Cost/Month | Max PDFs | Users |
|------|-------|------------|----------|-------|
| **Starter** | 4vCPU, 8GB RAM, 80GB NVMe | $15-25 | 5GB | 1-10 |
| **Growth** | 8vCPU, 16GB RAM, 160GB NVMe | $25-50 | 20GB | 10-50 |
| **Scale** | 8vCPU, 64GB RAM, 320GB NVMe | $65-85 | 100GB | 50-200 |

**Recommended:** Hetzner CPX41 (8vCPU, 16GB RAM, $25-35/mo).

### 11.3 Alternative: GCP

| Component | GCP Service | Specs | Cost/Month |
|-----------|-------------|-------|------------|
| Vector DB | Compute Engine (Qdrant) | e2-medium: 2vCPU, 4GB | $25-50 |
| API | Cloud Run | 1vCPU, 2GB per instance | $15-45 |
| Redis | Memorystore | 1GB Basic | $30-50 |
| Storage | Cloud Storage | 5GB Standard | $0.10 |
| **Total** | | | **$70-145** |

---

## 12. Compliance & Security

| Requirement | Implementation |
|-------------|----------------|
| **HIPAA Technical Safeguards** | AES-256 at rest, TLS 1.2+ in transit, RBAC, audit logs (6+ year retention) |
| **Data Minimization** | Retrieve only necessary chunks; never send full PHI to LLM APIs unless BAA exists |
| **Business Associate Agreements** | Required for all third-party API providers (OpenAI, Anthropic, etc.) |
| **Access Controls** | Role-based; minimum necessary principle; quarterly access reviews |
| **FDA Consideration** | If system suggests diagnoses/treatments -> SaMD requiring 510(k). If information retrieval only -> likely exempt as CDS tool. |
| **EU AI Act** | High-risk classification; requires QMS, ISO 14971 risk management, human oversight |

---

## 13. Success Metrics & Evaluation

### 13.1 RAG Evaluation

| Metric | Target | Method |
|--------|--------|--------|
| Context Precision | >0.85 | Relevant chunks in top-k |
| nDCG@10 (after reranking) | >0.85 | Ranking quality |
| Faithfulness | >0.90 | RAGAS automated + spot-check |
| Answer Relevance | >0.85 | RAGAS automated |
| Unsupported Sentence Ratio | <0.15 | Expert review |
| Latency (P95) | <3s | End-to-end with reranking |
| API Cost per Query | <$0.05 | Tracked via Langfuse |

### 13.2 Autocomplete Evaluation

| Metric | Target | Method |
|--------|--------|--------|
| Precision@K | >95% | Valid entities in top-K |
| MRR | >0.85 | Mean reciprocal rank |
| Type Correctness | >98% | Match declared field semantic type |
| Query Latency (P50) | <20ms (<10ms cached) | Server-side only |
| Query Latency (P95) | <50ms | Server-side only |
| Keystroke Savings | >60% | vs. manual typing |
| Cache Hit Rate | >40% | Redis metrics |

---

## 14. Implementation Roadmap

| Phase | Timeline | Objective | Key Deliverable |
|-------|----------|-----------|-----------------|
| **Phase 1: Foundation** | Week 1 | Local dev environment + project skeleton | uv + Python 3.12; Docker Compose (Qdrant + Redis); repo structure; shared models |
| **Phase 2: RAG Pipeline** | Weeks 2-4 | Working question-answering over pediatric corpus | PDF ingestion; chunking; BGE embeddings; Qdrant `rag_chunks`; basic `/chat` endpoint |
| **Phase 3: RAG Enhancements** | Weeks 4-6 | Production-ready RAG | Hybrid search; two-tier reranker; Redis cache + invalidation; request deduplication; Langfuse; RAGAS eval |
| **Phase 4: Autocomplete Foundation** | Implemented | Autocomplete skeleton with placeholder entities | SciSpaCy extraction; pluggable entity provider; trie; fuzzy matching; semantic expansion; `/autocomplete` endpoint; Redis cache; rate limiting |
| **Phase 5: UMLS Integration** | After license approval | Full UMLS-backed autocomplete | QuickUMLS + GLiNER; CUI/TUI normalization; SapBERT vectors; all 127 TUI filters |
| **Phase 6: Production Hardening** | Weeks 8-10 | Compliance, security, deployment | HIPAA-aligned setup; audit logging; admin dashboard; VPS deployment; load testing |

**Dependencies:** Phase 2 → Phase 3. Phase 1 infrastructure is reused by Phases 2–6. Phase 5 is blocked until UMLS license is approved. Phase 6 requires both RAG and autocomplete to be functional.

---

## 15. Method Selection Analysis

### 15.1 v1.0 Core Architecture -- OPTIMAL

| Decision | Selected | Status | Justification |
|----------|----------|--------|---------------|
| **Vector DB** | Qdrant (self-hosted) | Best choice | Lowest P95 latency, native hybrid search, scalar quantization, HIPAA-friendly |
| **RAG Framework** | LlamaIndex | Best choice | Highest retrieval accuracy (71%), lowest token overhead, best medical PDF support |
| **Embedding (RAG)** | BGE-Base-v1.5 | Best choice | Contrastive fine-tuning outperforms domain pretraining |
| **Embedding (AC)** | SapBERT | Best choice | Pretrained on UMLS synonym pairs; optimal for entity linking |
| **NER/Extraction** | **SciSpaCy-only initially**; QuickUMLS + GLiNER after UMLS license | Best choice | SciSpaCy is license-free and sufficient for v1 placeholder; full ensemble once UMLS is approved |
| **Chunking** | Dynamic token + overlap | Best choice | 87% nDCG@5 vs 72% fixed-size; preserves clinical context |
| **LLM Strategy** | API-only (GPT-4o/Claude) | Best choice | State-of-the-art accuracy; no local GPU needed |
| **Autocomplete Index** | Trie + Vector + RRF | Best choice | <1ms prefix + semantic richness + optimal merge |
| **Reranker (Tier 1)** | MiniLM cross-encoder | Best choice | ~5ms/pair; adds only ~100ms; sufficient for most queries |
| **Reranker (Tier 2)** | BGE-Reranker-v2-M3 | Best choice | ~20ms/pair; +10-15% accuracy for critical queries |
| **Cache** | Redis | Best choice | Industry standard; sub-millisecond reads; invalidation support |
| **Observability** | Langfuse | Best choice | Open-source; built for LLM tracing; cost and latency tracking |
| **Evaluation** | RAGAS + custom test suite | Best choice | Automated; no manual labeling per deploy; tracks drift |
| **Deployment** | VPS (Hetzner CPX41) | Best choice | 4x cheaper than managed; sufficient for 5GB/20 users |
| **API Server** | FastAPI + Uvicorn | Best choice | Async native; 4+ workers for concurrency |

### 15.2 v2.0 Deferred Methods -- APPROPRIATELY SCOPED

| Method | Deferral Reason | v2.0 Trigger |
|--------|----------------|--------------|
| **Query Expansion (HyDE)** | Adds latency; current retrieval sufficient | Context recall <0.80 for complex queries |
| **GraphRAG (SNOMED/UMLS KG)** | Requires major knowledge graph infrastructure | User demand for relationship-based reasoning |

---

## 16. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hallucination in clinical answers | Medium | Critical | Strict citation prompting, confidence thresholds, two-tier reranking, human-in-the-loop review |
| PHI data breach | Low | Critical | Self-hosted Qdrant, encryption, BAAs, no PHI in LLM prompts |
| LLM API rate limiting / downtime | Medium | High | **Cached answers serve stale-but-valid responses**; circuit breaker; queue for retry (no local LLM fallback on VPS without GPU) |
| Full reindexing takes 8-12 hours | High (without incremental) | Medium | **RAG-12 incremental indexing** -- add/update individual PDFs without full reindex |
| Reranker latency spikes | Low | Medium | Timeout fallback to vector-only retrieval; monitor via Langfuse |
| Cache serves stale data after PDF update | Medium (without invalidation) | High | **Cache invalidation on reindex** -- version key + source-based clearing |
| Cache stampede on popular query | Low | Medium | Redis TTL jitter; **RAG-13 request deduplication**; cache warming |
| Regulatory non-compliance | Medium | High | Legal review, QMS documentation, avoid diagnostic claims in v1.0 |
| UMLS license delay | Medium | Low | **SciSpaCy-only pipeline for initial development**; add QuickUMLS after license |
| Concurrent duplicate queries cause duplicate LLM API calls | Medium | Medium | **RAG-13 request deduplication** via Redis in-flight lock |

---

## 17. Conclusion

This PRD defines a **technically robust, financially viable, and production-ready** Medical AI system. The v1.0 architecture incorporates **two-tier reranking, caching with invalidation, incremental indexing, request deduplication, rate limiting, observability, and automated evaluation** as first-class components, while appropriately deferring **Query Expansion and GraphRAG** to v2.0 based on production telemetry and user feedback.

**Immediate next steps:**
1. Set up `uv` with Python 3.12 and remove old `.venv`
2. Create repository structure under `services/` and `shared/`
3. Add Docker Compose for Qdrant + Redis only
4. Implement Phase 1 (PDF parsing + chunking + Qdrant indexing + incremental payload)
5. Build basic `/chat` endpoint as Phase 2 milestone
6. Set up Langfuse Cloud (free tier) for development observability
7. Await UMLS license approval before Phase 5 entity integration

---

**Document Owner:** Product & Engineering Team  
**Reviewers:** Clinical Advisor, Compliance Officer, DevOps Lead  
**Next Review Date:** July 5, 2026
