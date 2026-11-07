# YOOS-APP

[![CI](https://github.com/yoldaolmak/YOOS-APP/actions/workflows/ci.yml/badge.svg)](https://github.com/yoldaolmak/YOOS-APP/actions/workflows/ci.yml) · Python 3.10+ · MIT License

**Bring your own writing. Inspect your voice. Generate a draft for review.**

YOOS-APP is an independent open-source Python CLI for local author-voice profiling and AI-assisted drafting. It reads text supplied by the user, extracts inspectable writing statistics into a portable JSON profile, supports optional language-model drafting, and exports text to local files, WordPress drafts, or Google Drive.

**Status: 0.1.0 alpha.** This is not a hosted service. Its 0–100 voice audit and 0–1 similarity result are uncalibrated heuristics, not proof of authorship, originality, factual quality, or fidelity to a human writer.

## Features

- Analyze TXT, HTML, or PDF corpus files into an inspectable `VoiceProfile` JSON file.
- Compare sentence rhythm, punctuation, transition expressions, and paragraph style.
- Draft with configured OpenAI, Anthropic, OpenRouter, Codex CLI, or local Ollama backend.
- Save TXT, standalone HTML, or PDF output; optionally export to Google Drive or WordPress.
- WordPress exports create a **draft by default**; publication requires an explicit `--publish` flag and HTTPS endpoint.

## Quick start

```bash
git clone https://github.com/yoldaolmak/YOOS-APP.git
cd YOOS-APP
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m yoos_app.demo
python -m pytest -q
```

The demo analyzes bundled sample excerpts and creates demonstration files in `examples/output/`. Without API credentials it uses explicitly labeled mock text; it does **not** test live model quality.

Analyze your own writing:

```bash
yoos-app analyze --corpus ./my-articles --author "Example Writer" --out voice.json
yoos-app generate --profile voice.json --type travel_guide --topic "Lisbon" --backend ollama --out draft.txt
yoos-app export --input draft.txt --title "Lisbon" --format html --dest downloads
```

Optional cloud backends require credentials and may require `pip install -e ".[llm]"`. `--backend auto` may select an available cloud provider. Local generation requires a running Ollama service.

For WordPress draft export configure `WP_URL`, `WP_USER` and `WP_APP_PASSWORD`. The endpoint must use HTTPS. Do not commit keys, private corpus files, generated text, or profile JSON containing sample sentences.

## Container

```bash
docker build -t yoos-app .
docker run --rm yoos-app demo
```

The image runs the CLI, not a web API. The demo runs in an ephemeral container; persistent files require an explicitly mounted output directory. `docker compose run --rm demo` provides the same one-off demonstration.

## Data handling and limitations

Local analysis does not call a language model. Voice profiles may contain verbatim sample sentences; cloud generation sends sample excerpts in a prompt to the selected provider. Google Drive and WordPress exports make separate outbound network requests. Keep original corpus files and profiles private.

Generated personal accounts and facts can be invented. Review every draft before publishing. Heuristic scores are diagnostic indicators only; a high score is not a guarantee of writing quality.

## References

- [Architecture](docs/ARCHITECTURE.md)
- [Python API](docs/API.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Legal notes](LEGAL.md)
- [MIT License](LICENSE)
