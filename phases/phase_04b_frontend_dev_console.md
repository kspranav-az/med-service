# Phase 4B: Frontend Dev Console

## Goal
Build a single, lightweight web UI for testing all backend services (RAG Chat Agent, Semantic Autocomplete, and future services) without relying on `curl`. This is intended as a developer/debug console, not the final clinician-facing frontend.

## Duration
1–2 days

## Prerequisites
- Phase 1–4 backend services implemented and running locally
- Qdrant and Redis running via `docker compose up -d`
- `entities` collection indexed for autocomplete
- `rag_chunks` collection indexed if testing the chat service

## Tasks

### 1. Scaffold Frontend
Create a `frontend/` directory at the repository root with:

- **React 18**
- **Vite**
- **TypeScript**
- **Tailwind CSS**

Suggested layout:

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── types/
    │   └── api.ts
    ├── api/
    │   ├── chat.ts
    │   ├── autocomplete.ts
    │   └── health.ts
    ├── components/
    │   ├── Layout.tsx
    │   ├── Tabs.tsx
    │   ├── ChatTab.tsx
    │   ├── AutocompleteTab.tsx
    │   └── HealthTab.tsx
    └── hooks/
        └── useDebounce.ts
```

### 2. Enable CORS on Backend Services
Add CORS middleware to both FastAPI apps so the Vite dev server can call them:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Apply to:
- `services/rag_chat_agent/api/main.py`
- `services/autocomplete/api/main.py`

### 3. API Client Layer
Create typed fetch wrappers for each service using environment variables:

```env
VITE_CHAT_API_URL=http://localhost:8000
VITE_AUTOCOMPLETE_API_URL=http://localhost:8001
```

Methods needed:
- `POST /api/v1/chat`
- `POST /api/v1/autocomplete`
- `GET /api/v1/health` on both services

### 4. Chat Tab
UI controls:
- Query input (textarea)
- Model override input
- Reranker selector (`minilm` / `bge-reranker-v2-m3`)
- `top_k` and `rerank_top_k` number inputs
- `require_citations` and `use_cache` toggles
- Submit button

Display:
- Generated answer rendered as Markdown
- Citations list with source id, page, and score
- Confidence score and `confidence_passed` flag
- `cached` flag and latency
- Trace ID

### 5. Autocomplete Tab
UI controls:
- Query input with live debounced autocomplete dropdown
- `field_types` input (e.g., `all`, `T047,T191`)
- `limit` number input
- `fuzzy` toggle
- `semantic_expansion` toggle

Display:
- Suggestion list with term, TUIs, match type (`prefix`/`fuzzy`/`semantic`), score
- `cached` flag and latency

### 6. Health / Status Tab
- Ping `/api/v1/health` on every configured service
- Show reachability, service name, and response time
- Useful for verifying that all backends are up

### 7. Build & Run Scripts
Add npm scripts:

```json
{
  "dev": "vite",
  "build": "tsc && vite build",
  "preview": "vite preview"
}
```

Update root `README.md` with:

```bash
cd frontend
npm install
npm run dev
```

## Key Considerations

- **Dev-only UI.** This console is for testing and debugging, not the final clinical interface.
- **No PHI in logs/state.** Do not persist query history to local storage or logs.
- **CORS origins should be restrictive in production.** `http://localhost:5173` is fine for local dev only.
- **Each backend keeps its own port.** The frontend uses separate base URLs per service rather than a gateway.
- **Future services** should only require adding a new tab + API client under `frontend/src/`.

## Verification Checklist

- [ ] `npm install` completes without errors
- [ ] `npm run dev` starts the console on `http://localhost:5173`
- [ ] CORS middleware allows requests from `http://localhost:5173`
- [ ] Chat tab sends a query and displays an answer with citations
- [ ] Autocomplete tab shows suggestions as the user types
- [ ] Health tab reports both services as reachable
- [ ] Build passes (`npm run build`)
- [ ] Root `README.md` includes frontend setup steps

## Outputs / Deliverables

1. `frontend/` directory with Vite + React + TypeScript + Tailwind scaffold
2. CORS middleware added to both FastAPI services
3. Typed API clients for chat and autocomplete
4. Chat tab, autocomplete tab, and health tab
5. Updated `README.md` with frontend quick-start instructions
