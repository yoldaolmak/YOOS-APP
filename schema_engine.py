"""
schema_engine.py v2.0 — Schema + FAQ Block Engine

v2.0 değişiklikleri:
  - TravelGuide → Article schema (Google rich snippet uyumlu)
  - FAQPage: doğru @context, acceptedAnswer/@type: Answer
  - FAQ system prompt: gerçekçi cevaplar, Kemal sesi, somut veriler
  - WHERE modu soru seti: ulaşım/bütçe/zaman odaklı
  - Türkiye: vize/saat farkı/kur soruları çıkarılır (is_turkey kontrolü)
  - Fallback cevaplar: somutlaştırıldı
  - ask_gpt → ask_gpt_mini (FAQ jenerik, mini yeter)
  - max_tokens: 1200 → 1400
"""

import re
import json
import datetime
from typing import Optional
from multi_ai import ask_gpt_mini


# ═══════════════════════════════════════════════════════════════════════════════
# TÜRKÇE SES UYUMU
# ═══════════════════════════════════════════════════════════════════════════════

_FRONT_V   = set('eiöüEİÖÜ')
_BACK_V    = set('aıouAIOU')
_ALL_V     = _FRONT_V | _BACK_V
_VOICELESS = set('çfhkpsştÇFHKPSŞT')


def _last_vowel(word: str) -> str:
    for ch in reversed(word):
        if ch in _ALL_V:
            return ch.lower()
    return 'e'


def _is_front(word: str) -> bool:
    return _last_vowel(word) in {c.lower() for c in _FRONT_V}


def _ends_voiceless(word: str) -> bool:
    return word[-1].lower() in {c.lower() for c in _VOICELESS}


def _ends_vowel(word: str) -> bool:
    return word[-1].lower() in {c.lower() for c in _ALL_V}


def tr_loc(word: str) -> str:
    f = _is_front(word); v = _ends_voiceless(word)
    s = ('te' if v else 'de') if f else ('ta' if v else 'da')
    return f"{word}'{s}"


def tr_abl(word: str) -> str:
    f = _is_front(word); v = _ends_voiceless(word)
    s = ('ten' if v else 'den') if f else ('tan' if v else 'dan')
    return f"{word}'{s}"


def tr_gen(word: str) -> str:
    lv = _last_vowel(word)
    if _ends_vowel(word):
        m = {'a':'nın','ı':'nın','e':'nin','i':'nin','o':'nun','u':'nun','ö':'nün','ü':'nün'}
    else:
        m = {'a':'ın','ı':'ın','e':'in','i':'in','o':'un','u':'un','ö':'ün','ü':'ün'}
    return f"{word}'{m.get(lv,'in')}"


def tr_acc(word: str) -> str:
    lv = _last_vowel(word)
    if _ends_vowel(word):
        m = {'a':'yı','ı':'yı','e':'yi','i':'yi','o':'yu','u':'yu','ö':'yü','ü':'yü'}
    else:
        m = {'a':'ı','ı':'ı','e':'i','i':'i','o':'u','u':'u','ö':'ü','ü':'ü'}
    return f"{word}'{m.get(lv,'i')}"


# ═══════════════════════════════════════════════════════════════════════════════
# TÜRKİYE TESPİT + YASAKLI KONULAR
# ═══════════════════════════════════════════════════════════════════════════════

_TURKEY_CITIES = {
    'İstanbul','Ankara','İzmir','Antalya','Bursa','Kapadokya',
    'Pamukkale','Efes','Bodrum','Marmaris','Fethiye','Trabzon',
    'Erzurum','Konya','Gaziantep','Şanlıurfa','Van','Diyarbakır',
    'Alanya','Kemer','Belek','Side','Kuşadası','Çeşme','Nevşehir','Türkiye',
}

def is_turkey(city: str, country: str = '') -> bool:
    return (
        city in _TURKEY_CITIES or
        'türkiye' in country.lower() or
        'turkey' in country.lower()
    )

_TURKEY_BANNED_RE = re.compile(
    r"(vize\b|visa\b|pasaport|saat\s+fark|zaman\s+fark|para\s+birimi"
    r"|döviz|kur(?:u|lar)?\b|kimlikle|kimlik\s+ile"
    r"|türk\s+liras|tl\s+ile"
    r"|türkiye['\"]?\s*(?:ye|den|de|dan)"
    r"|nasıl\s+gidilir.{0,30}türkiye)",
    re.IGNORECASE
)

