# Architecture

One Python core serves the CLI and local Studio. Studio is a browser interface over the existing functions, not a separate engine or public API.

## Modules

```text
pennovia/
├── ingestion/reader.py     Files and HTTPS article text
├── voice/analyzer.py       analyze() → VoiceProfile
├── voice/generator.py      generate() → draft
├── voice/scorer.py         score() → 0–1
├── audit.py                audit() → 0–100
├── content_types/registry.py
├── exporter/writer.py      TXT, HTML, PDF, Drive, WordPress
├── cli.py                  Command-line interface
├── studio/                 Local server and browser assets
└── demo/                   Offline demonstration
```

## Flow

```text
Files / HTTPS URLs / pasted text
              ↓
        List of texts
              ↓
           analyze()
              ↓
       VoiceProfile v1 ←→ JSON
              ↓
      profile + topic + type
              ↓
    configured model backend
              ↓
          draft text
              ↓
        audit() / score()
              ↓
      user review and edits
              ↓
    TXT / HTML / PDF / Drive / WP
```

Analysis and review run locally without a model. Studio permits browser downloads and **WordPress drafts only**; the CLI and Python API support explicit publishing. No automatic account or database is involved.

Studio keeps source, profile and draft revisions separate. Source or analysis-setting changes invalidate the profile and review without discarding the editable draft. While a request is active, inputs are locked and async results are checked against their starting revision. A remote export may end as confirmed, rejected or **outcome unknown**; the last state requires the user to verify the destination before explicitly retrying. Remote writes cannot be rolled back by the local process.

## Voice profile

`VoiceProfile` stores sentence length, first-person use, questions, negatives, paragraph rhythm, vocabulary and punctuation statistics, transitions, recurring phrases and up to five representative sentences. The portable JSON format uses `schema_version: 1`; old unversioned profiles remain readable.

Use `VoiceProfile.load(path)` or `VoiceProfile.from_dict(data)` to validate saved or in-memory profiles. Generated profiles may contain source excerpts.

## Model prompt

`_build_prompt()` sends:

- **System:** content structure, measured style traits and rules against invented facts or firsthand experiences.
- **User:** topic plus untrusted source-derived examples, phrases and author label.

OpenAI, Anthropic, OpenRouter and Ollama use role-separated messages. Codex CLI receives labeled text, not provider-enforced role separation. Source material may still influence the model; this is not a complete prompt-injection defense.

## Review

The heuristic audit assigns 40 points to voice markers, 20 to transitions, 20 to structure and 20 to avoiding common AI clichés. A PASS requires **at least 70/100 and 200 words**. Scores are not calibrated measures of authorship or writing quality.

## Integration

Use the [Python API](API.md), not Studio's localhost endpoints. The CLI and Studio share the same core functions.

To add a backend, update `voice/generator.py`, its CLI choice, Studio provider choice and tests. To add a content type, update `content_types/registry.py` and the explicit CLI/Studio choices. Avoid duplicating generation or scoring logic.
