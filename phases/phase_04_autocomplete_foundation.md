# Phase 4: Autocomplete Foundation

## Goal
Build the autocomplete skeleton using SciSpaCy-extracted placeholder entities, with a design that swaps cleanly to UMLS later.

## Duration
Weeks 6–7

## Prerequisites
- Phase 1 and Phase 2 completed
- PDF ingestion pipeline working
- Qdrant + Redis running
- UMLS license **not yet required**

## Tasks

### 1. Pluggable Entity Provider (`shared/models/entity_provider.py`)
- Define protocol:
  ```python
  class EntityProvider(Protocol):
      def get_entities(self) -> list[Entity]: ...
      def get_types(self) -> list[str]: ...
  ```
- Implement `SciSpaCyEntityProvider`:
  - Run SciSpaCy models over corpus
  - Extract entities with labels (e.g., `DISEASE`, `CHEMICAL`, `GENE`)
  - Map labels to temporary internal types
  - Generate `Entity` objects with nullable `cui` and `tuis`

### 2. Entity Extraction Script
- `scripts/extract_entities.py`
- Process all PDFs and output entity list
- Store under `data/processed/entities/scispacy_entities.json`

### 3. Qdrant `entities` Collection Skeleton
- 768-dim vectors
- Distance: cosine
- int8 quantization
- Payload: `entity_id`, `term`, `aliases`, `tuis`, `cui`, `source_id`
- Create even if empty initially

### 4. Trie / Prefix Index (`services/autocomplete/service/trie.py`)
- Use `pygtrie` or custom radix tree
- Insert all entity terms + aliases
- Support prefix search with limit

### 5. Fuzzy Matching (`shared/models/fuzzy.py`)
- Levenshtein distance ≤ 2
- Applied only when `fuzzy=true`
- Keep fast path for exact prefix matches

### 6. Entity Embeddings (Optional but Recommended)
- Embed placeholder entities with BGE-Base-v1.5 or a small model
- Store in Qdrant `entities` collection
- Enables semantic similarity search

### 7. Reciprocal Rank Fusion (`shared/models/rrf.py`)
- Generic RRF function
- Merge trie results + vector results
- Parameter `k=60`, configurable alpha

### 8. Autocomplete Service (`services/autocomplete/service/autocomplete_service.py`)
- Query pipeline:
  1. Check Redis cache
  2. Trie prefix search
  3. Fuzzy fallback
  4. Vector semantic search (if enabled)
  5. RRF merge
  6. Filter by temporary internal types
  7. Rank and return top-k

### 9. FastAPI `/autocomplete` Endpoint
- `POST /api/v1/autocomplete`
- Accept: `query`, `field_types`, `limit`, `fuzzy`, `semantic_expansion`
- Return: ranked results with `term`, `cui` (null), `tuis` (internal types), `aliases`, `match_type`, `score`

### 10. Rate Limiting (`shared/rate_limit/`)
- Token bucket algorithm via Redis
- 60 req/min per IP
- Burst: 10
- HTTP 429 with `Retry-After` header

### 11. Redis Autocomplete Cache
- Key: `ac:{field_types_hash}:{query_prefix}:{fuzzy_flag}`
- TTL: 24 hours

### 12. Frontend Autocomplete Input
- React/Vue input component
- Support `data-entity-types` attribute
- Wire to `/autocomplete` endpoint

## Key Considerations

- **Autocomplete is intentionally a skeleton.** CUIs and real TUIs come in Phase 5.
- **Type filter API must accept `"all"` and lists** so the contract is stable.
- **Trie must support incremental insertion** for Phase 5 entity additions.
- **Keep entity provider swappable.** Phase 5 should only require implementing `UMLSEntityProvider`.

## Verification Checklist

- [ ] `scripts/extract_entities.py` produces a non-empty entity list
- [ ] Qdrant `entities` collection exists with correct schema
- [ ] Trie returns prefix matches in <5ms
- [ ] Fuzzy matching handles typos (e.g., "diabetis" → "diabetes")
- [ ] `/autocomplete` returns ranked results
- [ ] Rate limiter blocks requests after 60/min
- [ ] Redis cache returns repeated queries in <10ms
- [ ] Frontend input calls `/autocomplete` and displays suggestions
- [ ] API response schema matches PRD contract (with nullable cui/tuis)

## Outputs / Deliverables

1. `EntityProvider` protocol + `SciSpaCyEntityProvider`
2. `scripts/extract_entities.py`
3. Qdrant `entities` collection
4. Trie + fuzzy matching modules
5. RRF utility
6. Autocomplete service
7. `/api/v1/autocomplete` endpoint
8. Rate limiter
9. Redis autocomplete cache
10. Frontend autocomplete component
