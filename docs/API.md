# Python API Reference

Pennovia 0.2.0 provides a Python API and CLI, not a maintained HTTP service. The numerical voice scores below are uncalibrated heuristics.

All public functions are importable from `pennovia.*`.

## ingestion.reader

```python
from pennovia.ingestion.reader import read_file, read_corpus

text: str = read_file("/path/to/file.pdf")
# Supports: .pdf, .html, .htm, .txt

texts: list[str] = read_corpus(["/path/file1.txt", "/path/file2.pdf"])
# Skips unreadable, unsupported and short files, warning on stderr
# Returns only texts with > 50 whitespace-delimited words
```

`read_file()` raises `ValueError` for unsupported extensions. The CLI scans a corpus directory non-recursively in sorted filename order and reports both candidate and usable file counts. For direct API use, `read_corpus()` remains best-effort: check the number of returned texts against your inputs.

## voice.analyzer

```python
from pennovia.voice.analyzer import analyze, VoiceProfile

profile: VoiceProfile = analyze(texts, author_name="Hemingway")
# Optional: analyze(texts, author_name="Writer", language="tr")

profile.save("hemingway.json")  # Python API preserves overwrite behavior
profile = VoiceProfile.load("hemingway.json")

print(profile.summary())
# Author: Hemingway (en, 5 texts, 12,400 words)
# Sentences: avg 8.2w ± 5.1w | short 42% / long 9%
# ...
```

### VoiceProfile fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int | Profile format version; currently `1` |
| `author_name` | str | As provided |
| `language` | str | `"en"`, `"tr"` or `"auto"` (insufficient or mixed evidence) |
| `text_count` | int | Number of input texts |
| `total_words` | int | Total word count across all texts |
| `avg_sentence_words` | float | Mean sentence length |
| `sentence_std_dev` | float | Standard deviation of sentence length |
| `short_sentence_rate` | float | Proportion of sentences < 8 words |
| `long_sentence_rate` | float | Proportion of sentences > 20 words |
| `first_person_rate` | float | Share of sentences with supported singular first-person pronouns (English/Turkish, language-aware). Does not infer inflected Turkish verbs or first-person plural |
| `question_rate` | float | Proportion of sentences ending with ? |
| `negative_rate` | float | Share of sentences containing at least one listed negation marker (0–1 for newly analyzed profiles); not a full Turkish morphological negation detector |
| `avg_paragraph_sentences` | float | Mean sentences per paragraph |
| `vocabulary_richness` | float | Mean type-token ratio over complete 500-word windows (including the final window), or the complete shorter corpus; words count Unicode letter tokens of 3+ characters |
| `emdash_rate` | float | Em-dashes per 100 sentences |
| `top_transitions` | list[str] | Most-used transition words |
| `signature_phrases` | list[str] | Recurring 2-gram phrases formed within source documents (never across separate files) |
| `sample_sentences` | list[str] | Up to five short/medium/long reference sentences, distributed across source documents where available |

### Profile JSON contract

For loss prevention, pass `profile.save(path, overwrite=False)` when writing a new profile via Python. CLI `analyze` and `run --save-profile` refuse replacement by default; `--overwrite` explicitly permits it. The direct Python method keeps its historical default (`overwrite=True`) for compatibility. New profile JSON files and CLI-generated drafts use restrictive permissions on POSIX systems (typically `0600`). Existing outputs are replaced atomically when overwrite is explicit, avoiding partially truncated previous content. This protects ordinary local file writes; it is not encryption or a guarantee against privileged local access.

`VoiceProfile.save()` writes JSON with `schema_version: 1`. Files written before this field existed remain loadable as version 1. Unknown extra keys are ignored, but a file explicitly declaring another version is rejected to prevent silent interpretation of an incompatible format.

`VoiceProfile.load()` checks that the root is an object, known fields have appropriate JSON types, numeric fields are finite and non-negative, rate fields stay in the 0–1 range, and language is `auto`, `en`, or `tr`. It raises `ValueError` for invalid profile contents. The format is not a proof of writer identity or scoring quality. Profiles may contain verbatim source excerpts; treat them as private user data.

The built-in detector handles **English and Turkish only**. It combines function-word evidence with Turkish-specific letters; ambiguous, short and mixed-language texts produce `"auto"` rather than inventing a language. `analyze(..., language="tr"|"en")`, `pennovia analyze --language tr`, and `pennovia run --language tr` override the detector. This is a deliberately limited heuristic, not language identification for arbitrary text. A profile with unresolved language prompts the model to follow its source samples instead of presuming English. In this state, analysis checks observed Turkish and English transition and explicit negation markers instead of silently using the English-only list.

## voice.generator

```python
from pennovia.voice.generator import generate

content: str = generate(
    profile,
    content_type="travel_blog",  # or: travel_guide, magazine, news, story, column
    topic="A weekend in Lisbon",
    backend="auto",              # auto, openai, anthropic, openrouter, ollama, codex
    model="gpt-4o",              # optional model override
)
```

`backend="auto"` tries: Anthropic → OpenRouter → OpenAI → Ollama. The CLI defaults to the `PENNOVIA_BACKEND` environment variable when it is set; an explicit `--backend` takes precedence.

## audit

```python
from pennovia.audit import audit, AuditResult

result: AuditResult = audit(content, profile)

result.total_score    # int 0–100
result.voice_match    # int 0–40
result.transition_match  # int 0–20
result.style_match    # int 0–20
result.no_ai_cliches  # int 0–20
result.issues         # list[str]
result.passed()       # bool: score >= 70 AND text is at least 200 words; not calibrated
result.report()       # str — formatted report
```

## voice.scorer

```python
from pennovia.voice.scorer import score

similarity: float = score(content, profile)  # 0.0 – 1.0
```

## exporter.writer

```python
from pennovia.exporter.writer import (
    to_html, to_pdf, save_local, save_google_drive, save_wordpress
)

html: str = to_html(content, title="My Article")
pdf_path: str = to_pdf(content, title="My Article", output_path="/tmp/out.pdf")

# Save locally
path: str = save_local(content, title, fmt="html",
                       destination="downloads")  # or "desktop" or "/abs/path"

# Upload to Google Drive
link: str = save_google_drive(content, title, fmt="html")
# Requires: GOOGLE_DRIVE_TOKEN env var

# Export to WordPress (draft by default; publication requires publish=True)
url: str = save_wordpress(content, title,
                          wp_url=None,       # HTTPS URL; falls back to WP_URL env var
                          wp_user=None,      # WP_USER
                          wp_password=None,  # WP_APP_PASSWORD
                          publish=False)     # True = publish, False = draft
```

WordPress export refuses redirects (rather than silently following a different host or protocol), validates successful JSON responses, and raises bounded `RuntimeError` on HTTP/network/invalid-response failures. Configure `wp_url` as the canonical HTTPS base URL, without query strings, fragments or embedded credentials. The response must include a non-empty post link.

### CLI export format contract

Local and Google Drive exports accept `html`, `txt`, or `pdf` (including comma-separated combinations). Unsupported or duplicate formats are rejected before writing. WordPress accepts only a single HTML export; multi-format requests are rejected rather than posting the same draft more than once. `run --dest wordpress` defaults to HTML, while local `run` defaults to HTML and TXT.

## content_types.registry

```python
from pennovia.content_types.registry import list_types, get

types: dict = list_types()
# {"travel_blog": "Seyahat Blogu / Travel Blog", ...}

ct: dict = get("travel_guide")
# {"label": "...", "structure": [...], "tone": "...", "length": "..."}
```
