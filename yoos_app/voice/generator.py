"""
Content generator — LLM + VoiceProfile → content in author's voice.
Supports: OpenAI API, Anthropic Claude, OpenRouter, local Ollama, Codex CLI
"""
import os
import subprocess
from .analyzer import VoiceProfile
from ..content_types.registry import get as get_type


def _build_prompt(profile: VoiceProfile, content_type: str, topic: str) -> tuple[str, str]:
    ctype = get_type(content_type)
    structure = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(ctype["structure"]))
    samples = "\n".join(f"« {s} »" for s in profile.sample_sentences[:4])
    lang = profile.language

    # Build rich style fingerprint
    rhythm_desc = (
        f"Average {profile.avg_sentence_words} words per sentence "
        f"(±{getattr(profile, 'sentence_std_dev', 0)}). "
        f"{int(getattr(profile, 'short_sentence_rate', 0)*100)}% of sentences are short (<8 words), "
        f"{int(getattr(profile, 'long_sentence_rate', 0)*100)}% are long (>20 words). "
        f"Mix short punchy sentences with longer flowing ones in the same ratio."
    )

    voice_desc_parts = []
    fp = profile.first_person_rate
    if fp > 0.3:
        voice_desc_parts.append(f"Very first-person ({int(fp*100)}% of sentences use I/me/my)")
    elif fp > 0.15:
        voice_desc_parts.append(f"Moderately first-person ({int(fp*100)}%)")
    else:
        voice_desc_parts.append(f"Rarely uses first person ({int(fp*100)}%)")

    neg = getattr(profile, 'negative_rate', 0)
    if neg > 0.2:
        voice_desc_parts.append(f"favours negative constructions ('did not', 'could not') — {int(neg*100)}% rate")

    q = profile.question_rate
    if q > 0.05:
        voice_desc_parts.append(f"asks questions rhetorically ({int(q*100)}% of sentences)")

    em = getattr(profile, 'emdash_rate', 0)
    if em > 5:
        voice_desc_parts.append(f"uses em-dashes frequently ({em:.0f} per 100 sentences)")

    vocab = getattr(profile, 'vocabulary_richness', 0)
    if vocab > 0.6:
        voice_desc_parts.append("rich, varied vocabulary")
    elif vocab < 0.4:
        voice_desc_parts.append("deliberately simple, repetitive vocabulary for effect")

    voice_desc = "; ".join(voice_desc_parts) + "."

    transitions_str = ", ".join(profile.top_transitions[:7])
    sigs = ", ".join(f'"{p}"' for p in profile.signature_phrases[:5])

    system = f"""You are a professional writer. Your task is to write new content in the exact voice, rhythm, and style of the author described below. Do NOT copy their text — capture their way of thinking and writing.

AUTHOR VOICE PROFILE ({profile.author_name}):

Sentence rhythm: {rhythm_desc}

Voice character: {voice_desc}

Favourite transition words (use these naturally): {transitions_str}

Characteristic phrases to echo (not copy): {sigs if sigs else "none identified"}

SAMPLE SENTENCES — study the rhythm and tone, do not reproduce:
{samples}

CONTENT TYPE: {ctype['label']}
TONE: {ctype['tone']}
TARGET LENGTH: {ctype['length']}

STRUCTURE TO FOLLOW:
{structure}

ABSOLUTE RULES:
1. Write ONLY the content — no preamble, no "Here is the article", no meta-commentary.
2. Match the author's sentence length distribution: {int(getattr(profile,'short_sentence_rate',0)*100)}% short, {int(getattr(profile,'long_sentence_rate',0)*100)}% long.
3. Do NOT use AI writing clichés: "delve into", "it's worth noting", "in conclusion", "furthermore", "moreover", "a testament to", "in today's world", "navigate", "tapestry".
4. Do not fabricate specific facts, prices, or dates you cannot verify — write around them instead.
5. Output language: {"Turkish" if lang == "tr" else "English"}.
6. Write as the author would — their level of irony, warmth, distance, or directness."""

    user = f"Topic: {topic}\n\nWrite this in the author's exact voice and the specified structure."
    return system, user


def generate_openai(profile: VoiceProfile, content_type: str, topic: str,
                    model: str = "gpt-4o", api_key: str = None) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("OpenAI support requires: pip install openai")

    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=key)
    system, user = _build_prompt(profile, content_type, topic)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()


def generate_ollama(profile: VoiceProfile, content_type: str, topic: str,
                    model: str = "llama3") -> str:
    try:
        import requests
    except ImportError:
        raise RuntimeError("Ollama support requires: pip install requests")

    system, user = _build_prompt(profile, content_type, topic)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    resp = requests.post("http://localhost:11434/api/chat", json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def generate_codex(profile: VoiceProfile, content_type: str, topic: str) -> str:
    system, user = _build_prompt(profile, content_type, topic)
    prompt = f"SYSTEM:\n{system}\n\nUSER:\n{user}\n\nFINAL OUTPUT:"
    result = subprocess.run(
        ["codex", "exec", "--ephemeral", "--dangerously-bypass-approvals-and-sandbox",
         "--skip-git-repo-check", "--color", "never", "-"],
        input=prompt, text=True, capture_output=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Codex error: {result.stderr[:200]}")
    return result.stdout.strip()


def generate_anthropic(profile: VoiceProfile, content_type: str, topic: str,
                       model: str = "claude-sonnet-4-6", api_key: str = None) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("Anthropic support requires: pip install anthropic")

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=key)
    system, user = _build_prompt(profile, content_type, topic)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


def generate_openrouter(profile: VoiceProfile, content_type: str, topic: str,
                        model: str = "openai/gpt-4o", api_key: str = None) -> str:
    try:
        import requests
    except ImportError:
        raise RuntimeError("OpenRouter support requires: pip install requests")

    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")

    system, user = _build_prompt(profile, content_type, topic)
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.8,
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def generate(profile: VoiceProfile, content_type: str, topic: str,
             backend: str = "auto", **kwargs) -> str:
    """
    backend: "auto" | "openai" | "anthropic" | "openrouter" | "ollama" | "codex"
    "auto" tries available keys in order: anthropic → openrouter → openai → ollama
    """
    if backend == "auto":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return generate_anthropic(profile, content_type, topic, **kwargs)
        if os.environ.get("OPENROUTER_API_KEY"):
            return generate_openrouter(profile, content_type, topic, **kwargs)
        if os.environ.get("OPENAI_API_KEY"):
            return generate_openai(profile, content_type, topic, **kwargs)
        try:
            return generate_ollama(profile, content_type, topic)
        except Exception:
            raise RuntimeError(
                "No LLM backend available. Set ANTHROPIC_API_KEY, OPENROUTER_API_KEY, "
                "or OPENAI_API_KEY, or run Ollama locally."
            )
    elif backend == "openai":
        return generate_openai(profile, content_type, topic, **kwargs)
    elif backend == "anthropic":
        return generate_anthropic(profile, content_type, topic, **kwargs)
    elif backend == "openrouter":
        return generate_openrouter(profile, content_type, topic, **kwargs)
    elif backend == "ollama":
        return generate_ollama(profile, content_type, topic, **kwargs)
    elif backend == "codex":
        return generate_codex(profile, content_type, topic)
    else:
        raise ValueError(f"Unknown backend: {backend}")
