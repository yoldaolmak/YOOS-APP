"""Representative writing examples should reflect more than the first file."""
from pennovia.voice.analyzer import _sample_sentences, analyze
from pennovia.voice.generator import _build_prompt


def _source(label):
    short = f"{label} makes a simple observation about this place today."
    medium = (
        f"{label} looks carefully at the unfamiliar surroundings while "
        "describing the quiet streets and the ordinary details of everyday life."
    )
    long = (
        f"{label} observes that even after many hours of wandering through "
        "the busy streets and narrow passages around the old market, "
        "the most memorable detail is often something small and completely "
        "unexpected along the way."
    )
    return " ".join((short, medium, long))


def test_multiple_source_texts_supply_prompt_examples():
    texts = [_source("Firstsource"), _source("Secondsource"), _source("Thirdsource")]
    profile = analyze(texts, language="en")
    assert len(profile.sample_sentences) == 5
    assert all(
        any(sentence.startswith(name) for sentence in profile.sample_sentences)
        for name in ("Firstsource", "Secondsource", "Thirdsource")
    )
    _, prompt = _build_prompt(profile, "travel_blog", "A test subject")
    for name in ("Firstsource", "Secondsource", "Thirdsource"):
        assert name in prompt


def test_sample_selection_is_deterministic_and_keeps_rhythm_buckets():
    documents = [[
        "One writes a very short sentence today.",
        "One continues with a more detailed sentence about the town and all its interesting people over the years.",
        "One makes a much longer and more detailed observation about the weather outside and the people moving through the streets in the city every morning and evening during their busy everyday routines.",
    ], [
        "Two writes a very short sentence today.",
        "Two continues with a more detailed sentence about the town and all its interesting people over the years.",
        "Two makes a much longer and more detailed observation about the weather outside and the people moving through the streets in the city every morning and evening during their busy everyday routines.",
    ]]
    first = _sample_sentences(documents)
    assert first == _sample_sentences(documents)
    assert len(first) == 5
    assert sum(5 <= len(s.split()) <= 12 for s in first) == 2
    assert sum(13 <= len(s.split()) <= 22 for s in first) == 2
    assert sum(len(s.split()) > 22 for s in first) == 1


def test_one_file_and_missing_long_sentences_still_have_examples():
    samples = _sample_sentences([
        ["One writes a very short sentence today.", "One brings another short piece of evidence today."]
    ])
    assert len(samples) == 2
    assert samples[0].startswith("One")
    assert _sample_sentences([]) == []
