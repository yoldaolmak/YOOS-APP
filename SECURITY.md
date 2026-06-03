# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x (main) | ✅ |

## Reporting a Vulnerability

Email **Alex@example.com** with subject `[SECURITY] YOOS-APP`.

Do not open a public GitHub issue for security vulnerabilities.

We will respond within 72 hours and coordinate a fix before public disclosure.

## Security Model

**What YOOS-APP does with your data:**
- Corpus texts are read from disk and processed in-memory — never stored, logged, or transmitted except to your chosen LLM backend.
- Generated content is written to your chosen destination only.
- No telemetry, no analytics, no external calls except LLM API.

**Credentials:**
- All API keys are read from environment variables — never hardcoded.
- `.env` files are in `.gitignore` — never commit them.
- WordPress application passwords are passed at runtime, not stored.

**LLM backends:**
- Sending corpus excerpts to a third-party LLM API means they are subject to that provider's privacy policy.
- Use `ollama` backend for fully local, no-data-leaving processing.