def is_banned_qa(question: str) -> bool:
    return bool(_TURKEY_BANNED_RE.search(question))


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA BLOK TESPİT / TEMİZLEME
# ═══════════════════════════════════════════════════════════════════════════════

_SCHEMA_MARKERS = ['"FAQPage"', 'yoa-faq-schema', 'yoldaolmak-faq-schema', 'application/ld+json']

def has_schema_block(html: str) -> bool:
    return any(marker in html for marker in _SCHEMA_MARKERS)


def remove_schema_block(html: str) -> str:
    block_re = re.compile(r'<!-- wp:html -->.*?<!-- /wp:html -->', re.DOTALL)
    def keep_block(m: re.Match) -> str:
        return '' if any(marker in m.group() for marker in _SCHEMA_MARKERS) else m.group()
    result = block_re.sub(keep_block, html)
    result = re.sub(
        r'<script\s+type=["\']application/ld\+json["\']>.*?</script>',
        '', result, flags=re.DOTALL
    )
    return result.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# GPT FAQ ÜRETİMİ
# ═══════════════════════════════════════════════════════════════════════════════

_FAQ_GPT_SYSTEM = """Görev: Türkçe seyahat SSS üret. Yazar: Kemal Kaya, yoldaolmak.com.

ÇIKTI FORMATI (başka hiçbir şey döndürme, markdown/``` YASAK):
{"faq": [{"q": "soru?", "a": "cevap."}, ...]}

CEVAP KURALLARI:
- 2-4 kısa cümle, somut ve sayısal
- 1. tekil şahıs: "Ben öneririm", "Bana göre", "Gittiğimde"
- Fiyatlar: € + kaynak + yıl (örn. "Numbeo 2026", "Google Flights Ocak 2026")
- Eksi yönleri de yaz — beklenti ayarı
- YASAK: muhteşem, harika, mükemmel, inanılmaz, cennet

ÖRNEK (gerçekçi cevap tonu):
{"faq": [
  {"q": "Prag pahalı mı?",
   "a": "Batı Avrupa'ya göre %30-40 ucuz ama İstanbul'a göre pahalı. Backpacker 45-55€/gün, orta segment 90-130€, konforlu 160€+ (Numbeo 2026). Turistik bölge restoranlarında yemek 15-25€, yerel semtlerde 8-12€."},
  {"q": "Prag'a nasıl gidilir?",
   "a": "İstanbul'dan THY veya Pegasus direkt sefer var, 2h 30dk, 80-220€ (Google Flights Ocak 2026). Václav Havel Havalimanı'ndan merkeze Metro A hattıyla 30 dk, 1.5€. Gece iniş yapıyorsan taksi 20-25€."},
  {"q": "Prag ne zaman gidilir?",
   "a": "Nisan-Mayıs ve Eylül-Ekim hem hava hem kalabalık açısından en iyi dönemler. Temmuz-Ağustos kalabalık ve pahalı. Aralık-Ocak Noel pazarı için güzel ama soğuk (-5/-10°C)."},
  {"q": "Prag'da kaç gün gerekir?",
   "a": "3 tam gün yeterli, 4. gün çevre kasabalar için kullanılabilir. Eski şehir (Staré Město) 1 günde, Hrad bölgesi (Prag Kalesi) yarım gün. Günübirlikçi için 1 gün yetmez, sabah erken başlamalısın."}
]}"""


