# Contributing

Pennovia is an open-source **Python author-voice toolkit**. Contributions may improve its reusable Python core, CLI, or local browser Studio. All three use the same analysis, generation, review and export behavior.

```bash
git clone https://github.com/yoldaolmak/Pennovia.git
cd Pennovia
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m compileall -q pennovia
python -m ruff check pennovia tests
python -m pytest -q
python -m pennovia.demo
pennovia studio --help
```

To inspect Studio locally, run `pennovia studio` and open the printed loopback address; stop with Ctrl+C. Studio is not a hosted service. Use the [Python API](docs/API.md) for integration, not the internal Studio HTTP routes.

## Review standard

Propose a small, verifiable improvement to working author voice profiling, draft guidance, usability or a concrete failure path. Include a focused reproduction/regression test where practical and update the affected documentation. Keep `VoiceProfile` schema v1 and existing CLI behavior compatible unless a breaking change has an explicit plan. Do not add a parallel core, an account system, a database or speculative infrastructure.

Use synthetic or properly licensed sample texts. Never commit private corpora, personal profiles, provider keys or user drafts. Tests must work without live API credentials. Existing CI checks Python 3.10–3.12, Ruff, packaged Studio JavaScript syntax, Docker demo and wheel assets. A green CI result verifies tested software paths, **not** model quality or author-voice accuracy.

WordPress is draft-by-default; the CLI alone exposes explicit publication via `--publish`. See [configuration](docs/CONFIGURATION.md), [architecture](docs/ARCHITECTURE.md), [validation limits](docs/VALIDATION.md), and the private disclosure process in [SECURITY.md](SECURITY.md).
