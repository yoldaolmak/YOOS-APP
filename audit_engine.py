"""
audit_engine.py — Yoldaolmak.com Editorial Audit Council
3 yargıçlı sistem: Authority Judge / Narrative Judge / Critical Judge
Editorial Constitution v2.0 tabanlı
"""

import re
import json
import os
import datetime
from typing import Optional
from multi_ai import ask_claude


# ─── ANAYASA SABİTLERİ ─────────────────────────────────────────────────────

FORBIDDEN_VOCABULARY = [
    "muhteşem", "harika", "mükemmel", "inanılmaz",
    "nefes kesici", "eşsiz", "büyüleyici", "görkemli",
    "unutulmaz", "rüya gibi", "cennet", "masalsı",
    "ziyaretçilerini bekliyor", "hayatınızın tatili",
    "bir açık hava müzesi", "her köşe başında tarih",
    "zaman durmuş gibi", "dünya size ait",
    "kesinlikle görülmeli",
]

NEGATIVE_SENTIMENT_KEYWORDS = [
    "pahalı", "kalabalık", "tuzak", "dezavantaj", "sorun",
    "dikkat", "uyarı", "hayal kırıklığı", "overhyped",
    "değmez", "aşırı", "yorucu", "can sıkıcı",
]

TOURIST_TRAP_PHRASES = [
    "turist tuzağı", "overhyped", "gerçekte", "aslında",
    "instagram'da", "ama gerçek", "beklentinizi düşürün",
    "abartıldığı kadar", "hayal kırıklığı yaratabili",
]

PASSIVE_VERB_PATTERNS = [
    r'\b(edilebilir|gidilir|görülür|yenilir|alınır|yapılır|bilinir|'
    r'ziyaret edilir|tavsiye edilir|önerilir|söylenir)\b'
]

FIRST_PERSON_MARKERS = [
    r'\b(ben\b|benim\b|bence\b|buldum\b|gördüm\b|öneririm\b|'
    r'gittiğimde\b|kaldım\b|fark ettim\b|denedim\b|gezdim\b|yaşadım\b)'
]

YEAR_PERSONAL_PATTERN = r'(19|20)\d{2}.{0,25}(gittiğimde|gittim|kaldım|gezdim|gördüm|ziyaret ettim|bulundum)'

PRICE_PATTERN = r'(\d+[\.,]?\d*)\s*(euro|€|eur|kč|czk|₺|tl|lira|dolar|\$|£|gbp)'
SOURCE_DATE_PATTERN = r'\((.*?),(.*?)(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\s*20\d{2}.*?\)'

DESTINATION_SECTION_PATTERNS = [
    r'nasıl bir|şehir profil|kimlik|hakkında',
    r'ne zaman|zaman gidil|en iyi dönem|iklim',
    r'gezilecek|görülecek|yapılacak|ziyaret',
    r'yeme|içme|restoran|mutfak|lezzet',
    r'konaklama|otel|nerede kal|kal(ın|mak)',
    r'nasıl gidilir|ulaşım|gidilir|uçuş|otobüs',
    r'pratik|bilgiler|vize|para|güvenlik',
    r'gezi plan|itinerary|kaç gün|program',
    r'sık sorul|faq|sorular',
]


# ─── HTML YARDIMCI FONKSİYONLARI ────────────────────────────────────────────

def strip_html(html: str) -> str:
    """HTML etiketlerini temizle, metin döndür."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_headings(html: str) -> dict:
    """H1-H6 başlıklarını çıkar."""
    headings = {}
    for level in range(1, 7):
        pattern = rf'<h{level}[^>]*>(.*?)</h{level}>'
        matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
        headings[f'h{level}'] = [strip_html(m) for m in matches]
    return headings


def count_words(text: str) -> int:
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words)


def count_internal_links(html: str, domain: str = "yoldaolmak.com") -> int:
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return sum(1 for l in links if domain in l or l.startswith('/'))


def detect_schema(html: str) -> bool:
    return bool(re.search(r'application/ld\+json', html, re.IGNORECASE))


def detect_toc(html: str, text: str) -> bool:
    toc_signals = [
        r'içindekiler',
        r'table.{0,10}content',
        r'#[a-z\-]+.*#[a-z\-]+',
        r'<nav',
        r'wp-block-table-of-contents',
    ]
    combined = (html + text).lower()
    return any(re.search(p, combined) for p in toc_signals)


def fetch_url_content(url: str) -> tuple[str, str]:
    """URL'den HTML ve düz metin çek. (html, text)"""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ClawdbotAudit/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='replace')
        text = strip_html(html)
        return html, text
    except Exception as e:
        return "", f"URL çekilemedi: {e}"


