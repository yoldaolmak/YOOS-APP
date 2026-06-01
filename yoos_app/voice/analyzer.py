"""
Voice Analyzer — extracts style profile from a set of author texts.
No embeddings, no external DB. Pure text analysis.
"""
import re
import json
from collections import Counter
from dataclasses import dataclass, field, asdict


@dataclass
class VoiceProfile:
    author_name: str = "unknown"
    language: str = "auto"
    text_count: int = 0
    avg_sentence_words: float = 0.0
    first_person_rate: float = 0.0
    question_rate: float = 0.0
    avg_paragraph_sentences: float = 0.0
    top_transitions: list = field(default_factory=list)
    signature_phrases: list = field(default_factory=list)
    forbidden_patterns: list = field(default_factory=list)
    sample_sentences: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "VoiceProfile":
        with open(path, encoding="utf-8") as f:
            return cls(**json.load(f))


TR_TRANSITIONS = [
    "ama", "fakat", "ancak", "oysa", "dahası", "üstelik",
    "aslında", "yani", "kısacası", "sonuçta", "öte yandan",
    "bir yanda", "bunun yanı sıra", "nitekim", "örneğin",
]
EN_TRANSITIONS = [
    "but", "however", "yet", "still", "moreover", "furthermore",
    "actually", "in fact", "that said", "on the other hand",
    "for example", "for instance", "in short", "ultimately",
]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 3]


def _detect_language(text: str) -> str:
    tr_chars = len(re.findall(r"[çğışöüÇĞİŞÖÜ]", text))
    return "tr" if tr_chars > 5 else "en"


def analyze(texts: list[str], author_name: str = "unknown") -> VoiceProfile:
    all_text = "\n\n".join(texts)
    lang = _detect_language(all_text)
    transitions = TR_TRANSITIONS if lang == "tr" else EN_TRANSITIONS

    all_sentences = []
    paragraph_lengths = []
    for text in texts:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            sents = _sentences(para)
            all_sentences.extend(sents)
            if sents:
                paragraph_lengths.append(len(sents))

    if not all_sentences:
        return VoiceProfile(author_name=author_name)

    word_counts = [len(s.split()) for s in all_sentences]
    avg_words = sum(word_counts) / len(word_counts)

    first_person = sum(
        1 for s in all_sentences
        if re.search(r"\b(ben|benim|bana|bende|beni|I|I'm|I've|I'd|my|me|myself)\b", s, re.I)
    )
    questions = sum(1 for s in all_sentences if s.strip().endswith("?"))

    found_transitions = []
    lower_text = all_text.lower()
    for t in transitions:
        count = lower_text.count(t)
        if count > 0:
            found_transitions.append((t, count))
    found_transitions.sort(key=lambda x: -x[1])
    top_transitions = [t for t, _ in found_transitions[:8]]

    # Extract signature phrases (2-4 word recurring patterns)
    words = re.findall(r"\b\w+\b", all_text.lower())
    bigrams = Counter(zip(words, words[1:]))
    signature = [
        f"{a} {b}" for (a, b), c in bigrams.most_common(30)
        if c >= 3 and len(a) > 3 and len(b) > 3
    ][:6]

    samples = [s for s in all_sentences if 8 < len(s.split()) < 25][:5]

    return VoiceProfile(
        author_name=author_name,
        language=lang,
        text_count=len(texts),
        avg_sentence_words=round(avg_words, 1),
        first_person_rate=round(first_person / len(all_sentences), 2),
        question_rate=round(questions / len(all_sentences), 2),
        avg_paragraph_sentences=round(
            sum(paragraph_lengths) / max(len(paragraph_lengths), 1), 1
        ),
        top_transitions=top_transitions,
        signature_phrases=signature,
        sample_sentences=samples,
    )
