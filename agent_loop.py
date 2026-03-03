"""
agent_loop.py v3.0 — Pattern Memory + Threshold Router

v3.0 yenilikleri:
  - FailureMemory: JSON-tabanlı pattern hafızası (son 100 post)
  - Tekrar eden hataları ağır prompt ile yakalar
  - Threshold router: full_rewrite vs polish vs skip
  - Rewrite: GPT-mini ile bölüm bazlı yeniden üretim
  - Polish: Haiku ile ses/ton düzeltme

Karar akışı:
  validate(html) → action
    "skip"         → return as-is
    "polish"       → Haiku polish
    "full_rewrite" → GPT-mini section rewrite
"""

import os
import json
import re
import datetime
from pathlib import Path
from content_validator import validate, auto_fix, ValidationResult, Failure
from multi_ai import ask_gpt_mini_strict, ask_claude_haiku, ask_gpt_mini


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE MEMORY — Pattern hafızası
# ═══════════════════════════════════════════════════════════════════════════════

_MEMORY_PATH = Path(os.path.dirname(__file__)) / "failure_memory.json"
_MAX_HISTORY = 100


def _load_memory() -> dict:
    """failure_code → {count, last_seen, cities, fix_worked}"""
    if _MEMORY_PATH.exists():
        try:
            return json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_memory(mem: dict) -> None:
    _MEMORY_PATH.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")


def record_failures(failures: list, city: str, fixed: bool = False) -> None:
    """Failure'ları hafızaya kaydet."""
    mem = _load_memory()
    for f in failures:
        code = f.code
        if code not in mem:
            mem[code] = {"count": 0, "cities": [], "fix_worked": 0, "fix_failed": 0}
        mem[code]["count"] += 1
        mem[code]["last_seen"] = datetime.datetime.now().isoformat()[:10]
        if city and city not in mem[code]["cities"]:
            mem[code]["cities"] = (mem[code]["cities"] + [city])[-20:]
        if fixed:
            mem[code]["fix_worked"] += 1
        else:
            mem[code]["fix_failed"] += 1

    # Max 100 entry
    if len(mem) > _MAX_HISTORY:
        sorted_codes = sorted(mem, key=lambda k: mem[k]["count"])
        for old in sorted_codes[:len(mem)-_MAX_HISTORY]:
            del mem[old]

    _save_memory(mem)


def get_failure_weight(code: str) -> int:
    """Tekrar eden hataları ağır prompt ile hedef — ağırlık 1-5."""
    mem = _load_memory()
    if code not in mem:
        return 1
    cnt = mem[code]["count"]
    if cnt >= 10: return 5
    if cnt >= 5:  return 4
    if cnt >= 3:  return 3
    if cnt >= 2:  return 2
    return 1


def get_top_failures(n: int = 5) -> list:
    """En sık görülen n failure kodu."""
    mem = _load_memory()
    return sorted(mem, key=lambda k: mem[k]["count"], reverse=True)[:n]


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA AYRIŞTIRICISI
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_schema(html: str) -> tuple:
    """(content_html, schema_suffix) — schema patch sırasında korunur."""
    idx = html.find('<!-- wp:html -->')
    if idx < 0:
        # JSON-LD <script> bloğuna da bak
        idx = html.find('<script type="application/ld+json">')
    if idx < 0:
        return html, ''
    return html[:idx].rstrip(), '\n\n' + html[idx:]


def _reattach_schema(content: str, schema_suffix: str) -> str:
    if not schema_suffix:
        return content
    if '<!-- wp:html -->' in content:
        content = content[:content.find('<!-- wp:html -->')].rstrip()
    return content + schema_suffix


# ═══════════════════════════════════════════════════════════════════════════════
# POLISH PROMPT (Haiku — ses/ton)
# ═══════════════════════════════════════════════════════════════════════════════

