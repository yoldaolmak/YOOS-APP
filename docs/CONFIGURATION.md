# Configuration and first run

Pennovia 0.2.0 alpha is a **local Python toolkit with a reusable API, CLI and browser Studio**, not a hosted platform. Corpus analysis needs no model key. Draft generation requires a working, explicitly configured provider.

## First run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pennovia --version
pennovia studio --help
pennovia demo
python -m ruff check pennovia tests
python -m pytest -q
```

Without provider credentials, the demo uses labeled mock writing. It tests the offline pipeline, not the quality of LLM generation.

## Browser Studio

```bash
pennovia studio
```

Open the printed local address in your browser. The UI runs on **127.0.0.1:8765** by default and opens your browser unless you pass `--no-browser`. Use `--port 8766` if the default port is taken. Stop it with Ctrl+C in the terminal. This is not a hosted website or a network-shared service.

The one-panel workflow is **Sources → Profile → Draft → Review → Export**. Studio is a browser UI backed by a bundled loopback-only local server; it is not a public hosting endpoint. Supply public HTTPS links, paste one or more writings, or choose local TXT/HTML/PDF files (4 MB each, up to 20 sources per analysis). Each usable sample needs at least 51 words. Download the profile as JSON for reuse or import a previously saved JSON profile without reanalyzing the source. Choose Ollama (local) or a specifically configured remote provider; the default selection is Ollama to avoid unexpected cloud transmission. No model is simulated in the Studio production flow. Draft text is editable, and `Review edited draft` refreshes the heuristic findings.

Downloads go to your browser's download destination. WordPress **always creates a draft** and asks for confirmation in Studio; use the existing CLI if you deliberately want to publish. Google Drive requires the existing optional dependencies and environment configuration. Browser profile/draft state is not saved between page loads. Refreshing the page loses unsaved work, so download the profile and draft before leaving.

Studio uses a session token and enforces loopback host/origin checks; it serves only fixed UI assets and local workflow actions. The browser endpoints are not a supported third-party integration API; use Pennovia's Python functions instead. It does not expose the editor to your network and is not designed to run behind a public reverse proxy. Keep model API keys in the shell environment, not the browser. This is a lightweight local tool, not an independent security sandbox for malicious websites or files.

## Your own writing

```bash
pennovia analyze --corpus ./my-articles --author "Example Writer" --out voice.json
pennovia generate --profile voice.json --type travel_guide \
  --topic "Three days in Lisbon" --backend ollama --out draft.txt
pennovia export --input draft.txt --title "Lisbon guide" \
  --format html,txt --dest downloads
```

You can instead pass one or more blog-post links directly, or paste a text as a separate writing sample:

```bash
pennovia analyze --url "https://example.org/article-1" \
  --url "https://example.org/article-2" \
  --author "Writer" --language en --out voice.json

# Supply pasted text via stdin (type/paste, then Ctrl+D on macOS/Linux)
pennovia analyze --text - --author "Writer" --language en --out voice.json

# Mix sources in one profile or generate directly from a link:
pennovia run --corpus ./older-articles \
  --url "https://example.org/recent-article" \
  --topic "Three days in Lisbon" --backend ollama
```

Both `analyze` and `run` accept repeatable `--url` and `--text` options and an optional `--corpus`. `--text "your text"` accepts inline text; `--text -` reads one text from stdin. Each individual sample requires at least **51 words**. Unreadable, inaccessible or short sources are reported and skipped; the command stops if none is usable. Public HTTPS web pages are fetched on demand (HTML or plain text; at most 2 MB), following only a few HTTPS redirects. The reader prefers an article or main element, removes common site chrome, and cannot extract content hidden behind logins, anti-bot pages or JavaScript-only rendering. URL fetching contacts the selected websites; it is not an unattended crawler or security isolation boundary.

A corpus can be one supported TXT, HTML or PDF file, or a directory of such files. English/Turkish language detection is heuristic; use `--language tr` or `--language en` when you know the corpus language, especially for short or mixed text. The directory scan is non-recursive and alphabetical. Each usable file must contain more than 50 whitespace-delimited words; rejected files are reported on stderr. Voice profiles can contain verbatim sample sentences from your source material. During generation these samples are supplied to the model as lower-priority untrusted style evidence, not trusted system instructions. This reduces prompt-injection risk but does not guarantee that a model ignores malicious directions inside source text.

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

**CLI only:** `--backend auto` selects Anthropic → OpenRouter → OpenAI → Ollama according to available environment credentials. Studio does not use that automatic selection; its provider dropdown starts at local Ollama. If cloud keys exist, auto mode may transmit samples of your writing to a cloud provider. Specify `--backend ollama` for locally hosted inference. Codex is opt-in, not part of auto selection.

## Export destinations

Local output accepts `html`, `txt` or `pdf`, including comma-separated combinations. Google Drive accepts the same formats; install `.[gdrive]` and set `GOOGLE_DRIVE_TOKEN` to authorized-user OAuth **JSON content**, not a filename.

WordPress requires `WP_URL` (the canonical HTTPS site base URL, without query strings or embedded credentials), `WP_USER`, and `WP_APP_PASSWORD`:

```bash
pennovia export --input draft.txt --title "A draft" --format html --dest wordpress
```

It creates a **draft** by default. Only explicit `--publish` publishes. Redirects and invalid success responses are rejected rather than being treated as successful exports. WordPress accepts one HTML export per CLI call; mixed formats are rejected so they cannot create duplicate posts.

## Common errors

- **No usable corpus texts:** verify file extensions, text length and skip messages.
- **Output already exists:** choose a fresh file path or add `--overwrite` deliberately.
- **Studio draft generation fails:** start Ollama (the default Studio selection) or configure and explicitly select a cloud provider. Studio does not fall back to mock output.
- **No LLM backend available in the CLI:** start Ollama or configure a supported provider.
- **Provider library missing:** install the required optional extras.
- **WordPress export accepts one HTML format:** use `--format html` only.

Empty, missing or malformed provider draft text is rejected rather than saved or exported. Network and provider errors are reported without echoing raw remote response payloads. This does not verify model output quality.

AI output can invent facts, quotations and personal experience. Human review remains required; voice matching scores are not authorship evidence.
