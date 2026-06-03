"""
Core tests — all run without any API key.
"""
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from yoos_app.ingestion.reader import read_corpus, read_file
from yoos_app.voice.analyzer import analyze, VoiceProfile
from yoos_app.content_types.registry import list_types, get
from yoos_app.exporter.writer import to_html, save_local, to_pdf
from yoos_app.voice.generator import _build_prompt
from yoos_app.voice.scorer import score
from yoos_app.audit import audit

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "corpus")
CORPUS = [os.path.join(CORPUS_DIR, f)
          for f in ["twain_01.txt", "twain_02.txt", "twain_03.txt"]]


# ── Ingestion ─────────────────────────────────────────────────────────────────

def test_reader_txt_files():
    texts = read_corpus(CORPUS)
    assert len(texts) == 3
    assert all(len(t.split()) > 50 for t in texts)

def test_reader_html():
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
        f.write("<html><body><h1>Title</h1><p>Test paragraph content here with enough words.</p></body></html>")
        tmp = f.name
    text = read_file(tmp)
    os.unlink(tmp)
    assert "Test paragraph" in text
    assert "Title" in text

def test_reader_skips_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("short")
        tmp = f.name
    texts = read_corpus([tmp])
    os.unlink(tmp)
    assert len(texts) == 0  # < 50 words, skipped

def test_reader_single_file():
    text = read_file(CORPUS[0])
    assert len(text.split()) > 50

def test_reader_mixed_corpus():
    with tempfile.TemporaryDirectory() as d:
        # TXT
        with open(os.path.join(d, "a.txt"), "w") as f:
            f.write(" ".join(["word"] * 100))
        # HTML
        with open(os.path.join(d, "b.html"), "w") as f:
            f.write("<html><body><p>" + " ".join(["text"] * 100) + "</p></body></html>")
        # Non-readable extension (should be ignored)
        with open(os.path.join(d, "c.csv"), "w") as f:
            f.write("a,b,c")
        texts = read_corpus([os.path.join(d, "a.txt"),
                             os.path.join(d, "b.html"),
                             os.path.join(d, "c.csv")])
        assert len(texts) == 2


# ── Voice Analyzer ────────────────────────────────────────────────────────────

def test_analyzer_basic():
    texts = read_corpus(CORPUS)
    profile = analyze(texts, "Test Author")
    assert profile.text_count == 3
    assert profile.avg_sentence_words > 0
    assert profile.total_words > 0

def test_analyzer_rates_in_range():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    assert 0.0 <= profile.first_person_rate <= 1.0
    assert 0.0 <= profile.question_rate <= 1.0
    assert 0.0 <= profile.exclamation_rate <= 1.0
    assert 0.0 <= profile.vocabulary_richness <= 1.0
    assert profile.sentence_std_dev >= 0.0

def test_analyzer_transitions_found():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    assert len(profile.top_transitions) > 0

def test_analyzer_sample_sentences():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    assert len(profile.sample_sentences) > 0
    assert all(len(s.split()) > 2 for s in profile.sample_sentences)

def test_analyzer_empty_texts():
    profile = analyze([], "Empty")
    assert profile.text_count == 0
    assert profile.avg_sentence_words == 0.0

def test_analyzer_turkish_detection():
    tr_text = ["Türkiye güzel bir ülkedir. İstanbul'da çok güzel yerler var. Ama gitmek zor olabilir."]
    profile = analyze(tr_text * 5)
    assert profile.language == "tr"

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
    assert loaded.top_transitions == profile.top_transitions