def generate_faq_pairs(city: str, city_en: str, country: str, country_en: str,
                       post_summary: str, is_turkey_dest: bool,
                       mode: str = "guide") -> list[dict]:
    loc = tr_loc(city); abl = tr_abl(city)
    gen = tr_gen(city); acc = tr_acc(city)

    turkey_block = ""
    if is_turkey_dest:
        turkey_block = """
YASAK SORULAR — Türkiye iç destinasyonu, şunları YAZMA:
- Vize / pasaport / kimlikle giriş
- Saat farkı / zaman dilimi
- Para birimi / döviz / TL kuru
- "Türkiye'ye nasıl gidilir" tarzı sorular
Bu sorular yerine: yerel yemekler, konaklama semtleri, gün sayısı, mevsim öner.
"""

    if mode == "where":
        questions = f"""WHERE modu — ulaşım ve pratik bilgi odaklı 10 soru:
1. {city} nerede? (kıta/ülke/bölge, somut konum)
2. {loc} nasıl gidilir? (en hızlı yol + İstanbul'dan uçuş süresi + fiyat tahmini)
3. {gen} en yakın havalimanı hangisi? (kod + merkeze mesafe/süre)
4. Havalimanından {city} merkezine nasıl gidilir? (tüm seçenekler + fiyat)
5. {city} için kaç gün yeterli? (minimum + ideal + detaylı)
6. {city} pahalı mı? (3 bütçe seviyesi: backpacker/orta/konforlu, €/gün)
7. {loc} ulaşım nasıl? (toplu taşıma ağı + tavsiye)
8. {city} ne zaman gidilir? (en iyi ay + neden + kaçınılacak dönem)
9. {loc} ne yenir? (2-3 spesifik yerel lezzet + fiyat)
10. {abl} günübirlik nereye gidilebilir? (1-2 somut öneri + süre)"""
        if not is_turkey_dest:
            questions += f"\n11. Türk vatandaşları {acc} vizesiz girebilir mi? (güncel durum + büyükelçilik uyarısı)"
    else:
        questions = f"""GUIDE modu — genel seyahat odaklı 10 soru:
1. {loc} kaç gün kalınır? (minimum + ideal + detaylı)
2. {city} pahalı mı? (3 bütçe seviyesi + günlük € tahmini)
3. {city} ne zaman gidilir? (en iyi mevsim + neden + kaçınılacak dönem)
4. {loc} ulaşım nasıl? (toplu taşıma + bilet + öneri)
5. {gen} en güzel semti neresi? (somut semt adı + neden)
6. {loc} ne yenir? (2-3 yerel lezzet + fiyat)
7. {loc} dil sorunu yaşanır mı? (pratik bilgi)
8. {gen} en önemli turistik yeri hangisi? (1-2 yer + neden önemli)
9. {abl} günübirlik nereye gidilebilir? (somut öneri + süre)
10. {"Türk vatandaşları için vize durumu nedir? (güncel + büyükelçilik uyarısı)" if not is_turkey_dest else loc + " en iyi hangi semtte konaklarım? (somut semt + neden)"}"""

    prompt = f"""Şehir: {city} ({city_en}), {country} ({country_en})

TÜRKÇE ÇEKİMLER (kullan):
  {loc} | {abl} | {gen} | {acc}

{turkey_block}
{questions}

Kaynak içerik (spesifik bilgi al, genel bilgiyle destekle):
{post_summary[:600]}

ZORUNLU: Sadece JSON döndür. 10-11 soru-cevap çifti."""

    raw = ask_gpt_mini(prompt, system=_FAQ_GPT_SYSTEM, max_tokens=1400, temperature=0.70)

    try:
        clean = re.sub(r'```(?:json)?\s*', '', raw).strip()
        m = re.search(r'\{[\s\S]*\}', clean)
        if m:
            data = json.loads(m.group())
            pairs = data.get('faq', [])
            if is_turkey_dest:
                pairs = [p for p in pairs if not is_banned_qa(p.get('q', ''))]
            if len(pairs) >= 5:
                return pairs
    except Exception as e:
        print(f"   ⚠️  FAQ JSON parse hatası: {e}")

    return _fallback_pairs(city, loc, abl, gen, acc, is_turkey_dest, mode=mode)


