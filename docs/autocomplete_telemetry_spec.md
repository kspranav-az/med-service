# MedService Autocomplete Telemetry Specification

This document is a technical contract for the data that Nori-Tura will send to MedService so that MedService can adapt its autocomplete ranking for the next phase.

**Scope:** This is a planning/spec document. No code changes are included.

---

## 1. Purpose

MedService currently returns autocomplete suggestions ordered by a combination of:

- prefix match score
- fuzzy match score
- semantic match score (when enabled)

These scores are generic. By receiving real selection feedback from Nori-Tura users, MedService can:

1. Boost terms that are actually chosen for a given field.
2. Learn which short queries (e.g. `lap`, `ga`, `cbc`) map to which full terms per field.
3. Build field-specific ranking models instead of relying on a single global index.
4. Optionally personalise suggestions per clinic or per surgeon in the future.

---

## 2. Architecture Overview

```
┌─────────────────┐     selection events        ┌──────────────────────┐
│  KMP Mobile App │ ───────────────────────────>│ Nori-Tura Backend    │
│                 │  (batched, with JWT auth)   │                      │
└─────────────────┘                             │  - validate          │
                                                │  - aggregate         │
                                                │  - forward to        │
                                                │    MedService        │
                                                └──────────┬───────────┘
                                                           │
                              aggregated telemetry         │
                              (API-key auth)               │
                                                           ▼
                                                ┌──────────────────────┐
                                                │ MedService           │
                                                │  - ingest feedback   │
                                                │  - update ranking    │
                                                │  - serve /autocomplete
                                                └──────────────────────┘
```

**Why not send directly from mobile to MedService?**

- The mobile client already authenticates to the Nori-Tura backend.
- The backend can validate, sanitise, and aggregate before forwarding.
- It avoids exposing the public `/autocomplete` endpoint to additional auth/rate-limit complexity.
- MedService can receive a single nightly batch per hospital instead of thousands of individual mobile requests.

---

## 3. Data Collection on Mobile

### 3.1 Event trigger

Every time a user selects a suggestion from the autocomplete dropdown, record an event:

```
onSuggestionSelected(
    fieldType: String?,          // e.g. "procedure", "approach", "anaesthesia"
    query: String,               // the token the user typed, e.g. "lap"
    selectedTerm: String,        // the full term they selected, e.g. "Laparoscopic"
    suggestionPosition: Int,     // 0-based index in the dropdown
    matchType: String?,          // "prefix" | "fuzzy" | "semantic" (from server response)
    score: Double?,              // server score for the selected term
    screen: String?              // e.g. "ConsentFormScreen", "AdmissionDetailScreen"
)
```

### 3.2 Local persistence

Events are buffered locally in a small queue. Two flushing strategies:

1. **Count-based:** flush when the buffer reaches 20–50 events.
2. **Time-based:** flush when the app goes to background, or every 6–24 hours.

If the flush fails, the buffer is kept and retried later.

### 3.3 Anonymisation on the device

- No patient identifiers.
- No free-text clinical notes — only the selected suggestion term.
- A stable, random `device_install_id` may be included for debugging, but it should not be linked to the user account or patient data.

---

## 4. Nori-Tura Backend Aggregation

Before forwarding to MedService, the Nori-Tura backend aggregates events into two artefacts:

### 4.1 Aggregated histograms (primary input for ranking)

Per field, count how many times each term was selected within the aggregation window.

```json
{
  "window_start": "2026-08-29T00:00:00Z",
  "window_end": "2026-08-30T00:00:00Z",
  "source": "noni-tura",
  "hospital_id": "9261bc48-eb7e-410a-901a-7880640b2f63",
  "histograms": {
    "approach": {
      "Laparoscopic": 45,
      "Open": 12,
      "Robotic": 3
    },
    "anaesthesia": {
      "General anaesthesia": 67,
      "Spinal anaesthesia": 14,
      "Local anaesthesia": 5
    },
    "procedure": {
      "Appendectomy": 23,
      "Laparoscopic appendectomy": 18,
      "Orchidopexy": 9
    }
  }
}
```

### 4.2 Query-to-selection map (secondary input for learning)

For learning short-query mappings, aggregate `(field, query, selected_term, count)`.

```json
{
  "window_start": "2026-08-29T00:00:00Z",
  "window_end": "2026-08-30T00:00:00Z",
  "source": "noni-tura",
  "hospital_id": "9261bc48-eb7e-410a-901a-7880640b2f63",
  "query_selections": [
    {
      "field_type": "approach",
      "query": "lap",
      "selected_term": "Laparoscopic",
      "count": 38
    },
    {
      "field_type": "anaesthesia",
      "query": "gen",
      "selected_term": "General anaesthesia",
      "count": 52
    }
  ]
}
```

