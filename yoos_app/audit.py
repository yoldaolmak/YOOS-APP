"""
Voice audit — scores generated content against the source voice profile.
No LLM required. Pure statistical comparison.
"""
import re
from dataclasses import dataclass
from .voice.analyzer import VoiceProfile, _sentences, _detect_language


@dataclass
class AuditResult:
    total_score: int          # 0-100
    voice_match: int          # 0-40 — sentence rhythm, first person, questions
    transition_match: int     # 0-20 — shared transition words
    style_match: int          # 0-20 — paragraph structure similarity
    no_ai_cliches: int        # 0-20 — penalty for AI generic phrases
    issues: list
    details: dict

    def passed(self) -> bool:
        return self.total_score >= 70

    def report(self) -> str:
        status = "PASS" if self.passed() else "FAIL"
        lines = [
            f"Voice Audit: {self.total_score}/100 [{status}]",
            f"  Voice match:      {self.voice_match}/40",
            f"  Transition match: {self.transition_match}/20",
            f"  Style match:      {self.style_match}/20",
            f"  No AI clichés:    {self.no_ai_cliches}/20",
        ]
        if self.issues:
            lines.append(f"  Issues: {', '.join(self.issues)}")
        return "\n".join(lines)


AI_CLICHES = [
    "delve into", "it's worth noting", "in conclusion", "to summarize",
    "furthermore", "moreover", "in today's", "fast-paced world",
    "in this article", "i will explore", "let's explore",
    "as an ai", "as a language model",
    # Turkish AI clichés (multilingual support)
    "bu makalede", "bu yazıda ele alacağız", "sonuç olarak",
    "öte yandan dikkat", "göz önünde bulundurulduğunda",
    "genel bir bakış", "kapsamlı bir şekilde",
]


def audit(content: str, profile: VoiceProfile) -> AuditResult:
    sentences = _sentences(content)
    if not sentences:
        return AuditResult(0, 0, 0, 0, 0, ["empty_content"], {})

    issues = []
    details = {}

    # 1. Voice match (0-40)
    word_counts = [len(s.split()) for s in sentences]
    avg_words = sum(word_counts) / len(word_counts)
    details["avg_sentence_words"] = round(avg_words, 1)

    # sentence length similarity (0-20)
    diff = abs(avg_words - profile.avg_sentence_words)
    length_score = max(0, 20 - int(diff * 2))

    # first person match (0-10)
    fp = sum(1 for s in sentences if re.search(
        r"\b(ben|benim|bana|bende|beni|I|I'm|I've|I'd|my|me|myself)\b", s, re.I
    )) / len(sentences)
    details["first_person_rate"] = round(fp, 2)
    fp_diff = abs(fp - profile.first_person_rate)
    fp_score = max(0, 10 - int(fp_diff * 30))

    # question match (0-10)
    qr = sum(1 for s in sentences if s.strip().endswith("?")) / len(sentences)
    details["question_rate"] = round(qr, 2)
    q_diff = abs(qr - profile.question_rate)
    q_score = max(0, 10 - int(q_diff * 40))

    voice_match = length_score + fp_score + q_score

    if length_score < 10:
        issues.append(f"sentence_length_mismatch ({avg_words:.0f}w vs {profile.avg_sentence_words:.0f}w)")
    if fp_score < 5:
        issues.append("first_person_rate_mismatch")

    # 2. Transition match (0-20)
    lower = content.lower()
    found = sum(1 for t in profile.top_transitions if t in lower)
    transition_match = min(20, int((found / max(len(profile.top_transitions), 1)) * 20 + found * 2))
    details["transitions_found"] = found

    if found < 2:
        issues.append("missing_transitions")

    # 3. Style match — paragraph structure (0-20)
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if paragraphs:
        para_lengths = [len(_sentences(p)) for p in paragraphs]
        avg_para = sum(para_lengths) / len(para_lengths)
        details["avg_para_sentences"] = round(avg_para, 1)
        para_diff = abs(avg_para - profile.avg_paragraph_sentences)
        style_match = max(0, 20 - int(para_diff * 4))
    else:
        style_match = 0
        issues.append("no_paragraphs")

    # 4. No AI clichés (0-20)
    lower_content = content.lower()
    found_cliches = [c for c in AI_CLICHES if c in lower_content]
    no_ai_score = max(0, 20 - len(found_cliches) * 5)
    details["ai_cliches_found"] = found_cliches

    if found_cliches:
        issues.append(f"ai_cliches: {', '.join(found_cliches[:3])}")

    # Minimum length check
    word_count = len(content.split())
    details["word_count"] = word_count
    if word_count < 200:
        issues.append("too_short")
        voice_match = int(voice_match * 0.5)

    total = voice_match + transition_match + style_match + no_ai_score

    return AuditResult(
        total_score=min(100, total),
        voice_match=voice_match,
        transition_match=transition_match,
        style_match=style_match,
        no_ai_cliches=no_ai_score,
        issues=issues,
        details=details,
    )
