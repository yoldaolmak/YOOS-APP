"""
multi_ai.py — Claude + GPT API wrapper v2.0

Yenilikler:
  - Anthropic prompt cache: cache_control ephemeral → sistem promptu %90 ucuz
  - Gerçek token takibi: _session_tokens input/output/cache_read/cache_write
  - GPT fallback: OPENAI_API_KEY yoksa veya 4xx alırsa Claude'a geç

Retry stratejisi:
  529 (overloaded): 30s→60s→120s→180s→240s (6 deneme)
  429 (rate limit) : Retry-After header, yoksa 60s
  5xx (server err) : 10s→20s→40s
  4xx diğer        : raise (retry yok)

Prompt cache nasıl çalışır:
  - system parametresine list[dict] geçilince cache aktif
  - cache_control: {"type": "ephemeral"} ile işaretlenen blok önbelleğe alınır
  - Cache TTL: ~5 dakika
  - Maliyet: write=1.25×, read=0.10× (normal input token)
  - Örnek: 420 token sistem prompt, 50 çağrı/gün
      Cachesiz: 50 × 420 = 21.000 token
      Cache: 1×525 + 49×42 = 2.583 token  (%88 tasarruf)
"""

import os
import json
import time
import ssl
import urllib.request
import urllib.error
import random
import datetime

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ─── Cache kontrolü ───────────────────────────────────────────────────────────
# False → test aşaması (eski cache temizlenir, prompt değişiklikleri anında geçer)
# True  → production (sistem promptu cache'lenir, maliyet %88 azalır)
CACHE_ENABLED: bool = False

_529_WAITS = [30, 60, 120, 180, 240]
_429_WAIT  = 60
_5XX_WAITS = [10, 20, 40]


# ─── Token takibi ──────────────────────────────────────────────────────────────

_session_tokens = {
    "input":       0,
    "output":      0,
    "cache_read":  0,   # 0.10× maliyetli
    "cache_write": 0,   # 1.25× maliyetli
    "calls":       0,
    "session_start": None,
}

_haiku_tokens = {"input": 0, "output": 0, "calls": 0}

def reset_session_cost():
    _session_tokens.update({
        "input": 0, "output": 0,
        "cache_read": 0, "cache_write": 0,
        "calls": 0,
        "session_start": datetime.datetime.now().isoformat()
    })
    _haiku_tokens.update({"input": 0, "output": 0, "calls": 0})

def _track(usage: dict):
    """API yanıtından token kullanımını kaydet."""
    if not usage:
        return
    _session_tokens["input"]       += usage.get("input_tokens", 0)
    _session_tokens["output"]      += usage.get("output_tokens", 0)
    _session_tokens["cache_read"]  += usage.get("cache_read_input_tokens", 0)
    _session_tokens["cache_write"] += usage.get("cache_creation_input_tokens", 0)
    _session_tokens["calls"]       += 1

def get_session_cost() -> dict:
    """Maliyet hesabı — Sonnet + Haiku ayrı oranlar."""
    # Sonnet: $3/Mtok input, $15/Mtok output
    s_inp = _session_tokens["input"]       * 3.0    / 1_000_000
    s_out = _session_tokens["output"]      * 15.0   / 1_000_000
    s_cr  = _session_tokens["cache_read"]  * 0.30   / 1_000_000
    s_cw  = _session_tokens["cache_write"] * 3.75   / 1_000_000
    # Haiku: $0.80/Mtok input, $4/Mtok output
    h_inp = _haiku_tokens["input"]  * 0.80 / 1_000_000
    h_out = _haiku_tokens["output"] * 4.0  / 1_000_000
    return {
        **_session_tokens,
        "haiku_input":  _haiku_tokens["input"],
        "haiku_output": _haiku_tokens["output"],
        "haiku_calls":  _haiku_tokens["calls"],
        "estimated_usd": round(s_inp + s_out + s_cr + s_cw + h_inp + h_out, 4),
    }