_POLISH_SYSTEM = """Sen Kemal Kaya sesini koruyan editörsün — yoldaolmak.com.
Forbidden word + mekanik sorunlar zaten temizlendi. Sadece ses/ton düzelt.

DÜZELT:
• Ansiklopedik açılış → kişisel tona çevir
• Geniş zamanlı genel anlatı → somut gözlem
• Pasif fiil → aktif, 1.tekil şahıs
• Broşür tonu → gerçekçi, dengeli, beklenti ayarı var

DOKUNMA:
• Gutenberg HTML yapısı
• Sayısal veriler (€, km, dk)
• İç link href değerleri
• H başlık metni ve emojiler
• Schema/FAQ bloğu

ÇIKTI: Sadece Gutenberg HTML."""


def _polish(html: str, failures: list, city: str) -> str:
    """Haiku ile ses/ton polish."""
    # Failure listesinden özel talimatlar oluştur
    issue_hints = []
    for f in failures[:5]:
        w = get_failure_weight(f.code)
        prefix = "⚠️ TEKRAR EDEN HATA" if w >= 3 else "Düzelt"
        issue_hints.append(f"{prefix}: {f.code} — {f.fix_hint}")

    issues_text = "\n".join(issue_hints) if issue_hints else "Ses ve ton düzeltmesi"
    prompt = f"""[{city}] Aşağıdaki içeriği Kemal'in sesine çevir.

SORUNLAR:
{issues_text}

HTML:
{html[:6000]}{"[...]" if len(html)>6000 else ""}"""

    return ask_claude_haiku(prompt, system=_POLISH_SYSTEM, max_tokens=3000)


# ═══════════════════════════════════════════════════════════════════════════════
# REWRITE PROMPT (GPT-mini — bölüm bazlı yeniden üretim)
# ═══════════════════════════════════════════════════════════════════════════════

_REWRITE_SYSTEM = """Sen Kemal Kaya'sın — 1971 doğumlu gezgin, yoldaolmak.com.
WHERE modu içeriği üretiyorsun.

ZORUNLU:
• 1.tekil şahıs: "gördüm","fark ettim","öneriyorum"
• Cümle maks 20kw
• Somut veri: €, km, saat, tarih+kaynak
• Artı+eksi dengeli, beklenti ayarı
• Gutenberg HTML: <!-- wp:paragraph --><p>...</p><!-- /wp:paragraph -->
• H2: <!-- wp:heading --><h2 class="wp-block-heading"><strong>Başlık</strong></h2><!-- /wp:heading -->
• H3: <!-- wp:heading {"level":3} --><h3 class="wp-block-heading"><strong>Başlık</strong></h3><!-- /wp:heading -->

YASAK: muhteşem, harika, mükemmel, cennet, eşsiz, büyüleyici, broşür dili, pasif fiil"""


def _rewrite_section(section_html: str, section_name: str,
                     failures: list, city: str, city_en: str) -> str:
    """GPT-mini ile tek bölümü yeniden üret."""
    # Ağırlıklı talimatlar
    directives = []
    for f in failures:
        w = get_failure_weight(f.code)
        emphasis = "KRITIK — " if w >= 3 else ""
        directives.append(f"• {emphasis}{f.fix_hint}")

    prompt = f"""Şehir: {city} ({city_en})
Bölüm: {section_name}

Bu WHERE bölümünü TAMAMEN YENİDEN YAZ.
Mevcut içerik kalıplarını kırıp Kemal'in sesine geçir.

GİDERİLECEK SORUNLAR:
{"".join(directives) if directives else "• Genel kalite iyileştirme"}

MEVCUT HTML (referans — koru: veriler, linkler, başlıklar):
{section_html[:3000]}

YAZ: Sadece Gutenberg HTML paragrafları. H2/H3 başlığını mevcut haliyle koru."""
    return ask_gpt_mini_strict(prompt, system=_REWRITE_SYSTEM,
                               max_tokens=1800, temperature=0.85)


