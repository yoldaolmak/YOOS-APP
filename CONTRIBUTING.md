# Contributing to YOOS-APP

## What We Welcome

- New content type templates (`yoos_app/content_types/registry.py`)
- New LLM backend integrations (`yoos_app/voice/generator.py`)
- New export destinations (`yoos_app/exporter/writer.py`)
- Voice analyzer improvements (`yoos_app/voice/analyzer.py`)
- Bug fixes and edge-case tests

## What We Do NOT Accept

- Contributions that include real author corpus data
- Contributions that bypass the public/private data boundary
- Changes to the audit scoring that would inflate scores artificially

## Development Setup

```bash
git clone https://github.com/example/YOOS-APP.git
cd YOOS-APP
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/           # must pass before any PR
python -m yoos_app.demo           # smoke test
```

## Pull Request Rules

1. All existing tests must pass (`python -m pytest tests/ -v`)
2. New features need at least one test
3. No API key required to run tests
4. No secrets, credentials, or corpus files in commits
5. Commit messages: `type: short description` (feat/fix/docs/test/refactor)

## Code Style

- Python 3.10+
- No external formatters required — match surrounding style
- Type hints where they add clarity, not everywhere
- Docstrings only for public-facing functions

## Reporting Issues

Open a GitHub issue with:
- Python version
- Backend used
- Minimal reproduction case
- Expected vs actual output
