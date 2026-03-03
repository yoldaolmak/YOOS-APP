"""
editorial_mode.py v1.0 — Mevcut İçerik İyileştirme Motoru

Görev: Yayınlanmış WordPress içeriğini az token ile Kemal Voice kalitesine çıkar.

Akış:
  1. URL → WordPress'ten içerik çek
  2. Audit (content_validator) → skor + action
  3. Karar:
     ≥ 82 → skip (dokunma)
     60-82 → surgical_polish (sadece zayıf bölümler, Haiku)
     < 60  → section_rewrite (bölüm bazlı GPT-mini, context sıfırla)
  4. Sonucu WordPress draft olarak kaydet
  5. Raporu döndür

Token optimizasyonu:
  - Bölüm bazlı session: her bölüm ayrı prompt, context birikmiyor
  - Sadece başarısız bölümler yeniden üretilir
  - Mechanical fix (0 token) önce çalışır
  - Haiku < GPT-mini < Sonnet (maliyet sırası)
"""

import re
import json
import datetime
import os
from typing import Optional

from content_validator import validate, auto_fix, print_audit_report
from agent_loop import (
    run_with_quality_gate, format_agent_report,
    record_failures, get_failure_weight, _extract_schema, _reattach_schema
)
from multi_ai import ask_gpt_mini_strict, ask_claude_haiku, mechanical_clean


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM AYRIŞTIRICI
# ═══════════════════════════════════════════════════════════════════════════════

def _split_sections(html: str) -> list[dict]:
    """
    HTML'yi H2 sınırlarında bölümlere ayır.
    Döndürür: [{"name": str, "html": str, "has_h2": bool}]
    """
    # Giriş (H2'den öncesi)
    sections = []
    intro_end = html.find("<!-- wp:heading -->")
    if intro_end == -1:
        intro_end = html.find("<h2")
    if intro_end == -1:
        intro_end = len(html)

    intro = html[:intro_end].strip()
    if intro:
        sections.append({"name": "Giriş", "html": intro, "has_h2": False})

    # H2 bölümleri
    pattern = r'(<!-- wp:heading -->.*?<h2[^>]*>.*?</h2>.*?<!-- /wp:heading -->)(.*?)(?=<!-- wp:heading -->.*?<h2|$)'
    for m in re.finditer(pattern, html[intro_end:], re.DOTALL | re.IGNORECASE):
        heading_block = m.group(1)
        body = m.group(2).strip()
        h2_text = re.sub(r'<[^>]+>', '', heading_block).strip()
        sections.append({
            "name": h2_text[:60],
            "html": heading_block + "\n" + body,
            "has_h2": True
        })

    # Fallback: <h2> tag olmayan HTML
    if not sections:
        parts = re.split(r'(?=<h2)', html, flags=re.IGNORECASE)
        for i, part in enumerate(parts):
            h2_text = re.sub(r'<[^>]+>', '', re.search(r'<h2[^>]*>(.*?)</h2>', part, re.DOTALL | re.I).group(0) if re.search(r'<h2', part, re.I) else "").strip() or f"Bölüm {i}"
            sections.append({"name": h2_text[:60], "html": part.strip(), "has_h2": bool(re.search(r'<h2', part, re.I))})

    return [s for s in sections if s["html"]]


def _join_sections(sections: list[dict]) -> str:
    SEP = ('<!-- wp:separator -->'
           '<hr class="wp-block-separator has-alpha-channel-opacity"/>'
           '<!-- /wp:separator -->')
    parts = [s["html"].strip() for s in sections if s["html"].strip()]
    return f'\n\n{SEP}\n\n'.join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM KALİTE ANALİZİ — hangi bölümler sorunlu?
# ═══════════════════════════════════════════════════════════════════════════════

def _section_score(section_html: str, city: str) -> dict:
    """Tek bölümün hızlı skoru (tam validate değil — sadece narrative+format)."""
    from content_validator import _narrative, _forbidden_count, _fp_density, _data_hits, _strip
    narr_sc, narr_fail = _narrative(section_html)
    wc = len(_strip(section_html).split())
    return {
        "score": narr_sc,
        "word_count": wc,
        "failures": narr_fail,
        "forbidden": _forbidden_count(section_html),
        "fp_density": _fp_density(section_html),
        "data_hits": _data_hits(section_html),
    }


