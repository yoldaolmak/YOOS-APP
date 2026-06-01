# YOOS-APP

> **Universal Author Voice Engine** — analyze any author's writing style, generate new content in their voice.

Give YOOS-APP a set of texts from any writer. It extracts their voice profile — sentence rhythm, transitions, first-person rate, signature phrases — and uses an LLM to write new content in that exact style for any topic and genre.

No embeddings. No vector database. Portable, forkable, runs on any machine.

---

## Quick Start

```bash
git clone https://github.com/example/YOOS-APP.git
cd YOOS-APP
pip install -r requirements.txt
cp .env.example .env  # add your OPENAI_API_KEY
python -m yoos_app.demo
```

Demo runs without an API key (mock output). Set `OPENAI_API_KEY` for real generation.

---

## How It Works

```
Your texts (PDF/HTML/TXT)
        ↓
  Voice Analyzer
  → sentence length, transitions,
    first-person rate, signature phrases
        ↓
  VoiceProfile (portable JSON)
        ↓
  Content Generator (OpenAI / Ollama / Codex)
  + content type structure (blog / guide / news…)
        ↓
  Output → Downloads / Desktop / Google Drive / WordPress
```

---

## Content Types

| Key | Label |
|-----|-------|
| `travel_blog` | Seyahat Blogu / Travel Blog |
| `travel_guide` | Seyahat Rehberi / Travel Guide |
| `magazine` | Dergi Yazısı / Magazine Article |
| `news` | Haber / News |
| `story` | Hikaye / Story |
| `column` | Köşe Yazısı / Column |

---

## CLI Usage

```bash
# Step 1 — Analyze author voice from a folder of texts
yoos-app analyze --corpus ./my-author-texts/ --author "Author Name" --out profile.json

# Step 2 — Generate content
yoos-app generate --profile profile.json --type travel_blog --topic "Lisbon" --backend openai

# Step 3 — Export
yoos-app export --input output.txt --title "Lisbon Guide" --format html --dest downloads

# Full pipeline in one command
yoos-app run --corpus ./texts/ --type travel_guide --topic "Tokyo" --backend openai --dest wordpress
```

---

## LLM Backends

| Backend | How to use |
|---------|-----------|
| `openai` | Set `OPENAI_API_KEY` in `.env` |
| `ollama` | Run `ollama serve` locally, set `YOOS_BACKEND=ollama` |
| `codex` | OpenAI Codex CLI (`codex` in PATH) |

---

## Output Destinations

| Destination | Value |
|------------|-------|
| Downloads folder | `--dest downloads` |
| Desktop | `--dest desktop` |
| Custom path | `--dest /path/to/folder` |
| Google Drive | `--dest google_drive` + `GOOGLE_DRIVE_TOKEN` |
| WordPress | `--dest wordpress` + `WP_URL`, `WP_USER`, `WP_APP_PASSWORD` |

Output formats: `--format html`, `--format pdf`, `--format txt`

---

## Copyright Note

YOOS-APP does not store, redistribute, or train on any uploaded texts. Voice analysis runs locally. You are responsible for ensuring you have the right to use any texts you provide as corpus input.

---

## Stack

- Python 3.10+
- OpenAI API / Ollama / Codex CLI (your choice)
- pdfplumber — PDF parsing
- reportlab — PDF export
- BeautifulSoup4 — HTML parsing
- Google Drive API (optional)
- WordPress REST API (optional)

---

## Related

- **[example.com](https://example.com)** — live publication powered by this engine