### 4.3 Raw event sample (optional, for deep analytics)

If MedService wants raw events for model training, a sampled subset can be sent separately. This is optional and should be batched.

```json
{
  "source": "noni-tura",
  "hospital_id": "9261bc48-eb7e-410a-901a-7880640b2f63",
  "sample_rate": 0.1,
  "events": [
    {
      "field_type": "approach",
      "query": "lap",
      "selected_term": "Laparoscopic",
      "suggestion_position": 0,
      "match_type": "prefix",
      "score": 1.0,
      "screen": "AdmissionDetailScreen",
      "timestamp": "2026-08-29T14:32:10Z"
    }
  ]
}
```

---

## 5. MedService API Contract

### 5.1 Endpoint

```
POST https://med-api.primeworld.tech/api/v1/autocomplete/feedback
```

### 5.2 Authentication

- **Mechanism:** API key in header.
- **Header:** `X-API-Key: <noritura-backend-key>`
- MedService issues one key per integrated client (Nori-Tura backend).

### 5.3 Request headers

```http
POST /api/v1/autocomplete/feedback HTTP/1.1
Host: med-api.primeworld.tech
Content-Type: application/json
X-API-Key: noritura_prod_xxxxxxxx
```

### 5.4 Request body

A single payload containing histograms, query-selections, and optionally sampled raw events.

```json
{
  "meta": {
    "source": "noni-tura",
    "source_version": "1.2.0",
    "hospital_id": "9261bc48-eb7e-410a-901a-7880640b2f63",
    "window_start": "2026-08-29T00:00:00Z",
    "window_end": "2026-08-30T00:00:00Z",
    "sent_at": "2026-08-30T01:00:00Z"
  },
  "histograms": {
    "approach": {
      "Laparoscopic": 45,
      "Open": 12,
      "Robotic": 3
    },
    "anaesthesia": {
      "General anaesthesia": 67,
      "Spinal anaesthesia": 14,
      "Local anaesthesia": 5
    },
    "procedure": {
      "Appendectomy": 23,
      "Laparoscopic appendectomy": 18
    },
    "diagnosis": {
      "Acute appendicitis": 19,
      "Inguinal hernia": 11
    }
  },
  "query_selections": [
    {
      "field_type": "approach",
      "query": "lap",
      "selected_term": "Laparoscopic",
      "count": 38
    },
    {
      "field_type": "anaesthesia",
      "query": "gen",
      "selected_term": "General anaesthesia",
      "count": 52
    }
  ],
  "sampled_events": [
    {
      "field_type": "approach",
      "query": "lap",
      "selected_term": "Laparoscopic",
      "suggestion_position": 0,
      "match_type": "prefix",
      "score": 1.0,
      "screen": "AdmissionDetailScreen",
      "timestamp": "2026-08-29T14:32:10Z"
    }
  ]
}
```

### 5.5 Field type values

The mobile app will send the following `field_type` values. MedService should treat unknown values as `"all"`.

| Value | Used in screen |
|---|---|
| `procedure` | OPD planned procedure, IPD notes, consent form, surgical templates |
| `approach` | IPD notes, surgical templates |
| `anaesthesia` | IPD notes, consent form, surgical templates |
| `investigation` | OPD investigations, IPD pre-op |
| `diagnosis` | OPD diagnosis, consent form |
| `complaint` | OPD chief complaint |
| `examination` | OPD examination findings |
| `medication` | OPD medications, discharge meds |
| `risk` | Consent form risks |
| `benefit` | Consent form benefits |
| `alternative` | Consent form alternatives |
| `complication` | Consent form / IPD complications |
| `post_op_care` | Consent form / surgical templates |
| `expected_recovery` | Consent form / surgical templates |
| `technique` | IPD intra-op, surgical templates |
| `finding` | IPD intra-op findings |
| `condition` | IPD post-op / discharge |
| `wound_status` | IPD post-op |
| `diet` | IPD post-op / discharge |
| `all` | Fallback when no field context is available |

### 5.6 Response

```json
{
  "status": "ok",
  "records_processed": 3,
  "window_start": "2026-08-29T00:00:00Z",
  "window_end": "2026-08-30T00:00:00Z"
}
```

### 5.7 Error handling

- `400 Bad Request` — malformed payload.
- `401 Unauthorized` — invalid API key.
- `429 Too Many Requests` — backoff and retry.
- `500 Server Error` — Nori-Tura backend retries with exponential backoff.

---

## 6. How MedService Should Use the Data

### 6.1 Short-term: popularity boosting

Maintain a table:

```
term_popularity (
  source,
  hospital_id,
  field_type,
  term,
  selection_count,
  window_start,
  window_end
)
```

