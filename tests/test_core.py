"""Core tests — run without any API key."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from yoos_app.ingestion.reader import read_corpus, read_file
from yoos_app.voice.analyzer import analyze, VoiceProfile
from yoos_app.content_types.registry import list_types, get
from yoos_app.exporter.writer import to_html, save_local, to_pdf
from yoos_app.voice.generator import _build_prompt
from yoos_app.voice.scorer import score
from yoos_app.audit import audit

CORPUS = [
    os.path.join(os.path.dirname(__file__), "..", "examples", "corpus", f)
    for f in ["twain_01.txt", "twain_02.txt", "twain_03.txt"]
]


def test_reader_txt():
    texts = read_corpus(CORPUS)
    assert len(texts) == 3
    assert all(len(t.split()) > 50 for t in texts)


def test_reader_html():
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
        f.write("<html><body><p>Test paragraph content here.</p></body></html>")
        tmp = f.name
    text = read_file(tmp)
    os.unlink(tmp)
    assert "Test paragraph" in text


def test_analyzer():
    texts = read_corpus(CORPUS)
    profile = analyze(texts, "Test Author")
    assert profile.text_count == 3
    assert profile.avg_sentence_words > 0
    assert 0.0 <= profile.first_person_rate <= 1.0
    assert 0.0 <= profile.question_rate <= 1.0


def test_profile_save_load():
    texts = read_corpus(CORPUS)
    profile = analyze(texts, "Save Test")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    profile.save(tmp)
    loaded = VoiceProfile.load(tmp)
    os.unlink(tmp)
    assert loaded.author_name == "Save Test"
    assert loaded.avg_sentence_words == profile.avg_sentence_words


def test_content_types():
    types = list_types()
    assert len(types) == 6
    for key in ["travel_blog", "travel_guide", "magazine", "news", "story", "column"]:
        assert key in types
    ct = get("travel_guide")
    assert "structure" in ct
    assert len(ct["structure"]) >= 4


def test_to_html():
    html = to_html("First paragraph.\n\nSecond paragraph.", "My Title")
    assert "<h1>My Title</h1>" in html
    assert "<p>First paragraph.</p>" in html
    assert "<p>Second paragraph.</p>" in html


def test_save_local_txt():
    with tempfile.TemporaryDirectory() as d:
        path = save_local("Test content.", "Test", "txt", d)
        assert os.path.exists(path)
        assert open(path).read() == "Test content."


def test_save_local_html():
    with tempfile.TemporaryDirectory() as d:
        path = save_local("Test content.", "Test", "html", d)
        assert os.path.exists(path)
        assert "<html" in open(path).read()


def test_to_pdf():
    path = to_pdf("PDF content test.", "PDF Title")
    assert os.path.exists(path)
    assert os.path.getsize(path) > 500
    os.unlink(path)


def test_generator_prompt():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    sys_p, usr_p = _build_prompt(profile, "travel_blog", "Istanbul")
    assert "Istanbul" in usr_p
    assert len(sys_p) > 100


def test_voice_scorer():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    sim = score(texts[0], profile)
    assert 0.0 <= sim <= 1.0


def test_audit():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    result = audit(texts[0], profile)
    assert 0 <= result.total_score <= 100
    assert result.voice_match >= 0
    assert isinstance(result.issues, list)
    assert result.report()
