# MedService TODO

## 1. Fix PDF text preprocessing, sanitization, and entity noise filtering (HIGH PRIORITY — IN PROGRESS)

**Reason:**
The current `PyMuPDFParser` extracts text page-by-page without cleaning line breaks. This creates two major data-quality issues that propagate into chunks, entities, autocomplete, and retrieval:

1. **Hyphenated word continuations** — words split across lines are captured with trailing hyphens, e.g. `Genito-uri-`, `bulbar fis-`, `International Classi-\nfication`. These appear as bogus autocomplete suggestions and pollute the vector index.
2. **Literal newlines inside entities** — 13,529 extracted entities contain `\n`, e.g. `Köln\nGermany`, `Peter \nDe Vries`. This breaks autocomplete display and semantic search quality.
3. **Corrupted PDF glyphs** — control characters, private-use glyphs, and Unicode replacement characters leak into suggestions, e.g. `Cord\x08\ufffd\ufffd`.
4. **Non-medical noise** — author names, URLs, citations, headers/footers, and numeric-only fragments are extracted as entities.

**Implementation:**
- Added `shared/ingestion/text_cleaner.py` with `TextCleaner`.
- Applied it in `PyMuPDFParser` and `MarkerPDFParser`.
- Handles intra-page and cross-page hyphenation, newline normalization, paragraph-break preservation, and Unicode artifact removal.
- Added `_is_noise_entity()` filter in `shared/entities/entity_provider.py` for authors, URLs, citations, headers/footers, numeric-only strings, and corrupted tokens.
- Tests in `tests/test_text_cleaner.py` and `tests/test_entity_provider_filtering.py`.

**Remaining step:**
Re-run entity extraction and indexing to regenerate `data/processed/entities/scispacy_entities.json` and the `entities` Qdrant collection.

**Long-running command:**

```bash
uv run extract-entities && uv run index-entities
```

**Impact:**
Cleaner autocomplete, better chunk quality, improved RAG retrieval, and smaller entity index.

---

*This file is intentionally lightweight. Larger planning docs live in `phases/`.*
