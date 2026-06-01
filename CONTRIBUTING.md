# Contributing to YOOS-APP

YOOS-APP is the editorial engine behind [example.com](https://example.com), a Turkish travel publication with 1,500+ long-form articles. Contributions that improve the editorial pipeline, voice enforcement, or WordPress integration are welcome.

## What We're Looking For

- **LLM routing improvements** — better provider fallback logic, cost optimization
- **Voice enforcement** — improvements to the similarity scoring or RAG retrieval
- **WordPress integration** — Gutenberg block handling, REST API edge cases
- **Audit criteria** — new quality checks aligned with EEAT standards
- **Performance** — batch processing, caching, embedding pipeline speed

## Getting Started

```bash
git clone git@github.com:example/YOOS-APP.git
cd YOOS-APP
python3.10 -m venv venv && source venv/bin/activate
pip install openai anthropic python-dotenv qdrant-client sentence-transformers beautifulsoup4 requests gitpython
cp .env.example .env  # fill in your credentials
```

## Code Style

- Python 3.10+
- No type stubs required, but type hints encouraged
- Keep functions focused — one responsibility per function
- Comments only when the WHY is non-obvious

## Pull Request Process

1. Open an issue first for significant changes
2. Branch from `main`
3. Keep PRs focused — one concern per PR
4. Test against a real WordPress draft post (use `--no-save` flag for dry runs)

## Voice Protocol

The voice protocol in `prompts/voice_profile.py` is the single source of truth for editorial rules. Changes to the prohibited word list or voice system require strong justification — these rules are derived from 16 years of full-time travel writing.

## License

By contributing, you agree your contributions are licensed under the MIT License.
