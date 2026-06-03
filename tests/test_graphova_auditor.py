"""
Tests for graphova.core.auditor and graphova.core.scorer.
No API keys required.
"""
from __future__ import annotations
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graphova.core.extractor import extract
from graphova.core.fingerprint import VoiceFingerprint
from graphova.core.auditor import audit, AuditResult, PASS_THRESHOLD
from graphova.core.scorer import score, score_detailed

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "corpus")

_TWAIN_TEXTS = []
for _f in ["twain_01.txt", "twain_02.txt", "twain_03.txt"]:
    _p = os.path.join(CORPUS_DIR, _f)
    if os.path.exists(_p):
        with open(_p, encoding="utf-8") as _fh:
            _TWAIN_TEXTS.append(_fh.read())


# ── AuditResult model ─────────────────────────────────────────────────────────

def test_audit_result_passed():
    r = AuditResult(total_score=75)
    assert r.passed() is True

def test_audit_result_failed():
    r = AuditResult(total_score=60)
    assert r.passed() is False

def test_audit_result_grade_A():
    assert AuditResult(total_score=92).grade() == "A"

def test_audit_result_grade_B():
    assert AuditResult(total_score=85).grade() == "B"

def test_audit_result_grade_C():
    assert AuditResult(total_score=72).grade() == "C"

def test_audit_result_grade_D():
    assert AuditResult(total_score=60).grade() == "D"

def test_audit_result_grade_F():
    assert AuditResult(total_score=40).grade() == "F"

def test_audit_result_report_format():
    r = AuditResult(total_score=78, voice_match=30, transition_match=15,
                    structure_match=18, no_ai_cliches=15,
                    issues=["too_short"])
    report = r.report()
    assert "78/100" in report
    assert "PASS" in report
    assert "too_short" in report


# ── Audit — empty / edge cases ────────────────────────────────────────────────

def test_audit_empty_content():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    result = audit("", fp)
    assert result.total_score == 0
    assert "empty_content" in result.issues

def test_audit_whitespace_only():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    result = audit("   \n\n\t  ", fp)
    assert result.total_score == 0

def test_audit_no_real_sentences():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    result = audit("OK. No. Yes.", fp)
    # "OK." "No." "Yes." are all < 3 words so split returns 0 sentences
    assert result.total_score == 0


# ── Audit — scoring logic ─────────────────────────────────────────────────────

def test_audit_score_in_range():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    text = "This is a test sentence. I went to the store and bought some groceries. She smiled warmly."
    result = audit(text, fp)
    assert 0 <= result.total_score <= 100

def test_audit_subscores_sum_to_total():
    fp = VoiceFingerprint(avg_sentence_words=10.0)
    text = "I walked there. She waited. He arrived. They talked for hours about nothing in particular."
    result = audit(text, fp)
    assert result.voice_match + result.transition_match + result.structure_match + result.no_ai_cliches == result.total_score

def test_audit_ai_cliche_detected():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    cliche_text = (
        "Let us delve into this fascinating tapestry. "
        "In conclusion, it is worth noting that furthermore we must navigate these challenges. "
        "In today's world, moreover, it is important to leverage all available synergies. "
        "As a comprehensive guide, this article will explore the paradigm shift. "
        "At the end of the day, we must shed light on these matters. " * 3
    )
    result = audit(cliche_text, fp)
    assert result.no_ai_cliches < 20
    assert any("cliche" in i.lower() or "clichés" in i.lower() for i in result.issues)

def test_audit_no_cliches_full_score():
    fp = VoiceFingerprint(avg_sentence_words=8.0, top_transitions=[])
    clean_text = (
        "The market was crowded. I pushed through the stalls. "
        "Every vendor called out different prices. "
        "I bought nothing but came away full. " * 5
    )
    result = audit(clean_text, fp)
    assert result.no_ai_cliches == 20

def test_audit_issues_is_list():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    result = audit("Test sentence with enough words here.", fp)
    assert isinstance(result.issues, list)

def test_audit_details_is_dict():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    result = audit("Test sentence with enough words here.", fp)
    assert isinstance(result.details, dict)


# ── Audit — with real profile ─────────────────────────────────────────────────

