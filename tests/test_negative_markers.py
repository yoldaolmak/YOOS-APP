"""Negation features are bounded, whole-expression observations."""
from pennovia.voice.analyzer import _has_negative_marker, analyze


def test_turkish_negative_does_not_match_inside_unrelated_words():
    assert not _has_negative_marker("Yoklama bugün başladı.", "tr")
    assert _has_negative_marker("Orada yok.", "tr")
    assert _has_negative_marker("Bu doğru değil.", "tr")


def test_multiple_negatives_count_as_one_sentence():
    text = "Yoklama başladı. Onlar geldi. Yok yok, bu doğru değil."
    profile = analyze([text], language="tr")
    assert profile.negative_rate == 0.33


def test_english_negative_expressions_are_whole_words():
    assert _has_negative_marker("I did not go and couldn't wait.", "en")
    assert not _has_negative_marker("This did notation on paper.", "en")


def test_unresolved_language_checks_both_vocabularies():
    text = "Ama but."
    profile = analyze([text], language="auto")
    assert profile.language == "auto"
    assert "ama" in profile.top_transitions
    assert "but" in profile.top_transitions
    assert _has_negative_marker("Yok, I didn't go.", "auto")


def test_negative_rate_never_exceeds_one_per_sentence():
    text = "Yok, yok, yok, değil, olmadı! Yok yok, yok."
    profile = analyze([text], language="tr")
    assert profile.negative_rate == 1.0
