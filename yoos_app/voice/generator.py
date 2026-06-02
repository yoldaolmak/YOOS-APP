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
    samples = "\n".join(f"« {s} »" for s in profile.sample_sentences[:3])

    system = f"""Sen bir içerik yazarısın. Aşağıdaki profil bilgileri ile belirlenen yazarın sesini, üslubunu ve anlatı tarzını kullanarak içerik üreteceksin.

YAZAR PROFİLİ:
- Dil: {profile.language}
- Ortalama cümle uzunluğu: {profile.avg_sentence_words} kelime
- Birinci şahıs oranı: %{int(profile.first_person_rate*100)}
- Soru oranı: %{int(profile.question_rate*100)}
- Kullanılan geçiş ifadeleri: {', '.join(profile.top_transitions[:5])}

ÖRNEK CÜMLELER (bu tonu yakala, kopyalama):
{samples}

İÇERİK TÜRÜ: {ctype['label']}
TON: {ctype['tone']}
UZUNLUK: {ctype['length']}

YAPI:
{structure}

KURALLAR:
- Sadece içeriği yaz, açıklama veya meta yorum ekleme
- Yazarın sesini kullan, onu taklit etme
- Gerçek olmayan bilgi uydurma"""

    user = f"Konu: {topic}\n\nYukarıdaki yazarın sesiyle ve belirlenen yapıyla bu konuda yaz."
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