@pytest.mark.skipif(not _TWAIN_TEXTS, reason="Twain corpus not available")
def test_audit_twain_source_text_reasonable():
    fp = extract(_TWAIN_TEXTS, "Mark Twain")
    result = audit(_TWAIN_TEXTS[0], fp)
    assert 0 <= result.total_score <= 100
    assert result.voice_match + result.transition_match + result.structure_match + result.no_ai_cliches == result.total_score

@pytest.mark.skipif(not _TWAIN_TEXTS, reason="Twain corpus not available")
def test_audit_twain_source_text_passes():
    """Source text should score well against its own profile."""
    fp = extract(_TWAIN_TEXTS, "Mark Twain")
    result = audit(_TWAIN_TEXTS[0], fp)
    assert result.total_score >= 50  # source text should score at least halfway

@pytest.mark.skipif(not _TWAIN_TEXTS, reason="Twain corpus not available")
def test_audit_passed_consistent():
    fp = extract(_TWAIN_TEXTS, "Mark Twain")
    result = audit(_TWAIN_TEXTS[0], fp)
    assert result.passed() == (result.total_score >= PASS_THRESHOLD)


# ── Scorer ────────────────────────────────────────────────────────────────────

def test_score_empty_content():
    fp = VoiceFingerprint(avg_sentence_words=12.0)
    assert score("", fp) == 0.0

def test_score_blank_fingerprint():
    fp = VoiceFingerprint()  # avg_sentence_words = 0.0
    assert score("Some content here.", fp) == 0.0

def test_score_range():
    fp = VoiceFingerprint(avg_sentence_words=10.0, first_person_rate=0.3,
                          vocabulary_richness=0.5)
    result = score("I walked. She waited. They talked. He said nothing.", fp)
    assert 0.0 <= result <= 1.0

@pytest.mark.skipif(not _TWAIN_TEXTS, reason="Twain corpus not available")
def test_score_source_text_positive():
    fp = extract(_TWAIN_TEXTS, "Mark Twain")
    s = score(_TWAIN_TEXTS[0], fp)
    assert s > 0.3  # source text should match its own profile

@pytest.mark.skipif(not _TWAIN_TEXTS, reason="Twain corpus not available")
def test_score_similar_higher_than_different():
    fp = extract(_TWAIN_TEXTS, "Mark Twain")
    similar_score = score(_TWAIN_TEXTS[1], fp)  # same author
    generic = "The report was submitted. Results were analysed. Conclusions drawn. Data reviewed."
    generic_score = score(generic * 5, fp)
    # Source text should score higher than very different generic text
    assert similar_score >= generic_score

def test_score_detailed_structure():
    fp = VoiceFingerprint(avg_sentence_words=10.0, first_person_rate=0.2,
                          top_transitions=["but", "however"])
    text = "I went there. But it was closed. However I tried again."
    d = score_detailed(text, fp)
    assert "overall" in d
    assert "sentence_length" in d
    assert "first_person_rate" in d
    assert "transitions" in d
    assert 0.0 <= d["overall"] <= 1.0

def test_score_detailed_empty():
    fp = VoiceFingerprint()
    d = score_detailed("", fp)
    assert d["overall"] == 0.0
    assert "error" in d


# ── Genres ────────────────────────────────────────────────────────────────────

def test_genres_list():
    from graphova.core.genres import list_genres, get_genre, validate_genre
    genres = list_genres()
    assert len(genres) >= 6
    for key in ["travel_blog", "travel_guide", "magazine", "news", "story", "column"]:
        assert key in genres

def test_genres_get_fallback():
    from graphova.core.genres import get_genre
    g = get_genre("nonexistent_genre")
    assert g == get_genre("travel_blog")

def test_genres_validate():
    from graphova.core.genres import validate_genre
    assert validate_genre("travel_blog") is True
    assert validate_genre("unknown") is False

def test_genre_structure_complete():
    from graphova.core.genres import GENRES
    for key, genre in GENRES.items():
        assert "label" in genre, f"{key} missing label"
        assert "structure" in genre, f"{key} missing structure"
        assert "tone" in genre, f"{key} missing tone"
        assert "length" in genre, f"{key} missing length"
        assert len(genre["structure"]) >= 3, f"{key} structure too short"
