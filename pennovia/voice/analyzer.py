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

    # Appended to preserve positional construction of older VoiceProfile instances.
    schema_version: int = 1

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def save(self, path: str, *, overwrite: bool = True) -> None:
        """Write a private JSON profile; keep the Python API overwrite default."""
        from ..storage import write_private_text

        # Serialize before opening anything so invalid data cannot destroy a file.
        write_private_text(path, self.to_json(), overwrite=overwrite)

    @classmethod
    def load(cls, path: str) -> "VoiceProfile":
        """Read and validate a stored profile, including legacy v1 files."""
        with open(path, encoding="utf-8") as source:
            return cls.from_dict(json.load(source))

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceProfile":
        """Validate an in-memory profile using the same contract as load()."""
        if not isinstance(data, dict):
            raise ValueError("Voice profile must be a JSON object")

        version = data.get("schema_version", 1)
        if type(version) is not int or version != 1:
            raise ValueError(f"Unsupported voice profile schema_version: {version!r}")

        defaults = cls()
        known = cls.__dataclass_fields__
        values = {key: value for key, value in data.items() if key in known}
        for key, value in values.items():
            expected = getattr(defaults, key)
            if isinstance(expected, list):
                valid = isinstance(value, list) and all(
                    isinstance(item, str) for item in value
                )
            elif type(expected) is int:
                valid = type(value) is int and value >= 0
            elif type(expected) is float:
                valid = (
                    type(value) in (int, float)
                    and math.isfinite(value)
                    and value >= 0
                )
            else:
                valid = isinstance(value, str)
            if not valid:
                raise ValueError(f"Invalid voice profile field: {key}")

        rates = (
            "short_sentence_rate", "long_sentence_rate",
            "first_person_rate", "question_rate", "exclamation_rate",
            "vocabulary_richness",
        )
        if any(values.get(name, 0) > 1 for name in rates):
            raise ValueError("Voice profile rate fields must be between 0 and 1")

        if values.get("language", "auto") not in ("auto", "en", "tr"):
            raise ValueError("Voice profile language must be auto, en or tr")

        return cls(**values)

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
    """Retain short emphatic sentences; discarding them biases rhythm metrics."""
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if any(char.isalpha() for char in s)]


# A deliberately small, auditable detector for the two supported languages.
# Weak or mixed evidence is unknown rather than silently classified English.
_TR_WORDS = frozenset(
    "ve bir bu ama ben benim bana sen biz siz onlar için ile gibi daha çok "
    "var yok değil ne nasıl sonra önce kadar olarak fakat ancak çünkü bugün "
    "yarın şimdi her burada orada bunu mi mı mu mü".split()
)
_EN_WORDS = frozenset(
    "the and a an is are was were with but for from on of to in i you we "
    "they it this that not have had has be as at or if then when what how "
    "could would should can will there here".split()
)


def _detect_language(text: str) -> str:
    """Return 'tr', 'en', or 'auto' when evidence is too weak or mixed."""
    normalized = text.lower().replace("i\u0307", "i")
    tokens = re.findall(r"[^\W\d_]+", normalized, re.UNICODE)
    tr_score = sum(token in _TR_WORDS for token in tokens)
    en_score = sum(token in _EN_WORDS for token in tokens)
    # Turkish-specific letters are supporting evidence, not proof: English
    # travel writing can mention İstanbul, Çeşme or other Turkish locations.
    tr_score += 2 * len(re.findall(r"[çğıöşü]", normalized))
    if tr_score >= 3 and tr_score >= 1.5 * en_score + 1:
        return "tr"
    if en_score >= 3 and en_score >= 1.5 * tr_score + 1:
        return "en"
    return "auto"


def _transition_count(text: str, transition: str) -> int:
    """Count complete transition expressions, not substrings inside other words."""
    terms = transition.split()
    if not terms:
        return 0
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(term) for term in terms) + r"(?!\w)"
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


# All voice metrics use the same language-aware first-person definition.
# These are explicit personal pronouns, not grammatical inflection detection.
_FIRST_PERSON_TR = re.compile(r"\b(?:ben|benim|bana|bende|beni)\b", re.I)
_FIRST_PERSON_EN = re.compile(r"\b(?:i|i'm|i've|i'd|my|me|myself)\b", re.I)


def _first_person_rate(sentences: list, language: str = "auto") -> float:
    if not sentences:
        return 0.0
    if language == "tr":
        patterns = (_FIRST_PERSON_TR,)
    elif language == "en":
        patterns = (_FIRST_PERSON_EN,)
    else:
        patterns = (_FIRST_PERSON_TR, _FIRST_PERSON_EN)
    return sum(any(p.search(sentence) for p in patterns) for sentence in sentences) / len(sentences)


