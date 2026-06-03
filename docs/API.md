# Python API Reference

All public functions are importable from `yoos_app.*`.

## ingestion.reader

```python
from yoos_app.ingestion.reader import read_file, read_corpus

text: str = read_file("/path/to/file.pdf")
# Supports: .pdf, .html, .htm, .txt

texts: list[str] = read_corpus(["/path/file1.txt", "/path/file2.pdf"])
# Skips unreadable files with a warning
# Returns only texts with > 50 words
```

## voice.analyzer

```python
from yoos_app.voice.analyzer import analyze, VoiceProfile

profile: VoiceProfile = analyze(texts, author_name="Hemingway")

profile.save("hemingway.json")
profile = VoiceProfile.load("hemingway.json")

print(profile.summary())
# Author: Hemingway (en, 5 texts, 12,400 words)
# Sentences: avg 8.2w ± 5.1w | short 42% / long 9%
# ...
```

### VoiceProfile fields

| Field | Type | Description |
|-------|------|-------------|
| `author_name` | str | As provided |
| `language` | str | "en" or "tr" (auto-detected) |
| `text_count` | int | Number of input texts |
| `total_words` | int | Total word count across all texts |
| `avg_sentence_words` | float | Mean sentence length |
| `sentence_std_dev` | float | Standard deviation of sentence length |
| `short_sentence_rate` | float | Proportion of sentences < 8 words |
| `long_sentence_rate` | float | Proportion of sentences > 20 words |
| `first_person_rate` | float | Proportion of sentences with I/me/my/ben |
| `question_rate` | float | Proportion of sentences ending with ? |
| `negative_rate` | float | Rate of negative constructions |
| `avg_paragraph_sentences` | float | Mean sentences per paragraph |
| `vocabulary_richness` | float | Type-token ratio (0–1) |
| `emdash_rate` | float | Em-dashes per 100 sentences |
| `top_transitions` | list[str] | Most-used transition words |
| `signature_phrases` | list[str] | Recurring 2-gram phrases |
| `sample_sentences` | list[str] | Representative sentences |

## voice.generator

```python
from yoos_app.voice.generator import generate

content: str = generate(
    profile,
    content_type="travel_blog",  # or: travel_guide, magazine, news, story, column
    topic="A weekend in Lisbon",
    backend="auto",              # auto, openai, anthropic, openrouter, ollama, codex
    model="gpt-4o",              # optional model override
)
```

`backend="auto"` tries: Anthropic → OpenRouter → OpenAI → Ollama.

## audit

```python
from yoos_app.audit import audit, AuditResult

result: AuditResult = audit(content, profile)

result.total_score    # int 0–100
result.voice_match    # int 0–40
result.transition_match  # int 0–20
result.style_match    # int 0–20
result.no_ai_cliches  # int 0–20
result.issues         # list[str]
result.passed()       # bool (score >= 70)
result.report()       # str — formatted report
```

## voice.scorer

```python
from yoos_app.voice.scorer import score

similarity: float = score(content, profile)  # 0.0 – 1.0
```

## exporter.writer

```python
from yoos_app.exporter.writer import (
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

# Publish to WordPress
url: str = save_wordpress(content, title,
                          wp_url=None,       # falls back to WP_URL env var
                          wp_user=None,      # WP_USER
                          wp_password=None,  # WP_APP_PASSWORD
                          publish=False)     # True = publish, False = draft
```

## content_types.registry

```python
from yoos_app.content_types.registry import list_types, get

types: dict = list_types()
# {"travel_blog": "Seyahat Blogu / Travel Blog", ...}

ct: dict = get("travel_guide")
# {"label": "...", "structure": [...], "tone": "...", "length": "..."}
```
