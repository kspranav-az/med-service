# Phase 3: RAG Enhancements

## Goal
Make the RAG system production-ready with reranking, caching, deduplication, evaluation, and observability.

## Duration
Weeks 4–6

## Prerequisites
- Phase 2 completed
- Basic `/chat` endpoint working
- Qdrant `rag_chunks` populated

## Tasks

### 1. Hybrid Search
- Add sparse vector support or keyword fallback in Qdrant
- Combine dense + keyword results (initially simple concat or RRF)
- Make hybrid search configurable per request

### 2. Two-Tier Reranking (`services/rag_chat_agent/service/reranker.py`)
- Implement reranker interface:
  ```python
  class Reranker(Protocol):
      def rerank(self, query: str, chunks: list[Chunk]) -> list[Chunk]: ...
  ```
- Tier 1: `cross-encoder/ms-marco-MiniLM-L-6-v2` (default)
- Tier 2: `BAAI/bge-reranker-v2-m3` (quality mode)
- Select via `reranker` field in request
- Add `rerank_top_k` parameter

### 3. Redis Caching (`shared/cache/`)
- RAG context cache:
  - Key: `rag_ctx:{query_hash}:{top_k}:{reranker}`
  - Value: list of chunk IDs + scores
  - TTL: 1 hour
- Cache version key:
  - `cache_version` global counter
  - Incremented on any source reindex
  - Cache lookup checks version
- Source-level invalidation helper

### 4. Request Deduplication (`shared/cache/dedup.py`)
- Compute query hash
- Check Redis `inflight:{query_hash}` lock
- If lock exists: wait/subscribe for result
- If not: acquire lock (5s TTL), process, publish result, release lock

### 5. Conversation History
- Store conversation turns in Redis or SQLite
- Include recent history in LLM prompt
- Support `conversation_id` in `/chat`

### 6. Confidence Thresholding
- Compute confidence score from retrieval scores + reranker scores
- If below threshold, return warning or defer response
- Expose `confidence_threshold` in API

### 7. Langfuse Tracing
- Add spans:
  - `query_preprocessing`
  - `vector_retrieval`
  - `reranking`
  - `llm_generation`
  - `post_processing`
- Log scores, token usage, cost, latency per span

### 8. RAGAS Evaluation
- Create evaluation test set: 50–100 pediatric QA pairs
- Run RAGAS metrics:
  - Faithfulness
  - Answer Relevance
  - Context Precision
  - Context Recall
- Schedule as script `scripts/evaluate_rag.py`

### 9. Admin Endpoints
- `GET /api/v1/admin/index/status` — counts per source
- `GET /api/v1/admin/query/logs` — recent query traces
- `POST /api/v1/admin/feedback` — thumbs up/down on answers

## Key Considerations

- **Reranker latency:** Tier 2 may add 300–500ms. Allow clients to choose.
- **Cache invalidation:** Always bump version on source reindex; source-level invalidation is best-effort.
- **Deduplication TTL:** 5 seconds balances crash safety vs. false blocking.
- **Evaluation:** Start with manual QA pairs; expand over time.
- **Cost tracking:** Log LLM tokens and estimated cost in every Langfuse trace.

## Verification Checklist

- [ ] Tier 1 reranker improves ranking over vector-only retrieval
- [ ] Tier 2 reranker selectable via API
- [ ] Redis cache returns results for repeated queries
- [ ] Reindexing a source invalidates relevant cache entries
- [ ] Simultaneous identical queries trigger only one LLM call
- [ ] Conversation history changes answers contextually
- [ ] RAGAS faithfulness >0.80 on test set
- [ ] End-to-end P95 latency <3s with Tier 1 reranker
- [ ] Langfuse shows full trace per request

## Outputs / Deliverables

1. Hybrid search implementation
2. Two-tier reranker module
3. Redis cache + invalidation module
4. Request deduplication module
5. Conversation history module
6. Confidence scoring module
7. RAGAS evaluation script
8. Admin endpoints
9. Updated `/api/v1/chat` with all options
