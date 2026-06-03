# Architecture

## Overview

YOOS-APP is designed as a single-responsibility pipeline. Each module does exactly one thing and is independently testable without any API key.

```
yoos_app/
├── ingestion/       Input parsing
│   └── reader.py   read_file(), read_corpus()
│
├── voice/           Voice intelligence
│   ├── analyzer.py  analyze() → VoiceProfile
│   ├── generator.py generate() → str
│   └── scorer.py    score() → float (0–1)
│
├── content_types/   Content structure
│   └── registry.py  list_types(), get()
│
├── exporter/        Output layer
│   └── writer.py    save_local(), save_google_drive(), save_wordpress()
│
├── audit.py         audit() → AuditResult (0–100)
├── cli.py           Command-line interface
└── demo/            Self-contained demo
    └── __main__.py  python -m yoos_app.demo
```

## Data Flow

```
[Corpus files]
     │ read_corpus()
     ▼
[List of str]
     │ analyze()
     ▼
[VoiceProfile JSON]  ←─ portable, versionable, shareable
     │
     │ _build_prompt()
     │     └─ profile stats + sample sentences + content type structure
     ▼
[LLM API call]  ← one call, fully formed prompt
     │
     ▼
[Generated text str]
     │
     ├─ audit()   → AuditResult (0–100, no LLM)
     ├─ score()   → float 0–1   (no LLM)
     │
     └─ save_local() / save_google_drive() / save_wordpress()
          └─ to_html() / to_pdf() / plain txt
```

## VoiceProfile

The `VoiceProfile` dataclass is the core artifact. It is:
- **Portable** — plain JSON, no binary dependencies
- **Versionable** — can be committed to source control
- **Forward-compatible** — `VoiceProfile.load()` ignores unknown fields

Key dimensions extracted by `analyzer.py`:

| Dimension | Metric |
|-----------|--------|
| Sentence rhythm | avg length, std dev, short/long ratio |
| Voice persona | first-person rate, question rate, negative rate |
| Paragraph style | avg sentences/words per paragraph |
| Vocabulary | type-token ratio, avg word length |
| Punctuation | em-dash, semicolon, parenthesis rates per 100 sentences |
| Fingerprint | top transition words, signature 2-gram phrases |
| Examples | 5 sample sentences (short, medium, long) |

## Prompt Strategy

The LLM receives a single, fully-formed prompt. No multi-turn conversation, no streaming complexity.

`_build_prompt()` constructs:
1. Author voice fingerprint (derived from profile stats)
2. Sample sentences (tone reference, not to copy)
3. Content type structure (numbered sections)
4. Hard rules (no AI clichés, no fabrication, output-only)

The prompt is backend-agnostic — the same prompt works with OpenAI, Anthropic, OpenRouter, and Ollama.

## Audit (Zero LLM)

`audit.py` scores generated content against the source profile using only statistical comparison:

- **Voice match (0–40)**: sentence length similarity, first-person rate, question rate
- **Transition match (0–20)**: shared transition words from profile
- **Style match (0–20)**: paragraph structure similarity
- **No AI clichés (0–20)**: penalty for known AI writing patterns

Pass threshold: ≥ 70/100.

## Adding a Backend

1. Add `generate_mybackend(profile, content_type, topic, **kwargs) → str` in `voice/generator.py`
2. Add branch in `generate()` dispatch dict
3. Add to `--backend` choices in `cli.py`
4. Add to `.env.example`
5. Add test in `tests/test_core.py`

## Adding a Content Type

1. Add entry to `CONTENT_TYPES` dict in `content_types/registry.py`
2. Keys: `label`, `structure` (list), `tone`, `length`
3. No other changes needed — the generator and CLI pick it up automatically