def _identify_weak_sections(sections: list[dict], city: str, threshold: int = 20) -> list[int]:
    """Narrative skoru threshold altındaki bölümlerin index listesini döndür."""
    weak = []
    for i, sec in enumerate(sections):
        s = _section_score(sec["html"], city)
        # Forbidden words veya düşük FP density veya çok az veri
        if s["forbidden"] >= 2 or s["fp_density"] < 0.3 or s["score"] < threshold:
            weak.append(i)
    return weak


# ═══════════════════════════════════════════════════════════════════════════════
# SURGICAL POLISH — sadece zayıf bölümler (Haiku)
# ═══════════════════════════════════════════════════════════════════════════════

_SURGICAL_SYSTEM = """Sen Kemal Kaya sesini koruyan editörsün — yoldaolmak.com.
Bir WHERE makalesi bölümünü alıyorsun. SADECE şunları düzelt:
• Ansiklopedik/broşür tonu → kişisel gözleme çevir
• Pasif fiil → aktif, 1.tekil şahıs (gördüm/fark ettim/öneriyorum)
• Forbidden: muhteşem/harika/mükemmel/cennet/eşsiz/büyüleyici → nötr alternatife
• Geniş zamanlı "her yıl milyonlarca..." → somut sahne

DOKUNMA: Gutenberg HTML yapısı, sayısal veriler (€/km/dk), linkler, H başlıkları.
ÇIKTI: Sadece düzeltilmiş Gutenberg HTML. Açıklama yok."""


def _surgical_polish_section(section_html: str, section_name: str,
                              failures: list, city: str) -> str:
    """Haiku ile tek bölüm surgical polish."""
    # Önce 0-token mekanik temizlik
    cleaned = mechanical_clean(section_html, verbose=False)

    # Tekrar eden hataları vurgula
    issue_lines = []
    for f in failures[:4]:
        w = get_failure_weight(f.code)
        prefix = "⚠️ TEKRAR EDEN:" if w >= 3 else "Düzelt:"
        issue_lines.append(f"{prefix} {f.code} — {f.fix_hint}")

    issues = "\n".join(issue_lines) if issue_lines else "Genel ses/ton iyileştirme"

    prompt = f"""Şehir: {city} | Bölüm: {section_name}

Sorunlar:
{issues}

HTML:
{cleaned}"""

    try:
        result = ask_claude_haiku(prompt, system=_SURGICAL_SYSTEM, max_tokens=1500)
        return result.strip()
    except Exception as e:
        print(f"     ⚠️ Haiku polish başarısız ({section_name}): {e}")
        return cleaned


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION REWRITE — düşük kaliteli bölüm GPT-mini ile yeniden üretim
# ═══════════════════════════════════════════════════════════════════════════════

_REWRITE_SYSTEM = """Sen Kemal Kaya'sın — 1971 doğumlu gezgin, yoldaolmak.com.
WHERE modu içeriği yeniden üretiyorsun.

ZORUNLU:
• 1.tekil şahıs: "gördüm","fark ettim","öneriyorum","ben gittim"
• Cümle maks 20 kelime
• Somut veri: €, km, saat, tarih+kaynak
• Artı+eksi dengeli, beklenti ayarı var
• Duyusal detay: koku, ışık, ses, doku

YASAK: muhteşem, harika, mükemmel, cennet, eşsiz, büyüleyici, masalsı
YASAK: pasif fiil, broşür dili, ansiklopedik açılış

FORMAT:
• Paragraf: <!-- wp:paragraph --><p>...</p><!-- /wp:paragraph -->
• H2: <!-- wp:heading --><h2 class="wp-block-heading"><strong>Başlık</strong></h2><!-- /wp:heading -->
• H3: <!-- wp:heading {"level":3} --><h3 class="wp-block-heading"><strong>Başlık</strong></h3><!-- /wp:heading -->"""


