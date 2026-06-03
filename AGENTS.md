# AGENTS.md — LLM Integration Guide

This file describes how AI agents interact with the YOOS-APP codebase.

## Architecture Overview

YOOS-APP uses LLMs as **generation backends only**. All analysis, profiling, auditing, and scoring is done locally with zero LLM calls. The LLM receives a fully-formed prompt built from the extracted voice profile and content type template.

```
VoiceProfile (local) + ContentType template (local)
            ↓
    build_prompt()  ←  yoos_app/voice/generator.py
            ↓
      LLM API call  (one call per generation)
            ↓
    audit() + score()  (local, no LLM)
```

## Prompt Structure

```
SYSTEM:
  - Author identity from VoiceProfile
  - Style rules (sentence length, first-person rate, transitions)
  - Sample sentences from corpus (3 examples — tone reference, not copy)
  - Content type structure (numbered sections)
  - Hard rules (no AI clichés, no fabrication, output only)

USER:
  - Topic: "..."
  - Instruction to write in voice + structure
```

## Supported Backends

| Backend | Module | Config |
|---------|--------|--------|
| OpenAI | `generate_openai()` | `OPENAI_API_KEY` |
| Anthropic Claude | `generate_anthropic()` | `ANTHROPIC_API_KEY` |
| OpenRouter | `generate_openrouter()` | `OPENROUTER_API_KEY` |
| Ollama (local) | `generate_ollama()` | `ollama serve` |
| OpenAI Codex CLI | `generate_codex()` | `codex login` |

## Adding a New Backend

1. Add `generate_mybackend(profile, content_type, topic, **kwargs)` in `yoos_app/voice/generator.py`
2. Add a branch in `generate()` dispatch
3. Add to CLI `--backend` choices in `yoos_app/cli.py`
4. Add to `YOOS_BACKEND` docs in `.env.example`

## Working with This Repo (Codex/Claude)

- Entry point: `yoos_app/cli.py` → `main()`
- Voice logic: `yoos_app/voice/`
- No credentials in code — all via environment variables
- Tests require no API key: `python -m pytest tests/`
- Demo: `python -m yoos_app.demo`
