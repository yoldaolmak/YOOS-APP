# Pennovia

**A writer's voice is not a prompt preset.**

*Your voice. Your words.*

Pennovia is an open-source author-voice engine. It studies the measurable patterns in existing writing, turns them into a portable profile, and uses that profile to guide new drafts. The author remains the editor: inspect the analysis, revise the text, and decide what leaves the workspace.

**One core, three ways to work:** the Python API for developers, the CLI for automation, and Studio for a focused local browser experience. No hosted account, proprietary voice service, or separate generation engine.

[![CI](https://github.com/yoldaolmak/Pennovia/actions/workflows/ci.yml/badge.svg)](https://github.com/yoldaolmak/Pennovia/actions/workflows/ci.yml) · [v0.2.0 alpha](https://github.com/yoldaolmak/Pennovia/releases/tag/v0.2.0) · Python 3.10+ · MIT

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

The bundled demo corpus is **illustrative fiction**, not authenticated historical writing. The real-model experiment below uses original public-domain text from Project Gutenberg.

## Tested with a real model

The [v0.2.0 alpha release](https://github.com/yoldaolmak/Pennovia/releases/tag/v0.2.0) passed six CI jobs and a separate, **unmocked Ollama run**. The live trial used *The Innocents Abroad* by Mark Twain from [Project Gutenberg #3176](https://www.gutenberg.org/ebooks/3176), not the bundled demo corpus.

| Evidence | Verified result |
| --- | --- |
| Model | Ollama · `qwen2.5:1.5b` |
| Source separation | Chapters I, II and IV for the profile; chapter III held out (350 words per excerpt) |
| Pennovia-generated drafts | 814 words / **77/100**, and 672 words / **68/100** |
| Neutral model control | **83/100** heuristic audit |
| Output | Real TXT, HTML and PDF exports; source hash, model digest and drafts archived |
| Reproducibility | [Live-model workflow and artifacts](https://github.com/yoldaolmak/Pennovia/actions/runs/42406098002) · [Main CI](https://github.com/yoldaolmak/Pennovia/actions/runs/42406097987) |

**What this proves:** the real model, analysis, review and export pipeline ran end to end. **What it does not prove:** reliable author-voice fidelity, factual accuracy, or publishable text. The neutral draft scored above both profile-guided drafts; the numerical scores are uncalibrated. See [validation limits](docs/VALIDATION.md).

## Integrate

Use the [Python API](docs/API.md) and `VoiceProfile` JSON schema. Studio's localhost endpoints are internal; they are not a public integration API. No hosted service or account is needed.

Cloud providers receive selected source excerpts when you request generation. Studio and CLI default WordPress exports to drafts; only the CLI or Python API can explicitly publish. Style scores are **uncalibrated heuristics**. Review factual claims, personal experiences and quotes before publishing.

## Documentation

[Setup and providers](docs/CONFIGURATION.md) · [Python API](docs/API.md) · [Architecture](docs/ARCHITECTURE.md) · [Validation limits](docs/VALIDATION.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Brand](docs/BRAND.md) · [Changelog](CHANGELOG.md) · [Legal](LEGAL.md)
