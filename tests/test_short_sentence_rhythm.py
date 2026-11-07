"""One- and two-word sentences must contribute to author rhythm metrics."""
from pennovia.audit import audit
from pennovia.voice.analyzer import _sentences, analyze


def test_retains_short_standalone_sentences():
    text = "Go. Stop! Really? This is a much longer sentence."
    assert _sentences(text) == [
        "Go.", "Stop!", "Really?", "This is a much longer sentence."
    ]


def test_ignores_punctuation_only_fragments():
    assert _sentences("... ! ?") == []


def test_short_paragraphs_count_in_author_profile():
    profile = analyze(["Go.\n\nStop!\n\nThis is a much longer sentence with several words."])
    assert profile.text_count == 1
    assert profile.avg_sentence_words > 0
    assert profile.short_sentence_rate == 0.67
    assert profile.avg_paragraph_sentences == 1.0
    assert profile.avg_paragraph_words < 5


def test_all_short_sentences_are_not_treated_as_empty_corpus():
    profile = analyze(["Go now.\n\nTurn left.\n\nCome back."])
    assert profile.text_count == 1
    assert profile.total_words == 6
    assert profile.avg_sentence_words == 2.0
    assert profile.short_sentence_rate == 1.0


def test_audit_question_rate_sees_one_word_questions():
    profile = analyze(["Why?\n\nNo.\n\nThis is a sentence of several words."])
    result = audit("Why? No. This is a sentence of several words.", profile)
    assert result.details["question_rate"] > 0
