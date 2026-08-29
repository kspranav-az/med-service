# MedService TODO

## 1. Fix PDF text preprocessing: dehyphenation + newline normalization (HIGH PRIORITY — IN PROGRESS)

**Reason:**
The current `PyMuPDFParser` extracts text page-by-page without cleaning line breaks. This creates two major data-quality issues that propagate into chunks, entities, autocomplete, and retrieval:

1. **Hyphenated word continuations** — words split across lines are captured with trailing hyphens, e.g. `Genito-uri-`, `bulbar fis-`, `International Classi-\nfication`. These appear as bogus autocomplete suggestions and pollute the vector index.
2. **Literal newlines inside entities** — 13,529 extracted entities contain `\n`, e.g. `Köln\nGermany`, `Peter \nDe Vries`. This breaks autocomplete display and semantic search quality.

Stats from `data/processed/entities/scispacy_entities.json`:
- Total entities: 465,039
- Entities with hyphens: 44,300
- Entities with literal newlines: 13,529

**Implementation:**
- Added `shared/ingestion/text_cleaner.py` with `TextCleaner`.
- Applied it in `PyMuPDFParser` and `MarkerPDFParser`.
- Handles intra-page and cross-page hyphenation, newline normalization, and paragraph-break preservation.
- Tests in `tests/test_text_cleaner.py`.

**Remaining step:**
Re-run the full preprocessing pipeline to regenerate `qdrant_storage/` and `data/processed/entities/scispacy_entities.json`.

**Long-running command:**

```bash
uv run extract-entities && uv run reindex-all --parser pymupdf --batch-size 32 --restart
```

**Impact:**
Cleaner autocomplete, better chunk quality, improved RAG retrieval, and smaller entity index.

---

*This file is intentionally lightweight. Larger planning docs live in `phases/`.*
