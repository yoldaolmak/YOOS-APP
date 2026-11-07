# Architecture

Pennovia is a Python library with a CLI and an optional **loopback-only Studio**. Studio serves a small browser interface and locally invokes the existing Python modules; it is not a public HTTP API or hosted platform. Local metrics are diagnostic heuristics, not independently calibrated quality or authorship measures.

## Overview

Pennovia is designed as a single-responsibility pipeline. Each module does exactly one thing and is independently testable without any API key.

```
pennovia/
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
├── studio/          Optional loopback browser interface and static assets
│   ├── server.py    Local HTTP adapter (no business-logic duplication)
│   ├── index.html   Author workspace
│   ├── app.css      Responsive layout
│   └── app.js       Browser-side editing and local export controls
└── demo/            Self-contained demo
    └── __main__.py  python -m pennovia.demo
```

## Data Flow

```
[Files, URLs or pasted writing]
     │ read_file() / read_url() / input collection
     ▼
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

## Interfaces and integration

- **Python API** remains the reusable core. Studio imports the same `analyze()`, `generate()`, `audit()`, `score()` and exporter functions as the CLI.
- **CLI** remains suitable for scripted workflows and deliberate publishing.
- **Studio** runs only on `127.0.0.1`, serves packaged HTML/CSS/JS and exposes a small session-token-protected local adapter. It does not add persistent server state, authentication accounts or another scoring implementation.
- Voice profiles are ordinary JSON. Use `VoiceProfile.from_dict(data)` for in-memory validation or `VoiceProfile.load(path)` for local files; all interfaces use schema v1.

Developers should integrate through the Python API, **not** depend on Studio's browser endpoints as a stable external service. Studio is an optional presentation layer, not a competing architecture.

## VoiceProfile

The `VoiceProfile` dataclass is the core artifact. It is:
- **Portable** — plain JSON, no binary dependencies
- **Versionable** — can be stored in private version control; do not publish corpus excerpts without permission
- **Versioned** — JSON schema version 1 is explicit; legacy files without a version are read as v1, unknown optional keys are ignored, and incompatible or malformed known fields are rejected

Key dimensions extracted by `analyzer.py`:

| Dimension | Metric |
|-----------|--------|
| Sentence rhythm | avg length, std dev, short/long ratio (including 1–2 word sentences) |
| Voice persona | first-person rate, question rate, negative rate |
| Paragraph style | avg sentences/words per non-empty paragraph, including short paragraphs |
| Vocabulary | type-token ratio, avg word length |
| Punctuation | em-dash, semicolon, parenthesis rates per 100 sentences |
| Fingerprint | top transition words (whole expressions only), signature 2-gram phrases |
| Examples | 5 sample sentences (short, medium, long) |

## Prompt Strategy

The provider receives one system message containing trusted structure and rules, plus one user message containing the topic and **untrusted corpus-derived evidence**. There is no agent loop or streaming pipeline. Codex CLI receives the equivalent labeled text; its prompt labels do not provide provider-enforced role isolation.

`_build_prompt()` constructs:
1. Trusted system instructions: structure, output constraints, style statistics and rules against invented experiences.
2. Untrusted user evidence: corpus-derived author label, observed transitions, characteristic phrases and sample sentences, which are data rather than instructions.
3. The user-selected topic, delivered with the evidence at user-message priority.

The prompt is backend-agnostic — the same prompt works with OpenAI, Anthropic, OpenRouter, and Ollama. The separation reduces accidental elevation of corpus text into system instructions, but is not a complete prompt-injection defense: a model may still follow malicious source content. Generated claims and first-person accounts still require human verification.

## Audit (Zero LLM)

`audit.py` scores generated content against the source profile using only statistical comparison:

- **Voice match (0–40)**: sentence length similarity, first-person rate, question rate
- **Transition match (0–20)**: shared transition words from profile
- **Style match (0–20)**: paragraph structure similarity
- **No AI clichés (0–20)**: penalty for known AI writing patterns

Diagnostic PASS requires a heuristic total ≥ 70/100 **and at least 200 words**. Insufficient text cannot pass solely by matching superficial traits. Scores remain uncalibrated, and PASS is not an editorial or authorship acceptance decision.

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

## Data boundary

Voice profiles can include verbatim source excerpts. Optional cloud LLM generation transmits prompt material to the chosen provider. Google Drive and WordPress exports are separate network actions; WordPress drafts are the default and HTTPS is mandatory.
