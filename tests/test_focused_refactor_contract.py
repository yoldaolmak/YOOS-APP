"""Behavior contracts for the two extracted core and Studio responsibilities."""
from pathlib import Path

import pytest

from pennovia.exporter import writer
from pennovia.studio import server
from pennovia.voice.analyzer import (
    _collect_sentence_structure, _signature_phrases, analyze,
)


def test_sentence_structure_preserves_document_and_paragraph_boundaries():
    texts = [
        "I walk slowly. I notice the harbor.\n\nBut I return.",
        "I walk slowly. I notice the harbor.",
    ]
    sentences, documents, paragraph_words, paragraph_sentences = (
        _collect_sentence_structure(texts)
    )
    assert [len(document) for document in documents] == [3, 2]
    assert len(sentences) == 5
    assert paragraph_words == [7, 3, 7]
    assert paragraph_sentences == [2, 1, 2]

    profile = analyze(texts, author_name="Example", language="en")
    assert profile.text_count == 2
    assert profile.total_words == 17
    assert profile.avg_sentence_words == 3.4
    assert profile.avg_paragraph_sentences == 1.7
    assert profile.avg_paragraph_words == 5.7
    assert profile.first_person_rate == 1.0


def test_signature_phrases_do_not_bridge_documents_or_mutate_sources():
    sources = [
        "coastal market coastal market coastal market",
        "evening harbor evening harbor evening harbor",
    ]
    snapshot = list(sources)
    phrases = _signature_phrases(sources)
    assert phrases == ["coastal market", "evening harbor"]
    assert "market evening" not in phrases
    assert sources == snapshot


def test_analyze_empty_and_explicit_language_contracts_still_hold():
    profile = analyze(["", "..."], language="tr", author_name="Empty")
    assert profile.author_name == "Empty"
    assert profile.language == "tr"
    assert profile.text_count == 0
    with pytest.raises(ValueError, match="language must be auto"):
        analyze(["A sample."], language="unknown")


@pytest.mark.parametrize("path", [
    "/api/profile", "/api/generate", "/api/review", "/api/export", "/unknown",
])
def test_studio_dispatch_rejects_non_object_payloads_before_action(path):
    with pytest.raises(ValueError, match="Expected a JSON object"):
        server._handle_api(path, [])


def test_studio_dispatch_keeps_draft_only_wordpress_boundary(monkeypatch):
    from pennovia.voice.analyzer import VoiceProfile

    profile = VoiceProfile(text_count=1, total_words=100)
    calls = []

    def save(draft, title, publish=False):
        calls.append((draft, title, publish))
        return "https://example.org/draft"

    monkeypatch.setattr(writer, "save_wordpress", save)
    response = server._handle_api("/api/export", {
        "profile": profile.__dict__,
        "draft": "This is an existing draft.",
        "title": "A title",
        "destination": "wordpress",
        "publish": True,
    })
    assert response == {
        "url": "https://example.org/draft",
        "message": "WordPress draft created",
    }
    assert calls == [("This is an existing draft.", "A title", False)]


def test_studio_pdf_download_removes_temporary_file_on_read_error(
    monkeypatch, tmp_path,
):
    missing = tmp_path / "missing.pdf"

    def fake_pdf(*args):
        missing.write_text("temporary document", encoding="utf-8")
        return missing

    original_read = Path.read_bytes

    def broken_read(path):
        if path == missing:
            raise OSError("simulated I/O failure")
        return original_read(path)

    monkeypatch.setattr(writer, "to_pdf", fake_pdf)
    monkeypatch.setattr(Path, "read_bytes", broken_read)
    with pytest.raises(OSError, match="simulated I/O failure"):
        server._download_draft("Content", "Title", "pdf")
    assert not missing.exists()