# ─── STAGE 1: PRE-CHECK ─────────────────────────────────────────────────────

def run_pre_check(text: str, html: str, content_type: str) -> dict:
    word_floor = 2500 if content_type != "Destination_Guide" else 3000
    word_count = count_words(text)

    headings = extract_headings(html)
    h2_texts = ' '.join(headings.get('h2', [])).lower()
    h3_texts = ' '.join(headings.get('h3', [])).lower()
    all_headings = h2_texts + ' ' + h3_texts

    # Zorunlu bölüm kontrolü
    sections_found = sum(
        1 for pattern in DESTINATION_SECTION_PATTERNS
        if re.search(pattern, all_headings)
    )
    sections_missing = len(DESTINATION_SECTION_PATTERNS) - sections_found

    # Yasaklı kelime
    text_lower = text.lower()
    forbidden_found = [w for w in FORBIDDEN_VOCABULARY if w in text_lower]

    failures = []
    if word_count < word_floor:
        failures.append(f"AF3: Kelime sayısı yetersiz ({word_count} < {word_floor})")
    if sections_missing >= 2:
        failures.append(f"AF5: {sections_missing} zorunlu bölüm eksik")
    if len(forbidden_found) >= 3:
        failures.append(f"AF1: {len(forbidden_found)} yasaklı kelime: {forbidden_found[:5]}")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "word_count": word_count,
        "word_floor": word_floor,
        "sections_found": sections_found,
        "sections_missing": sections_missing,
        "forbidden_found": forbidden_found,
    }


# ─── STAGE 2: AUTO-SCAN ──────────────────────────────────────────────────────

