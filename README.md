# YOOS-APP — Bring Your Own Voice

[![CI](https://github.com/yoldaolmak/YOOS-APP/actions/workflows/ci.yml/badge.svg)](https://github.com/yoldaolmak/YOOS-APP/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Feed it your own writing. It learns your voice. Then it writes in that voice — consistently, at scale.**

Most "AI writing" tools sound like everyone else's AI writing: flat, generic, instantly recognizable. YOOS-APP solves the opposite problem. You give it a folder of texts *you* have written; it builds a portable profile of *how you write* — your sentence rhythm, your punctuation habits, your vocabulary, your openings — and then generates new content that stays in **your** voice.

It's built for people who **have something to publish but find writing slow or hard**: solo founders, bloggers, small brands, newsletter authors, anyone who needs a steady stream of on-brand content without sounding like a robot.

---

## Why it exists

Writing consistently is the bottleneck. Not everyone can sit down and produce clean, on-voice copy every week — but everyone has a backlog of things worth saying. Generic LLM output doesn't help: it's correct but voiceless, and readers feel it.

YOOS-APP turns *your existing writing* into a reusable voice asset. Analyze once, generate forever.

- **No embeddings. No vector database. No cloud lock-in.** Voice is captured as plain, inspectable statistics in a portable JSON file.
- **Runs fully local** with [Ollama](https://ollama.com), or with any major API (OpenAI, Anthropic).
- **Auditable output** — every generation gets a 0–100 voice-match score so you know how close it landed.

---

## What it does

```
   Your corpus (.txt / .pdf / .html)
            │
            ▼
     ┌─────────────┐    25+ stylometric dimensions:
     │   analyze   │    sentence-length distribution, first-person rate,
     │             │    punctuation fingerprint, vocabulary richness,
     └──────┬──────┘    paragraph rhythm, signature phrases…
            │  voice profile  →  portable JSON
            ▼
     ┌─────────────┐    Genre templates: blog, guide, magazine,
     │  generate   │    news, story, column, essay, marketing
     │  + backend  │    Backends: OpenAI · Anthropic · Ollama (local)
     └──────┬──────┘
            │  draft + voice-match score (0–100)
            ▼
     ┌─────────────┐
     │   export    │    → file · PDF · WordPress
     └─────────────┘
```

---

## Quickstart

```bash
git clone https://github.com/yoldaolmak/YOOS-APP.git
cd YOOS-APP
pip install -r requirements.txt

# See it work end-to-end, no setup:
python -m yoos_app demo
```

### Use it on your own writing

```bash
# 1. Learn your voice from a folder of your texts
yoos-app analyze --corpus ./my-articles/ --author "Me" --out my-voice.json

# 2. Generate a new piece in that voice
yoos-app generate --profile my-voice.json --type magazine \
                  --topic "Three days in Lisbon" --backend openai

# 3. Or run the whole pipeline at once and publish
yoos-app run --corpus ./my-articles/ --type travel_blog \
             --topic "Why I keep going back to Tokyo" --dest wordpress
```

That's the whole loop: **analyze → generate → export.**

---

## Who it's for / what it unlocks

| You are… | YOOS-APP gives you… |
|----------|---------------------|
| A solo founder / indie brand | On-voice blog & marketing copy without hiring a writer |
| A blogger or newsletter author | A way to keep publishing on the weeks you can't write |
| An agency | One reusable voice profile per client, consistent across drafts |
| A non-native or reluctant writer | Your ideas, in clean prose that still sounds like you |

The opportunity is **consistency at scale**: capture a voice once, then produce dozens of pieces that read like the same human wrote them.

---

## How the voice profile works

The analyzer is pure, transparent text statistics — no black-box embeddings. It measures things like:

- Sentence-length distribution (mean, spread, short/long ratio)
- First-person, question, and exclamation rates
- Paragraph rhythm (sentences per paragraph)
- Punctuation style (em-dash, semicolon, parenthesis use)
- Vocabulary richness (type–token ratio)
- Signature 2-gram phrases and typical openings

The result is a small JSON file you can read, diff, version, and reuse anywhere.

---

## Backends

| Backend | Use it when |
|---------|-------------|
| **Ollama** (local) | You want zero API cost and full privacy |
| **OpenAI** | You want top-tier quality out of the box |
| **Anthropic** | You prefer Claude models |

Set your key in `.env` (see `.env.example`). No key needed for the local Ollama path or the demo.

---

## Project status & sibling project

YOOS-APP is the **accessible, bring-your-own-voice** entry point: give it your texts, get consistent content in your voice.

> **graphova** is its more advanced sibling — a voice-print engine for writing in *any* author's tone. YOOS-APP is the simple front door; graphova is the deep end.

---

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, build on it.
