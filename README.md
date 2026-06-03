# Graphova

[![CI](https://github.com/example/YOOS-APP/actions/workflows/ci.yml/badge.svg)](https://github.com/example/YOOS-APP/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-155%20passing-brightgreen.svg)](#testing)
[![Backends](https://img.shields.io/badge/LLM-Anthropic%20%7C%20OpenAI%20%7C%20OpenRouter%20%7C%20Ollama-purple.svg)](#llm-backends)

> **Universal Author Voice Engine**
>
> Feed Graphova any author's texts — it extracts their voice fingerprint and generates new content in that exact voice, across any genre.

No embeddings. No vector database. No cloud lock-in. Runs fully local with Ollama, or with any major LLM API.

---

## What It Does

```
Your corpus (PDF / HTML / TXT)
         │
         ▼
  ┌──────────────┐
  │   Extractor  │  ← 25+ stylometric dimensions:
  │              │    sentence length distribution (mean, std, quartiles)
  │              │    vocabulary richness, lexical density
  │              │    punctuation fingerprint (em-dash, semicolons)
  │              │    personal pronoun rates, readability grade
  │              │    transition words, paragraph openers
  └──────┬───────┘
         │  VoiceFingerprint (portable JSON)
         ▼
  ┌──────────────┐     Genre:
  │  Generator   │  ←  travel_blog / travel_guide / magazine
  │              │     news / story / column / essay / marketing
  │  + LLM Router│  ←  Anthropic / OpenAI / OpenRouter / Ollama / Codex
  └──────┬───────┘
         │
         ▼
  Content in the author's voice + audit score (0–100)
```

---

## Quick Start

### Web App (recommended)

```bash
git clone https://github.com/example/YOOS-APP.git
cd YOOS-APP
pip install -r requirements.txt
pip install anthropic  # or: pip install openai

export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY / OPENROUTER_API_KEY

python -m graphova.app
# → open http://127.0.0.1:8000
```

### Docker

```bash
ANTHROPIC_API_KEY=sk-ant-... docker-compose up
# → open http://localhost:8000
```

### Command Line

```bash
# Extract voice fingerprint from a folder of texts
python -m graphova.cli analyze --corpus ./hemingway/ --author "Hemingway" --out hem.json

# Generate content
python -m graphova.cli generate \
  --profile hem.json \
  --genre travel_blog \
  --topic "Havana in the rain" \
  --backend anthropic
```

---

## Architecture

```
graphova/
├── core/
│   ├── extractor.py       Stylometric analysis (25+ dimensions, pure Python)
│   ├── fingerprint.py     VoiceFingerprint dataclass — save/load/diff/distance
│   ├── generator.py       Prompt construction from fingerprint
│   ├── router.py          LLM provider router (Anthropic / OpenAI / OpenRouter / Ollama)
│   ├── auditor.py         Voice quality scoring 0–100 with letter grades
│   ├── scorer.py          Statistical voice similarity 0.0–1.0
│   └── genres.py          8 content genre definitions
├── api/
│   ├── db.py              SQLite profile store (WAL mode)
│   ├── models.py          Pydantic v2 request/response schemas
│   └── routes.py          FastAPI endpoints
├── exporter/
│   └── writer.py          HTML / PDF / TXT export + WordPress / Google Drive
├── utils/
│   ├── file_handlers.py   PDF / HTML / TXT reader (with security checks)
│   └── logger.py          Structured logger (JSON or human-readable)
├── frontend/
│   ├── index.html         Single-page app (no framework, no build step)
│   ├── app.js             API client + UI logic
│   └── style.css          Minimal design system
├── app.py                 FastAPI entrypoint with lifespan
└── cli.py                 CLI (serve / analyze / generate / demo)
```

---

## Voice Fingerprint — 25 Dimensions

| Category | Dimensions |
|----------|-----------|
| **Sentence rhythm** | avg words, std dev, p25/p50/p75 quartiles, short rate (<8w), long rate (>20w) |
| **Voice markers** | first/second/third-person rates, question rate, exclamation rate, negative construction rate |
| **Vocabulary** | type-token richness, avg word length, lexical density |
| **Readability** | Flesch-Kincaid grade (EN), avg syllables per word |
| **Punctuation** | comma, semicolon, em-dash, parenthesis, ellipsis rates per sentence |
| **Structure** | avg paragraph sentences, avg paragraph words, paragraph openers |
| **Style** | top transition words, sentence openers, characteristic 2-grams, sample sentences |
| **Tone** | declarative rate, imperative rate, function word density |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Server status + available backends |
| `POST` | `/api/profiles` | Upload corpus → extract fingerprint |
| `GET` | `/api/profiles` | List all profiles |
| `GET` | `/api/profiles/{id}` | Profile detail + full fingerprint |
| `DELETE` | `/api/profiles/{id}` | Delete profile |
| `POST` | `/api/generate` | Generate content in author's voice |
| `POST` | `/api/export` | Export as HTML / PDF / TXT |
| `GET` | `/api/genres` | List available genres |

Interactive docs: `http://localhost:8000/api/docs`

### Example: Create Profile

```bash
curl -X POST http://localhost:8000/api/profiles \
  -F "name=My Voice" \
  -F "author=Me" \
  -F "files=@blog_post_1.txt" \
  -F "files=@blog_post_2.html" \
  -F "files=@essay.pdf"
```

### Example: Generate

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "uuid-from-create",
    "topic": "Solo travel in Cappadocia at dawn",
    "genre": "travel_blog",
    "backend": "anthropic"
  }'
```

---

## LLM Backends

| Backend | Key Required | Notes |
|---------|-------------|-------|
| `anthropic` | `ANTHROPIC_API_KEY` | Default when available |
| `openai` | `OPENAI_API_KEY` | |
| `openrouter` | `OPENROUTER_API_KEY` | Access 100+ models |
| `ollama` | none | Run locally: `ollama serve` |
| `codex` | none | OpenAI Codex CLI |
| `auto` | — | Tries available in priority order |

---

## Testing

```bash
# All 155 tests, no API key required
python -m pytest tests/test_graphova_extractor.py \
                 tests/test_graphova_handlers.py \
                 tests/test_graphova_auditor.py \
                 tests/test_graphova_api.py \
                 tests/test_core.py -v
```

Tests run in **~0.5 seconds**. No network calls, no mocks.

---

## Product Tiers

| Tier | Target | Features |
|------|--------|---------|
| **Graphova Penova** | Individual | Single voice, local use |
| **Graphova Penovate** | Professional | Multiple voices, API access, team sharing |
| **Graphova Evowrite** | Enterprise | White-label, on-prem, unlimited |

---

## Requirements

- Python 3.10+
- At least one LLM API key (or Ollama running locally)
- Optional: `pdfplumber` for PDF input, `reportlab` for PDF export

```bash
pip install -r requirements.txt
pip install anthropic  # recommended
```

---

## License

MIT — see [LICENSE](LICENSE).
