"""Transition detection must not confuse words with embedded substrings."""
from pennovia.audit import audit
from pennovia.voice.analyzer import VoiceProfile, _transition_count, analyze
from pennovia.voice.scorer import score


def test_transition_word_boundaries_in_english():
    assert _transition_count("Butter tastes good. But it is rich.", "but") == 1
    assert _transition_count("Butter tastes good.", "but") == 0
    assert _transition_count("However, it is still here.", "however") == 1


def test_transition_word_boundaries_in_turkish():
    assert _transition_count("Zaman tamamlandı; tamamdır.", "ama") == 0
    assert _transition_count("Ama bugün zaman yok.", "ama") == 1


def test_multiword_transition_tolerates_newlines():
    assert _transition_count("On the other\nhand, consider this.", "on the other hand") == 1
    assert _transition_count("This other hand is useful.", "on the other hand") == 0


def test_analyzer_does_not_invent_transition_from_embedded_word():
    text = "Güneşli İzmir güzel, yarın zaman tamamlanacak. " * 10
    profile = analyze([text])
    assert profile.language == "tr"
    assert "ama" not in profile.top_transitions


def test_scorer_does_not_reward_embedded_transition():
    profile = VoiceProfile(avg_sentence_words=6.0, first_person_rate=0, top_transitions=["but"])
    with_transition = score("But this is really a sentence.", profile)
    embedded_only = score("Butter this is really a sentence.", profile)
    assert with_transition > embedded_only


def test_audit_uses_same_transition_semantics():
    profile = VoiceProfile(avg_sentence_words=6.0, first_person_rate=0, top_transitions=["but"])
    result = audit("Butter is an ingredient, not a conjunction.", profile)
    assert result.details["transitions_found"] == 0
