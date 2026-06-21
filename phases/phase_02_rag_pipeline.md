# Phase 2: RAG Pipeline

## Goal
Build a working question-answering system over the 24 pediatric surgery/urology textbooks.

## Duration
Weeks 2–4

## Prerequisites
- Phase 1 completed
- Qdrant and Redis running
- Manifest loader working
- Python dependencies installed

## Tasks

### 1. PDF Ingestion (`shared/ingestion/`)
- Build PDF text extractor using `pypdf` or `pymupdf`
- Extract text + page number per page
- Handle split books (e.g., `campbell_walsh_urology_11e_part_*.pdf`) as a single logical source
- Preserve source metadata: `source_id`, `filename`, `title`, `page_number`
- Add script `scripts/ingest_pdfs.py` to parse a single source or all sources

### 2. Chunking (`shared/chunking/`)
- Implement dynamic token-based chunking
- Target: ~400 tokens per chunk, ~200 token overlap
- Preserve page range metadata in each chunk
- Output schema:
  ```json
  {
    "chunk_id": "arm_holschneider_2_00042",
    "source_id": "arm_holschneider_2",
    "chunk_index": 42,
    "page_start": 120,
    "page_end": 121,
    "text": "..."
  }
  ```

### 3. Embeddings (`shared/embeddings/`)
- Load `BAAI/bge-base-en-v1.5` via sentence-transformers
- Support CPU and MPS backends
- Implement batch embedding function
- Normalize embeddings before storage

### 4. Vector Store (`shared/vector_store/`)
- Create Qdrant `rag_chunks` collection:
  - 768 dimensions
  - Distance: cosine
  - Scalar quantization: int8
  - Payload indexing on `source_id`, `page_number`, `chunk_index`
- Implement:
  - `upsert_chunks(chunks, embeddings, source_id, version)`
  - `delete_by_source(source_id)`
  - `search(query_embedding, top_k, filters=None)`

### 5. Incremental Indexing
- Track source version in Qdrant payload
- Ingest flow:
  1. Parse PDF → chunks
  2. Embed chunks
  3. Delete old points by `source_id`
  4. Insert new points with incremented version
- Add `scripts/reindex_source.py` and `scripts/reindex_all.py`

### 6. Basic RAG Service (`services/rag_chat_agent/`)
- Build `RAGService` class:
  - `retrieve(query, top_k=20)` → vector search
  - `generate(query, chunks, model)` → call LLM API with citation prompt
- Implement prompt template that:
  - Requires answers to be grounded in provided context
  - Includes source/page citations
  - Refuses to answer if context is insufficient
- Integrate with Langfuse tracing

### 7. FastAPI `/chat` Endpoint
- `POST /api/v1/chat`
- Accept: `query`, `conversation_id` (optional), `model`, `top_k`, `require_citations`
- Return: `answer`, `citations`, `confidence`, `trace_id`

## Key Considerations

- **Start with one small PDF** for end-to-end testing, then scale to all 24.
- **Chunking quality is critical.** Test different sizes/overlaps on sample medical queries.
- **MPS may fail on some operations.** Always test CPU fallback.
- **Keep LLM prompts citation-strict** from day one to reduce hallucination.
- **Do not commit embeddings or parsed text.** Store outputs under `data/` which is gitignored.

## Verification Checklist

- [ ] All 24 PDFs can be parsed without fatal errors
- [ ] Total chunk count is reasonable (~50k–150k for this corpus)
- [ ] `rag_chunks` collection exists in Qdrant with correct schema
- [ ] Reindexing a source updates points correctly (version increments, old points removed)
- [ ] `/chat` returns a grounded answer with citations
- [ ] Citations include source title and page number
- [ ] Langfuse traces show retrieval + generation spans
- [ ] End-to-end latency for a simple query is <10s on local dev

## Outputs / Deliverables

1. `shared/ingestion/` PDF parser
2. `shared/chunking/` chunker
3. `shared/embeddings/` embedder
4. `shared/vector_store/` Qdrant client
5. `services/rag_chat_agent/service/rag_service.py`
6. `services/rag_chat_agent/api/chat.py`
7. `scripts/ingest_pdfs.py`, `scripts/reindex_source.py`, `scripts/reindex_all.py`
8. Working `/api/v1/chat` endpoint