def _full_rewrite(html: str, failures: list, city: str, mode: str) -> str:
    """
    Full rewrite: H2 bölümlerine ayır → her birini ayrı GPT-mini session'ı ile yeniden üret.
    Bu sayede context birikmez, her bölüm temiz başlar.
    """
    content, schema = _extract_schema(html)

    # Bölüm bazlı ayır (H2 sınırlarında)
    parts = re.split(r'(?=<!-- wp:heading -->.*?<h2)', content, flags=re.DOTALL)

    city_en = city  # basit fallback
    try:
        from where_engine import _CITY_META
        meta = _CITY_META.get(city)
        if meta:
            city_en = meta[0]
    except ImportError:
        pass

    # Failure'ları bölüm bazlı grupla (axis ile)
    tech_failures  = [f for f in failures if f.axis == "technical"]
    narr_failures  = [f for f in failures if f.axis == "narrative"]
    auth_failures  = [f for f in failures if f.axis == "authority"]

    rewritten_parts = []
    for part in parts:
        if not part.strip():
            continue
        # Hangi bölüm olduğunu tespit et
        h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', part, re.DOTALL | re.I)
        section_name = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip() if h2_match else "Giriş"

        # Bölüme özgü failure'lar
        section_failures = narr_failures[:]  # narrative tüm bölümleri etkiler
        if "Gidilir" in section_name:
            section_failures += [f for f in tech_failures if "BILET" in f.code or "LINK" in f.code]
        if "Plan" in section_name:
            section_failures += [f for f in tech_failures if "PLAN" in f.code]
        if "Nerede" in section_name or "Nasıl Bir Yer" in section_name:
            section_failures += auth_failures

        rewritten = _rewrite_section(part, section_name, section_failures, city, city_en)
        rewritten_parts.append(rewritten)

    result = '\n\n'.join(rewritten_parts)
    return _reattach_schema(result, schema)


# ═══════════════════════════════════════════════════════════════════════════════
# ANA AGENT DÖNGÜSÜ
# ═══════════════════════════════════════════════════════════════════════════════

def run_with_quality_gate(
    html:           str,
    mode:           str  = "where",
    city:           str  = "",
    max_retries:    int  = 2,
    pass_threshold: int  = 82,   # v3.0: 70→82
    verbose:        bool = True,
) -> dict:
    """
    Döndürür: {html, passed, score, action, attempts, log, final_validation}
    """
    if verbose:
        print(f"\n{'─'*55}")
        print(f"🔍 AGENT v3.0 — {mode.upper()} | {city}")
        print(f"{'─'*55}")

    agent_log = []

    # ── Aşama 0: Mekanik temizlik ─────────────────────────────────────────────
    html = auto_fix(html)
    if verbose: print("  [0] auto_fix ✓")

    # ── Aşama 1: İlk audit ───────────────────────────────────────────────────
    result = validate(html, mode=mode, city=city)
    agent_log.append({"step": "initial", "score": result.score, "action": result.action,
                       "failures": [f.code for f in result.failures]})
    if verbose:
        print(f"  [1] {result.summary()}")

    # Failure'ları hafızaya kaydet
    record_failures(result.failures, city, fixed=False)

    # ── Skip ─────────────────────────────────────────────────────────────────
    if result.action == "skip":
        if verbose: print(f"  ✅ SKIP — skor {result.score}/100, dokunulmuyor")
        return {"html": html, "passed": True, "score": result.score,
                "action": "skip", "attempts": 0,
                "log": agent_log, "final_validation": result}

    best_html  = html
    best_score = result.score
    best_result = result

    # ── Polish veya Rewrite döngüsü ───────────────────────────────────────────
    for attempt in range(1, max_retries + 1):
        action = result.action
        fixable = result.gpt_fixable_failures()

        if not fixable and action != "full_rewrite":
            if verbose: print(f"  [{attempt}] GPT fix gereken sorun yok — dur")
            break

        if verbose:
            print(f"\n  [{attempt}/{max_retries}] {action.upper()} başlatılıyor...")
            for f in fixable[:4]:
                w = get_failure_weight(f.code)
                star = "⭐" * min(w, 3)
                print(f"    {star} {f.code}: {f.detail[:55]}")

        try:
            content_for_fix, schema_suffix = _extract_schema(html)

            if action == "full_rewrite":
                fixed_content = _full_rewrite(content_for_fix, fixable, city, mode)
            else:   # polish
                fixed_content = _polish(content_for_fix, fixable, city)

            fixed_content = auto_fix(fixed_content)
            fixed_html = _reattach_schema(fixed_content, schema_suffix)

            new_result = validate(fixed_html, mode=mode, city=city)
            agent_log.append({"step": f"fix_{attempt}", "action": action,
                               "score": new_result.score, "action_after": new_result.action,
                               "failures": [f.code for f in new_result.failures]})

            if verbose:
                print(f"    → {new_result.summary()}")

            # Hafızayı güncelle
            fixed = new_result.score > result.score
            record_failures(result.failures, city, fixed=fixed)

            if new_result.score > best_score:
                best_html, best_score, best_result = fixed_html, new_result.score, new_result
                if verbose: print(f"    ↑ Yeni best: {best_score}/100")

            if new_result.action == "skip":
                if verbose: print(f"  ✅ {attempt}. denemede geçti")
                return {"html": fixed_html, "passed": True, "score": new_result.score,
                        "action": action, "attempts": attempt,
                        "log": agent_log, "final_validation": new_result}

            html, result = fixed_html, new_result

        except Exception as e:
            if verbose: print(f"    ❌ Hata: {e}")
            agent_log.append({"step": f"error_{attempt}", "error": str(e)})

    # ── Döngü sonu ───────────────────────────────────────────────────────────
    passed = best_score >= pass_threshold
    if verbose:
        icon = "✅" if passed else "⚠️ "
        print(f"\n  {icon} Döngü bitti — best skor: {best_score}/100")
        if not passed:
            print("  Draft kaydedildi (manuel kontrol önerilir)")
            top = get_top_failures(3)
            if top:
                print(f"  Tekrar eden sorunlar: {', '.join(top)}")

    return {"html": best_html, "passed": passed, "score": best_score,
            "action": best_result.action, "attempts": max_retries,
            "log": agent_log, "final_validation": best_result}