def run_auto_scan(text: str, html: str) -> dict:
    text_lower = text.lower()
    sentences = re.split(r'[.!?]\s+', text)
    sentence_count = max(len(sentences), 1)

    # AM1 - Yasaklı kelime sayısı
    forbidden_count = sum(1 for w in FORBIDDEN_VOCABULARY if w in text_lower)

    # AM2 - Birinci şahıs tekil
    first_person_count = sum(
        len(re.findall(p, text_lower))
        for p in FIRST_PERSON_MARKERS
    )

    # AM3 - Edilgen yapı oranı
    passive_count = sum(
        len(re.findall(p, text_lower))
        for p in PASSIVE_VERB_PATTERNS
    )
    passive_ratio = passive_count / sentence_count

    # AM4 - Fiyat atıf uyumu
    price_mentions = re.findall(PRICE_PATTERN, text_lower)
    price_count = len(price_mentions)
    sourced_price_count = len(re.findall(SOURCE_DATE_PATTERN, text_lower))
    price_compliance = (sourced_price_count / price_count) if price_count > 0 else 1.0

    # AM5 - Tarih tazeliği
    current_year = datetime.datetime.now().year
    year_mentions = re.findall(r'\b(20\d{2})\b', text)
    fresh_years = [y for y in year_mentions if current_year - int(y) <= 1]
    date_freshness = len(fresh_years) / max(len(year_mentions), 1)

    # AM6 - Heading hiyerarşisi
    headings = extract_headings(html)
    h1_count = len(headings.get('h1', []))
    h2_count = len(headings.get('h2', []))
    h3_count = len(headings.get('h3', []))
    heading_valid = (
        h1_count == 1 and
        8 <= h2_count <= 12 and
        h3_count >= 8
    )
    heading_issues = []
    if h1_count != 1:
        heading_issues.append(f"H1 sayısı: {h1_count} (beklenen: 1)")
    if h2_count < 8:
        heading_issues.append(f"H2 sayısı: {h2_count} (min: 8)")
    if h3_count < 8:
        heading_issues.append(f"H3 sayısı: {h3_count} (min: 8)")

    # AM7 - Kelime sayısı
    word_count = count_words(text)

    # AM8 - İç link yoğunluğu
    internal_links = count_internal_links(html)
    internal_link_density = (internal_links / word_count * 1000) if word_count > 0 else 0

    # AM9 - Schema varlığı
    has_schema = detect_schema(html)

    # AM10 - Tarihli kişisel referans
    personal_year_refs = re.findall(YEAR_PERSONAL_PATTERN, text_lower)
    personal_year_count = len(personal_year_refs)

    # AM11 - Negatif duygu ifadesi
    negative_count = sum(1 for k in NEGATIVE_SENTIMENT_KEYWORDS if k in text_lower)

    # AM12 - Turist tuzağı uyarısı
    tourist_trap_count = sum(1 for p in TOURIST_TRAP_PHRASES if p in text_lower)

    # AM13 - Dinamik içerik etiketi
    volatile_mentions = len(re.findall(PRICE_PATTERN, text_lower))
    labeled_volatile = len(re.findall(r'\(.*?(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\s*20\d{2}.*?\)', text_lower))
    dynamic_label_ratio = (labeled_volatile / volatile_mentions) if volatile_mentions > 0 else 1.0

    # AM14 - Ay-saat bazlı zamanlama
    timing_count = len(re.findall(
        r'(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık).{0,40}(\d{1,2}:\d{2}|sabah|öğle|akşam|saat)',
        text_lower
    ))

    # ToC
    has_toc = detect_toc(html, text)

    return {
        "AM1_forbidden_count": forbidden_count,
        "AM2_first_person_count": first_person_count,
        "AM3_passive_ratio": round(passive_ratio, 3),
        "AM4_price_compliance": round(price_compliance, 2),
        "AM4_price_count": price_count,
        "AM4_sourced_count": sourced_price_count,
        "AM5_date_freshness": round(date_freshness, 2),
        "AM6_heading_valid": heading_valid,
        "AM6_heading_issues": heading_issues,
        "AM6_h1": h1_count, "AM6_h2": h2_count, "AM6_h3": h3_count,
        "AM7_word_count": word_count,
        "AM8_internal_link_density": round(internal_link_density, 2),
        "AM8_internal_links": internal_links,
        "AM9_has_schema": has_schema,
        "AM9_has_toc": has_toc,
        "AM10_personal_year_refs": personal_year_count,
        "AM11_negative_count": negative_count,
        "AM12_tourist_trap_count": tourist_trap_count,
        "AM13_dynamic_label_ratio": round(dynamic_label_ratio, 2),
        "AM14_timing_count": timing_count,
    }


# ─── STAGE 3-5: AI YARGIÇLAR ────────────────────────────────────────────────

AUTHORITY_JUDGE_PROMPT = """Sen Yoldaolmak.com'un Otorite Yargıcısın.
Görevin: Aşağıdaki seyahat rehberini SADECE otorite ve güvenilirlik açısından değerlendirmek.

Değerlendirme kriterlerin:
1. Karşılaştırmalı analiz var mı? (şehir vs şehir, dönem vs dönem, fiyat karşılaştırması)
2. Tarihsel bağlam doğru ve spesifik mi? (yüzeysel değil, tarih + neden-sonuç bağı)
3. Güncel bilgi var mı? (son 12 ay içinde)
4. Yapısal bütünlük: tüm zorunlu bölümler mevcut mu?
5. Derinlik skoru: bilgi yüzeysel mi, gerçek insight mi?
6. Kaynak atıfları: fiyatlar, istatistikler kaynaklı mı?

Şunu da tespit et:
- "Neden bu makale var?" sorusuna cevap veriyor mu?
- "Rakip içerikten farkı ne?" belli mi?

Çıktı formatı (sadece JSON, başka hiçbir şey yazma):
{
  "authority_score": <0-100 arası tam sayı>,
  "signal_scores": {
    "comparative_analysis": <0-20>,
    "historical_context": <0-20>,
    "updated_facts": <0-20>,
    "structural_completeness": <0-15>,
    "depth_score": <0-15>,
    "source_citations": <0-10>
  },
  "risk_flags": ["...", "..."],
  "improvement_directives": ["...", "..."],
  "strengths": ["...", "..."]
}"""

