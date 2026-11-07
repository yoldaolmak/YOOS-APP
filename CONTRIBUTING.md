# Contributing

Contributions to the standalone YOOS-APP CLI should improve working analysis, author voice profiling, drafting, tests, or safe exports.

```bash
git clone https://github.com/yoldaolmak/YOOS-APP.git
cd YOOS-APP
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m compileall -q yoos_app
python -m pytest -q
python -m yoos_app.demo
```

Use synthetic or properly licensed fixtures; never commit private corpus data, secret keys, personal profiles, or generated drafts. Tests must run without an API key. A proposed change must have an observable behavior or verified bug fix, regression tests, and a documented limitation where relevant.

Keep CLI behavior and `VoiceProfile` schema compatible unless a breaking change is justified. The audit is heuristic, and WordPress publication is explicitly opt-in. For security disclosures follow [SECURITY.md](SECURITY.md), not public issues.
