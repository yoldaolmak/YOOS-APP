# Configuration and first run

Pennovia 0.2.0 alpha is a **local Python command-line toolkit**, not a hosted platform. Corpus analysis runs without a model API key. Draft generation requires an explicitly available backend.

## First run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pennovia --version
pennovia demo
python -m ruff check pennovia tests
python -m pytest -q
```

Without provider credentials, the demo uses labeled mock writing. It tests the offline pipeline, not the quality of LLM generation.

## Your own writing

```bash
pennovia analyze --corpus ./my-articles --author "Example Writer" --out voice.json
pennovia generate --profile voice.json --type travel_guide \
  --topic "Three days in Lisbon" --backend ollama --out draft.txt
pennovia export --input draft.txt --title "Lisbon guide" \
  --format html,txt --dest downloads
```

A corpus can be one supported TXT, HTML or PDF file, or a directory of such files. The directory scan is non-recursive and alphabetical. Each usable file must contain more than 50 whitespace-delimited words; rejected files are reported on stderr. Voice profiles can contain verbatim sample sentences from your source material.

CLI `analyze`, `generate` and `run --save-profile` refuse to replace an existing output unless you explicitly pass `--overwrite`. Local exports use unique filenames.

## Choosing a backend

**Pennovia does not automatically read `.env` files.** `.env.example` is only a reference. Supply credentials through environment variables or a secret manager; never commit them.

| Backend | Configuration | Data transfer |
| --- | --- | --- |
| `ollama` | Run a local Ollama service; default model `llama3`, or set `--model` | Prompts go to the local Ollama endpoint |
| `openai` | Install `.[llm]` and set `OPENAI_API_KEY` | Prompts go to OpenAI |
| `anthropic` | Install `.[llm]` and set `ANTHROPIC_API_KEY` | Prompts go to Anthropic |
| `openrouter` | Set `OPENROUTER_API_KEY` | Prompts go to OpenRouter |
| `codex` | Install and authenticate the Codex CLI separately | A separate model-aware executable runs in a read-only sandbox; provider privacy depends on its configuration |

For example:

```bash
python -m pip install -e ".[llm]"
export OPENAI_API_KEY="<private-key>"
pennovia generate --profile voice.json --type column \
  --topic "A writing subject" --backend openai --out draft.txt
```

**Important:** `--backend auto` selects Anthropic → OpenRouter → OpenAI → Ollama according to available environment credentials. If cloud keys exist, auto mode may transmit samples of your writing to a cloud provider. Specify `--backend ollama` for locally hosted inference. Codex is opt-in, not part of auto selection.

## Export destinations

Local output accepts `html`, `txt` or `pdf`, including comma-separated combinations. Google Drive accepts the same formats; install `.[gdrive]` and set `GOOGLE_DRIVE_TOKEN` to authorized-user OAuth **JSON content**, not a filename.

WordPress requires `WP_URL` (HTTPS), `WP_USER`, and `WP_APP_PASSWORD`:

```bash
pennovia export --input draft.txt --title "A draft" --format html --dest wordpress
```

It creates a **draft** by default. Only explicit `--publish` publishes. WordPress accepts one HTML export per CLI call; mixed formats are rejected so they cannot create duplicate posts.

## Common errors

- **No usable corpus texts:** verify file extensions, text length and skip messages.
- **Output already exists:** choose a fresh file path or add `--overwrite` deliberately.
- **No LLM backend available:** start Ollama or configure one supported provider.
- **Provider library missing:** install the required optional extras.
- **WordPress export accepts one HTML format:** use `--format html` only.

AI output can invent facts, quotations and personal experience. Human review remains required; voice matching scores are not authorship evidence.