NARRATIVE_JUDGE_PROMPT = """Sen Yoldaolmak.com'un Anlatı Yargıcısın.
Görevin: Aşağıdaki seyahat rehberini SADECE anlatı kalitesi ve kişisel ses açısından değerlendirmek.

Değerlendirme kriterlerin:
1. Birinci şahıs markerleri: "ben gittiğimde", "1995'te", "2019'da" gibi tarihli anekdotlar var mı?
2. Duyusal dil yoğunluğu: somut gözlem ve betimleme mi, yoksa soyut söylem mi?
3. Spesifik sahne referansları: o yere özgü detaylar mı, genel bilgi mi?
4. Jenerik sıfat yokluğu: "muhteşem", "harika" gibi boş kelimeler yerine ölçülebilir detay var mı?
5. Ses tutarlılığı: Kemal Kaya'nın samimi, eleştirel, karşılaştırmacı sesi korunuyor mu?

Kemal Kaya'nın sesi: Arkadaşça ama bilgili. Eleştirel ama yapıcı. Karşılaştırmacı. "Ben bunu denedim, şunu gördüm" der. "Ziyaretçilerini bekliyor" demez.

Çıktı formatı (sadece JSON, başka hiçbir şey yazma):
{
  "narrative_score": <0-100 arası tam sayı>,
  "signal_scores": {
    "first_hand_markers": <0-25>,
    "sensory_language": <0-20>,
    "specific_scene_refs": <0-20>,
    "no_generic_adjectives": <0-20>,
    "voice_consistency": <0-15>
  },
  "risk_flags": ["...", "..."],
  "improvement_directives": ["...", "..."],
  "strengths": ["...", "..."]
}"""

CRITICAL_JUDGE_PROMPT = """Sen Yoldaolmak.com'un Eleştirel Denge Yargıcısın.
Görevin: Aşağıdaki seyahat rehberini SADECE eleştirel denge açısından değerlendirmek.

Değerlendirme kriterlerin:
1. Net artı/eksi dengesi: her önemli yer veya karar için hem olumlu hem olumsuz nokta var mı?
2. Beklenti yönetimi: "Instagram'da şöyle görünür, gerçekte şudur" ayrımı yapılıyor mu?
3. Hedef kitle segmentasyonu: "Bu şehir X türden gezgin için değil" analizi var mı?
4. Abartılı/kaçınılması gereken yer uyarısı: turist tuzakları açıkça belirtilmiş mi?
5. Gerçek vs token eleştiri: "Biraz pahalı olabilir" (token) vs "Gondol turu 80€, değmez, alternatif vaporetto 7€" (gerçek)

"Kim için değil?" sorusuna cevap var mı?
"Ne beklentinizi düzeltmeli?" sorusuna cevap var mı?

Çıktı formatı (sadece JSON, başka hiçbir şey yazma):
{
  "critical_score": <0-100 arası tam sayı>,
  "signal_scores": {
    "pros_cons_balance": <0-25>,
    "expectation_management": <0-25>,
    "audience_segmentation": <0-20>,
    "overrated_flags": <0-15>,
    "real_vs_token_critique": <0-15>
  },
  "risk_flags": ["...", "..."],
  "improvement_directives": ["...", "..."],
  "strengths": ["...", "..."]
}"""



# OPT-5: tier belirleme icin auto-skor (0 API cagrısı)
def _auto_score(auto, pre):
    s = 60
    s -= auto['AM1_forbidden_count'] * 8
    if auto['AM10_personal_year_refs'] == 0:      s -= 20
    if not auto['AM6_heading_valid']:              s -= 12
    if not auto['AM9_has_schema']:                 s -= 5
    if auto['AM2_first_person_count'] < 3:        s -= 10
    if auto['AM12_tourist_trap_count'] == 0:      s -= 8
    if auto['AM4_price_compliance'] < 0.40 and auto['AM4_price_count'] > 0: s -= 15
    if not pre['passed']:                          s -= 20
    s += min(auto['AM2_first_person_count'] * 3, 15)
    s += min(auto['AM10_personal_year_refs'] * 5, 15)
    s += min(auto['AM12_tourist_trap_count'] * 4, 12)
    if auto['AM9_has_toc']:                        s += 5
    if auto['AM13_dynamic_label_ratio'] > 0.5:    s += 5
    return max(0, min(100, s))

