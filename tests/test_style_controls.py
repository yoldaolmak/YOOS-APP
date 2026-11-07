"""Synthetic negative controls: no claim of real authorship calibration."""
from pennovia.audit import audit
from pennovia.voice.analyzer import VoiceProfile, analyze
from pennovia.voice.scorer import score


def test_short_content_cannot_pass_despite_high_metric_match():
    source = VoiceProfile(
        avg_sentence_words=2, avg_paragraph_sentences=1,
        first_person_rate=0, question_rate=0, top_transitions=["but"],
    )
    result = audit("But now.", source)
    assert result.total_score >= 70  # demonstrates misleading raw heuristic
    assert "too_short" in result.issues
    assert not result.passed()
    assert "[FAIL]" in result.report()


def test_transition_warning_respects_available_profile_features():
    none = VoiceProfile(avg_sentence_words=2, top_transitions=[])
    one = VoiceProfile(avg_sentence_words=2, top_transitions=["but"])
    two = VoiceProfile(avg_sentence_words=2, top_transitions=["but", "however"])
    assert "missing_transitions" not in audit("But now.", none).issues
    assert "missing_transitions" not in audit("But now.", one).issues
    assert "missing_transitions" in audit("But now.", two).issues


def test_obviously_different_synthetic_styles_are_ordered_as_expected():
    terse_train = ["I go now. But I return. I keep walking. " * 48]
    verbose_train = [(
        "However, the detailed expedition through the extensive city required "
        "considerable attention to the constantly changing conditions throughout the season. "
    ) * 30]
    terse_holdout = "I see it. But I go. I am here. " * 25
    verbose_holdout = (
        "However, the considerable investigation across the unfamiliar countryside "
        "required sustained attention to many complex and continually shifting conditions. "
    ) * 24
    terse_profile = analyze(terse_train, language="en")
    verbose_profile = analyze(verbose_train, language="en")
    assert score(terse_holdout, terse_profile) > score(terse_holdout, verbose_profile)
    assert score(verbose_holdout, verbose_profile) > score(verbose_holdout, terse_profile)