def print_session_cost():
    c = get_session_cost()
    print(f"\n💰 Token Özeti ({c['calls']} Sonnet + {c['haiku_calls']} Haiku çağrı):")
    print(f"   Sonnet  Input: {c['input']:,}  Output: {c['output']:,}  CacheR: {c['cache_read']:,}")
    print(f"   Haiku   Input: {c['haiku_input']:,}  Output: {c['haiku_output']:,}")
    print(f"   Tahmini: ~${c['estimated_usd']:.4f}")


# ─── Retry yardımcıları ───────────────────────────────────────────────────────

def _jitter(s): return s * (0.8 + random.random() * 0.4)

def _wait_for_retry(code, attempt, headers=None):
    if code == 529:
        wait = _jitter(_529_WAITS[min(attempt, len(_529_WAITS)-1)])
        print(f"   ⏳ 529 Overloaded — {wait:.0f}s (deneme {attempt+1}/{len(_529_WAITS)+1})...")
    elif code == 429:
        wait = _429_WAIT
        if headers:
            ra = headers.get("Retry-After") or headers.get("retry-after")
            try: wait = float(ra) + 5
            except: pass
        wait = _jitter(wait)
        print(f"   ⏳ 429 Rate limit — {wait:.0f}s bekleniyor...")
    elif code >= 500:
        wait = _jitter(_5XX_WAITS[min(attempt, len(_5XX_WAITS)-1)])
        print(f"   ⏳ {code} Server error — {wait:.0f}s bekleniyor...")
    else:
        return
    time.sleep(wait)

def _retryable(code, attempt, max_retries):
    return attempt < max_retries - 1 and code in (429, 500, 502, 503, 529)


# ─── Prompt cache yardımcısı ──────────────────────────────────────────────────

def _make_cached_system(system_text: str):
    """
    Claude API için cache_control'lü sistem mesajı bloğu.
    String yerine list[dict] döner — cache aktif olur.
    Aynı metin → cache hit → 0.10× fiyat.
    """
    if not system_text:
        return []
    return [{"type": "text", "text": system_text,
             "cache_control": {"type": "ephemeral"}}]


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE
# ═══════════════════════════════════════════════════════════════════════════════

