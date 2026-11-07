# Configuration

Pennovia runs locally. Analysis needs no model provider; generation needs a configured backend.

## Install and start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pennovia studio
```

Studio opens at **http://127.0.0.1:8765**. Use `--port 8766` to change the port or `--no-browser` to suppress automatic browser launch. Stop with Ctrl+C. Studio is local only, not a hosted site.

In Studio: **Sources → Profile → Draft → Review → Export**. Add HTTPS article links, pasted writing or TXT/HTML/PDF files; each sample needs at least 51 words. Studio accepts up to 20 samples, files up to 4 MB each. Save or import a profile as JSON. Edit drafts and run *Review edited draft* to refresh style scores.

Studio initially selects **Ollama**. Choose a configured provider before generating. It does not fall back to mock content. Changing samples, author or language invalidates the old profile and review; the draft text is preserved. Inputs are locked during active requests to prevent stale results. Importing a saved profile clears the current unsent sample list, not the draft. Browser state is temporary: download your work before reloading the page.

## CLI examples

```bash
pennovia analyze --corpus ./articles --author "Writer" \
  --language en --out voice.json

pennovia analyze --url "https://example.org/article" --out voice.json
pennovia analyze --text - --out voice.json  # paste; Ctrl+D to finish

pennovia generate --profile voice.json --type travel_guide \
  --topic "Lisbon" --backend ollama --out draft.txt

pennovia export --input draft.txt --title "Lisbon" \
  --format html,txt --dest downloads
```

`analyze` and `run` accept a file or non-recursive directory via `--corpus`, repeated URLs via `--url`, and inline or stdin text via `--text`. Inputs can be mixed. Files: TXT, HTML, PDF. HTTPS pages: HTML/plain text, up to 2 MB; redirects and DNS targets must remain public. Environment proxies are not used. Login-protected and JavaScript-only content may not work. Invalid or short sources are skipped; analysis stops if none are usable.

Use `--language tr` or `--language en` for known languages; automatic detection may abstain. CLI output profiles/drafts are not overwritten without `--overwrite`. Local exports use distinct filenames.

## Model providers

Pennovia **does not load** `.env` files automatically. Export credentials in your shell or use a secret manager.

| Backend | Setup |
| --- | --- |
| Ollama | Run local Ollama; model defaults to `llama3` |
| OpenAI | Install `.[llm]`; set `OPENAI_API_KEY` |
| Anthropic | Install `.[llm]`; set `ANTHROPIC_API_KEY` |
| OpenRouter | Set `OPENROUTER_API_KEY` |
| Codex CLI | Install and authenticate Codex separately |

Cloud backends send prompts, including selected source sentences, to the provider. CLI `--backend auto` selects Anthropic → OpenRouter → OpenAI → Ollama based on credentials; it may send writing to a cloud service. Studio requires an explicit provider selection.

Example:

```bash
python -m pip install -e ".[llm]"
export OPENAI_API_KEY="<private-key>"
pennovia generate --profile voice.json --type column \
  --topic "A subject" --backend openai --out draft.txt
```

## Exports

TXT, HTML and PDF are available locally. Google Drive requires `.[gdrive]` and `GOOGLE_DRIVE_TOKEN` containing authorized-user OAuth JSON.

WordPress requires `WP_URL` (canonical HTTPS base URL), `WP_USER` and `WP_APP_PASSWORD`:

```bash
pennovia export --input draft.txt --title "A draft" \
  --format html --dest wordpress
```

WordPress creates a **draft** by default. The CLI publishes only with `--publish`; Studio has no publish action. WordPress accepts one HTML export per command.

**Uncertain remote result:** A WordPress/Drive timeout, server error or unreadable success response may mean the write succeeded without an acknowledgment. Pennovia does not retry automatically. Check the remote account before retrying. Studio requires explicit confirmation for an identical repeat in the same browser session; this is not persistent or server-side exactly-once protection. For CLI multi-format exports, completed remote uploads are reported; failed local multi-format exports remove files created by that attempt. The CLI saves an optional profile only after model generation succeeds.

## Checks

```bash
python -m ruff check pennovia tests
python -m pytest -q
pennovia demo
```

The demo may use mock output. A green test suite does not establish model quality or author-voice fidelity. See [Validation](VALIDATION.md) and [Security](../SECURITY.md).