# ═══════════════════════════════════════════════════════════════════════════════
# RAPOR
# ═══════════════════════════════════════════════════════════════════════════════

def format_agent_report(loop_result: dict) -> str:
    r = loop_result
    icon = "✅" if r.get("passed") else "⚠️ "
    lines = [
        f"\n{'─'*50}",
        f"Agent Loop Raporu:",
        f"  Sonuç   : {icon}{'GEÇTİ' if r.get('passed') else 'BAŞARISIZ'}",
        f"  Skor    : {r['score']}/100",
        f"  Eylem   : {r.get('action','?').upper()}",
        f"  Deneme  : {r['attempts']}",
    ]
    fv = r.get("final_validation")
    if fv and fv.failures:
        lines.append("  Kalan:")
        for f in fv.failures[:4]:
            lines.append(f"    - [{f.axis}] {f.code}: {f.detail[:55]}")
    if '<!-- wp:html -->' in r.get("html",""):
        lines.append("  Schema  : ✅ korundu")
    top = get_top_failures(3)
    if top:
        lines.append(f"  Hafıza  : {', '.join(top)}")
    lines.append(f"{'─'*50}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# HAFIZA RAPORU (CLI debug için)
# ═══════════════════════════════════════════════════════════════════════════════

def print_memory_report() -> None:
    mem = _load_memory()
    if not mem:
        print("Hafıza boş.")
        return
    print(f"\n{'═'*55}")
    print("🧠 FAILURE MEMORY RAPORU")
    print(f"{'─'*55}")
    for code, data in sorted(mem.items(), key=lambda x: -x[1]["count"])[:15]:
        fix_rate = 0
        total_fixes = data.get("fix_worked",0) + data.get("fix_failed",0)
        if total_fixes:
            fix_rate = int(data["fix_worked"] / total_fixes * 100)
        print(f"  {code:<35} x{data['count']:>3}  fix:%{fix_rate:>3}  son:{data.get('last_seen','?')}")
    print(f"{'═'*55}")
