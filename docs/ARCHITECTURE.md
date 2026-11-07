# Architecture

Pennovia is a Python library with a CLI and an optional **loopback-only Studio**. Studio serves a small browser interface and locally invokes the existing Python modules; it is not a public HTTP API or hosted platform. Local metrics are diagnostic heuristics, not independently calibrated quality or authorship measures.

## Overview

Pennovia is designed as a single-responsibility pipeline. Each module does exactly one thing and is independently testable without any API key.

```
pennovia/
├── ingestion/       Input parsing
│   └── reader.py   read_file(), read_corpus(), read_url()
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

```text
[Local TXT/HTML/PDF]    [Public HTTPS article]    [Pasted text]
         \                    |                     /
          \____ read_file()/read_url()/user input ___/
                            |
                            v
                      [List of str]
                            |
                         analyze()
                            v
                       [VoiceProfile] <--> [JSON file / import]
                            |
                   _build_prompt() + topic
                            v
                   [Selected model backend]
                            |
                       [Draft text]
                            |
                  +---------+---------+
                  |                   |
              audit()/score()     User editing
                  |                   |
                  +---------+---------+
                            |
                   [Explicit export action]
                  /            |           \
           TXT/HTML/PDF    Google Drive   WordPress draft
```

The CLI and Studio feed the **same analyzer, generator, review and export functions**. Studio offers browser downloads and saves WordPress drafts only; the CLI can also publish with explicit `--publish`. No model call is needed for analysis or review. The offline demo may use labeled mock output, but Studio production generation does not.

## Interfaces and integration

- **Python API** remains the reusable core. Studio imports the same `analyze()`, `generate()`, `audit()`, `score()` and exporter functions as the CLI.
- **CLI** remains suitable for scripted workflows and deliberate publishing.
- **Studio** runs only on `127.0.0.1`, serves packaged HTML/CSS/JS and exposes a small session-token-protected local adapter. It does not add persistent server state, authentication accounts or another scoring implementation.
- Voice profiles are ordinary JSON. Use `VoiceProfile.from_dict(data)` for in-memory validation or `VoiceProfile.load(path)` for local files; all interfaces use schema v1.

Developers should integrate through the Python API, **not** depend on Studio's browser endpoints as a stable external service. Studio is an optional presentation layer, not a competing architecture.

## VoiceProfile

The `VoiceProfile` dataclass is the core artifact. It is:
- **Portable** — plain JSON; optional PDF and model backends have their own dependencies
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

## Extending Supported Choices

A new **model backend** needs an adapter in `voice/generator.py`, dispatch in `generate()`, a CLI `--backend` choice, the Studio provider allowlist/dropdown and relevant configuration and tests. Keep provider failures bounded and ensure no accidental fallback to another cloud service.

A new **content type** belongs in `content_types/registry.py` with `label`, `structure`, `tone` and `length`. The CLI accepts named choices and Studio has an explicit dropdown; update both and their tests. Do not create a separate content-type engine for Studio.

## Data boundary

Voice profiles can include verbatim source excerpts. Optional cloud LLM generation transmits prompt material to the chosen provider. Google Drive and WordPress exports are separate network actions; WordPress drafts are the default and HTTPS is mandatory.