def _rewrite_section(section_html: str, section_name: str,
                     failures: list, city: str, city_en: str = "") -> str:
    """GPT-mini ile bölümü tamamen yeniden üret — temiz session."""
    # Hata ağırlıklarını hesapla
    directives = []
    for f in failures:
        w = get_failure_weight(f.code)
        emphasis = "KRİTİK — " if w >= 3 else ""
        directives.append(f"• {emphasis}{f.fix_hint}")

    dirs = "\n".join(directives) if directives else "• Kemal Voice standardına çıkar"

    # Mevcut içerikten korunacak verileri çıkar
    existing_data = re.findall(r'[\d,.]+ *[€$₺kmKMhdsaat dakika]', section_html)
    existing_links = re.findall(r'href="[^"]+"', section_html)
    preserve_note = ""
    if existing_data:
        preserve_note += f"\nKORU (sayısal veriler): {', '.join(existing_data[:8])}"
    if existing_links:
        preserve_note += f"\nKORU (linkler): {', '.join(existing_links[:4])}"

    # H2/H3 başlıklarını koru
    h_tags = re.findall(r'<h[23][^>]*>.*?</h[23]>', section_html, re.DOTALL | re.I)
    if h_tags:
        preserve_note += f"\nBAŞLIK (birebir koru): {h_tags[0][:200]}"

    prompt = f"""Şehir: {city}{f' ({city_en})' if city_en else ''}
Bölüm: {section_name}

Bu WHERE bölümünü TAMAMEN YENİDEN YAZ — Kemal Voice ile.

GİDERİLECEK SORUNLAR:
{dirs}
{preserve_note}

MEVCUT HTML (referans — yapıyı koru, içeriği değiştir):
{section_html[:2500]}"""

    try:
        result = ask_gpt_mini_strict(prompt, system=_REWRITE_SYSTEM,
                                     max_tokens=1500, temperature=0.85)
        return auto_fix(result.strip())
    except Exception as e:
        print(f"     ⚠️ GPT-mini rewrite başarısız ({section_name}): {e}")
        return auto_fix(section_html)


# ═══════════════════════════════════════════════════════════════════════════════
# ANA FONKSİYON
# ═══════════════════════════════════════════════════════════════════════════════

