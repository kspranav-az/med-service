# MedService Project Context

## Overview
MedService is a medical-domain AI toolkit built around a curated corpus of pediatric surgery and urology reference material. The project is organized as a multi-service codebase with shared infrastructure for ingestion, embeddings, and retrieval.

Planned services:
- **RAG Chat Agent** — question-answering over the medical corpus
- **Autocomplete Service** — domain-aware text completion for clinical notes
- Additional services may be added under `services/` as the project grows

## Repository Layout

```
med-service/
├── services/                  # Deployable service modules
│   ├── rag_chat_agent/        # TBD
│   ├── autocomplete/          # TBD
│   └── ...
├── shared/                    # Libraries shared across services
│   ├── ingestion/
│   ├── embeddings/
│   ├── chunking/
│   ├── vector_store/
│   └── corpus_client.py
├── data/                      # NOT committed to Git
│   └── corpus/
│       ├── manifest.json      # Metadata registry for all sources
│       └── books/
│           └── pediatric/     # Domain-specific subfolder
│               └── *.pdf
├── scripts/                   # Utility scripts (ingest, rebuild manifest, etc.)
├── notebooks/                 # Exploration notebooks
├── tests/
├── README.md
├── CONTEXT.md                 # This file
└── AGENTS.md                  # AI-agent specific instructions
```

## Data Corpus

### Location
All source material lives in:
```
data/corpus/books/<domain>/
```

Currently all books are pediatric-focused:
```
data/corpus/books/pediatric/
```

### Manifest
`data/corpus/manifest.json` is the source of truth for the corpus. Each entry has:

```json
{
  "id": "arm_holschneider_2",
  "file": "arm_holschneider_2.pdf",
  "title": "ARM Holschneider (2nd ed.)",
  "pages": 477,
  "tags": ["pediatric-surgery", "colorectal", "anorectal-malformation"],
  "path": "books/pediatric/arm_holschneider_2.pdf",
  "domain": "pediatric"
}
```

### Current Stats
- **Books:** 24
- **Pages:** 19,714
- **Domain:** pediatric
- **Largest source:** Campbell-Walsh Urology (split into 4 parts, 4,899 pages total)

### Full Book List
| File | Title | Pages | Domain |
|------|-------|-------|--------|
| `arm_holschneider_2.pdf` | ARM Holschneider (2nd ed.) | 477 | pediatric |
| `campbell_walsh_urology_11e_part_1.pdf` | Campbell-Walsh Urology 11E - Part 1 | 1,224 | pediatric |
| `campbell_walsh_urology_11e_part_2.pdf` | Campbell-Walsh Urology 11E - Part 2 | 1,224 | pediatric |
| `campbell_walsh_urology_11e_part_3.pdf` | Campbell-Walsh Urology 11E - Part 3 | 1,224 | pediatric |
| `campbell_walsh_urology_11e_part_4.pdf` | Campbell-Walsh Urology 11E - Part 4 | 1,227 | pediatric |
| `coran_pediatric_surgery_part_1.pdf` | Coran Pediatric Surgery - Part 1 | 628 | pediatric |
| `coran_pediatric_surgery_part_2.pdf` | Coran Pediatric Surgery - Part 2 | 628 | pediatric |
| `coran_pediatric_surgery_part_3.pdf` | Coran Pediatric Surgery - Part 3 | 629 | pediatric |
| `dk_gupta_pediatric_surgery_vol_1.pdf` | DK Gupta Pediatric Surgery Vol. 1 | 858 | pediatric |
| `dk_gupta_pediatric_surgery_vol_5.pdf` | DK Gupta Pediatric Surgery Vol. 5 | 681 | pediatric |
| `hadidi_hypospadias.pdf` | Hadidi - Hypospadias | 372 | pediatric |
| `harriet_lane_handbook.pdf` | The Harriet Lane Handbook | 893 | pediatric |
| `hinmans_atlas_pediatric_urologic_surgery_2e.pdf` | Hinman's Atlas of Pediatric Urologic Surgery 2nd ed. | 949 | pediatric |
| `kelalis_king_belman_clinical_pediatric_urology_part_1.pdf` | Kelalis-King-Belman Clinical Pediatric Urology - Part 1 | 739 | pediatric |
| `kelalis_king_belman_clinical_pediatric_urology_part_2.pdf` | Kelalis-King-Belman Clinical Pediatric Urology - Part 2 | 738 | pediatric |
| `meherbaan_singh.pdf` | Meherbaan Singh | 109 | pediatric |
| `nelson_essentials_pediatrics_2018.pdf` | Nelson Essentials of Pediatrics (2018) | 2,301 | pediatric |
| `neofax_2014.pdf` | Neofax 2014 | 869 | pediatric |
| `nephrology_bagga.pdf` | Nephrology Bagga | 598 | pediatric |
| `operative_pediatric_surgery_7e_rob_smith.pdf` | Operative Pediatric Surgery 7th ed. (Rob & Smith) | 1,128 | pediatric |
| `pena_colorectal_surgery.pdf` | Pena - Colorectal Surgery | 510 | pediatric |
| `rickhams_neonatal_surgery_2018.pdf` | Rickham's Neonatal Surgery 1st ed. (2018) | 1,307 | pediatric |
| `roy_chaudhary_handbook_pediatric_surgery.pdf` | Roy Chaudhary - Handbook of Pediatric Surgery | 393 | pediatric |
| `urodynamics_iaps.pdf` | Urodynamics IAPS | 8 | pediatric |

## Conventions

### File Naming
- All PDFs use `snake_case`.
- No spaces, brackets, or special characters in filenames.
- Split books are named `<title>_part_<N>.pdf`.

### Domain Organization
- Books are grouped under `data/corpus/books/<domain>/`.
- The manifest must reflect the actual path with `path` and `domain` fields.
- When adding a new domain, create a new folder and update the manifest.

### Code Organization
- Services live under `services/` and should be independently runnable.
- Shared logic lives under `shared/` and must not depend on a specific service.
- Each service can have its own `pyproject.toml` / `requirements.txt` and `Dockerfile`.

### Git Rules
- `data/` is **never** committed to Git.
- `manifest.json` is also kept outside Git by project decision.
- The repository should contain code, configs, scripts, tests, and documentation only.

## Environment
A Python virtual environment exists at `.venv/` with `pypdf` installed for PDF processing. Additional dependencies should be added per service or in a root `requirements.txt` / `pyproject.toml`.

## Python Version
- Currently using Python 3.9 (based on `.venv`).

## Notes for Future Work
- The corpus is currently pediatric-only. Future domains (e.g., cardiology, radiology, oncology) should follow the same folder + manifest pattern.
- The RAG and autocomplete services should read from `data/corpus/manifest.json` and resolve PDF paths relative to `data/corpus/`.
- Any ingestion pipeline should handle page-range splits and large PDFs gracefully.
