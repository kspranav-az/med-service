# Phase 5: UMLS Integration

## Goal
Replace SciSpaCy placeholder entities with full UMLS-backed entities: CUIs, all 127 TUIs, and SapBERT embeddings.

## Duration
After UMLS license approval; estimated 2–3 weeks

## Prerequisites
- Phase 4 completed
- UMLS license approved
- UMLS Metathesaurus downloaded and accessible
- QuickUMLS and GLiNER installed

## Tasks

### 1. UMLS Data Setup
- Download UMLS Metathesaurus
- Load MRCONSO.RRF, MRSTY.RRF for English terms + types
- Build local term → CUI + TUI mapping

### 2. UMLS Entity Provider (`shared/models/entity_provider.py`)
- Implement `UMLSEntityProvider`:
  - Query UMLS for candidate terms
  - Return `Entity` with `cui`, `tuis`, `aliases`
- Keep `SciSpaCyEntityProvider` as fallback for development

### 3. NER Ensemble
- Integrate QuickUMLS + GLiNER
- Use QuickUMLS for UMLS-aware matching
- Use GLiNER for additional entity boundary detection
- Ensemble strategy: union + confidence filtering

### 4. Entity Extraction over Corpus
- Run ensemble NER over all 24 PDFs
- Normalize to CUIs
- Assign all 127 TUIs
- Store in `data/processed/entities/umls_entities.json`

### 5. SapBERT Embeddings
- Load `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`
- Embed all UMLS entity terms + aliases
- Store vectors in Qdrant `entities` collection
- Replace or augment placeholder vectors

### 6. Full TUI Filter Implementation
- Validate TUI codes in API requests
- Support single type, multi-type union, and `"all"`
- Filter trie and vector results by TUI

### 7. Incremental Entity Updates
- When a new PDF is ingested:
  - Extract entities
  - Add to trie
  - Upsert vectors to Qdrant
  - Update manifest
- When a PDF is updated/deleted:
  - Remove old entities by `source_id`
  - Add new entities

### 8. Autocomplete Accuracy Benchmarks
- Build evaluation set of pediatric form-field queries
- Metrics:
  - Precision@K >95%
  - MRR >0.85
  - Type Correctness >98%
  - P50 latency <20ms (<10ms cached)
  - P95 latency <50ms

### 9. Replace Provider in Config
- Switch `ENTITY_PROVIDER=scispacy` → `ENTITY_PROVIDER=umls`
- Restart autocomplete service
- Verify no API contract changes

## Key Considerations

- **UMLS download is large (~20–40GB).** Ensure disk space and do not commit it.
- **QuickUMLS can be slow to build its CUI/term database.** Allocate time for initial setup.
- **Keep SciSpaCy provider available** for offline development or if UMLS data is unavailable.
- **Alias expansion is critical** for autocomplete quality.
- **TUI validation must reject invalid codes** with clear 400 errors.

## Verification Checklist

- [ ] UMLS Metathesaurus is loaded and queryable
- [ ] `UMLSEntityProvider` returns entities with valid CUIs
- [ ] All 127 TUIs are represented in the entity index
- [ ] `/autocomplete` with `field_types=T047` returns only disease/disorder entities
- [ ] `/autocomplete` with `field_types=all` returns entities across all types
- [ ] SapBERT vectors are stored in Qdrant `entities`
- [ ] Incremental entity update works when reindexing a source
- [ ] Precision@K >95% on evaluation set
- [ ] P95 latency <50ms
- [ ] API contract remains unchanged from Phase 4

## Outputs / Deliverables

1. UMLS loading utilities
2. `UMLSEntityProvider`
3. QuickUMLS + GLiNER NER ensemble
4. UMLS entity extraction script
5. SapBERT embedding pipeline
6. Full TUI filter implementation
7. Incremental entity update support
8. Autocomplete benchmark suite
9. Updated config with UMLS provider
