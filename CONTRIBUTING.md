# Contributing

Contributions to the standalone Pennovia CLI should improve working analysis, author voice profiling, drafting, tests, or safe exports.

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
```

Use synthetic or properly licensed fixtures; never commit private corpus data, secret keys, personal profiles, or generated drafts. Tests must run without an API key. A proposed change must have an observable behavior or verified bug fix, regression tests, and a documented limitation where relevant.

Keep CLI behavior and `VoiceProfile` schema compatible unless a breaking change is justified. The audit is heuristic, and WordPress publication is explicitly opt-in. For security disclosures follow [SECURITY.md](SECURITY.md), not public issues.

## Review standard

Submit a small, verifiable change that corrects a demonstrated behavior or improves a working capability. Include a failing case or reproduction where practical, the smallest safe fix, relevant regression tests, and documentation of any changed CLI or Python API behavior.

CI checks Ruff, Python 3.10–3.12 and Docker. Passing checks and higher heuristic voice scores do not by themselves establish authorship accuracy or product quality. Avoid speculative dependencies, private corpora, large cosmetic refactors and breaking profile changes without an explicit compatibility plan.

Update [configuration](docs/CONFIGURATION.md), [API](docs/API.md) or [changelog](CHANGELOG.md) as appropriate. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
