# Python API Reference

Use these Python functions to integrate Pennovia. Studio's localhost endpoints are internal, not a public API. Style scores are uncalibrated.

## ingestion.reader

```python
from pennovia.ingestion.reader import read_file, read_corpus, read_url

article: str = read_url("https://example.org/my-article")

text: str = read_file("/path/to/file.pdf")
# Supports: .pdf, .html, .htm, .txt

texts: list[str] = read_corpus(["/path/file1.txt", "/path/file2.pdf"])
# Skips unreadable, unsupported and short files, warning on stderr
# Returns only texts with > 50 whitespace-delimited words
```

`read_url()` reads public HTTPS HTML/plain-text pages (2 MB maximum, limited redirects, local-address rejection). It does not crawl websites. `read_corpus()` skips unreadable or short files and reports them on stderr; check the number of returned texts. CLI `analyze`/`run` also accept repeated `--url`, `--text` and optional `--corpus`. Each source needs **51+ words**.

## voice.analyzer

```python
import json
from pennovia.voice.analyzer import analyze, VoiceProfile

profile: VoiceProfile = analyze(texts, author_name="Hemingway")
# Optional: analyze(texts, author_name="Writer", language="tr")

profile.save("hemingway.json")  # Python API preserves overwrite behavior
profile = VoiceProfile.load("hemingway.json")
profile = VoiceProfile.from_dict(json.loads(profile.to_json()))  # in-memory validation

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
| `first_person_rate` | float | Share of sentences with listed singular pronouns; not inflected Turkish verbs |
| `question_rate` | float | Proportion of sentences ending with ? |
| `negative_rate` | float | Sentences with listed negation markers (0–1); limited Turkish coverage |
| `avg_paragraph_sentences` | float | Mean sentences per paragraph |
| `vocabulary_richness` | float | Mean type-token ratio across 500-token windows (including tail) |
| `emdash_rate` | float | Em-dashes per 100 sentences |
| `top_transitions` | list[str] | Most-used transition words |
| `signature_phrases` | list[str] | Recurring within-document word pairs |
| `sample_sentences` | list[str] | Up to five representative sentences across sources |

### Profile JSON contract

Use `profile.save(path, overwrite=False)` to prevent replacement. The Python method defaults to `overwrite=True` for compatibility; CLI commands refuse overwrite unless `--overwrite` is given. Writes use restrictive permissions where supported and atomic replacement, **not encryption**.

Profile JSON uses `schema_version: 1`. Older unversioned files load as v1; unknown fields are ignored and incompatible versions are rejected.

`load()` and `from_dict()` validate known field types, finite nonnegative metrics, 0–1 rates and language (`auto`, `en`, `tr`). Invalid data raises `ValueError`. Profiles may contain verbatim excerpts.

Language detection covers **Turkish and English**. Ambiguous samples return `auto`. Set `language="tr"` or `"en"` when known; the CLI accepts `--language`.

## voice.generator

```python
from pennovia.voice.generator import generate

content: str = generate(
    profile,
    content_type="travel_blog",  # travel_guide, magazine, news, story, column
    topic="A weekend in Lisbon",
    backend="ollama",            # or openai, anthropic, openrouter, codex, auto
    # model="llama3",            # optional: match the chosen provider
)
```

`auto` selects Anthropic → OpenRouter → OpenAI → Ollama based on configured credentials. CLI supports `PENNOVIA_BACKEND`; Studio defaults to local Ollama. A `model` override must match the provider; Codex CLI does not accept one.

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

WordPress requires a canonical HTTPS base URL. Redirects and invalid responses are rejected; network failures raise `RuntimeError`.

### CLI export format contract

Local/Drive: TXT, HTML or PDF (comma-separated formats allowed). WordPress: one HTML output only. Local `run` defaults to HTML+TXT; WordPress `run` defaults to HTML.

## content_types.registry

```python
from pennovia.content_types.registry import list_types, get

types: dict = list_types()
# {"travel_blog": "Travel Blog", "travel_guide": "Travel Guide", ...}

ct: dict = get("travel_guide")
# {"label": "Travel Guide", "structure": [...], "tone": "...", "length": "..."}
```
