# MedService API Reference

Production base URLs:

- **RAG Chat Agent:** `https://med.primeworld.tech`
- **Semantic Autocomplete:** `https://med-api.primeworld.tech`

Both services expose `/api/v1/health` and a primary POST endpoint under `/api/v1/`.

---

## RAG Chat Agent

### `GET /api/v1/health`

Health check.

**Example request**

```bash
curl https://med.primeworld.tech/api/v1/health
```

**Example response**

```json
{
  "status": "ok",
  "service": "rag_chat_agent"
}
```

---

### `POST /api/v1/chat`

Retrieval-augmented chat over the pediatric surgery/urology corpus.

**URL**

```
https://med.primeworld.tech/api/v1/chat
```

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | User question. |
| `conversation_id` | string | `null` | Optional session id for future continuity. |
| `model` | string | `null` | LLM model override (falls back to `DEFAULT_LLM_MODEL` from env). |
| `top_k` | integer | `20` | Number of chunks to retrieve (1–100). |
| `rerank_top_k` | integer | `5` | Number of chunks after reranking (1–20). |
| `reranker` | string | `"minilm"` | Reranker tier: `"minilm"` or `"bge-reranker-v2-m3"`. |
| `hybrid_search` | boolean | `true` | Combine dense + keyword retrieval. |
| `require_citations` | boolean | `true` | Return source citations. |
| `confidence_threshold` | float | `0.65` | Minimum citation score (0.0–1.0). |
| `max_tokens` | integer | `2048` | Max LLM output tokens (256–8192). |
| `use_cache` | boolean | `true` | Allow cached responses. |

**Example request**

```bash
curl -X POST https://med.primeworld.tech/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What are the causes of hypospadias?",
    "top_k": 20,
    "rerank_top_k": 5,
    "require_citations": true,
    "max_tokens": 2048
  }'
```

**Example response**

```json
{
  "answer": "The causes of hypospadias are heterogeneous...",
  "citations": [
    {
      "chunk_id": "d14715e7-12f2-5ed5-bc11-66dc0a9eaf41",
      "source_id": "coran_pediatric_surgery_part_3",
      "source_title": null,
      "page": 378,
      "score": 0.9799
    }
  ],
  "confidence": 0.93,
  "confidence_passed": true,
  "tokens_used": 5595,
  "trace_id": "8abaffbb-93d7-427b-80ad-1d2c974524cc",
  "reranker_used": "minilm",
  "cached": false
}
```

---

## Semantic Autocomplete

### `GET /api/v1/health`

Health check.

**Example request**

```bash
curl https://med-api.primeworld.tech/api/v1/health
```

**Example response**

```json
{
  "status": "ok",
  "service": "autocomplete"
}
```

---

### `POST /api/v1/autocomplete`

Field-aware medical term autocomplete over SciSpaCy-extracted entities.

**URL**

```
https://med-api.primeworld.tech/api/v1/autocomplete
```

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | Typed prefix or phrase. |
| `field_types` | string or list | `"all"` | Semantic type filter. Use `"all"` or a list of TUIs. |
| `limit` | integer | `10` | Max results to return (1–50). |
| `fuzzy` | boolean | `true` | Enable fuzzy/typo-tolerant matching. |
| `semantic_expansion` | boolean | `true` | Include vector similarity results. |

**Example request — with semantic expansion**

```bash
curl -X POST https://med-api.primeworld.tech/api/v1/autocomplete \
  -H 'Content-Type: application/json' \
  -d '{"query":"vesico","limit":5}'
```

**Example response**

```json
{
  "query": "vesico",
  "field_types": "all",
  "results": [
    {
      "term": "vesico",
      "cui": null,
      "tuis": ["TUI-ENTITY"],
      "aliases": [],
      "match_type": "prefix",
      "score": 1.0
    },
    {
      "term": "large vesico",
      "cui": null,
      "tuis": ["TUI-ENTITY"],
      "aliases": [],
      "match_type": "semantic",
      "score": 0.3272
    }
  ],
  "latency_ms": 152.77,
  "cached": false
}
```

**Example request — without semantic expansion**

```bash
curl -X POST https://med-api.primeworld.tech/api/v1/autocomplete \
  -H 'Content-Type: application/json' \
  -d '{"query":"myo","limit":5,"semantic_expansion":false}'
```

**Example response**

```json
{
  "query": "myo",
  "field_types": "all",
  "results": [
    {
      "term": "MYOG",
      "cui": null,
      "tuis": ["TUI-ENTITY"],
      "aliases": [],
      "match_type": "prefix",
      "score": 1.0
    },
    {
      "term": "myo-",
      "cui": null,
      "tuis": ["TUI-ENTITY"],
      "aliases": [],
      "match_type": "fuzzy",
      "score": 1.0
    }
  ],
  "latency_ms": 70.1,
  "cached": false
}
```

### Match types

| Type | Description |
|---|---|
| `prefix` | Entity starts with the typed query. |
| `fuzzy` | Typo-tolerant match (rapidfuzz). |
| `semantic` | Vector-similar entity from Qdrant. |

### Performance note

Semantic expansion adds ~50–80 ms of latency per uncached query and loads the sentence-transformers embedding model into memory on first use. For a lighter, faster autocomplete, set `semantic_expansion: false`.
