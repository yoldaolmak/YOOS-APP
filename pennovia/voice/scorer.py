"""
Voice similarity scorer — compares content style to profile using
sentence-level statistical fingerprint. No embeddings needed.
"""
import re
import math
from .analyzer import VoiceProfile, _sentences


def score(content: str, profile: VoiceProfile) -> float:
    """Returns 0.0-1.0 similarity to the voice profile."""
    sentences = _sentences(content)
    if not sentences or profile.avg_sentence_words == 0:
        return 0.0

    # Sentence length distribution similarity
    word_counts = [len(s.split()) for s in sentences]
    avg = sum(word_counts) / len(word_counts)
    length_sim = 1.0 - min(1.0, abs(avg - profile.avg_sentence_words) / profile.avg_sentence_words)

    # First person similarity
    fp = sum(1 for s in sentences if re.search(
        r"\b(ben|benim|bana|I|my|me)\b", s, re.I
    )) / len(sentences)
    fp_sim = 1.0 - min(1.0, abs(fp - profile.first_person_rate) / max(profile.first_person_rate, 0.01))

    # Transition coverage
    lower = content.lower()
    if profile.top_transitions:
        trans_found = sum(1 for t in profile.top_transitions if t in lower)
        trans_sim = trans_found / len(profile.top_transitions)
    else:
        trans_sim = 0.5

    # Weighted combination
    score_val = (length_sim * 0.4) + (fp_sim * 0.35) + (trans_sim * 0.25)
    return round(score_val, 3)