def run_judge(judge_name: str, system_prompt: str, article_text: str) -> dict:
    """Tek bir yargıcı çalıştır, JSON döndür."""
    print(f"   ⚖️  {judge_name} değerlendiriyor...")

    # Metin çok uzunsa kırp (token limiti)
    max_chars = 12000
    if len(article_text) > max_chars:
        article_text = article_text[:max_chars] + "\n\n[...metin kısaltıldı...]"

    prompt = f"{system_prompt}\n\n---\n\nMAKALE:\n{article_text}"

    try:
        raw = ask_claude(prompt, max_tokens=1200)
        # JSON bloğunu çıkar
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {"error": "JSON parse edilemedi", "raw": raw[:200]}
    except Exception as e:
        return {"error": str(e)}


# ─── STAGE 6: SKOR HESAPLAMA ─────────────────────────────────────────────────

def calculate_scores(auto: dict, judge_a: dict, judge_b: dict, judge_c: dict) -> dict:
    """Auto-scan + 3 yargıç skorlarını birleştir, final hesapla."""

    # Yargıç ham skorları
    a_score = judge_a.get("authority_score", 50)
    b_score = judge_b.get("narrative_score", 50)
    c_score = judge_c.get("critical_score", 50)

    # Auto-scan ceza/bonus uygulaması
    # C2/C4 cap: fiyat uyumu düşükse otorite sınırla
    if auto["AM4_price_compliance"] < 0.40 and auto["AM4_price_count"] > 0:
        a_score = min(a_score, 50)

    # AF2: kişisel anekdot yoksa narrative cap
    if auto["AM10_personal_year_refs"] == 0:
        b_score = min(b_score, 45)

    # Heading sorunları varsa authority düşür
    if not auto["AM6_heading_valid"]:
        a_score = max(0, a_score - 8)

    # Schema yoksa authority küçük penaltı
    if not auto["AM9_has_schema"]:
        a_score = max(0, a_score - 5)

    # İlk şahıs zayıfsa narrative penaltı
    if auto["AM2_first_person_count"] < 3:
        b_score = max(0, b_score - 10)

    # Turist tuzağı uyarısı yoksa critical cap
    if auto["AM12_tourist_trap_count"] == 0:
        c_score = min(c_score, 55)

    # Ağırlıklı toplam
    total = (a_score * 0.40) + (b_score * 0.35) + (c_score * 0.25)

    return {
        "authority_score": round(a_score),
        "narrative_score": round(b_score),
        "critical_score": round(c_score),
        "total_score": round(total, 1),
    }


# ─── STAGE 7: VERDICT ────────────────────────────────────────────────────────

def determine_verdict(scores: dict, pre_check: dict) -> dict:
    total = scores["total_score"]

    if not pre_check["passed"]:
        return {
            "verdict": "YAYINLAMA",
            "action": "Ön kontrol başarısız — önce bu sorunları çöz",
            "publish_ready": False,
            "re_audit_required": True,
            "estimated_effort": "high",
        }

    if total >= 90:
        return {"verdict": "YAYINLA", "action": "Direkt yayın",
                "publish_ready": True, "re_audit_required": False, "estimated_effort": "none"}
    elif total >= 82:
        return {"verdict": "YAYINLA — KÜÇÜK DÜZELTME", "action": "Opsiyonel iyileştirme",
                "publish_ready": True, "re_audit_required": False, "estimated_effort": "low"}
    elif total >= 65:
        return {"verdict": "REVİZYON GEREKLİ", "action": "Zorunlu revizyon sonra yeniden audit",
                "publish_ready": False, "re_audit_required": True, "estimated_effort": "medium"}
    else:
        return {"verdict": "YAYINLAMA", "action": "Kapsamlı yeniden yazım gerekli",
                "publish_ready": False, "re_audit_required": True, "estimated_effort": "high"}


