"""Language detection must not mistake Turkish place names for author language."""
import pytest

from pennovia.voice.analyzer import _detect_language, analyze
from pennovia.voice.generator import _build_prompt


def test_ascii_only_turkish_corpus():
    text = ("Ben bugün burada uzun zaman kaldım. Ama sonra yine eve gittim. "
            "Siz bu konuda ne diyorsunuz? Biz daha sonra yine geliriz. ") * 3
    assert _detect_language(text) == "tr"


def test_english_with_turkish_location_names():
    text = ("I went to İstanbul and visited Çeşme with my friends. "
            "The weather was warm and the journey was good. "
            "We were there for a week and then we came home. ") * 3
    assert _detect_language(text) == "en"


def test_ambiguous_and_empty_corpus_abstains():
    assert _detect_language("") == "auto"
    assert _detect_language("Cappadocia, Istanbul, Ankara.") == "auto"


def test_explicit_language_override_is_preserved():
    profile = analyze(["The coast is in view."] * 5, language="tr")
    assert profile.language == "tr"


def test_invalid_explicit_language_rejected():
    with pytest.raises(ValueError, match="language"):
        analyze(["Words"], language="de")


def test_unknown_profile_language_does_not_default_to_english():
    profile = analyze(["Cappadocia, Istanbul, Ankara."])
    assert profile.language == "auto"
    prompt, _ = _build_prompt(profile, "story", "A topic")
    assert "do not assume English" in prompt
