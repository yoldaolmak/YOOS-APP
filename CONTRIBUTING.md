# Contributing

Pennovia has a shared Python core, CLI and local Studio. Keep changes focused on a working author-voice capability or a reproducible defect.

## Run checks

```bash
git clone https://github.com/yoldaolmak/Pennovia.git
cd Pennovia
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m ruff check pennovia tests
python -m pytest -q
pennovia studio --help
```

CI covers Python 3.10–3.12, Ruff, Studio JavaScript syntax, Docker demo and installed-wheel assets.

## Pull requests

Provide the behavior change, a focused test and any needed documentation update. Preserve CLI compatibility and `VoiceProfile` v1 unless a breaking change is justified. Do not add a parallel core or speculative infrastructure.

Use synthetic or licensed corpus samples. Never commit personal writing, profiles, drafts or secrets. Tests must work without provider keys; passing tests do not prove style fidelity.

For integration use the [Python API](docs/API.md), not Studio's internal HTTP routes. Studio exports WordPress drafts; CLI and Python API can explicitly publish. Report vulnerabilities privately per [Security](SECURITY.md).