def build_revision_queue(scores: dict, judge_a: dict, judge_b: dict, judge_c: dict, auto: dict) -> list:
    """Öncelikli revizyon kuyruğu — etki büyüklüğüne göre sırala."""
    items = []

    # Yargıç direktifleri
    for directive in judge_a.get("improvement_directives", []):
        items.append({"source": "Authority Judge", "directive": directive, "weight": 0.40,
                      "gap": 100 - scores["authority_score"]})
    for directive in judge_b.get("improvement_directives", []):
        items.append({"source": "Narrative Judge", "directive": directive, "weight": 0.35,
                      "gap": 100 - scores["narrative_score"]})
    for directive in judge_c.get("improvement_directives", []):
        items.append({"source": "Critical Judge", "directive": directive, "weight": 0.25,
                      "gap": 100 - scores["critical_score"]})

    # Auto-scan kritik bulgular
    if auto["AM1_forbidden_count"] > 0:
        items.append({"source": "AUTO", "directive": f"Yasaklı kelime temizle ({auto['AM1_forbidden_count']} adet)",
                      "weight": 0.40, "gap": auto["AM1_forbidden_count"] * 15})
    if auto["AM10_personal_year_refs"] == 0:
        items.append({"source": "AUTO", "directive": "Tarihli kişisel anekdot ekle (örn: '2019'da gittiğimde')",
                      "weight": 0.35, "gap": 40})
    if auto["AM4_price_compliance"] < 0.6 and auto["AM4_price_count"] > 0:
        items.append({"source": "AUTO", "directive": f"Fiyatlara kaynak+tarih ekle — {auto['AM4_price_count']} fiyattan sadece {auto['AM4_sourced_count']} kaynaklı",
                      "weight": 0.40, "gap": 30})
    if auto["AM12_tourist_trap_count"] == 0:
        items.append({"source": "AUTO", "directive": "En az 1 turist tuzağı uyarısı + alternatif ekle",
                      "weight": 0.25, "gap": 35})
    if not auto["AM6_heading_valid"]:
        issues = ', '.join(auto["AM6_heading_issues"])
        items.append({"source": "AUTO", "directive": f"Başlık hiyerarşisini düzelt: {issues}",
                      "weight": 0.40, "gap": 20})

    # Öncelik skoru hesapla ve sırala
    for item in items:
        item["priority_score"] = item["weight"] * item["gap"]
    items.sort(key=lambda x: x["priority_score"], reverse=True)

    return [{"directive": i["directive"], "source": i["source"]} for i in items[:8]]


# ─── ANA AUDİT FONKSİYONU ────────────────────────────────────────────────────

