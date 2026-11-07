"""
Voice Analyzer — extracts a rich style profile from a set of author texts.
No embeddings, no external DB. Pure statistical text analysis.

Extracted dimensions:
  - Sentence length distribution (avg, std dev, short/long ratio)
  - First-person rate, question rate, exclamation rate
  - Paragraph rhythm (avg sentences per paragraph)
  - Transition word fingerprint
  - Vocabulary richness (type-token ratio)
  - Punctuation style (em-dash, semicolon, parenthesis usage)
  - Negative construction rate ("did not", "could not"…)
  - Signature 2-gram phrases
  - Sample sentences for prompt reference
"""
import re
import json
import math
from collections import Counter
from dataclasses import dataclass, field, asdict


@dataclass
class VoiceProfile:
    # Identity
    author_name: str = "unknown"
    language: str = "auto"
    text_count: int = 0
    total_words: int = 0

    # Sentence rhythm
    avg_sentence_words: float = 0.0
    sentence_std_dev: float = 0.0
    short_sentence_rate: float = 0.0   # < 8 words
    long_sentence_rate: float = 0.0    # > 20 words

    # Voice markers
    first_person_rate: float = 0.0
    question_rate: float = 0.0
    exclamation_rate: float = 0.0
    negative_rate: float = 0.0         # "did not", "could not", "was not"…

    # Paragraph style
    avg_paragraph_sentences: float = 0.0
    avg_paragraph_words: float = 0.0

    # Vocabulary
    vocabulary_richness: float = 0.0   # type-token ratio (0–1)
    avg_word_length: float = 0.0

    # Punctuation fingerprint
    emdash_rate: float = 0.0           # per 100 sentences
    semicolon_rate: float = 0.0
    parenthesis_rate: float = 0.0

    # Fingerprints
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
            data = json.load(f)
        # Forward-compat: ignore unknown fields from older profile versions
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})

    def summary(self) -> str:
        lines = [
            f"Author: {self.author_name} ({self.language}, {self.text_count} texts, {self.total_words} words)",
            f"Sentences: avg {self.avg_sentence_words}w ± {self.sentence_std_dev}w | short {self.short_sentence_rate:.0%} / long {self.long_sentence_rate:.0%}",
            f"Voice: 1st-person {self.first_person_rate:.0%} | questions {self.question_rate:.0%} | negatives {self.negative_rate:.0%}",
            f"Vocabulary richness: {self.vocabulary_richness:.2f} | avg word length: {self.avg_word_length:.1f}",
            f"Punctuation: em-dash {self.emdash_rate:.1f}/100s | semicolon {self.semicolon_rate:.1f}/100s",
            f"Top transitions: {', '.join(self.top_transitions[:6])}",
        ]
        return "\n".join(lines)


TR_TRANSITIONS = [
    "ama", "fakat", "ancak", "oysa", "dahası", "üstelik", "aslında",
    "yani", "kısacası", "sonuçta", "öte yandan", "bir yanda",
    "bunun yanı sıra", "nitekim", "örneğin", "bununla birlikte",
    "ne var ki", "buna karşın", "şu ki",
]
EN_TRANSITIONS = [
    "but", "however", "yet", "still", "moreover", "furthermore",
    "actually", "in fact", "that said", "on the other hand",
    "for example", "for instance", "in short", "ultimately",
    "and yet", "even so", "then again", "all the same",
]

TR_NEGATIVES = ["değil", "yok", "olmadı", "etmedi", "gelmedi", "istemedi"]
EN_NEGATIVES = [
    r"\b(did not|didn't|could not|couldn't|would not|wouldn't|"
    r"was not|wasn't|were not|weren't|have not|haven't|had not|hadn't|"
    r"do not|don't|does not|doesn't)\b"
]


def _sentences(text: str) -> list:
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if len(s.split()) > 2]


def _detect_language(text: str) -> str:
    tr_chars = len(re.findall(r"[çğışöüÇĞİŞÖÜ]", text))
    return "tr" if tr_chars > 5 else "en"


def _std_dev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return round(math.sqrt(variance), 1)