When serving `/autocomplete`, compute a final score:

```
final_score = base_score * (1 + log(selection_count + 1) * field_weight)
```

- `base_score` is the existing prefix/fuzzy/semantic score.
- `selection_count` is the historical number of times this term was selected for this field.
- `field_weight` is a tunable parameter (start with 0.1–0.3).

This immediately improves the ranking without retraining models.

### 6.2 Medium-term: query-to-term learning

Use `query_selections` to build a secondary index:

```
query_term_map (
  field_type,
  query,
  selected_term,
  count
)
```

When a user types a query that exists in this map with high count, include the mapped term in the suggestion list even if the base scorer would not have returned it (as long as it is semantically related).

### 6.3 Long-term: field-specific model fine-tuning

- Use sampled raw events as training data for field-specific rerankers.
- Train a small model that predicts `P(selected_term | query, field_type)`.
- Combine the reranker score with the base score.

### 6.4 Decay and freshness

To prevent stale data from dominating:

- Apply a time decay to counts, e.g. exponential moving average over 30-day windows.
- Or keep only the last N windows (e.g. last 90 days).

---

## 7. Privacy and Compliance

### 7.1 What is NOT sent

- Patient names, IDs, phone numbers.
- Free-text notes entered by the user (unless the user explicitly selects a suggested term from the dropdown).
- Exact visit/admission IDs.

### 7.2 What IS sent

- Selected autocomplete term (e.g. "Laparoscopic").
- Field context (e.g. "approach").
- Typed query prefix (e.g. "lap").
- Anonymous selection counts.
- Optional screen name for debugging.

### 7.3 Optional IDs

- `hospital_id` can be included for per-hospital personalisation, but only if the hospital consents.
- `device_install_id` should be a random UUID, not tied to the user account.
- If MedService does not need per-hospital personalisation, `hospital_id` can be omitted or hashed.

---

## 8. Example Full Lifecycle

### Step 1: User types in mobile app

Field: `approach`  
Typed token: `lap`  
Dropdown shows: `Laparoscopic`, `Laparotomy`, `Laparoscopy`  
User taps: `Laparoscopic`

### Step 2: Mobile records event locally

```json
{
  "field_type": "approach",
  "query": "lap",
  "selected_term": "Laparoscopic",
  "suggestion_position": 0,
  "match_type": "prefix",
  "score": 1.0,
  "screen": "AdmissionDetailScreen",
  "timestamp": "2026-08-29T14:32:10Z"
}
```

### Step 3: Buffer reaches threshold / app goes to background

Mobile sends a batch to `POST https://nori-tura.primeworld.tech/analytics/autocomplete`.

### Step 4: Nori-Tura backend aggregates

After 24 hours, it produces:

```json
{
  "meta": {
    "source": "noni-tura",
    "hospital_id": "9261bc48-eb7e-410a-901a-7880640b2f63",
    "window_start": "2026-08-29T00:00:00Z",
    "window_end": "2026-08-30T00:00:00Z"
  },
  "histograms": {
    "approach": { "Laparoscopic": 45, "Open": 12 }
  },
  "query_selections": [
    { "field_type": "approach", "query": "lap", "selected_term": "Laparoscopic", "count": 38 }
  ]
}
```

### Step 5: Nori-Tura backend forwards to MedService

`POST https://med-api.primeworld.tech/api/v1/autocomplete/feedback`

### Step 6: MedService updates ranking

The next time a Nori-Tura user types `lap` in the approach field, `Laparoscopic` appears higher or is returned with a boosted score.

---

## 9. Open Questions for MedService

1. Does MedService prefer per-hospital histograms, or a global aggregate?
2. Should the `hospital_id` be the raw UUID, a hashed value, or omitted entirely?
3. What is the preferred batching window? (daily is recommended)
4. Does MedService want sampled raw events, or only aggregated histograms?
5. What `field_weight` should be used for popularity boosting? (recommend starting at 0.2)
6. Should MedService expose a new parameter (e.g. `user_context`) so Nori-Tura can request hospital-specific ranking?

---

## 10. Files That Will Be Involved (Future Implementation)

- `shared/src/commonMain/kotlin/com/example/nori_tura/presentation/components/MedicalAutoCompleteTextField.kt`
- `shared/src/commonMain/kotlin/com/example/nori_tura/data/MedicalTermRepository.kt`
- New: `shared/src/commonMain/kotlin/com/example/nori_tura/data/AutocompleteTelemetryRepository.kt`
- New: `shared/src/commonMain/kotlin/com/example/nori_tura/data/AutocompleteSelectionCache.kt`
- `backend/app/routers/analytics.py` (or similar)
- MedService: new `/api/v1/autocomplete/feedback` endpoint and ranking update.
