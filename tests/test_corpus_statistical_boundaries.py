"""Corpus statistics must use observed tokens, not artificial input joins."""
from pennovia.voice.analyzer import _vocabulary_richness, analyze


def _letters(value: int) -> str:
    """Unique alphabetic tokens; no digits to confuse the word tokenizer."""
    result = ""
    value += 1
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(97 + remainder) + result
    return "token" + result


def test_vocabulary_exactly_one_full_window_counts_all_words():
    corpus = " ".join(_letters(i) for i in range(500))
    assert _vocabulary_richness(corpus) == 1.0


def test_vocabulary_501_words_includes_final_token():
    corpus = " ".join(["alpha"] * 500 + ["omega"])
    # First 500-word window: 1/500, tail-anchored window: 2/500.
    assert _vocabulary_richness(corpus) == 0.003


def test_vocabulary_strided_windows_include_complete_last_window():
    corpus = " ".join(["alpha"] * 500 + ["omega"] * 250)
    # Two windows, at offsets 0 and 250: 1/500 and 2/500.
    assert _vocabulary_richness(corpus) == 0.003


def test_vocabulary_tail_is_not_silently_dropped_after_strided_windows():
    corpus = " ".join(["alpha"] * 500 + ["omega"] * 250 + ["sigma"])
    # Offsets 0, 250, 251 have respectively one, two and three token types.
    assert _vocabulary_richness(corpus) == 0.004


def test_vocabulary_handles_turkish_capital_dotted_i():
    assert _vocabulary_richness("İstanbul istanbul") == 0.5


def test_bigrams_never_cross_separate_input_documents():
    texts = ["alpha omega", "sigma taupe"] * 4
    profile = analyze(texts, language="en")
    assert "alpha omega" in profile.signature_phrases
    assert "sigma taupe" in profile.signature_phrases
    assert "omega sigma" not in profile.signature_phrases
    assert "taupe alpha" not in profile.signature_phrases