def run_audit(url: str = None, html: str = None, text: str = None,
              post_id: int = None,
              content_type: str = "Destination_Guide") -> dict:
    """
    Ana audit fonksiyonu.
    URL veya (html, text) ikilisi kabul eder.
    """
    print("\n" + "=" * 65)
    print("⚖️  YOLDAOLMAK.COM — EDİTORYAL AUDİT KURULU")
    print("=" * 65)

    # OPT-5c: post_id (WP API) > html/text > url
    if post_id and not html:
        print(f"   📥 WP post cekiliyor (ID: {post_id})...")
        try:
            from wp import get_post, strip_html as _ws
            post = get_post(post_id)
            if post:
                rc = post.get("content", {})
                html = rc.get("rendered","") if isinstance(rc,dict) else str(rc)
                text = _ws(html)
                print(f"   ✅ Post alındı: {count_words(text):,} kelime")
            else:
                return {"error": f"Post {post_id} bulunamadı", "post_id": post_id}
        except Exception as e:
            return {"error": f"WP API: {e}", "post_id": post_id}
    elif url:
        print(f"   📥 URL cekiliyor: {url}")
        html, text = fetch_url_content(url)
        if not text or "cekilemedi" in text:
            return {"error": f"URL cekilemedi: {url}", "url": url}
        print(f"   ✅ Icerik alindi: {count_words(text):,} kelime")

    if not html:
        html = ""
    if not text:
        text = strip_html(html)

    print(f"\n📊 AŞAMA 1/5: Ön Kontrol...")
    pre = run_pre_check(text, html, content_type)
    status = "✅ GEÇTİ" if pre["passed"] else "❌ BAŞARISIZ"
    print(f"   {status} — {pre['word_count']:,} kelime, {pre['sections_found']}/9 bölüm")
    if pre["failures"]:
        for f in pre["failures"]:
            print(f"   ⛔ {f}")

    print(f"\n📊 AŞAMA 2/5: Otomatik Tarama...")
    auto = run_auto_scan(text, html)
    print(f"   Yasaklı kelime: {auto['AM1_forbidden_count']} | "
          f"1. şahıs: {auto['AM2_first_person_count']} | "
          f"Fiyat uyumu: %{int(auto['AM4_price_compliance']*100)} | "
          f"Kişisel anekdot: {auto['AM10_personal_year_refs']}")

    # OPT-5d: 3-tier sistem
    auto_score = _auto_score(auto, pre)
    print(f"\n   📊 Auto-skor: {auto_score}/100")
    if auto_score >= 65:
        print("   ✅ TIER 1: AI yargiç atlandı (0 API)")
        base = {"improvement_directives":[],"risk_flags":[],"strengths":[],"signal_scores":{}}
        judge_a = {**base, "authority_score": auto_score}
        judge_b = {**base, "narrative_score": auto_score}
        judge_c = {**base, "critical_score":  auto_score}
        tier = 1
    elif auto_score >= 40:
        print("   ⚠️  TIER 2: Narrative Judge (1 API)")
        judge_b = run_judge("Narrative Judge", NARRATIVE_JUDGE_PROMPT, text)
        base = {"improvement_directives":[],"risk_flags":[],"strengths":[],"signal_scores":{}}
        judge_a = {**base, "authority_score": auto_score}
        judge_c = {**base, "critical_score":  auto_score}
        tier = 2
    else:
        print("   ❌ TIER 3: 3 yargiç (3 API)")
        judge_a = run_judge("Authority Judge", AUTHORITY_JUDGE_PROMPT, text)
        judge_b = run_judge("Narrative Judge", NARRATIVE_JUDGE_PROMPT, text)
        judge_c = run_judge("Critical Judge",  CRITICAL_JUDGE_PROMPT,  text)
        tier = 3
    print(f"   📊 Skor hesaplaniyor (Tier {tier})...")
    scores = calculate_scores(auto, judge_a, judge_b, judge_c)
    verdict = determine_verdict(scores, pre)
    revision_queue = build_revision_queue(scores, judge_a, judge_b, judge_c, auto)

    # Risk flagleri birleştir
    all_risk_flags = (
        judge_a.get("risk_flags", []) +
        judge_b.get("risk_flags", []) +
        judge_c.get("risk_flags", [])
    )

    # Güçlü yönler
    all_strengths = (
        judge_a.get("strengths", []) +
        judge_b.get("strengths", []) +
        judge_c.get("strengths", [])
    )

    # Auto-fail kontrol
    auto_fails = []
    if auto["AM1_forbidden_count"] >= 3:
        auto_fails.append(f"AF1: {auto['AM1_forbidden_count']} yasaklı kelime")
    if auto["AM10_personal_year_refs"] == 0:
        auto_fails.append("AF2: Tarihli kişisel anekdot yok")
    if auto["AM7_word_count"] < pre["word_floor"]:
        auto_fails.append(f"AF3: {auto['AM7_word_count']} kelime < {pre['word_floor']} minimum")
    if not pre["passed"] and pre["sections_missing"] >= 2:
        auto_fails.append(f"AF5: {pre['sections_missing']} zorunlu bölüm eksik")

    report = {
        "audit_version": "2.0",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "url": url or "(direkt metin)",
        "content_type": content_type,

        "pre_check": pre,
        "auto_scan": auto,

        "judge_authority": {
            "score": scores["authority_score"],
            "signal_scores": judge_a.get("signal_scores", {}),
            "risk_flags": judge_a.get("risk_flags", []),
            "improvement_directives": judge_a.get("improvement_directives", []),
            "strengths": judge_a.get("strengths", []),
        },
        "judge_narrative": {
            "score": scores["narrative_score"],
            "signal_scores": judge_b.get("signal_scores", {}),
            "risk_flags": judge_b.get("risk_flags", []),
            "improvement_directives": judge_b.get("improvement_directives", []),
            "strengths": judge_b.get("strengths", []),
        },
        "judge_critical": {
            "score": scores["critical_score"],
            "signal_scores": judge_c.get("signal_scores", {}),
            "risk_flags": judge_c.get("risk_flags", []),
            "improvement_directives": judge_c.get("improvement_directives", []),
            "strengths": judge_c.get("strengths", []),
        },

        "scores": {
            "authority": scores["authority_score"],
            "narrative": scores["narrative_score"],
            "critical": scores["critical_score"],
            "total": scores["total_score"],
            "formula": "total = (authority*0.40) + (narrative*0.35) + (critical*0.25)",
        },

        "verdict": verdict["verdict"],
        "action": verdict["action"],
        "publish_ready": verdict["publish_ready"],
        "re_audit_required": verdict["re_audit_required"],
        "estimated_revision_effort": verdict["estimated_effort"],

        "auto_fail_triggers": auto_fails,
        "risk_flags": all_risk_flags[:6],
        "strengths": all_strengths[:4],
        "revision_priority_queue": revision_queue,
    }

    return report


