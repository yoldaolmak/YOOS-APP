"""One real, reproducible Ollama run against verified public-domain prose.

Runs outside normal unit tests. No mocked provider, no API key and no
claim of calibrated style fidelity. GitHub Actions uploads the exact drafts.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from pennovia.audit import audit
from pennovia.exporter.writer import save_local
from pennovia.voice.analyzer import analyze
from pennovia.voice.generator import generate
from pennovia.voice.scorer import score

SOURCE = "https://www.gutenberg.org/cache/epub/3176/pg3176.txt"
MODEL = "qwen2.5:1.5b"
OLLAMA = "http://127.0.0.1:11434"
TOPICS = (
    "A practical guide to arriving in an unfamiliar seaside town",
    "How to plan a walk through a small city without rushing",
)


def select_chapters(book: str) -> dict[str, str]:
    """Select nonoverlapping narrative excerpts, not the table of contents."""
    if "The Innocents Abroad" not in book or "Mark Twain" not in book:
        raise ValueError("Source is not the expected Mark Twain work")
    headings = {}
    for number in ("I", "II", "III", "IV", "V"):
        matches = list(re.finditer(
            rf"(?m)^CHAPTER {number}\.[ \t]*$", book
        ))
        if len(matches) != 1:
            raise ValueError(f"Expected one body heading for chapter {number}")
        headings[number] = matches[0]
    pieces = {}
    for number, next_number in (("I", "II"), ("II", "III"),
                                ("III", "IV"), ("IV", "V")):
        chapter = book[headings[number].end():headings[next_number].start()]
        tokens = list(re.finditer(r"\S+", chapter))
        if len(tokens) < 350:
            raise ValueError(f"Chapter {number} is unexpectedly short")
        # Keep paragraph boundaries and original punctuation intact.
        pieces[number] = chapter[:tokens[349].end()].strip()
    return pieces


def _download_source() -> tuple[str, str]:
    response = requests.get(SOURCE, timeout=(10, 45))
    response.raise_for_status()
    if len(response.content) > 3_000_000:
        raise RuntimeError("Gutenberg source exceeds the expected size")
    raw = response.content
    text = raw.decode("utf-8-sig")
    return text, hashlib.sha256(raw).hexdigest()


def _model_digest() -> str:
    response = requests.get(f"{OLLAMA}/api/tags", timeout=15)
    response.raise_for_status()
    for item in response.json().get("models", []):
        if item.get("name") == MODEL:
            digest = item.get("digest", "")
            if len(digest) >= 32:
                return digest
    raise RuntimeError(f"Required real Ollama model is not installed: {MODEL}")


def _baseline(topic: str) -> str:
    """Same real model, no Pennovia style profile: illustrative control."""
    response = requests.post(
        f"{OLLAMA}/api/chat",
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": (
                    "Write an informative travel article with clear paragraphs. "
                    "Avoid invented personal visits, precise unsupported facts, "
                    "and fabricated quotations. Do not imitate an author."
                )},
                {"role": "user", "content": topic},
            ],
            "stream": False,
        },
        timeout=300,
    )
    response.raise_for_status()
    text = response.json()["message"]["content"].strip()
    if len(text.split()) < 50:
        raise RuntimeError("Neutral live-model draft was too short to inspect")
    return text


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    book, source_sha256 = _download_source()
    chapters = select_chapters(book)
    model_digest = _model_digest()
    training = [chapters[name] for name in ("I", "II", "IV")]
    held_out = chapters["III"]
    profile = analyze(training, author_name="Mark Twain (Project Gutenberg)",
                      language="en")
    profile.save(str(out / "voice-profile.json"), overwrite=False)

    # Explicitly keep chapter III out of all training data and sample prompts.
    if held_out in "\n".join(training):
        raise RuntimeError("Held-out material leaked into training corpus")
    held_out_score = score(held_out, profile)
    held_out_audit = audit(held_out, profile)
    drafts = []
    for index, topic in enumerate(TOPICS, 1):
        # The actual Pennovia model adapter calls the local Ollama service.
        text = generate(profile, "travel_guide", topic, backend="ollama",
                        model=MODEL)
        if len(text.split()) < 50:
            raise RuntimeError(f"Live-model draft #{index} is too short")
        filename = out / f"styled-{index}.txt"
        filename.write_text(text, encoding="utf-8")
        result = audit(text, profile)
        drafts.append({
            "topic": topic,
            "file": filename.name,
            "words": len(text.split()),
            "score_0_to_1": score(text, profile),
            "audit_0_to_100": result.total_score,
            "audit_pass": result.passed(),
            "issues": result.issues,
        })
        if index == 1:
            # Exercise the real exporters, not mock writers.
            exports = {}
            for fmt in ("html", "pdf", "txt"):
                path = Path(save_local(text, "Pennovia real model trial",
                                       fmt, str(out)))
                if not path.is_file() or path.stat().st_size == 0:
                    raise RuntimeError(f"{fmt.upper()} export is empty")
                exports[fmt] = path.name

    neutral = _baseline(TOPICS[0])
    (out / "neutral-control.txt").write_text(neutral, encoding="utf-8")
    report = {
        "status": "real_model_executed",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_sha256": source_sha256,
        "training_chapters": ["I", "II", "IV"],
        "held_out_chapter": "III",
        "training_word_counts": [len(part.split()) for part in training],
        "held_out_words": len(held_out.split()),
        "held_out_score_0_to_1": held_out_score,
        "held_out_audit_0_to_100": held_out_audit.total_score,
        "provider": "local Ollama",
        "model": MODEL,
        "model_digest": model_digest,
        "actual_model_calls": 3,
        "styled_drafts": drafts,
        "neutral_control": {
            "file": "neutral-control.txt",
            "words": len(neutral.split()),
            "score_0_to_1": score(neutral, profile),
            "audit_0_to_100": audit(neutral, profile).total_score,
        },
        "exports": exports,
        "interpretation": (
            "Single source book, one small language model, two styled drafts "
            "and one neutral control. These are descriptive observations, "
            "not calibrated voice fidelity or evidence of editorial quality."
        ),
    }
    _write_json(out / "evidence.json", report)
    # CI logs show only a short result; the exact outputs are downloadable.
    print(json.dumps({
        "status": report["status"],
        "model": MODEL,
        "training_chapters": report["training_chapters"],
        "held_out_chapter": report["held_out_chapter"],
        "styled_words": [d["words"] for d in drafts],
        "styled_audits": [d["audit_0_to_100"] for d in drafts],
        "control_audit": report["neutral_control"]["audit_0_to_100"],
    }))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"Live model validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