def _vocabulary_richness(text: str) -> float:
    words = re.findall(r"\b[a-zA-ZçğışöüÇĞİŞÖÜ]{3,}\b", text.lower())
    if not words:
        return 0.0
    # Measure over sliding windows of 500 words for stability
    window = 500
    ratios = []
    for i in range(0, len(words) - window, window // 2):
        chunk = words[i:i + window]
        ratios.append(len(set(chunk)) / len(chunk))
    return round(sum(ratios) / len(ratios), 3) if ratios else round(len(set(words)) / len(words), 3)


def analyze(texts, author_name: str = "unknown") -> VoiceProfile:
    all_text = "\n\n".join(texts)
    lang = _detect_language(all_text)
    transitions = TR_TRANSITIONS if lang == "tr" else EN_TRANSITIONS
    neg_patterns = TR_NEGATIVES if lang == "tr" else EN_NEGATIVES

    all_sentences = []
    paragraph_word_counts = []
    paragraph_sent_counts = []

    for text in texts:
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.split()) > 3]
        for para in paragraphs:
            sents = _sentences(para)
            all_sentences.extend(sents)
            if sents:
                paragraph_sent_counts.append(len(sents))
                paragraph_word_counts.append(len(para.split()))

    if not all_sentences:
        return VoiceProfile(author_name=author_name, language=lang)

    # --- Sentence metrics ---
    wc = [len(s.split()) for s in all_sentences]
    avg_words = sum(wc) / len(wc)
    std_dev = _std_dev(wc)
    short_rate = sum(1 for w in wc if w < 8) / len(wc)
    long_rate = sum(1 for w in wc if w > 20) / len(wc)

    # --- Voice markers ---
    fp_pat = re.compile(r"\b(ben|benim|bana|bende|beni|I|I'm|I've|I'd|my|me|myself)\b", re.I)
    first_person = sum(1 for s in all_sentences if fp_pat.search(s))
    questions = sum(1 for s in all_sentences if s.strip().endswith("?"))
    exclamations = sum(1 for s in all_sentences if s.strip().endswith("!"))

    neg_count = 0
    for pat in neg_patterns:
        neg_count += len(re.findall(pat, all_text, re.I))
    neg_rate = neg_count / max(len(all_sentences), 1)

    # --- Paragraph metrics ---
    avg_para_sents = sum(paragraph_sent_counts) / max(len(paragraph_sent_counts), 1)
    avg_para_words = sum(paragraph_word_counts) / max(len(paragraph_word_counts), 1)

    # --- Vocabulary ---
    richness = _vocabulary_richness(all_text)
    all_words = re.findall(r"\b\w+\b", all_text)
    avg_word_len = sum(len(w) for w in all_words) / max(len(all_words), 1)

    # --- Punctuation fingerprint ---
    n = max(len(all_sentences), 1)
    emdash = len(re.findall(r"—", all_text))
    semicolons = len(re.findall(r";", all_text))
    parens = len(re.findall(r"\(", all_text))

    # --- Transitions ---
    lower_text = all_text.lower()
    found_transitions = sorted(
        [(t, lower_text.count(t)) for t in transitions if lower_text.count(t) > 0],
        key=lambda x: -x[1]
    )
    top_transitions = [t for t, _ in found_transitions[:10]]

    # --- Signature 2-grams ---
    words = re.findall(r"\b\w+\b", lower_text)
    bigrams = Counter(zip(words, words[1:]))
    signature = [
        f"{a} {b}" for (a, b), c in bigrams.most_common(50)
        if c >= 3 and len(a) > 3 and len(b) > 3
        and a not in ("that", "this", "with", "from", "they", "have", "were", "been")
        and b not in ("that", "this", "with", "from", "they", "have", "were", "been")
    ][:8]

    # --- Sample sentences (representative variety) ---
    short_samples = [s for s in all_sentences if 5 <= len(s.split()) <= 12][:2]
    medium_samples = [s for s in all_sentences if 12 < len(s.split()) <= 22][:2]
    long_samples = [s for s in all_sentences if len(s.split()) > 22][:1]
    samples = (short_samples + medium_samples + long_samples)[:5]

    total_words = len(all_words)

    return VoiceProfile(
        author_name=author_name,
        language=lang,
        text_count=len(texts),
        total_words=total_words,
        avg_sentence_words=round(avg_words, 1),
        sentence_std_dev=std_dev,
        short_sentence_rate=round(short_rate, 2),
        long_sentence_rate=round(long_rate, 2),
        first_person_rate=round(first_person / n, 2),
        question_rate=round(questions / n, 2),
        exclamation_rate=round(exclamations / n, 2),
        negative_rate=round(neg_rate, 2),
        avg_paragraph_sentences=round(avg_para_sents, 1),
        avg_paragraph_words=round(avg_para_words, 1),
        vocabulary_richness=richness,
        avg_word_length=round(avg_word_len, 1),
        emdash_rate=round(emdash / n * 100, 1),
        semicolon_rate=round(semicolons / n * 100, 1),
        parenthesis_rate=round(parens / n * 100, 1),
        top_transitions=top_transitions,
        signature_phrases=signature,
        sample_sentences=samples,
    )
