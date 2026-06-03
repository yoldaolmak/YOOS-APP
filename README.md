# YOOS-APP

[![CI](https://github.com/example/YOOS-APP/actions/workflows/ci.yml/badge.svg)](https://github.com/example/YOOS-APP/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Backends](https://img.shields.io/badge/LLM-OpenAI%20%7C%20Claude%20%7C%20Ollama%20%7C%20Codex-purple.svg)](#llm-backends)

> **Universal Author Voice Engine**
>
> Give YOOS-APP a set of texts from any writer. It extracts their voice — sentence rhythm, transitions, personal style — and generates new content in that exact voice for any topic and genre.

No embeddings. No vector database. No cloud dependency. Runs fully local with Ollama, or with any major LLM API.

---

## What It Does

```
Your texts (PDF / HTML / TXT)
        │
        ▼
  ┌─────────────┐
  │ VoiceAnalyzer│  ← sentence length, first-person rate,
  │             │     transitions, signature phrases,
  │             │     paragraph rhythm, vocabulary richness
  └──────┬──────┘
         │  VoiceProfile (portable JSON)
         ▼
  ┌─────────────┐     Content type:
  │  Generator  │  ←  travel_blog / travel_guide / magazine
  │             │     news / story / column
  │ OpenAI      │
  │ Claude      │
  │ OpenRouter  │
  │ Ollama      │
  │ Codex CLI   │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐     Destination:
  │  Exporter   │  →  Downloads / Desktop / custom path
  │             │     Google Drive / WordPress (draft or publish)
  └─────────────┘
         │
         ▼
    HTML · PDF · TXT
```

---

## Quick Start

```bash
git clone https://github.com/example/YOOS-APP.git
cd YOOS-APP
pip install -r requirements.txt
cp .env.example .env        # add your API key (or use Ollama)
python -m yoos_app.demo     # runs without API key — mock output
```

With a real API key, the demo:
- Analyzes 3 Mark Twain travel texts (public domain, included)
- Extracts his voice profile
- Generates a 1,200–1,500 word travel blog post about Cappadocia
- Exports HTML + PDF + TXT
- Reports voice audit score (typically 82–92/100)

---

## Installation

### Requirements

- Python 3.10+
- One of: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, or [Ollama](https://ollama.com) running locally

```bash
pip install -r requirements.txt
# or install as package:
pip install -e .
```

### Environment

```bash
cp .env.example .env
# edit .env and set your preferred backend key
```

---

## CLI Usage

### Full pipeline in one command

```bash
yoos-app run \
  --corpus ./my-author-texts/ \
  --author "Author Name" \
  --type travel_blog \
  --topic "Lisbon in three days" \
  --backend openai \
  --format html,pdf,txt \
  --dest downloads
```

### Step by step

```bash
# 1. Analyze — extract voice profile from a folder of texts
yoos-app analyze \
  --corpus ./texts/ \
  --author "Ernest Hemingway" \
  --out hemingway_profile.json

# 2. Generate — write new content in that voice
yoos-app generate \
  --profile hemingway_profile.json \
  --type magazine \
  --topic "Fishing in Patagonia" \
  --backend anthropic \
  --out patagonia.txt

# 3. Export — save to any destination in any format
yoos-app export \
  --input patagonia.txt \
  --title "Fishing in Patagonia" \
  --format pdf \
  --dest desktop

# Publish directly to WordPress
yoos-app export \
  --input patagonia.txt \
  --title "Fishing in Patagonia" \
  --format html \
  --dest wordpress
```

---

## Content Types

| Key | Description | Typical length |
|-----|-------------|----------------|
| `travel_blog` | First-person, personal, conversational | 800–1,500 words |
| `travel_guide` | Authoritative, structured, practical | 1,500–3,000 words |
| `magazine` | Narrative, deep, scene-setting | 1,200–2,500 words |
| `news` | Objective, inverted pyramid | 400–800 words |
| `story` | Narrative arc, character, scene | 1,000–3,000 words |
| `column` | Opinion, argument, personal angle | 500–900 words |

---

## LLM Backends

| Backend | Key required | How to set |
|---------|-------------|------------|
| `openai` | `OPENAI_API_KEY` | `.env` |
| `anthropic` | `ANTHROPIC_API_KEY` | `.env` |
| `openrouter` | `OPENROUTER_API_KEY` | `.env` |
| `ollama` | None | Run `ollama serve` locally |
| `codex` | Codex CLI login | `codex login` |
| `auto` *(default)* | any | Uses first available key |

`auto` mode tries keys in order: Anthropic → OpenRouter → OpenAI → Ollama.

---

## Output Destinations

| Value | Where |
|-------|-------|
| `downloads` | `~/Downloads/` |
| `desktop` | `~/Desktop/` |
| `/any/path` | Custom absolute path |
| `google_drive` | Google Drive root (requires `GOOGLE_DRIVE_TOKEN`) |
| `wordpress` | WordPress draft or publish (requires `WP_URL`, `WP_USER`, `WP_APP_PASSWORD`) |

Output formats: `html`, `pdf`, `txt` — or comma-separated for multiple.

---

## Voice Profile

After `yoos-app analyze`, a portable `voice_profile.json` captures:

```json
{
  "author_name": "Mark Twain",
  "language": "en",
  "text_count": 3,
  "avg_sentence_words": 11.4,
  "first_person_rate": 0.26,
  "question_rate": 0.04,
  "avg_paragraph_sentences": 4.2,
  "top_transitions": ["yet", "but", "still", "however"],
  "signature_phrases": ["very large", "did not", "could not"],
  "sample_sentences": [
    "I have seen photographs of this place a hundred times, yet nothing had prepared me for the weight of standing inside it.",
    "The food deserves its own chapter."
  ]
}
```

Profiles are portable — share them, version-control them, swap them between projects.

---

## Voice Audit

Every generated output is scored against the source profile:

```
Voice Audit: 87/100 [PASS]
  Voice match:      34/40   ← sentence rhythm, first-person rate
  Transition match: 18/20   ← shared transition words
  Style match:      16/20   ← paragraph structure
  No AI clichés:   19/20   ← penalises "delve into", "it's worth noting"…
```

---

## Demo Output

Running `python -m yoos_app.demo` with an Anthropic key produces:

> *Cappadocia sits in the heart of Turkey, in the Anatolian plateau, and it does not look like a place that belongs to the living world. It looks like something dreamed up by a geology that had grown tired of convention. We are travelers who arrive here with our cameras ready and our expectations high, and still the landscape manages to exceed them.*

Voice audit: **87/100** · Similarity: **0.81** · Words: **1,314**

---

## Copyright & Legal

YOOS-APP does not store, redistribute, or train on uploaded texts. Voice analysis runs locally in-process. Generated text belongs to the user.

You are responsible for ensuring you have the right to use any texts you provide as corpus input. Public domain texts (Gutenberg, pre-1928 works) are safe. See [LEGAL.md](LEGAL.md).

---

## Project Structure

```
yoos_app/
├── ingestion/          PDF, HTML, TXT reader
│   └── reader.py
├── voice/
│   ├── analyzer.py     Voice profile extraction
│   ├── generator.py    Multi-backend LLM generation
│   └── scorer.py       Voice similarity scoring
├── content_types/
│   └── registry.py     6 content type templates
├── exporter/
│   └── writer.py       HTML/PDF/TXT + destinations
├── audit.py            Voice quality audit (0-100)
├── cli.py              Command-line interface
└── demo/               Runnable demo, no API key needed
examples/
├── corpus/             Mark Twain public domain texts
└── output/             Generated demo outputs
tests/                  12+ tests, all API-free
.github/workflows/      CI: Python 3.10/3.11/3.12
```

---

## Related

- **[example.com](https://example.com)** — live travel publication powered by this engine
