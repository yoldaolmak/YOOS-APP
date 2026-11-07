# Pennovia contributor and agent guide

Pennovia is a standalone public Python **author-voice toolkit** with three interfaces over one core: reusable Python API, automation-friendly CLI and optional **local browser Studio**. Do not introduce a competing generation/scoring engine, unrelated repositories, private corpora, proprietary runtimes, hosted accounts or an unnecessary service architecture.

**Product flow:** user-selected TXT/HTML/PDF files, public HTTPS URLs or pasted writing → local `VoiceProfile` → optional configured model generation → heuristic review → explicit export. Studio wraps the same core functions; its loopback HTTP endpoints are implementation details, not a supported external API.

Core modules: `pennovia/ingestion/reader.py`, `pennovia/voice/analyzer.py`, `pennovia/voice/generator.py`, `pennovia/voice/scorer.py`, `pennovia/audit.py` and `pennovia/exporter/writer.py`. Interfaces: `pennovia/cli.py` and `pennovia/studio/` (local server and bundled HTML/CSS/JS).

Useful commands:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q pennovia
python -m ruff check pennovia tests
python -m pytest -q
python -m pennovia.demo
pennovia studio --help
pennovia studio           # local browser interface; Ctrl+C to stop
```

Tests and demo must work without API keys; use synthetic or appropriately licensed fixtures, never private writing or live credentials. Studio synthetic provider tests prove software integration **only**. Do not claim validated author identity, real-world voice fidelity or live provider/WordPress success based on mock results. Scores remain uncalibrated.

Preserve CLI compatibility and `VoiceProfile` schema v1. WordPress remains draft-by-default; Studio can create drafts only, while the CLI requires explicit `--publish` for publication. The Studio server must remain loopback-only, with local request protections and no keys entered in the browser.

Before a public release, compare runnable behavior against README, `docs/CONFIGURATION.md`, `docs/API.md`, `docs/ARCHITECTURE.md`, SECURITY.md, CHANGELOG.md, CLI help, Studio UI, packaging, Docker and CI. Prefer fixes that improve a real user action; avoid proof-system or abstraction growth without demonstrated need.