def test_profile_load_forward_compat():
    """Load should not crash if profile JSON has extra unknown fields."""
    data = {
        "author_name": "Test",
        "language": "en",
        "text_count": 1,
        "total_words": 100,
        "avg_sentence_words": 10.0,
        "unknown_future_field": "ignored",
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(data, f)
        tmp = f.name
    profile = VoiceProfile.load(tmp)
    os.unlink(tmp)
    assert profile.author_name == "Test"

def test_profile_summary():
    texts = read_corpus(CORPUS)
    profile = analyze(texts, "Summary Test")
    summary = profile.summary()
    assert "Summary Test" in summary
    assert "sentences" in summary.lower()


# ── Content Types ─────────────────────────────────────────────────────────────

def test_content_types_count():
    assert len(list_types()) == 6

def test_all_content_types_present():
    types = list_types()
    for key in ["travel_blog", "travel_guide", "magazine", "news", "story", "column"]:
        assert key in types, f"Missing content type: {key}"

def test_content_type_structure():
    for key in list_types():
        ct = get(key)
        assert "label" in ct
        assert "structure" in ct
        assert "tone" in ct
        assert "length" in ct
        assert len(ct["structure"]) >= 3

def test_content_type_fallback():
    ct = get("nonexistent_type")
    assert ct == get("travel_blog")


# ── Exporter ──────────────────────────────────────────────────────────────────

def test_to_html_basic():
    html = to_html("First paragraph.\n\nSecond paragraph.", "My Title")
    assert "<h1>My Title</h1>" in html
    assert "<p>First paragraph.</p>" in html
    assert "<p>Second paragraph.</p>" in html

def test_to_html_headings():
    html = to_html("# H1 heading\n\nParagraph.", "")
    assert "<h1>H1 heading</h1>" in html

def test_to_html_no_title():
    html = to_html("Content.", "")
    assert "<h1>" not in html
    assert "<p>Content.</p>" in html

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

def test_save_local_filename_contains_title():
    with tempfile.TemporaryDirectory() as d:
        path = save_local("Content.", "MySpecialTitle", "txt", d)
        assert "myspecialtitle" in os.path.basename(path).lower()

def test_to_pdf():
    path = to_pdf("PDF content test.", "PDF Title")
    assert os.path.exists(path)
    assert os.path.getsize(path) > 500
    os.unlink(path)


# ── Generator Prompt ──────────────────────────────────────────────────────────

def test_generator_prompt_contains_topic():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    _, user = _build_prompt(profile, "travel_blog", "MyUniqueTopic")
    assert "MyUniqueTopic" in user

def test_generator_prompt_contains_structure():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    sys_p, _ = _build_prompt(profile, "travel_guide", "Rome")
    assert "1." in sys_p or "structure" in sys_p.lower()

def test_generator_prompt_all_types():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    for ct in list_types():
        sys_p, usr_p = _build_prompt(profile, ct, "Test Topic")
        assert len(sys_p) > 100
        assert "Test Topic" in usr_p

def test_generator_prompt_no_ai_cliches_rule():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    sys_p, _ = _build_prompt(profile, "travel_blog", "Test")
    assert "delve into" in sys_p.lower() or "clich" in sys_p.lower()


# ── Scorer ────────────────────────────────────────────────────────────────────

def test_scorer_range():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    sim = score(texts[0], profile)
    assert 0.0 <= sim <= 1.0

def test_scorer_same_text_high():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    sim = score(texts[0], profile)
    assert sim > 0.4

def test_scorer_empty_content():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    sim = score("", profile)
    assert sim == 0.0


# ── Audit ─────────────────────────────────────────────────────────────────────

def test_audit_range():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    result = audit(texts[0], profile)
    assert 0 <= result.total_score <= 100

def test_audit_subscores_sum():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    result = audit(texts[0], profile)
    sub_total = result.voice_match + result.transition_match + result.style_match + result.no_ai_cliches
    assert sub_total == result.total_score

def test_audit_issues_is_list():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    result = audit(texts[0], profile)
    assert isinstance(result.issues, list)

def test_audit_report_string():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    result = audit(texts[0], profile)
    report = result.report()
    assert "Voice Audit:" in report
    assert "/100" in report

def test_audit_ai_cliche_detected():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    cliche_text = "Let us delve into the fascinating tapestry of this city. In conclusion, it is worth noting that navigation is key. In today's world, we must furthermore consider the implications."
    result = audit(cliche_text, profile)
    assert result.no_ai_cliches < 20

def test_audit_passed_threshold():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    result = audit(texts[0], profile)
    assert result.passed() == (result.total_score >= 70)

def test_audit_empty_content():
    texts = read_corpus(CORPUS)
    profile = analyze(texts)
    result = audit("", profile)
    assert result.total_score == 0