def _fallback_pairs(city, loc, abl, gen, acc, is_turkey_dest, mode='guide') -> list[dict]:
    """JSON parse başarısız olursa somut minimal Q&A seti."""
    year = datetime.date.today().year
    if mode == 'where':
        pairs = [
            {"q": f"{city} nerede?",
             "a": f"{city}, {gen} bölgesinde yer alan önemli bir destinasyon. Kesin konum için yoldaolmak.com gezi rehberine bakabilirsin."},
            {"q": f"{loc} nasıl gidilir?",
             "a": f"İstanbul'dan uçak en pratik yol. Aktarmalı sefer olabilir — Google Flights ile güncel fiyat için kalkış tarihinizi girin. Havalimanından merkeze toplu taşıma veya taksi seçeneği var."},
            {"q": f"{city} için kaç gün yeterli?",
             "a": f"Minimum 2-3 gün, ana noktalar için ideal 4-5 gün. Günübirlik çevre gezileri yapacaksan 1 gün daha ekle."},
            {"q": f"{city} pahalı mı?",
             "a": f"Backpacker: 40-60€/gün, orta segment: 80-120€, konforlu: 150€+ ({year} tahmini). Güncel fiyatlar için Numbeo'ya bak."},
            {"q": f"{city} ne zaman gidilir?",
             "a": f"İlkbahar (Nisan-Mayıs) ve sonbahar (Eylül-Ekim) hem hava hem kalabalık açısından dengeli. Yaz yoğun ve pahalı, kış bazı noktalar kapalı olabilir."},
            {"q": f"{loc} ulaşım nasıl?",
             "a": f"Merkezi bölgeler yürünebilir, geniş çaplı geziler için toplu taşıma önerilir. Araç kiralamak şehir içinde genellikle gereksiz."},
        ]
    else:
        pairs = [
            {"q": f"{loc} kaç gün kalınır?",
             "a": f"Minimum 3-4 gün. Merkezi noktalar için 2 gün, yerel semtler ve günübirlikler için 1-2 gün ekleyebilirsin."},
            {"q": f"{city} pahalı mı?",
             "a": f"Backpacker: 40-50€/gün, orta: 80-120€, konforlu: 150€+ ({year}). Batı Avrupa ortalamasına göre konuma bağlı değişiyor."},
            {"q": f"{city} ne zaman gidilir?",
             "a": f"Nisan-Mayıs ve Eylül-Ekim hem hava hem kalabalık açısından en dengeli dönemler. Yaz turist yoğunluğu çok, kış bazı çekim yerleri kapalı."},
            {"q": f"{gen} en önemli turistik yeri hangisi?",
             "a": f"Rehberde detaylı anlattım. Zamanın kısıtlıysa önce tarihi merkezden başla."},
            {"q": f"{abl} günübirlik nereye gidilebilir?",
             "a": f"Çevre şehirlere 1-2 saatlik bağlantılar var. Gezi planı bölümündeki önerilere bak."},
        ]
    if not is_turkey_dest:
        pairs.append({"q": f"Türk vatandaşları {acc} vizesiz girebilir mi?",
                      "a": f"Güncel vize ve giriş koşulları değişkenlik gösterebilir. Seyahatten önce {city} büyükelçiliğini veya Dışişleri Bakanlığı sitesini kontrol et."})
    return pairs


# ═══════════════════════════════════════════════════════════════════════════════
# HTML + JSON-LD ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════

def _faq_accordion_html(city: str, faq_pairs: list[dict]) -> str:
    """Styled details/summary akordeon FAQ kutusu."""
    items = []
    for p in faq_pairs:
        q = p.get('q', '').strip()
        a = p.get('a', '').strip()
        if not q or not a:
            continue
        items.append(
            f'<details style="margin:0;padding:0.85em 0;border-bottom:1px solid #ddd;">'
            f'<summary style="cursor:pointer;font-weight:700;font-size:0.97em;'
            f'color:#1a1a1a;list-style:none;padding-right:1.5em;">❓ {q}</summary>'
            f'<p style="margin:0.65em 0 0;color:#444;line-height:1.7;font-size:0.94em;">{a}</p>'
            f'</details>'
        )
    body = '\n'.join(items)
    return (
        f'<div class="yoa-faq-schema" '
        f'style="border:2px solid #0073aa;border-radius:10px;padding:24px 28px;'
        f'margin:2.5em 0;background:#f0f7ff;">'
        f'\n<h3 style="margin:0 0 18px;color:#0073aa;font-size:1.15em;font-weight:700;">'
        f'📋 {city} Hakkında Sık Sorulan Sorular</h3>'
        f'\n{body}'
        f'\n</div>'
    )


def _article_schema(city: str, city_en: str, country_en: str, url: str) -> dict:
    """
    Article schema — Google Search'te rich snippet üretir.
    TravelGuide Google'da tanınan bir @type değil, bu yüzden Article kullanıyoruz.
    """
    today = datetime.date.today()
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{city} Gezi Rehberi {today.year}",
        "description": (
            f"{city} gezi rehberi — gezilecek yerler, konaklama, nasıl gidilir ve "
            f"pratik bilgiler. Kemal Kaya, yoldaolmak.com"
        ),
        "url": url,
        "dateModified": today.strftime("%Y-%m-%d"),
        "datePublished": today.strftime("%Y-%m-%d"),
        "author": {
            "@type": "Person",
            "name": "Kemal Kaya",
            "url": "https://yoldaolmak.com/hakkimda"
        },
        "publisher": {
            "@type": "Organization",
            "name": "Yoldaolmak.com",
            "url": "https://yoldaolmak.com",
            "logo": {
                "@type": "ImageObject",
                "url": "https://yoldaolmak.com/wp-content/uploads/logo.png"
            }
        },
        "about": {
            "@type": "City",
            "name": city_en,
            "alternateName": city,
            "containedInPlace": {
                "@type": "Country",
                "name": country_en
            }
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": url
        }
    }


