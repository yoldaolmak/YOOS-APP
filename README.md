# Pennovia

**Your voice. Your words.**

[![CI](https://github.com/yoldaolmak/Pennovia/actions/workflows/ci.yml/badge.svg)](https://github.com/yoldaolmak/Pennovia/actions/workflows/ci.yml) · Python 3.10+ · MIT · Open source

Pennovia analyzes writing style and uses a portable voice profile to guide new drafts. It has three interfaces: **Python API** for integrations, **CLI** for automation and **Studio** for a local browser workflow.

## Install

```bash
git clone https://github.com/yoldaolmak/Pennovia.git
cd Pennovia
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Studio

```bash
pennovia studio
```

Studio opens at **http://127.0.0.1:8765**. Stop it with Ctrl+C.

**Sources → Profile → Draft → Review → Export**

Add public HTTPS article links, pasted writing or TXT/HTML/PDF files. Extract a profile, save or import its JSON, choose a model provider, edit the draft and review its style. Download TXT/HTML/PDF or export to Google Drive or a WordPress **draft**.

Analysis needs no model key. Generation requires Ollama running locally or a configured provider. Studio selects Ollama by default; it never silently substitutes mock text. Browser work is not saved across reloads.

## CLI

```bash
pennovia analyze --corpus ./articles --author "Example Writer" \
  --language en --out voice.json

pennovia generate --profile voice.json --type travel_guide \
  --topic "Three days in Lisbon" --backend ollama --out draft.txt

pennovia export --input draft.txt --title "Lisbon guide" \
  --format html,txt --dest downloads
```

You can analyze URLs or pasted text without saving files:

```bash
pennovia analyze --url "https://example.org/article-1" \
  --url "https://example.org/article-2" --out voice.json

pennovia analyze --text - --out voice.json  # paste text; finish with Ctrl+D
```

`analyze` and `run` accept `--corpus`, repeatable `--url` and `--text`. Each usable source needs at least 51 words. Supported content types: travel blog, travel guide, magazine, news, story and column.

For an offline demonstration:

```bash
pennovia demo
```

Without provider credentials, the demo uses **labeled mock output**.

Demo's Twain-themed samples are **illustrative, not authenticated historic quotations**. The separate [live-model validation](docs/VALIDATION.md) uses original text from Project Gutenberg.

## Integrate

Use the [Python API](docs/API.md) and `VoiceProfile` JSON schema. Studio's localhost endpoints are internal; they are not a public integration API. No hosted service or account is needed.

Cloud providers receive selected source excerpts when you request generation. Studio and CLI default WordPress exports to drafts; only the CLI or Python API can explicitly publish. Style scores are **uncalibrated heuristics**. Review factual claims, personal experiences and quotes before publishing.

## Documentation

[Setup and providers](docs/CONFIGURATION.md) · [Python API](docs/API.md) · [Architecture](docs/ARCHITECTURE.md) · [Validation limits](docs/VALIDATION.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Brand](docs/BRAND.md) · [Changelog](CHANGELOG.md) · [Legal](LEGAL.md)
