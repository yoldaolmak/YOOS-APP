# Pennovia contributor and agent guide

This repository is a standalone public Python CLI. Keep product code, tests, documentation, and release metadata self-contained; do not introduce references to other products, unrelated repositories, private corpora, or proprietary runtime dependencies.

Actual flow: user corpus -> local text reader -> local `VoiceProfile` -> optional provider generation -> heuristic audit -> user-selected export.

Core modules: `pennovia/ingestion/reader.py`, `pennovia/voice/analyzer.py`, `pennovia/voice/generator.py`, `pennovia/voice/scorer.py`, `pennovia/audit.py`, `pennovia/exporter/writer.py` and `pennovia/cli.py`.

Commands:

```bash
python -m pip install -e ".[dev]"
python -m compileall -q pennovia
python -m ruff check pennovia tests
python -m pytest -q
python -m pennovia.demo
```

Tests and demo must work without provider keys. Use synthetic or properly licensed fixtures, never private author corpora. The score is uncalibrated: preserve uncertainty rather than claiming human voice fidelity. WordPress must remain draft-by-default and HTTPS-only. The supported user interface is the CLI, not an HTTP service.

Before a public release compare README, package version, CLI, CI, security documentation, container entrypoint and the installed wheel against runnable code.

Keep README, docs/API.md, docs/CONFIGURATION.md, SECURITY.md and CHANGELOG.md consistent with actual behavior. Do not infer capability from test counts, produce credentials in logs, or add decorative abstractions without a specific user problem.