def run_editorial_rewrite(
    url: str = "",
    html_content: str = "",       # direkt HTML geçilebilir (test için)
    post_id: int = 0,
    city: str = "",
    mode: str = "where",
    max_passes: int = 2,
    output_dir: str = "./output",
    backup_dir: str = "./backups",
    report_dir: str = "./reports",
    verbose: bool = True,
) -> dict:
    """
    Mevcut yayınlanmış içeriği iyileştir.

    Döndürür:
        success:       bool
        draft_id:      int | None
        draft_title:   str
        score_before:  int
        score_after:   int
        action:        str  ("skip" | "surgical_polish" | "section_rewrite")
        html:          str  — düzeltilmiş HTML
        cost_estimate: float  — USD
        error:         str | None
    """
    if verbose:
        print(f"\n{'═'*58}")
        print(f"📝 EDITORIAL MODE — {url or f'post:{post_id}' or 'local'}")
        print(f"{'═'*58}")

    # ── 1. İçerik yükle ──────────────────────────────────────────────────────
    if html_content:
        raw_html = html_content
        post_title = city or "Test Post"
    elif url or post_id:
        try:
            from wp import get_post_by_url, get_post_by_id
            if url:
                post = get_post_by_url(url)
            else:
                post = get_post_by_id(post_id)
            raw_html   = post.get("content", {}).get("rendered", "")
            post_title = post.get("title", {}).get("rendered", "")
            if not city:
                # URL'den şehir adını çıkarmaya çalış
                slug = url.rstrip("/").split("/")[-1]
                city = slug.replace("-nerede-nasil-gidilir", "").replace("-", " ").title()
        except Exception as e:
            return {"success": False, "error": f"İçerik yüklenemedi: {e}",
                    "action": "error"}
    else:
        return {"success": False, "error": "URL, post_id veya html_content gerekli",
                "action": "error"}

    if not raw_html:
        return {"success": False, "error": "HTML içerik boş", "action": "error"}

    city = city or "Bilinmiyor"

    # ── 2. Mekanik ön-temizlik (0 token) ─────────────────────────────────────
    html = auto_fix(raw_html)
    if verbose: print(f"  [0] Mekanik temizlik ✓  ({len(raw_html)} → {len(html)} kar)")

    # ── 3. İlk audit ─────────────────────────────────────────────────────────
    result_before = validate(html, mode=mode, city=city)
    score_before  = result_before.score
    action        = result_before.action

    if verbose:
        print_audit_report(result_before, city=city)

    record_failures(result_before.failures, city, fixed=False)

    # ── 4. Skip kararı ───────────────────────────────────────────────────────
    if action == "skip":
        if verbose: print(f"  ✅ SKIP — skor {score_before}/100, mükemmel")
        return {
            "success": True, "action": "skip",
            "score_before": score_before, "score_after": score_before,
            "html": html, "draft_id": None, "draft_title": post_title,
            "cost_estimate": 0.0,
        }

    # ── 5. Schema bloğunu ayır (patch sırasında korunur) ─────────────────────
    content_html, schema_suffix = _extract_schema(html)

    # ── 6. Bölümlere ayır ────────────────────────────────────────────────────
    sections = _split_sections(content_html)
    if verbose:
        print(f"\n  📐 {len(sections)} bölüm tespit edildi:")
        for s in sections:
            ss = _section_score(s["html"], city)
            print(f"    • {s['name'][:40]:40}  narr:{ss['score']:>2}/35  wc:{ss['word_count']:>4}  fb:{ss['forbidden']}")

    # ── 7. İyileştirme döngüsü ────────────────────────────────────────────────
    total_api_cost = 0.0
    improved_sections = list(sections)  # kopya

    for pass_num in range(1, max_passes + 1):
        if verbose: print(f"\n  — Pass {pass_num}/{max_passes} ({action.upper()}) —")

        if action == "full_rewrite":
            # Tüm bölümler GPT-mini ile yeniden üretilir
            city_en = city  # basit fallback
            try:
                from where_engine import _CITY_META
                meta = _CITY_META.get(city)
                if meta: city_en = meta[0]
            except ImportError:
                pass

            for i, sec in enumerate(improved_sections):
                sec_score = _section_score(sec["html"], city)
                # Çok kısa (< 50 kw) veya forbidden dolu bölümleri yeniden yaz
                if sec_score["word_count"] < 60 or sec_score["forbidden"] >= 2 or sec_score["score"] < 15:
                    if verbose: print(f"     🔴 Rewrite: {sec['name'][:40]}")
                    new_html = _rewrite_section(
                        sec["html"], sec["name"],
                        result_before.failures, city, city_en
                    )
                    improved_sections[i] = {"name": sec["name"], "html": new_html, "has_h2": sec["has_h2"]}
                    total_api_cost += 0.0035  # GPT-mini tahmin
                else:
                    if verbose: print(f"     ⚪ Koru  : {sec['name'][:40]}")

        else:  # "polish"
            # Sadece zayıf bölümler Haiku ile düzeltilir
            weak_indices = _identify_weak_sections(improved_sections, city)
            if verbose: print(f"     Zayıf bölüm: {len(weak_indices)}/{len(sections)}")

            for i in weak_indices:
                sec = improved_sections[i]
                # Bu bölümle ilgili failure'ları filtrele
                sec_failures = [f for f in result_before.failures
                                if f.axis == "narrative" or
                                   (f.axis == "technical" and any(
                                       x in sec["name"] for x in ["Gidilir","Plan","Bilet"]))]
                if verbose: print(f"     🔧 Polish: {sec['name'][:40]}")
                new_html = _surgical_polish_section(
                    sec["html"], sec["name"], sec_failures, city
                )
                improved_sections[i] = {"name": sec["name"], "html": new_html, "has_h2": sec["has_h2"]}
                total_api_cost += 0.0008  # Haiku tahmin

        # Pass sonrası ara değerlendirme
        current_html = _join_sections(improved_sections)
        current_html = _reattach_schema(current_html, schema_suffix)
        current_html = auto_fix(current_html)

        result_check = validate(current_html, mode=mode, city=city)
        if verbose: print(f"     → Pass {pass_num} skor: {result_check.score}/100 [{result_check.action}]")

        if result_check.action == "skip":
            if verbose: print(f"  ✅ Pass {pass_num}'de geçti!")
            html = current_html
            break

        # Bir sonraki pass için action güncelle
        action = result_check.action
        html   = current_html
    else:
        # Max pass doldu
        result_check = validate(html, mode=mode, city=city)

    # ── 8. Son audit ─────────────────────────────────────────────────────────
    result_after = validate(html, mode=mode, city=city)
    score_after  = result_after.score
    record_failures(result_after.failures, city,
                    fixed=(score_after > score_before))

    if verbose:
        print(f"\n  📊 SONUÇ: {score_before}/100 → {score_after}/100 (+{score_after-score_before})")
        print(f"  💰 Tahmini maliyet: ~${total_api_cost:.4f}")

    # ── 9. WordPress'e draft kaydet ──────────────────────────────────────────
    draft_id    = None
    draft_title = post_title

    if url or post_id:
        try:
            from wp import create_draft, get_active_site
            draft_result = create_draft(
                title=post_title,
                content=html,
                status="draft"
            )
            draft_id    = draft_result.get("id")
            draft_title = draft_result.get("title", {}).get("rendered", post_title)
            if verbose:
                print(f"  💾 Draft kaydedildi: ID={draft_id} | '{draft_title[:50]}'")
        except Exception as e:
            if verbose: print(f"  ⚠️ Draft kaydetme başarısız: {e} (HTML raporda mevcut)")

    # ── 10. Rapor kaydet ──────────────────────────────────────────────────────
    _save_editorial_report({
        "url": url, "post_id": post_id, "city": city,
        "score_before": score_before, "score_after": score_after,
        "action": result_before.action,
        "passes": max_passes,
        "cost": round(total_api_cost, 4),
        "draft_id": draft_id,
        "timestamp": datetime.datetime.now().isoformat()[:19],
        "failures_before": [f.code for f in result_before.failures],
        "failures_after": [f.code for f in result_after.failures],
    }, report_dir)

    return {
        "success":       True,
        "action":        result_before.action,
        "score_before":  score_before,
        "score_after":   score_after,
        "html":          html,
        "draft_id":      draft_id,
        "draft_title":   draft_title,
        "cost_estimate": total_api_cost,
        "error":         None,
        "final_result":  result_after,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TOPLU İYİLEŞTİRME (daily_command için)
# ═══════════════════════════════════════════════════════════════════════════════

def run_editorial_batch(
    posts: list[dict],
    mode: str = "where",
    max_passes: int = 2,
    report_dir: str = "./reports",
    budget_usd: float = 1.0,
    verbose: bool = True,
) -> dict:
    """
    Toplu iyileştirme — budget kontrolü ile.
    posts: [{"url": str, "post_id": int, "city": str, "html": str}]
    """
    results  = []
    spent    = 0.0
    skipped  = 0
    improved = 0
    failed   = 0

    for i, post in enumerate(posts, 1):
        if spent >= budget_usd:
            print(f"  💸 Bütçe tükendi (${spent:.3f}/${budget_usd}), duruyorum.")
            break

        city = post.get("city", "")
        url  = post.get("url", "")
        if verbose:
            print(f"\n[{i}/{len(posts)}] {city or url}")

        r = run_editorial_rewrite(
            url=url,
            html_content=post.get("html", ""),
            post_id=post.get("post_id", 0),
            city=city,
            mode=mode,
            max_passes=max_passes,
            report_dir=report_dir,
            verbose=verbose,
        )

        spent += r.get("cost_estimate", 0)
        if r["success"]:
            if r["action"] == "skip":
                skipped += 1
            else:
                improved += 1
        else:
            failed += 1

        results.append({**r, "city": city, "url": url})

    return {
        "total":    len(posts),
        "improved": improved,
        "skipped":  skipped,
        "failed":   failed,
        "cost_usd": round(spent, 4),
        "results":  results,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RAPOR KAYDET
# ═══════════════════════════════════════════════════════════════════════════════

def _save_editorial_report(data: dict, report_dir: str) -> None:
    try:
        os.makedirs(report_dir, exist_ok=True)
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fn  = os.path.join(report_dir, f"editorial_{ts}.json")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # rapor kaydetme hata fırlattırmasın