def _faqpage_schema(faq_pairs: list[dict]) -> dict:
    """FAQPage JSON-LD — Google rich snippet üretir."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": p.get('q', '').strip(),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": p.get('a', '').strip()
                }
            }
            for p in faq_pairs if p.get('q') and p.get('a')
        ]
    }


def build_schema_block(city: str, city_en: str, country_en: str,
                       faq_pairs: list[dict], url: str) -> str:
    """
    wp:html bloğu içinde:
    - Styled FAQ akordeon (kullanıcıya görünür)
    - Article JSON-LD (Google indexleme)
    - FAQPage JSON-LD (Google rich snippet)
    """
    accordion = _faq_accordion_html(city, faq_pairs)
    art_json  = json.dumps(_article_schema(city, city_en, country_en, url),
                           ensure_ascii=False, indent=2)
    faq_json  = json.dumps(_faqpage_schema(faq_pairs),
                           ensure_ascii=False, indent=2)
    inner = (
        f'{accordion}\n'
        f'<script type="application/ld+json">\n{art_json}\n</script>\n'
        f'<script type="application/ld+json">\n{faq_json}\n</script>'
    )
    return f'<!-- wp:html -->\n{inner}\n<!-- /wp:html -->'


# ═══════════════════════════════════════════════════════════════════════════════
# ANA ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_schema_block(city: str, city_en: str, country: str, country_en: str,
                          post_summary: str, post_slug: str,
                          is_turkey_dest: bool, mode: str = "guide") -> str:
    """
    Tam schema bloğunu üret.
    mode: "guide" | "where"
    """
    print("   🟣 Schema + FAQ bloğu üretiliyor (GPT-mini)...")
    from wp import get_site_url
    base_url = get_site_url().rstrip('/')
    url = f"{base_url}/{post_slug}/"

    faq_pairs = generate_faq_pairs(
        city=city, city_en=city_en,
        country=country, country_en=country_en,
        post_summary=post_summary,
        is_turkey_dest=is_turkey_dest,
        mode=mode
    )
    block = build_schema_block(
        city=city, city_en=city_en, country_en=country_en,
        faq_pairs=faq_pairs, url=url
    )
    print(f"   ✅ {len(faq_pairs)} SSS çifti oluşturuldu")
    return block


# ── CITY_META mini tablo (run_schema_mode için) ────────────────────────────────
_CITY_META = {
    "Bosna Hersek": ("Bosnia and Herzegovina", "Bosna Hersek",    "Bosnia and Herzegovina"),
    "Saraybosna":   ("Sarajevo",               "Bosna Hersek",    "Bosnia and Herzegovina"),
    "Mostar":       ("Mostar",                 "Bosna Hersek",    "Bosnia and Herzegovina"),
    "Prag":         ("Prague",                 "Çek Cumhuriyeti", "Czech Republic"),
    "Brno":         ("Brno",                   "Çek Cumhuriyeti", "Czech Republic"),
    "Viyana":       ("Vienna",                 "Avusturya",       "Austria"),
    "Budapeşte":    ("Budapest",               "Macaristan",      "Hungary"),
    "Varşova":      ("Warsaw",                 "Polonya",         "Poland"),
    "Krakow":       ("Krakow",                 "Polonya",         "Poland"),
    "Berlin":       ("Berlin",                 "Almanya",         "Germany"),
    "Münih":        ("Munich",                 "Almanya",         "Germany"),
    "Leipzig":      ("Leipzig",                "Almanya",         "Germany"),
    "Dresden":      ("Dresden",                "Almanya",         "Germany"),
    "Paris":        ("Paris",                  "Fransa",          "France"),
    "Lizbon":       ("Lisbon",                 "Portekiz",        "Portugal"),
    "Madrid":       ("Madrid",                 "İspanya",         "Spain"),
    "Barselona":    ("Barcelona",              "İspanya",         "Spain"),
    "Amsterdam":    ("Amsterdam",              "Hollanda",        "Netherlands"),
    "Roma":         ("Rome",                   "İtalya",          "Italy"),
    "Floransa":     ("Florence",               "İtalya",          "Italy"),
    "Venedik":      ("Venice",                 "İtalya",          "Italy"),
    "Atina":        ("Athens",                 "Yunanistan",      "Greece"),
    "Selanik":      ("Thessaloniki",           "Yunanistan",      "Greece"),
    "Dubrovnik":    ("Dubrovnik",              "Hırvatistan",     "Croatia"),
    "Zagreb":       ("Zagreb",                 "Hırvatistan",     "Croatia"),
    "Split":        ("Split",                  "Hırvatistan",     "Croatia"),
    "Belgrad":      ("Belgrade",               "Sırbistan",       "Serbia"),
    "Kotor":        ("Kotor",                  "Karadağ",         "Montenegro"),
    "Tiran":        ("Tirana",                 "Arnavutluk",      "Albania"),
    "Üsküp":        ("Skopje",                 "Kuzey Makedonya", "North Macedonia"),
    "İstanbul":     ("Istanbul",               "Türkiye",         "Turkey"),
    "Kapadokya":    ("Cappadocia",             "Türkiye",         "Turkey"),
    "Antalya":      ("Antalya",                "Türkiye",         "Turkey"),
    "İzmir":        ("Izmir",                  "Türkiye",         "Turkey"),
    "Konya":        ("Konya",                  "Türkiye",         "Turkey"),
    "Tokyo":        ("Tokyo",                  "Japonya",         "Japan"),
    "Bangkok":      ("Bangkok",                "Tayland",         "Thailand"),
    "Dubai":        ("Dubai",                  "BAE",             "UAE"),
    "Bali":         ("Bali",                   "Endonezya",       "Indonesia"),
    "Marakeş":      ("Marrakech",              "Fas",             "Morocco"),
    "Kahire":       ("Cairo",                  "Mısır",           "Egypt"),
    "New York":     ("New York",               "ABD",             "USA"),
}


def run_schema_mode(post: dict) -> tuple[str, str]:
    """
    --mode schema için ana fonksiyon.
    Post'u alır, schema bloğunu ekler veya günceller.
    """
    import html as _html_mod
    from wp import strip_html

    raw_title = post.get("title", {})
    title_str = raw_title.get("rendered", "") if isinstance(raw_title, dict) else str(raw_title)
    title_str = _html_mod.unescape(re.sub(r'<[^>]+>', '', title_str)).strip()

    raw_content = post.get("content", {})
    html_content = raw_content.get("rendered", "") if isinstance(raw_content, dict) else str(raw_content)
    post_summary = strip_html(html_content)
    post_slug    = post.get("slug", "")

    # Şehir tespiti
    city = "Bilinmiyor"
    m = re.match(r'^(.+?)\s+(?:Gezi Rehberi|Seyahat Rehberi)', title_str, re.IGNORECASE)
    if m:
        city = re.sub(r'\s*\(20\d{2}\)', '', m.group(1)).strip()
    elif title_str:
        city = title_str.split(':')[0].split('–')[0].split('(')[0].strip()

    meta = _CITY_META.get(city, (city, "Bilinmiyor", "Unknown"))
    city_en, country, country_en = meta
    is_turkey_dest = is_turkey(city, country)

    print(f"\n{'='*55}")
    print(f"🟣 SCHEMA ENGINE — Mode: schema")
    print(f"{'='*55}")
    print(f"📍 Şehir : {city} ({city_en})")
    print(f"🌍 Ülke  : {country} ({country_en})")
    print(f"🇹🇷 TR    : {'Evet — vize/kur/saat farkı yasak' if is_turkey_dest else 'Hayır'}")

    if has_schema_block(html_content):
        print("🔄 Mevcut schema siliniyor, yenisi üretiliyor...")
        html_content = remove_schema_block(html_content)
    else:
        print("➕ İlk kez ekleniyor...")

    new_block = generate_schema_block(
        city=city, city_en=city_en,
        country=country, country_en=country_en,
        post_summary=post_summary,
        post_slug=post_slug or (city.lower().replace(' ', '-') + "-gezi-rehberi"),
        is_turkey_dest=is_turkey_dest
    )

    if '<!-- SON GÜNCELLEME' in html_content:
        html_content = re.sub(r'(<!-- SON GÜNCELLEME)', f'\n{new_block}\n\n\\1', html_content)
    else:
        html_content = html_content.rstrip() + f'\n\n{new_block}'

    year = datetime.date.today().year
    new_title = re.sub(r'\(20\d{2}\)', f'({year})', title_str)
    if new_title == title_str and len(title_str) > 10:
        new_title = f"{title_str} ({year})"

    print(f"✅ Schema eklendi: {new_title}")
    print(f"{'='*55}\n")
    return new_title, html_content

