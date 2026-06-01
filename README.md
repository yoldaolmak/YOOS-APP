# YOOS-APP

> **YO Operating System** — AI-powered editorial engine for [example.com](https://example.com)

An autonomous content intelligence system that audits, rewrites, and optimizes long-form travel content — preserving a specific authorial voice across 1,500+ articles while enforcing EEAT and SEO standards.

---

## What This Is

YOOS-APP is the backend brain of a travel publication that has been running since 2011 with 685+ days of on-the-road content. It is not a generic CMS plugin or a prompt wrapper.

It is a multi-pass editorial pipeline that:

1. **Audits** existing content against EEAT, SEO, and voice standards
2. **Rewrites** weak sections using RAG-retrieved context
3. **Enforces** a specific authorial voice via embedding similarity
4. **Publishes** directly to WordPress via REST API

---

## Architecture

```
YOOS-APP/
├── modules/
│   ├── editorial/
│   │   ├── audit_patch.py          # Section-level audit engine
│   │   ├── full_rewrite.py         # Full post rewrite pipeline
│   │   ├── semantic_blueprint.py   # Content structure planner
│   │   ├── editorial_brief.py      # Per-article editorial brief
│   │   └── state_ledger.py         # Cross-section state tracking
│   ├── rewrite/
│   │   ├── section_rewrite_engine.py  # Section-by-section rewriter
│   │   ├── html_assembler.py          # Gutenberg HTML output builder
│   │   ├── html_section_splitter.py   # DOM-aware section parser
│   │   └── rag_adapter.py             # RAG context injector
│   ├── voice/
│   │   ├── voice_enforcer.py       # Voice consistency enforcement
│   │   ├── voice_embedder.py       # Author voice embeddings
│   │   └── voice_similarity.py     # Cosine similarity scoring
│   ├── llm_router.py               # Multi-provider LLM routing
│   ├── cache_manager.py            # Disk-based API call cache
│   └── batch_runner.py             # Parallel job orchestration
├── rag/
│   ├── retrieval/                  # Qdrant vector retrieval
│   ├── embedding/                  # Embedding pipeline
│   └── split/                      # Semantic chunk splitter
├── prompts/
│   ├── voice_profile.py            # Alex Rivera voice system (single source)
│   ├── pass1_audit.py              # Pass 1: content audit
│   └── pass2_rewrite.py            # Pass 2: full rewrite pipeline
├── wp.py                           # WordPress REST API client
├── audit_engine.py                 # Top-level audit orchestrator
├── rewrite_engine.py               # Top-level rewrite orchestrator
└── priority_engine.py              # Content priority scoring
```

---

## Pipeline

```
WordPress Post (REST API)
    ↓
first_edit() — HTML cleanup, deduplication
    ↓
Pass 1 — Audit (EEAT, SEO, voice, yasak kelime scan)
    ↓
Editorial Brief — one-time semantic intent extraction
    ↓
Pass 2 — Section-by-section rewrite
    │   ├── RAG retrieval (Qdrant: top-3 voice examples)
    │   ├── State ledger (cross-section consistency)
    │   └── Voice enforcer (cosine similarity gate)
    ↓
Checklist validator (14 criteria, retry if < 10/14)
    ↓
WordPress draft via REST API
```

---

## Key Capabilities

| Capability | Details |
|---|---|
| **Voice enforcement** | Author voice embedded via multilingual-e5-large; rewrites below similarity threshold are rejected |
| **RAG context** | Qdrant vector DB with curated gold corpus of approved author texts |
| **Editorial brief** | One-time per-post semantic extraction: thesis, timeline lock, cliché list |
| **State ledger** | Tracks used openings, personal claims, and comparisons across H2 sections |
| **Multi-LLM routing** | Provider-agnostic router: local (LM Studio/Qwen), cloud (Codex, Kimi), fallback chain |
| **WP integration** | Direct REST publish, Gutenberg HTML output, meta updates |
| **Telemetry** | SQLite job tracking, cost logging, failure memory |

---

## Stack

- **Python 3.10** — core engine
- **Qdrant** — vector database for voice RAG
- **intfloat/multilingual-e5-large** — embedding model (local, Turkish-capable)
- **WordPress REST API** — content publishing (Gutenberg blocks)
- **SQLite** — job state, telemetry, failure memory
- **LM Studio / Qwen3** — local LLM inference
- **HashiCorp Vault** — secrets management

---

## Setup

```bash
git clone git@github.com:example/YOOS-APP.git
cd YOOS-APP
python3.10 -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # or install from imports

# Copy and configure environment
cp .env.example .env
# Fill in: example_URL, WP_USER, WP_APP_PASSWORD

# Start Qdrant and ingest voice corpus
./qdrant &
python3 rebuild_qdrant_gold.py

# Run pipeline on a post
python3 prompts/pass2_rewrite.py <POST_ID>
```

---

## Related

- **[example.com](https://example.com)** — live publication (1,500+ travel articles)
