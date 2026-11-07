"""Shared first-person semantics must agree across the whole pipeline."""
from pennovia.audit import audit
from pennovia.voice.analyzer import VoiceProfile, _first_person_rate, analyze
from pennovia.voice.scorer import score


def test_first_person_turkish_forms_count_consistently():
    sentence = "Beni burada hep beklediler."
    profile = VoiceProfile(language="tr", avg_sentence_words=5, first_person_rate=1)
    assert _first_person_rate([sentence], "tr") == 1.0
    assert audit(sentence, profile).details["first_person_rate"] == 1
    assert score(sentence, profile) > score("Onu burada hep beklediler.", profile)


def test_english_and_turkish_pronouns_do_not_leak_languages():
    assert _first_person_rate(["I am here."], "tr") == 0
    assert _first_person_rate(["Ben bugün geldim."], "en") == 0
    assert _first_person_rate(["Ben bugün geldim."], "auto") == 1
    assert _first_person_rate(["I am here."], "auto") == 1


def test_metric_denominator_is_sentences_not_pronouns():
    sentences = ["Ben bugün buradayım.", "Ben kendime bakıyorum.", "Onlar oradalar."]
    assert _first_person_rate(sentences, "tr") == 2 / 3


def test_analyzer_and_audit_share_person_marker_semantics():
    text = ("Beni burada hep beklediler. Onu orada da beklediler. " * 8)
    profile = analyze([text], language="tr")
    result = audit(text, profile)
    assert profile.first_person_rate == 0.5
    assert result.details["first_person_rate"] == 0.5


def test_empty_sentences_have_zero_rate():
    assert _first_person_rate([], "tr") == 0
