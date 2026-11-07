# Contributor and agent guide

Pennovia is a public Python author-voice toolkit: **Core + CLI + local Studio**. All interfaces use the same ingestion, analysis, generation, audit and export code.

**Scope:** improve working capabilities. Preserve CLI behavior and `VoiceProfile` schema v1. Do not add a second engine, hosted service, database or unrelated product integration without a demonstrated need.

**Modules:** `pennovia/ingestion/`, `pennovia/voice/`, `pennovia/audit.py`, `pennovia/exporter/`, `pennovia/cli.py`, `pennovia/studio/`.

```bash
python -m pip install -e ".[dev]"
python -m ruff check pennovia tests
python -m pytest -q
python -m pennovia.demo
pennovia studio --help
```

Tests must run without real provider keys. Use synthetic or licensed samples; never commit private writing, drafts or credentials. Mock integration tests do not establish real-model quality or author identity.

Studio stays loopback-only; it exports WordPress **drafts**. CLI publication requires explicit `--publish`; the Python API also supports explicit publishing. Other products integrate through the [Python API](docs/API.md), not Studio endpoints.

Keep changes small, check relevant docs against actual behavior and preserve documented limitations.
