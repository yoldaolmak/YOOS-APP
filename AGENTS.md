# AGENTS.md — Codex Integration Guide

This file describes how AI agents (primarily OpenAI Codex) interact with this repository.

## How Codex Is Used

YOOS-APP uses **Codex as the primary content rewrite agent** in its editorial pipeline. Codex handles the core writing task — rewriting travel articles section by section — while the system provides:

- Editorial brief (semantic intent, destination character, thesis)
- Voice protocol (Alex Rivera's 16-year full-time authorial voice rules)
- State ledger (cross-section consistency tracking)
- RAG context (top-3 similar passages from approved author corpus)

```
Codex receives:
  - Section HTML (factual inventory)
  - Editorial brief (thesis, audience, cliché list)
  - Voice protocol (prohibited patterns, signature phrases)
  - Previous section summary (state ledger)
  - RAG examples (3 approved author passages from Qdrant)

Codex outputs:
  - Gutenberg HTML (WordPress block format)
  - Section rewrite in author's voice
```

## Codex Workflow

```bash
# Codex is invoked per H2 section via multi_ai.py
USE_CODEX=true python3 prompts/pass2_rewrite.py <POST_ID>

# Codex runs in ephemeral, read-only mode
codex exec --ephemeral --skip-git-repo-check -s read-only -C /path/to/yoos-app
```

## What Codex Should Know

- **Working directory:** project root
- **Entry point:** `prompts/pass2_rewrite.py`
- **Voice rules:** `prompts/voice_profile.py` — single source of truth, read before writing
- **Architecture docs:** `GPT.md` — full system context
- **Do not modify:** `.env`, `data/gold/`, `corpus/`

## Codex Constraints

- Never hallucinate personal experiences — only use what's in the editorial brief
- Timeline lock: if brief says `explicit_year_allowed=false`, do not invent years
- Output must be valid Gutenberg HTML — no markdown, no code fences
- Voice threshold: similarity score ≥ 0.45 against `Alex_voice_travel` Qdrant collection

## Repository Structure for Agents

```
prompts/voice_profile.py     ← READ FIRST: voice rules + prohibited word list
prompts/pass2_rewrite.py     ← main pipeline entry point
modules/editorial/           ← editorial brief + state ledger
modules/voice/               ← voice enforcement via Qdrant RAG
modules/llm_router.py        ← LLM provider routing (Codex → Kimi → fallback)
data/gold/                   ← approved author texts (read-only reference)
GPT.md                       ← full system context for AI assistants
```