def print_audit_report(report: dict):
    """Terminal'e okunabilir özet yazdır."""
    print("\n" + "=" * 65)
    print("📋 AUDİT RAPORU")
    print("=" * 65)
    print(f"🔗 URL: {report.get('url', '-')}")
    print(f"📅 Tarih: {report.get('timestamp', '-')}")
    print(f"📂 Tip: {report.get('content_type', '-')}")

    print("\n─── SKORLAR ───────────────────────────────────────────────")
    scores = report.get("scores", {})
    print(f"  ⚖️  Otorite     : {scores.get('authority', 0):>3}/100")
    print(f"  📖 Anlatı      : {scores.get('narrative', 0):>3}/100")
    print(f"  🔍 Eleştirel   : {scores.get('critical', 0):>3}/100")
    print(f"  {'─'*30}")
    total = scores.get('total', 0)
    print(f"  🏆 TOPLAM      : {total:>5}/100")

    print("\n─── KARAR ─────────────────────────────────────────────────")
    verdict = report.get("verdict", "-")
    action = report.get("action", "-")
    effort = report.get("estimated_revision_effort", "-")
    ready = "✅ EVET" if report.get("publish_ready") else "❌ HAYIR"
    print(f"  Karar: {verdict}")
    print(f"  Aksiyon: {action}")
    print(f"  Yayına hazır: {ready}")
    print(f"  Revizyon yükü: {effort.upper()}")

    auto_fails = report.get("auto_fail_triggers", [])
    if auto_fails:
        print("\n─── AUTO-FAIL TETİKLEYİCİLER ──────────────────────────────")
        for f in auto_fails:
            print(f"  ⛔ {f}")

    print("\n─── ÖNCELİKLİ REVİZYON SIRALAMA ───────────────────────────")
    queue = report.get("revision_priority_queue", [])
    for i, item in enumerate(queue[:5], 1):
        source = item.get("source", "")
        directive = item.get("directive", "")
        print(f"  {i}. [{source}] {directive}")

    strengths = report.get("strengths", [])
    if strengths:
        print("\n─── GÜÇLÜ YÖNLER (KORU) ────────────────────────────────────")
        for s in strengths[:3]:
            print(f"  ✅ {s}")

    print("\n" + "=" * 65)


def save_report(report: dict, output_dir: str = "./reports") -> str:
    """Raporu JSON olarak kaydet."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # URL'den dosya adı üret
    url = report.get("url", "unknown")
    slug = re.sub(r'[^\w\-]', '_', url.split("//")[-1].replace("/", "_"))[:50]
    filename = f"audit_{slug}_{ts}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return filepath