def _has_negative_marker(sentence: str, language: str) -> bool:
    """Conservative explicit negative constructions, counted once per sentence."""
    if language in ("tr", "auto") and any(
        _transition_count(sentence, term) for term in TR_NEGATIVES
    ):
        return True
    if language in ("en", "auto") and any(
        re.search(pattern, sentence, flags=re.IGNORECASE)
        for pattern in EN_NEGATIVES
    ):
        return True
    return False


def _std_dev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return round(math.sqrt(variance), 1)


def _vocabulary_richness(text: str) -> float:
    """Mean 500-token type-token ratio, including the corpus tail."""
    # Unicode letters only; normalize Turkish capital dotted-I after lower().
    normalized = text.lower().replace("i\u0307", "i")
    words = re.findall(r"\b[^\W\d_]{3,}\b", normalized, re.UNICODE)
    if not words:
        return 0.0
    window = 500
    if len(words) <= window:
        return round(len(set(words)) / len(words), 3)

    starts = list(range(0, len(words) - window + 1, window // 2))
    final_start = len(words) - window
    if starts[-1] != final_start:
        starts.append(final_start)
    ratios = [len(set(words[i:i + window])) / window for i in starts]
    return round(sum(ratios) / len(ratios), 3)


def _sample_sentences(documents: list[list[str]]) -> list[str]:
    """Select short, medium and long examples across source texts."""
    lengths = ((5, 12, 2), (13, 22, 2), (23, None, 1))
    picked_per_document = [0] * len(documents)
    samples = []
    for minimum, maximum, limit in lengths:
        candidates = [
            [s for s in sentences
             if minimum <= len(s.split()) and
             (maximum is None or len(s.split()) <= maximum)]
            for sentences in documents
        ]
        for _ in range(limit):
            available = [i for i, choices in enumerate(candidates) if choices]
            if not available:
                break
            document = min(available, key=lambda i: (picked_per_document[i], i))
            samples.append(candidates[document].pop(0))
            picked_per_document[document] += 1
    return samples


def analyze(
    texts, author_name: str = "unknown", language: str = "auto"
) -> VoiceProfile:
    """Extract a profile; explicit language overrides weak auto-detection."""
    if language not in ("auto", "en", "tr"):
        raise ValueError("language must be auto, en or tr")
    all_text = "\n\n".join(texts)
    lang = _detect_language(all_text) if language == "auto" else language
    transitions = (
        TR_TRANSITIONS if lang == "tr"
        else EN_TRANSITIONS if lang == "en"
        else TR_TRANSITIONS + EN_TRANSITIONS
    )

    all_sentences = []
    document_sentences = []
    paragraph_word_counts = []
    paragraph_sent_counts = []

    for text in texts:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        document = []
        for para in paragraphs:
            sents = _sentences(para)
            all_sentences.extend(sents)
            document.extend(sents)
            if sents:
                paragraph_sent_counts.append(len(sents))
                paragraph_word_counts.append(len(para.split()))
        document_sentences.append(document)

    if not all_sentences:
        return VoiceProfile(author_name=author_name, language=lang)

    # --- Sentence metrics ---
    wc = [len(s.split()) for s in all_sentences]
    avg_words = sum(wc) / len(wc)
    std_dev = _std_dev(wc)
    short_rate = sum(1 for w in wc if w < 8) / len(wc)
    long_rate = sum(1 for w in wc if w > 20) / len(wc)

    # --- Voice markers ---
    first_person_rate = _first_person_rate(all_sentences, lang)
    questions = sum(1 for s in all_sentences if s.strip().endswith("?"))
    exclamations = sum(1 for s in all_sentences if s.strip().endswith("!"))

    neg_rate = sum(
        _has_negative_marker(sentence, lang) for sentence in all_sentences
    ) / len(all_sentences)

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
    transition_counts = [(t, _transition_count(all_text, t)) for t in transitions]
    found_transitions = sorted(
        ((t, count) for t, count in transition_counts if count > 0),
        key=lambda x: -x[1],
    )
    top_transitions = [t for t, _ in found_transitions[:10]]

    # --- Signature 2-grams ---
    # Do not invent phrase pairs across the boundaries of separate texts.
    bigrams = Counter()
    for text in texts:
        words = re.findall(r"\b\w+\b", text.lower())
        bigrams.update(zip(words, words[1:]))
    signature = [
        f"{a} {b}" for (a, b), c in bigrams.most_common(50)
        if c >= 3 and len(a) > 3 and len(b) > 3
        and a not in ("that", "this", "with", "from", "they", "have", "were", "been")
        and b not in ("that", "this", "with", "from", "they", "have", "were", "been")
    ][:8]

    # --- Sample sentences: preserve rhythm variety across source texts ---
    samples = _sample_sentences(document_sentences)

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
        first_person_rate=round(first_person_rate, 2),
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
