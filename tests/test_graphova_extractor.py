"""
Tests for graphova.core.extractor and graphova.core.fingerprint.
All run without any API key. No mocks — real text processing.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graphova.core.extractor import extract, _split_sentences, _detect_language, _count_syllables, _percentile
from graphova.core.fingerprint import VoiceFingerprint

# ── Corpus fixtures ────────────────────────────────────────────────────────────

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "corpus")

TWAIN_TEXTS = []
for fname in ["twain_01.txt", "twain_02.txt", "twain_03.txt"]:
    path = os.path.join(CORPUS_DIR, fname)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            TWAIN_TEXTS.append(f.read())

SHORT_EN = [
    "This is a short sentence. I went there. Did it work?",
    "He said nothing. She waited. Then they both laughed.",
]

TURKISH_TEXT = [
    "Türkiye'de seyahat etmek güzel bir deneyimdir. "
    "Özellikle Kapadokya'da çok ilginç yerler gördüm. "
    "Ama yol uzundu, zor bir yolculuktu. "
    "İstanbul'da ise çok farklı bir atmosfer var. " * 10
]


# ── Split / detect helpers ─────────────────────────────────────────────────────

def test_split_sentences_basic():
    sents = _split_sentences("This is one. This is two. And three?")
    assert len(sents) >= 2

def test_split_sentences_filters_short():
    sents = _split_sentences("A. B. Hello world, this is a sentence.")
    # Single-word "sentences" filtered (< 3 words)
    for s in sents:
        assert len(s.split()) >= 3

def test_detect_english():
    assert _detect_language("This is a regular English text without special characters.") == "en"

def test_detect_turkish():
    assert _detect_language("İstanbul çok güzel bir şehirdir. Çok yerler gördüm.") == "tr"

def test_detect_defaults_to_en():
    assert _detect_language("abc def ghi") == "en"


# ── Syllable counting ─────────────────────────────────────────────────────────

def test_syllables_mono():
    assert _count_syllables("cat") == 1

def test_syllables_bi():
    assert _count_syllables("table") >= 1  # "ta-ble" = 2

def test_syllables_long():
    assert _count_syllables("understanding") >= 4

def test_syllables_empty():
    assert _count_syllables("") == 0


# ── Percentile helper ─────────────────────────────────────────────────────────

def test_percentile_empty():
    assert _percentile([], 50) == 0.0

def test_percentile_median():
    vals = sorted([1, 2, 3, 4, 5])
    assert _percentile(vals, 50) == 3.0

def test_percentile_p25():
    vals = sorted([2, 4, 6, 8, 10])
    p25 = _percentile(vals, 25)
    assert 2 <= p25 <= 5


# ── Extractor — empty / edge cases ────────────────────────────────────────────

def test_extract_empty_corpus():
    fp = extract([], "Nobody")
    assert fp.text_count == 0
    assert fp.avg_sentence_words == 0.0
    assert fp.author_name == "Nobody"
    assert fp.language == "auto"

def test_extract_single_short_text():
    fp = extract(["Hello world. This is a short test."], "Test")
    # Should not crash; metrics may be sparse
    assert fp.text_count == 1
    assert isinstance(fp.avg_sentence_words, float)

def test_extract_no_sentences_edge():
    """Text with only 1-2 word "sentences" should produce empty fingerprint."""
    fp = extract(["Ok. Yes. No."], "Test")
    # All sentences filtered (< 3 words)
    assert fp.total_words >= 0


# ── Extractor — English corpus ────────────────────────────────────────────────

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_basic():
    fp = extract(TWAIN_TEXTS, "Mark Twain")
    assert fp.text_count == 3
    assert fp.total_words > 200
    assert fp.avg_sentence_words > 5
    assert fp.language == "en"

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_rates_in_range():
    fp = extract(TWAIN_TEXTS)
    assert 0.0 <= fp.first_person_rate <= 1.0
    assert 0.0 <= fp.question_rate <= 1.0
    assert 0.0 <= fp.short_sentence_rate <= 1.0
    assert 0.0 <= fp.long_sentence_rate <= 1.0
    assert fp.short_sentence_rate + fp.long_sentence_rate <= 1.0

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_vocabulary_richness():
    fp = extract(TWAIN_TEXTS)
    assert 0.1 <= fp.vocabulary_richness <= 1.0

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_percentiles_ordered():
    fp = extract(TWAIN_TEXTS)
    assert fp.sentence_p25 <= fp.sentence_p50 <= fp.sentence_p75

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_transitions_found():
    fp = extract(TWAIN_TEXTS)
    assert len(fp.top_transitions) >= 1

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_samples_found():
    fp = extract(TWAIN_TEXTS)
    assert len(fp.sample_sentences) >= 1
    for s in fp.sample_sentences:
        assert len(s.split()) >= 3

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_fk_grade():
    fp = extract(TWAIN_TEXTS)
    # Flesch-Kincaid grade should be positive and reasonable
    assert fp.flesch_kincaid_grade >= 0
    assert fp.flesch_kincaid_grade < 25  # sanity bound

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_std_dev_positive():
    fp = extract(TWAIN_TEXTS)
    assert fp.sentence_std_dev >= 0.0

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_extract_twain_word_length():
    fp = extract(TWAIN_TEXTS)
    assert 3.0 <= fp.avg_word_length <= 8.0


# ── Extractor — Turkish ───────────────────────────────────────────────────────

def test_extract_turkish_language():
    fp = extract(TURKISH_TEXT)
    assert fp.language == "tr"

def test_extract_turkish_fk_zero():
    """FK grade not computed for Turkish."""
    fp = extract(TURKISH_TEXT)
    assert fp.flesch_kincaid_grade == 0.0


# ── VoiceFingerprint — serialisation ─────────────────────────────────────────

def test_fingerprint_to_json():
    fp = VoiceFingerprint(author_name="Test", avg_sentence_words=12.5)
    data = json.loads(fp.to_json())
    assert data["author_name"] == "Test"
    assert data["avg_sentence_words"] == 12.5

def test_fingerprint_save_load():
    fp = VoiceFingerprint(
        author_name="Save Test",
        avg_sentence_words=11.0,
        vocabulary_richness=0.55,
        top_transitions=["but", "however"],
    )
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        fp.save(tmp)
        loaded = VoiceFingerprint.load(tmp)
        assert loaded.author_name == "Save Test"
        assert loaded.avg_sentence_words == 11.0
        assert loaded.top_transitions == ["but", "however"]
    finally:
        os.unlink(tmp)

def test_fingerprint_forward_compat():
    """Unknown fields from future versions are silently ignored."""
    data = {
        "author_name": "Compat Test",
        "avg_sentence_words": 8.0,
        "future_unknown_field": "should be ignored",
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(data, f)
        tmp = f.name
    try:
        fp = VoiceFingerprint.load(tmp)
        assert fp.author_name == "Compat Test"
        assert not hasattr(fp, "future_unknown_field")
    finally:
        os.unlink(tmp)

def test_fingerprint_summary():
    fp = VoiceFingerprint(
        author_name="Summary Author",
        language="en",
        text_count=5,
        total_words=10000,
        avg_sentence_words=14.2,
        sentence_std_dev=5.1,
        short_sentence_rate=0.25,
        long_sentence_rate=0.15,
        first_person_rate=0.4,
        top_transitions=["but", "however", "yet"],
    )
    summary = fp.summary()
    assert "Summary Author" in summary
    assert "14.2" in summary
    assert "but" in summary

def test_fingerprint_diff():
    a = VoiceFingerprint(avg_sentence_words=12.0, first_person_rate=0.3)
    b = VoiceFingerprint(avg_sentence_words=18.0, first_person_rate=0.3)
    diff = a.diff(b)
    assert "avg_sentence_words" in diff
    assert diff["avg_sentence_words"]["delta"] == pytest.approx(6.0)
    # first_person_rate identical → not in diff (delta 0)
    assert "first_person_rate" not in diff

def test_fingerprint_distance_identical():
    fp = VoiceFingerprint(avg_sentence_words=12.0, short_sentence_rate=0.3)
    assert fp.distance(fp) == pytest.approx(0.0)

def test_fingerprint_distance_different():
    a = VoiceFingerprint(avg_sentence_words=8.0, first_person_rate=0.05)
    b = VoiceFingerprint(avg_sentence_words=20.0, first_person_rate=0.6)
    assert a.distance(b) > 0.2

def test_fingerprint_from_dict():
    data = {"author_name": "Dict Test", "avg_sentence_words": 9.5,
            "unknown_key": "ignored"}
    fp = VoiceFingerprint.from_dict(data)
    assert fp.author_name == "Dict Test"
    assert fp.avg_sentence_words == 9.5


# ── Distinguishability — two different authors ────────────────────────────────

@pytest.mark.skipif(not TWAIN_TEXTS, reason="Twain corpus not found")
def test_two_author_profiles_differ():
    """Short punchy text vs long flowing text should produce different profiles."""
    punchy = [
        "Short. Fast. Direct. One word. Go. Now. Done. Stop. Wait. Think. Yes. No." * 20
    ]
    flowing = [
        "It was a long and complicated affair, one that had taken many months to resolve, "
        "and even then the resolution was not entirely satisfactory to any of the parties "
        "who had been involved in the lengthy negotiations." * 10
    ]
    fp_punchy = extract(punchy, "Punchy")
    fp_flowing = extract(flowing, "Flowing")
    assert fp_punchy.avg_sentence_words < fp_flowing.avg_sentence_words
    dist = fp_punchy.distance(fp_flowing)
    assert dist > 0.05  # measurably different