def ask_claude(prompt: str, system: str = "", max_tokens: int = 4000,
               retries: int = 6, use_cache: bool = True) -> str:
    """
    Claude Sonnet API.
    use_cache=True AND CACHE_ENABLED=True → prompt cache aktif (%88 tasarruf).
    CACHE_ENABLED=False → cache kapalı (test modu, prompt değişiklikleri anında geçer).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY bulunamadı")

    _use = use_cache and CACHE_ENABLED   # ← global flag kontrolü

    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    if _use:
        headers["anthropic-beta"] = "prompt-caching-2024-07-31"

    body = {
        "model":      "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages":   [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = (_make_cached_system(system) if _use else system)

    data = json.dumps(body).encode("utf-8")
    last_err = None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                _track(result.get("usage", {}))
                if attempt > 0:
                    print(f"   ✅ Claude yanıt verdi (deneme {attempt+1})")
                return result["content"][0]["text"]

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            code     = e.code
            resp_h   = dict(e.headers) if e.headers else {}
            last_err = f"HTTP {code}: {err_body[:200]}"
            if _retryable(code, attempt, retries):
                print(f"   ⚠️  Claude {code} (deneme {attempt+1}/{retries}): {err_body[:80]}")
                _wait_for_retry(code, attempt, resp_h)
            else:
                raise RuntimeError(f"Claude API hatası: {last_err}")

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = str(e)
            if attempt < retries - 1:
                wait = _jitter(10 * (attempt + 1))
                print(f"   ⚠️  Claude bağlantı hatası (deneme {attempt+1}): {e} — {wait:.0f}s")
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(f"Claude API {retries} denemede başarısız: {last_err}")


def ask_claude_haiku(prompt: str, system: str = "", max_tokens: int = 2000,
                     retries: int = 6) -> str:
    """
    Claude Haiku API — polish için optimize edilmiş ucuz model.
    claude-haiku-4-5-20251001: $0.80/Mtok input, $4/Mtok output
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY bulunamadı")

    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    body = {
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": max_tokens,
        "messages":   [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    data = json.dumps(body).encode("utf-8")
    last_err = None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                usage = result.get("usage", {})
                _haiku_tokens["input"]  += usage.get("input_tokens", 0)
                _haiku_tokens["output"] += usage.get("output_tokens", 0)
                _haiku_tokens["calls"]  += 1
                if attempt > 0:
                    print(f"   ✅ Haiku yanıt verdi (deneme {attempt+1})")
                return result["content"][0]["text"]

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            code     = e.code
            resp_h   = dict(e.headers) if e.headers else {}
            last_err = f"HTTP {code}: {err_body[:200]}"
            if _retryable(code, attempt, retries):
                print(f"   ⚠️  Haiku {code} (deneme {attempt+1}/{retries}): {err_body[:80]}")
                _wait_for_retry(code, attempt, resp_h)
            else:
                raise RuntimeError(f"Haiku API hatası: {last_err}")

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = str(e)
            if attempt < retries - 1:
                wait = _jitter(10 * (attempt + 1))
                print(f"   ⚠️  Haiku bağlantı hatası (deneme {attempt+1}): {e} — {wait:.0f}s")
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(f"Haiku API {retries} denemede başarısız: {last_err}")


# ═══════════════════════════════════════════════════════════════════════════════
# OPENAI ÇOKLU KEY ROTASYONU
# .env: OPENAI_KEY_1, OPENAI_KEY_2, OPENAI_KEY_3, OPENAI_KEY_4
# Fallback: OPENAI_API_KEY (tek key, geriye dönük uyumluluk)
# Strateji: round-robin + 429 alınan key geçici cooldown'a alınır
# ═══════════════════════════════════════════════════════════════════════════════

def _load_openai_keys() -> list:
    """Tüm OPENAI_KEY_N ve OPENAI_API_KEY'leri yükle, boşları filtrele."""
    keys = []
    for i in range(1, 8):
        k = os.environ.get(f"OPENAI_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    fallback = os.environ.get("OPENAI_API_KEY", "").strip()
    if fallback and fallback not in keys:
        keys.append(fallback)
    return keys

_OPENAI_KEYS: list = _load_openai_keys()
_KEY_COOLDOWN: dict = {}  # {key_index: unix_timestamp_until}
_key_cursor: int = 0


def _next_key() -> tuple:
    """Round-robin: cooldown'da olmayan sıradaki key. (key_str, key_idx)"""
    global _key_cursor
    now = time.time()
    n   = len(_OPENAI_KEYS)
    if not n:
        return "", -1
    for _ in range(n):
        idx = _key_cursor % n
        _key_cursor += 1
        until = _KEY_COOLDOWN.get(idx, 0)
        if now < until:
            remaining = int(until - now)
            print(f"   ⏳ Key-{idx+1} cooldown ({remaining}s kaldı), atlıyorum...")
            continue
        return _OPENAI_KEYS[idx], idx
    # Hepsi cooldown'da → en erken açılacak key'i bekle
    earliest = min(_KEY_COOLDOWN, key=lambda k: _KEY_COOLDOWN[k])
    wait = max(1, int(_KEY_COOLDOWN[earliest] - now) + 1)
    print(f"   ⏳ Tüm keyler cooldown'da → {wait}s bekleniyor...")
    time.sleep(wait)
    idx = earliest % n
    return _OPENAI_KEYS[idx], idx


def _set_key_cooldown(idx: int, resp_h: dict, default_sec: int = 60) -> None:
    retry_after = int(resp_h.get("Retry-After", resp_h.get("retry-after", default_sec)))
    retry_after = max(retry_after, 30)
    _KEY_COOLDOWN[idx] = time.time() + retry_after
    print(f"   🔒 Key-{idx+1} → {retry_after}s cooldown")


def _ask_gpt_model(model: str, prompt: str, system: str = "",
                   max_tokens: int = 4000, retries: int = 4,
                   no_fallback: bool = False,
                   temperature: float = 0.85) -> str:
    """
    Çoklu key rotasyonlu OpenAI çağrısı.
    - round-robin key seçimi
    - 429 → o key cooldown'a, sonraki key denenir
    - 401/403 → key 1 saat devre dışı
    - no_fallback=True → tüm keyler çöktüğünde RuntimeError (sistem durur)
    - no_fallback=False → Claude'a geç (geriye dönük uyumluluk)
    """
    if not _OPENAI_KEYS:
        if no_fallback:
            raise RuntimeError(
                "❌ Hiç OPENAI_KEY_N veya OPENAI_API_KEY bulunamadı\n"
                "   .env dosyasına OPENAI_KEY_1 ... OPENAI_KEY_4 ekle"
            )
        return ask_claude(prompt, system=system, max_tokens=max_tokens)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body_base = {"model": model, "messages": messages, "max_tokens": max_tokens,
                 "temperature": temperature}
    short     = model.replace("gpt-", "").replace("-preview", "")
    last_err  = None
    # toplam deneme = retries + key sayısı (her key için en az 1 şans)
    max_attempts = retries + len(_OPENAI_KEYS)

    for attempt in range(max_attempts):
        key, kidx = _next_key()
        if not key:
            break
        label = f"Key-{kidx+1}/{len(_OPENAI_KEYS)}"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        data    = json.dumps(body_base).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                usage  = result.get("usage", {})
                _session_tokens["input"]  += usage.get("prompt_tokens", 0)
                _session_tokens["output"] += usage.get("completion_tokens", 0)
                _session_tokens["calls"]  += 1
                if attempt > 0:
                    print(f"   ✅ GPT({short}) [{label}] yanıt (deneme {attempt+1})")
                return result["choices"][0]["message"]["content"]

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            code     = e.code
            resp_h   = dict(e.headers) if e.headers else {}
            last_err = f"HTTP {code}: {err_body[:200]}"

            if code == 429:
                _set_key_cooldown(kidx, resp_h)
                print(f"   🔄 [{label}] 429 → sonraki key...")
                continue                              # aynı retry sayacı, farklı key

            if code in (401, 403):
                print(f"   ❌ [{label}] {code} geçersiz key — 1 saat devre dışı")
                _KEY_COOLDOWN[kidx] = time.time() + 3600
                continue

            if _retryable(code, attempt, retries):
                print(f"   ⚠️  GPT({short}) [{label}] {code} (deneme {attempt+1})")
                _wait_for_retry(code, attempt, resp_h)
            else:
                if no_fallback:
                    raise RuntimeError(
                        f"❌ GPT({short}) [{label}] başarısız ({code})\n{err_body[:300]}"
                    )
                print(f"   ℹ️  GPT({short}) {code} → Claude'a geçiliyor...")
                return ask_claude(prompt, system=system, max_tokens=max_tokens)

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = str(e)
            if attempt < max_attempts - 1:
                wait = _jitter(8 * (attempt + 1))
                print(f"   ⚠️  GPT({short}) [{label}] bağlantı hatası: {e} — {wait:.0f}s")
                time.sleep(wait)
            else:
                if no_fallback:
                    raise RuntimeError(
                        f"❌ GPT({short}) bağlantı başarısız ({len(_OPENAI_KEYS)} key)\n{last_err}"
                    )
                print(f"   ℹ️  GPT({short}) → Claude'a geçiliyor...")
                return ask_claude(prompt, system=system, max_tokens=max_tokens)

    if no_fallback:
        raise RuntimeError(
            f"❌ GPT({short}) tüm keyler başarısız "
            f"({len(_OPENAI_KEYS)} key, {max_attempts} deneme)\nSon hata: {last_err}"
        )
    print(f"   ℹ️  GPT({short}) tüm keyler başarısız → Claude'a geçiliyor...")
    return ask_claude(prompt, system=system, max_tokens=max_tokens)


def ask_gpt(prompt: str, system: str = "", max_tokens: int = 4000,
            retries: int = 4, temperature: float = 0.85) -> str:
    """GPT-4o — kalite kritik bölümler. (Claude fallback AÇIK)"""
    return _ask_gpt_model("gpt-4o", prompt, system=system,
                          max_tokens=max_tokens, retries=retries,
                          no_fallback=False, temperature=temperature)


def ask_gpt_strict(prompt: str, system: str = "", max_tokens: int = 4000,
                   retries: int = 4, temperature: float = 0.85) -> str:
    """
    GPT-4o — fallback YOK. WHERE/GUIDE engine bölüm üretimi için.
    temperature: anlatı bölümleri 0.85, bilgi bölümleri 0.70
    """
    return _ask_gpt_model("gpt-4o", prompt, system=system,
                          max_tokens=max_tokens, retries=retries,
                          no_fallback=True, temperature=temperature)


def ask_gpt_mini(prompt: str, system: str = "", max_tokens: int = 4000,
                 retries: int = 4, temperature: float = 0.70) -> str:
    """GPT-4o-mini — yapısal görevler, spot-fix. Default 0.70."""
    return _ask_gpt_model("gpt-4o-mini", prompt, system=system,
                          max_tokens=max_tokens, retries=retries,
                          no_fallback=False, temperature=temperature)


def ask_gpt_mini_strict(prompt: str, system: str = "", max_tokens: int = 4000,
                        retries: int = 4, temperature: float = 0.70) -> str:
    """GPT-4o-mini — fallback YOK."""
    return _ask_gpt_model("gpt-4o-mini", prompt, system=system,
                          max_tokens=max_tokens, retries=retries,
                          no_fallback=True, temperature=temperature)


# ═══════════════════════════════════════════════════════════════════════════════
# PYTHON MEKANİK PRE-PROCESSOR (0 token)
# ═══════════════════════════════════════════════════════════════════════════════

import re as _re

_FORBIDDEN_REPLACEMENTS = {
    # abartılı sıfatlar → nötr
    r'\bmuhteşem\b':             'etkileyici',
    r'\bharika\b':               'güzel',
    r'\bmükemmel\b':             'iyi',
    r'\binanılmaz\b':            'dikkat çekici',
    r'\bnefes kesici\b':         'çarpıcı',
    r'\beşsiz\b':                'özgün',
    r'\bbüyüleyici\b':           'ilgi çekici',
    r'\bgoerkemli\b':            'görkemli',  # encoding guard
    r'\bgörkemli\b':             'etkileyici',
    r'\bunutulmaz\b':            'akılda kalan',
    r'\brüya gibi\b':            'sakin',
    r'\bcennet\b':               'ideal',
    r'\bmasalsı\b':              'kendine özgü',
    # broşür klişeleri → sil/değiştir
    r'ziyaretçilerini bekliyor': 'ziyaret edilebilir',
    r'hayatınızın tatili':       'keyifli bir tatil',
    r'bir açık hava müzesi':     'tarihi bir kent',
    r'her köşe başında tarih':   'tarihin izleri her yerde',
    r'zaman durmuş gibi':        'sakin bir atmosfer var',
    r'dünya size ait':           '',
    r'kesinlikle görülmeli':     'görmeye değer',
    r'\bdikkat çekiyor\b':       'öne çıkıyor',
    # pasif fiil → aktif
    r'\bziyaret edilebilir\b':   'ziyaret edebilirsiniz',
    r'\btercih edilmektedir\b':  'tercih edilir',
    r'\bbilinmektedir\b':        'biliniyor',
    r'\bgörülmektedir\b':        'görülüyor',
}

_MARKDOWN_BOLD = _re.compile(r'\*\*(.+?)\*\*', _re.DOTALL)
_LONG_SENTENCE = _re.compile(r'<p[^>]*>([^<]{120,})</p>')   # ~20+ kw proxy


def mechanical_clean(html: str, verbose: bool = False) -> str:
    """
    Python tabanlı mekanik temizleyici — 0 token.
    1. ** markdown → <strong>
    2. Forbidden kelime değiştirme (regex)
    3. Uzun cümle tespiti (log, değiştirmez)
    4. Boş satır normalizasyonu
    """
    # 1. Markdown bold
    html = _MARKDOWN_BOLD.sub(r'<strong>\1</strong>', html)

    # 2. Forbidden word replacement
    fixes = 0
    for pattern, replacement in _FORBIDDEN_REPLACEMENTS.items():
        new_html, n = _re.subn(pattern, replacement, html, flags=_re.IGNORECASE)
        if n:
            fixes += n
            html = new_html
    if verbose and fixes:
        print(f"   🔧 mechanical_clean: {fixes} forbidden word düzeltildi")

    # 3. Uzun cümle tespiti (log only)
    long_hits = _LONG_SENTENCE.findall(html)
    if verbose and long_hits:
        print(f"   ⚠️  {len(long_hits)} uzun paragraf tespit edildi (manual review önerilir)")

    # 4. Ardışık boş satır normalizasyonu
    html = _re.sub(r'\n{3,}', '\n\n', html)

    return html


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE POLISH — SADECE SES KRİTİK BÖLÜMLER
# Giriş (4-5 para) + Nasıl Bir Yer para 1-2 + Kapanış
# ═══════════════════════════════════════════════════════════════════════════════

_POLISH_SYSTEM = """Sen Alex Rivera'nın sesini koruyan kıdemli bir editörsün.
GPT metnini mekanik olarak temizlenmiş olarak alıyorsun (forbidden wordlar, markdown zaten düzeltildi).
Senden istenen: SADECE SES VE TON düzeltmesi.

Alex Rivera SESİ:
• 1971 doğumlu, 1995'ten beri aktif gezgin, example.com
• 1. tekil şahıs: "gördüm", "fark ettim", "ben tercih ederim"
• Kısa cümle, somut veri, beklenti ayarı
• Anlatısal coğrafya: "Balkanların ortasında" ✅ — "X enlem Y boylam" ❌

DÜZELT:
1. Ansiklopedik açılış → kişisel tona çevir
2. Geniş zamanlı genel anlatı → somut gözlem
3. Broşür tonu → gerçekçi, dengeli
4. "Hissedebilirsiniz" → gözlemlenebilir sahne

DOKUNMA:
• Gutenberg HTML yapısı (wp:paragraph, wp:heading, wp:list)
• Sayısal veriler (€, km, dakika, tarih)
• İç link href değerleri
• Başlık metni ve emoji
• Teknik bilgiler (havalimanı kodu, tren hattı, vize)

ÇIKTI: Sadece düzeltilmiş Gutenberg HTML. Açıklama yok.
"""

# Bölüm bazlı token limitleri
_POLISH_TOKENS = {
    "Giriş":              1800,   # 4-5 para, ses kritik
    "Nasıl Bir Yer p1-2": 1200,   # sadece ilk 2 para
    "Kapanış":            1200,   # 2 para, ses kritik
    "default":            1500,
}


def ask_claude_polish(gpt_html: str, section_label: str = "") -> str:
    """
    Claude Haiku ile GPT çıktısını polish et.
    Sadece ses-kritik bölümler: Giriş, Nasıl Bir Yer p1-2, Kapanış.
    """
    cleaned = mechanical_clean(gpt_html, verbose=True)
    label   = f"[{section_label}] " if section_label else ""
    max_tok = _POLISH_TOKENS.get(section_label, _POLISH_TOKENS["default"])
    prompt  = f"""{label}Gutenberg HTML içeriğini Alex'in sesine göre düzelt.
Forbidden word + mekanik düzeltmeler zaten yapıldı. Sadece ansiklopedik/broşür tonunu kişisel anlatıya çevir.
Gutenberg yapısı, sayısal veriler, linkler, teknik bilgiler KORUNACAK.

{cleaned}"""
    before = _haiku_tokens["output"]
    result = ask_claude_haiku(prompt, system=_POLISH_SYSTEM, max_tokens=max_tok)
    used   = _haiku_tokens["output"] - before
    print(f"   🪶 Haiku Polish({section_label or 'genel'}) → {used}t")
    return result


def mechanical_only(gpt_html: str, section_label: str = "") -> str:
    """
    Sadece Python temizliği — Claude çağrısı YOK.
    Ses-kritik olmayan bölümler için (Nerede, Nasıl Gidilir p4-7, Gezi Planı, Nerede).
    """
    result = mechanical_clean(gpt_html, verbose=True)
    print(f"   🔧 mechanical_only({section_label or 'genel'}) — Claude çağrısı yapılmadı")
    return result
