# MedService TODO

## 1. Fix PDF text preprocessing: dehyphenation + newline normalization (HIGH PRIORITY)

**Reason:**
The current `PyMuPDFParser` extracts text page-by-page without cleaning line breaks. This creates two major data-quality issues that propagate into chunks, entities, autocomplete, and retrieval:

1. **Hyphenated word continuations** — words split across lines are captured with trailing hyphens, e.g. `Genito-uri-`, `bulbar fis-`, `International Classi-\nfication`. These appear as bogus autocomplete suggestions and pollute the vector index.
2. **Literal newlines inside entities** — 13,529 extracted entities contain `\n`, e.g. `Köln\nGermany`, `Peter \nDe Vries`. This breaks autocomplete display and semantic search quality.

Stats from `data/processed/entities/scispacy_entities.json`:
- Total entities: 465,039
- Entities with hyphens: 44,300
- Entities with literal newlines: 13,529

**Scope:**
- Add a `TextCleaner` utility in `shared/ingestion/` (or a preprocessing pipeline step) that:
  - Dehyphenates within and across pages (`-\n` → ``, `- \n` → ` `)
  - Normalizes newlines within paragraphs to spaces
  - Optionally strips headers/footers and page numbers
- Apply it before chunking and entity extraction.
- Re-run `ingest_pdfs.py` → `extract_entities.py` → `index_entities.py` → `reindex_all.py`.

**Impact:**
Cleaner autocomplete, better chunk quality, improved RAG retrieval, and smaller entity index.

---

*This file is intentionally lightweight. Larger planning docs live in `phases/`.*
