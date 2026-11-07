"""The prompt should protect author-specific style and avoid invented experience."""
from pennovia.audit import AI_CLICHES, audit
from pennovia.voice.analyzer import VoiceProfile
from pennovia.voice.generator import _build_prompt


def test_turkish_voice_examples_are_turkish():
    profile = VoiceProfile(
        language="tr", avg_sentence_words=10,
        first_person_rate=0.5, negative_rate=0.3,
    )
    system, _ = _build_prompt(profile, "travel_blog", "İzmir")
    assert "ben/benim/bana" in system
    assert "değil, yok, olmadı" in system
    assert "use I/me/my" not in system
    assert "did not, could not" not in system


def test_english_voice_examples_remain_english():
    profile = VoiceProfile(
        language="en", avg_sentence_words=10,
        first_person_rate=0.5, negative_rate=0.3,
    )
    system, _ = _build_prompt(profile, "story", "Coast")
    assert "I/me/my" in system
    assert "did not, could not" in system


def test_generator_prohibits_invented_firsthand_experience():
    system, _ = _build_prompt(VoiceProfile(language="en"), "travel_guide", "Prague")
    assert "Never invent firsthand visits" in system
    assert "A voice profile is evidence of writing style" in system
    assert "quotations" in system


def test_real_author_transitions_are_not_banned_as_cliches():
    profile = VoiceProfile(
        language="en", top_transitions=["furthermore", "moreover"]
    )
    system, _ = _build_prompt(profile, "column", "A topic")
    assert "Favourite transition words (use these naturally): furthermore, moreover" in system
    rule = system.split("3. Avoid generic AI writing clichés", 1)[1].split("\n4.", 1)[0]
    assert "furthermore" not in rule.lower()
    assert "moreover" not in rule.lower()
    assert "furthermore" not in AI_CLICHES
    assert "moreover" not in AI_CLICHES


def test_common_author_transition_is_not_penalized_by_audit():
    result = audit(
        "Furthermore, this is a normal sentence used in a natural context.",
        VoiceProfile(avg_sentence_words=10),
    )
    assert result.no_ai_cliches == 20
