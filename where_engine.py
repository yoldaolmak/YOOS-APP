"""
where_engine.py v5.0 — WHERE Mode Engine

v5.0 değişiklikleri:
  - H SIRASI DÜZELTİLDİ: Giriş → Nerede → Nasıl Bir Yer → Nasıl Gidilir → Gezi Planı → Kapanış
  - Model: ask_gpt_strict (GPT-4o) → ask_gpt_mini_strict (GPT-4o-mini)
  - Polish: Claude Sonnet → Claude Haiku (3x ucuz)
  - System promptlar: voice.py v5.0 (~2150t, önceki ~5903t)

BAŞLIK HİYERARŞİSİ:
H1: {city} Nasıl Bir Yer? Nerede, Nasıl Gidilir ve Gezi Planı
  [Giriş — başlıksız, 4-5 para]             GPT-mini 1600t + Haiku polish
  H2: {city} Nerede 📍                       GPT-mini 800t  + mechanical
  H2: {city} Nasıl Bir Yer [?|flag]         GPT-mini 2800t + Haiku polish (p1-2)
  H2: {dest_abl} Nasıl Gidilir ✈️🚗          GPT-mini 2200t + mechanical
      H3: ✈️ {city} Ucuz Uçak Bileti        sabit blok
  H2: {city} Gezi Planı 🗓                   GPT-mini 2000t + mechanical
      H3: [Tip A: 3/5/7 | B: 1-2/3/4-5 | C: 1/2-3 gün]
  [Kapanış — başlıksız, 2 para]             GPT-mini 800t  + Haiku polish
  [Schema + FAQ block]

MALİYET TAHMİNİ (v5.0):
  GPT-4o-mini:  ~$0.008/article
  Claude Haiku: ~$0.003/article  (3 polish: Giriş + Nasıl p1-2 + Kapanış)
  GPT-mini FAQ: ~$0.001/article
  TOPLAM: ~$0.012/article  (önceki: ~$0.07)
"""

import re
import datetime
import html as _html_mod
from typing import Optional
from multi_ai import ask_gpt_mini_strict, ask_claude_polish, mechanical_only, get_session_cost
from voice import (
    SYS_WHERE_INTRO, SYS_WHERE_NASIL, SYS_WHERE_NEREDE,
    SYS_WHERE_GIDILIR, SYS_WHERE_PLAN, SYS_WHERE_KAPANIS,
    FORBIDDEN_WORDS_STR,
)


SEP = ('<!-- wp:separator -->'
       '<hr class="wp-block-separator has-alpha-channel-opacity"/>'
       '<!-- /wp:separator -->')

# ─── 5 statik uçak bileti linki ───────────────────────────────────────────────
_BILET_LINKS_TPL = """\
<!-- wp:heading {{"level":3}} -->
<h3 class="wp-block-heading"><strong>✈️ {city} Ucuz Uçak Bileti Bulma</strong></h3>
<!-- /wp:heading -->

<!-- wp:list -->
<ul class="wp-block-list"><!-- wp:list-item -->
<li>✈️ <a href="https://yoldaolmak.com/ucuz-ucak-bileti-nasil-alinir" target="_blank" rel="noopener"><em>Ucuz Uçak Bileti Nasıl Alınır</em></a></li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>✈️ <a href="https://yoldaolmak.com/ucak-bileti-kampanyalari-nasil-bulunur" target="_blank" rel="noopener"><em>Uçak Bileti Kampanyaları Nasıl Bulunur</em></a></li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>✈️ <a href="https://yoldaolmak.com/ucakta-en-iyi-koltuk-hangisi" target="_blank" rel="noopener"><em>Uçakta En İyi Koltuk Hangisi</em></a></li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>✈️ <a href="https://yoldaolmak.com/en-ucuz-ucak-bileti-ne-zaman-alinir" target="_blank" rel="noopener"><em>En Ucuz Uçak Bileti Ne Zaman Alınır</em></a></li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>✈️ <a href="https://yoldaolmak.com/en-ucuz-bilet-sunan-havayolu-firmalari" target="_blank" rel="noopener"><em>En Ucuz Bilet Sunan Havayolu Firmaları</em></a></li>
<!-- /wp:list-item --></ul>
<!-- /wp:list -->"""

# ─── Küçük / günübirlik destinasyonlar → 1/3 gün planı ──────────────────────
_SMALL_CITIES = {
    "Mostar", "Kotor", "Brno", "Selanik", "Konya", "Krakow",
    "Bergen", "Kopenhag", "Varşova",
}


# ═══════════════════════════════════════════════════════════════════════════════
# CITY META
# ═══════════════════════════════════════════════════════════════════════════════

_CITY_META = {
    "Bosna Hersek":  ("Bosnia and Herzegovina", "Bosna Hersek",    "Bosnia and Herzegovina", "🇧🇦"),
    "Saraybosna":    ("Sarajevo",               "Bosna Hersek",    "Bosnia and Herzegovina", "🇧🇦"),
    "Mostar":        ("Mostar",                 "Bosna Hersek",    "Bosnia and Herzegovina", "🇧🇦"),
    "Dubrovnik":     ("Dubrovnik",              "Hırvatistan",     "Croatia",                "🇭🇷"),
    "Zagreb":        ("Zagreb",                 "Hırvatistan",     "Croatia",                "🇭🇷"),
    "Split":         ("Split",                  "Hırvatistan",     "Croatia",                "🇭🇷"),
    "Belgrad":       ("Belgrade",               "Sırbistan",       "Serbia",                 "🇷🇸"),
    "Kotor":         ("Kotor",                  "Karadağ",         "Montenegro",             "🇲🇪"),
    "Tiran":         ("Tirana",                 "Arnavutluk",      "Albania",                "🇦🇱"),
    "Üsküp":         ("Skopje",                 "Kuzey Makedonya", "North Macedonia",        "🇲🇰"),
    "Prag":          ("Prague",                 "Çek Cumhuriyeti", "Czech Republic",         "🇨🇿"),
    "Brno":          ("Brno",                   "Çek Cumhuriyeti", "Czech Republic",         "🇨🇿"),
    "Viyana":        ("Vienna",                 "Avusturya",       "Austria",                "🇦🇹"),
    "Budapeşte":     ("Budapest",               "Macaristan",      "Hungary",                "🇭🇺"),
    "Varşova":       ("Warsaw",                 "Polonya",         "Poland",                 "🇵🇱"),
    "Krakow":        ("Krakow",                 "Polonya",         "Poland",                 "🇵🇱"),
    "Berlin":        ("Berlin",                 "Almanya",         "Germany",                "🇩🇪"),
    "Münih":         ("Munich",                 "Almanya",         "Germany",                "🇩🇪"),
    "Leipzig":       ("Leipzig",                "Almanya",         "Germany",                "🇩🇪"),
    "Dresden":       ("Dresden",                "Almanya",         "Germany",                "🇩🇪"),
    "Paris":         ("Paris",                  "Fransa",          "France",                 "🇫🇷"),
    "Lizbon":        ("Lisbon",                 "Portekiz",        "Portugal",               "🇵🇹"),
    "Madrid":        ("Madrid",                 "İspanya",         "Spain",                  "🇪🇸"),
    "Barselona":     ("Barcelona",              "İspanya",         "Spain",                  "🇪🇸"),
    "Amsterdam":     ("Amsterdam",              "Hollanda",        "Netherlands",            "🇳🇱"),
    "Roma":          ("Rome",                   "İtalya",          "Italy",                  "🇮🇹"),
    "Floransa":      ("Florence",               "İtalya",          "Italy",                  "🇮🇹"),
    "Venedik":       ("Venice",                 "İtalya",          "Italy",                  "🇮🇹"),
    "Atina":         ("Athens",                 "Yunanistan",      "Greece",                 "🇬🇷"),
    "Selanik":       ("Thessaloniki",           "Yunanistan",      "Greece",                 "🇬🇷"),
    "İstanbul":      ("Istanbul",               "Türkiye",         "Turkey",                 "🇹🇷"),
    "Kapadokya":     ("Cappadocia",             "Türkiye",         "Turkey",                 "🇹🇷"),
    "Antalya":       ("Antalya",                "Türkiye",         "Turkey",                 "🇹🇷"),
    "İzmir":         ("Izmir",                  "Türkiye",         "Turkey",                 "🇹🇷"),
    "Konya":         ("Konya",                  "Türkiye",         "Turkey",                 "🇹🇷"),
    "Tokyo":         ("Tokyo",                  "Japonya",         "Japan",                  "🇯🇵"),
    "Osaka":         ("Osaka",                  "Japonya",         "Japan",                  "🇯🇵"),
    "Bangkok":       ("Bangkok",                "Tayland",         "Thailand",               "🇹🇭"),
    "Hanoi":         ("Hanoi",                  "Vietnam",         "Vietnam",                "🇻🇳"),
    "Ho Chi Minh":   ("Ho Chi Minh City",       "Vietnam",         "Vietnam",                "🇻🇳"),
    "Bali":          ("Bali",                   "Endonezya",       "Indonesia",              "🇮🇩"),
    "Dubai":         ("Dubai",                  "BAE",             "UAE",                    "🇦🇪"),
    "Kahire":        ("Cairo",                  "Mısır",           "Egypt",                  "🇪🇬"),
    "Marakeş":       ("Marrakech",              "Fas",             "Morocco",                "🇲🇦"),
    "New York":      ("New York",               "ABD",             "USA",                    "🇺🇸"),
    "Bergen":        ("Bergen",                 "Norveç",          "Norway",                 "🇳🇴"),
    "Oslo":          ("Oslo",                   "Norveç",          "Norway",                 "🇳🇴"),
    "Kopenhag":      ("Copenhagen",             "Danimarka",       "Denmark",                "🇩🇰"),
    "Stockholm":     ("Stockholm",              "İsveç",           "Sweden",                 "🇸🇪"),
    "Helsinki":      ("Helsinki",               "Finlandiya",      "Finland",                "🇫🇮"),
    "Brüksel":       ("Brussels",               "Belçika",         "Belgium",                "🇧🇪"),
    "Cape Town":     ("Cape Town",              "Güney Afrika",    "South Africa",           "🇿🇦"),
    "Johannesburg":  ("Johannesburg",           "Güney Afrika",    "South Africa",           "🇿🇦"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ═══════════════════════════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    text = text.replace('\u0130', 'i').replace('I', 'i')
    return (text.lower()
            .replace(' ', '-')
            .replace('\u0131', 'i').replace('\u015f', 's').replace('\u011f', 'g')
            .replace('\xfc', 'u').replace('\xf6', 'o').replace('\xe7', 'c')
            .replace('\xe2', 'a').replace('\xee', 'i').replace('\xfb', 'u'))


def _city_from_slug(slug: str) -> Optional[str]:
    slug = slug.lower()
    for city in _CITY_META:
        if _slugify(city) in slug:
            return city
    return None


def _strip_html(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    text = _html_mod.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def _context(html: str, city: str, max_chars: int = 1200) -> str:
    """Mevcut içerikten sayısal verileri çıkar."""
    text = _strip_html(html)
    nums = re.findall(r'\d[\d.,]*(?:\s*(?:€|TL|km|saat|dk|yıl|m²|°C|NOK|USD))?', text)
    num_block = " | ".join(nums[:10]) if nums else ""
    header = f"[{city} mevcut sayısal veriler: {num_block}]\n" if num_block else ""
    return header + text[:max_chars]


def _fix_bold(html: str) -> str:
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)


def _clean_artifacts(html: str) -> str:
    html = re.sub(r'\[BOLUM-\d\]\n?', '', html)
    html = re.sub(r'^── .+? ──\n?', '', html, flags=re.MULTILINE)
    html = re.sub(r'^(GÖREV:|ÇIKTI|MEVCUT|İÇ LİNK|SON KURAL).*\n?', '', html, flags=re.MULTILINE)
    return html


def _ensure_wp_wrap(html: str) -> str:
    """wp:paragraph wrapper olmayan <p> taglarını düzelt."""
    lines = html.split('\n')
    result = []
    for line in lines:
        s = line.strip()
        if re.match(r'^<p[^>]*>', s) and (not result or '<!-- wp:paragraph -->' not in result[-1]):
            result += ['<!-- wp:paragraph -->', line, '<!-- /wp:paragraph -->']
        elif re.match(r'^<h2[^>]*>', s) and (not result or '<!-- wp:heading -->' not in result[-1]):
            result += ['<!-- wp:heading -->', line, '<!-- /wp:heading -->']
        elif re.match(r'^<h3[^>]*>', s) and (not result or '<!-- wp:heading' not in result[-1]):
            result += ['<!-- wp:heading {"level":3} -->', line, '<!-- /wp:heading -->']
        else:
            result.append(line)
    return '\n'.join(result)


def _token_log(label: str, cost_before: dict, cost_after: dict) -> None:
    """Bölüm tamamlandıktan sonra token tüketimini logla."""
    inp  = cost_after.get('input_tokens', 0)  - cost_before.get('input_tokens', 0)
    out  = cost_after.get('output_tokens', 0) - cost_before.get('output_tokens', 0)
    usd  = cost_after.get('total_usd', 0.0)   - cost_before.get('total_usd', 0.0)
    print(f"     📊 {label}: in={inp} out={out} ~${usd:.4f}")


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM ÜRETİCİLERİ
# Her bölüm: ask_gpt_mini_strict (GPT-4o-mini, fallback YOK) + Haiku polish
# Polish    : ask_claude_polish (Sonnet, sadece giriş + nasıl gidilir)
# ═══════════════════════════════════════════════════════════════════════════════

def _gen_intro(city: str, city_en: str, country: str, context: str) -> str:
    """Giriş + Kişisel Bakış (4-5 para, başlıksız) → GPT üretir, Sonnet polish eder."""
    prompt = f"""Şehir: {city} ({city_en}), {country}
{f"Mevcut veriler: {context}" if context else ""}

{city} için 4-5 başlıksız giriş + kişisel bakış paragrafı yaz.

• Para 1: <strong>{city}</strong> ile BAŞLA.
  Konum bilgisini ANLATıSAL COĞRAFYA diliyle ver — "Balkanların ortasında" ✅
  km mesafesi / uçuş süresi / havalimanı kodu YASAK (bunlar Nasıl Gidilir'de).
  SEO: ilk 60 kelimede "{city} nerede" doğal geçmeli.

• Para 2: Genius Loci — şehrin gerçek ruhu. Duyusal gözlem (koku/ışık/ses/doku).
  Pratik paradoks ya da şaşırtıcı gerçek. Broşür dili YASAK.

• Para 3-5: Kişisel Bakış — başlık KULLANMA, anlatıya yedir.
  "Ben {city}'e..." tonu. Artı+eksi aynı anlatı içinde.
  Son paragrafta beklenti ayarı — abartma.

YASAK: Ansiklopedik açılış | Geniş zamanlı genel anlatı | km/uçuş | Broşür dili
FORMAT: Sadece Gutenberg HTML paragrafları. Başlık, separator YOK."""
    raw = ask_gpt_mini_strict(prompt, system=SYS_WHERE_INTRO, max_tokens=1600, temperature=0.90)
    return ask_claude_polish(raw, section_label="Giriş")


def _gen_nasil_bir_yer(city: str, city_en: str, country: str,
                        nasil_baslik: str, context: str, is_turkey: bool) -> str:
    """Nasıl Bir Yer H2 + 9 paragraf → GPT üretir, Sonnet polish eder."""
    vize = ("" if is_turkey
            else "\n  Para 9 sonunda: Türk vatandaşları için vize 1 cümle (büyükelçilik uyarısı).")
    prompt = f"""Şehir: {city} ({city_en}), {country}
{f"Veriler: {context}" if context else ""}

Birebir bu H2 başlığıyla başla:
<!-- wp:heading --><h2 class="wp-block-heading"><strong>{nasil_baslik}</strong></h2><!-- /wp:heading -->

9 paragraf yaz — LİSTE YASAK | İÇ LİNK YASAK | ANSİKLOPEDİK DİL YASAK
"Ben" dili zorunlu. Her paragrafta en az 1 <strong> bold öbek.

Para 1 — KONUM VE COĞRAFYA (100-120 kw):
  Kıta, ülke, bölge, denize/dağa/nehre yakınlık. Coğrafyanın şehrin karakterine etkisi.

Para 2 — KISA TARİH (100-120 kw):
  Hangi medeniyetler geçmiş, 2-3 somut tarih/yıl. Mimari katmanlar, tarihsel miras.

Para 3 — İKLİM VE EN İYİ ZAMAN (80-100 kw):
  Mevsimler, ne zaman gidilmeli/gidilmemeli? İdeal dönem + fiyat avantajı.

Para 4 — GÜVENLİK (70-90 kw):
  Tek başına güvenli mi? Kaçınılacak bölgeler. Kadın gezginler için somut not.

Para 5 — BÜTÇE VE PAHALILIK (90-110 kw):
  Yeme-içme, konaklama, ulaşım — somut € rakamları + kaynak + tarih. Günlük ortalama.

Para 6 — GEZMEK KOLAY MI, ZOR MU? (80-100 kw):
  Yürünebilirlik, toplu taşıma, araç kiralama, trafik.

Para 7 — MUTFAK VE YEMEK KÜLTÜRÜ (90-110 kw):
  Ne yenir/içilir, sokak lezzetleri, fiyatlar, turistik tuzaklar.

Para 8 — KARAKTERİ VE RUHU / GENIUS LOCI (90-110 kw):
  Şehir sana ne hissettiriyor? Romantik mi, enerjik mi, melankolik mi? Kim için?

Para 9 — BEKLENTİ AYARI VE ÖZET (90-110 kw):
  Kimler gelmeli, kimler gelmemeli? Eksileri açıkça söyle, abartma.{vize}"""
    raw = ask_gpt_mini_strict(prompt,
                         system=SYS_WHERE_NASIL.replace("{nasil_baslik}", nasil_baslik),
                         max_tokens=2800, temperature=0.80)
    # Para 1-2 (coğrafya+tarih) → Claude polish (ses kritik)
    # Para 3-9 (iklim/güvenlik/bütçe/vb.) → mechanical only
    paras = re.findall(r'<!-- wp:paragraph -->.*?<!-- /wp:paragraph -->', raw, re.DOTALL)
    if len(paras) >= 2:
        h2_match = re.search(r'<!-- wp:heading -->.*?<!-- /wp:heading -->', raw, re.DOTALL)
        h2_block = h2_match.group(0) + '\n\n' if h2_match else ""
        p1p2     = '\n'.join(paras[:2])
        rest_raw = raw[raw.find(paras[1]) + len(paras[1]):]
        polished = ask_claude_polish(p1p2, section_label="Nasıl Bir Yer p1-2")
        rest     = mechanical_only(rest_raw, section_label="Nasıl Bir Yer p3-9")
        return h2_block + polished + rest
    return mechanical_only(raw, section_label="Nasıl Bir Yer")


def _gen_nerede(city: str, city_en: str, country: str,
                guide_url: str, context: str, is_turkey: bool) -> str:
    """Nerede H2 + 2 paragraf → GPT üretir, Sonnet polish eder. max_tokens=800"""
    saat_dilimi = "" if is_turkey else "\n  Saat dilimi: Türkiye ile farkı 1 cümle."
    prompt = f"""Şehir: {city} ({city_en}), {country}
Gezi rehberi URL: {guide_url}
{f"Veriler: {context}" if context else ""}

Birebir bu H2 başlığıyla başla:
<!-- wp:heading --><h2><strong>{city} Nerede</strong> 📍</h2><!-- /wp:heading -->

Para 1 — KONUM VE COĞRAFYA (100-120 kw):
  İlk cümlede <strong>{city}</strong> bold zorunlu.
  Kıta → ülke → ülke içindeki bölge adı.
  Coğrafi önem: dağ/nehir/deniz/ova ilişkisi ve şehrin karakterine etkisi.
  Komşu şehirler/bölgeler (yön + mesafe).
  Rakım (biliniyorsa).
  Zorunlu link: <a href="{guide_url}">{city} gezi rehberi</a>

Para 2 — TARİHİ ÖNEM VE STRATEJİK KONUM (90-110 kw):
  Tarihsel önem: neden önemliydi? (ticaret yolu, liman, başkent, sınır kenti)
  Stratejik konum: bugün ulaşım açısından avantajlı mı?
  Ulaşım aksları: karayolu/demiryolu/hava bağlantısı özet.{saat_dilimi}"""
    raw = ask_gpt_mini_strict(prompt,
                         system=SYS_WHERE_NEREDE.replace("{city}", city).replace("{guide_url}", guide_url),
                         max_tokens=800, temperature=0.75)
    return mechanical_only(raw, section_label="Nerede")


def _gen_nasil_gidilir(city: str, city_en: str, country: str,
                        dest_abl: str, context: str, is_turkey: bool) -> str:
    """Nasıl Gidilir H2 + 6-8 para + Ucuz Bilet H3+list → GPT üretir, Sonnet polish eder ilk 3 para."""
    bilet_block = _BILET_LINKS_TPL.replace("{city}", city)

    prompt = f"""Şehir: {city} ({city_en}), {country}
Türkçe hal: {dest_abl}
Türkiye içi: {"Evet" if is_turkey else "Hayır"}

Birebir bu H2 başlığıyla başla:
<!-- wp:heading --><h2><strong>{dest_abl} Nasıl Gidilir</strong> ✈️🚗</h2><!-- /wp:heading -->

─── UÇAK BLOĞU ──────────────────────────────────────────────────────────────

Para 1 — UÇUŞLAR (100-120 kw):
  İlk cümlede <strong>{city}</strong> bold. Havalimanı adı+kodu+merkeze km.
  Türkiye'den direkt uçuşlar: hangi şehirler, hangi havayolları.
  Aktarmalı alternatifler: ucuz hub + % fiyat farkı varsa belirt.
  Uçuş süresi: direkt ve aktarmalı.

Para 2 — HAVALİMANINDAN MERKEZE (80-100 kw):
  Tren/metro/otobüs/taksi — her biri için süre + fiyat (€+kaynak+tarih).
  Hangisi önerilir? Ne zaman taksi mantıklı? Araç kiralama mantıklıysa belirt.

Para 3 — BİRDEN FAZLA HAVALİMANI VARSA (60-80 kw — YOKSA BU PARAGRAFI YAZMA):
  Karşılaştırmalı özet: hangi havalimanı hangi durum için?

Para 4 — UÇUŞ TAVSİYESİ VE DEVAM ULAŞIM (50-70 kw):
  Geç iniş uyarısı (tren/otobüs saatleri). Konaklama bölgesi önerisi.
  Ülke/bölge içi devam ulaşımı varsa 1 cümle (tren erken al, vb.).

─── KARA + DEMİRYOLU + DENİZ ────────────────────────────────────────────────

Para 5 — KARA YOLU (60-80 kw — SADECE mantıklıysa, değilse kısaca geç):
  Türkiye veya komşu ülkeden karayolu. Süre, güzergah.
  Varsa ZTL/vize/otoyol ücreti uyarısı.

Para 6 — DEMİRYOLU (60-80 kw — SADECE aktif hat varsa, YOKSA BU PARAGRAFI YAZMA):
  Hat adı, nereden, süre, fiyat (€). Yurt dışı bağlantıları varsa belirt.

Para 7 — DENİZ YOLU (40-60 kw — SADECE gerçekçi feribot varsa, YOKSA YAZMA):
  Liman, hat, süre, fiyat.

─── H3 BLOĞU ────────────────────────────────────────────────────────────────

Son olarak sadece bu H3 paragrafını yaz (başlık ve liste aşağıda ayrıca eklenecek):

H3 giriş paragrafı (80-100 kw):
  En ucuz dönem + fiyat aralığı (kaynak+tarih).
  Skyscanner / Google Flights taktikleri. Ucuz aktarmalı rota örneği.
  1 kişisel taktik: "Ben genellikle...".
  Son cümle: "Ulaşım tarifeleri dönemsel değişebilir — seyahat öncesi resmi sitelerden kontrol edin." """
    raw = ask_gpt_mini_strict(prompt,
                         system=SYS_WHERE_GIDILIR.replace("{dest_abl}", dest_abl).replace("{city}", city),
                         max_tokens=2200, temperature=0.75)

    # Mechanical clean (forbidden words, markdown → bold) — Claude çağrısı yok
    raw = mechanical_only(raw, section_label="Nasıl Gidilir")

    # Ayıraç + H3 başlığı + liste bloğunu sona ekle
    raw = raw.rstrip() + f'\n\n{SEP}\n\n' + bilet_block
    return raw



# ─── Destinasyon tipi tespiti ─────────────────────────────────────────────────
# TİP A: Ülke bazlı (birden fazla şehri kapsayan destinasyon)
_COUNTRY_DESTS = {
    "Bosna Hersek", "Hırvatistan", "Karadağ", "Arnavutluk",
    "İtalya", "Fransa", "İspanya", "Türkiye", "Yunanistan",
    "Almanya", "Japonya", "Vietnam", "Endonezya",
}

# TİP C: Küçük şehir/günübirlik (eski _SMALL_CITIES ile aynı)
_SMALL_CITIES = {
    "Mostar", "Kotor", "Brno", "Selanik", "Konya", "Krakow",
    "Bergen", "Kopenhag", "Varşova",
}


def _dest_type(city: str, is_turkey: bool) -> str:
    """A=ülke, B=büyük şehir, C=küçük şehir"""
    if city in _COUNTRY_DESTS:
        return "A"
    if city in _SMALL_CITIES:
        return "C"
    return "B"


def _gen_gezi_plani(city: str, city_en: str, country: str,
                     context: str, is_turkey: bool) -> str:
    """Gezi Planı H2 + giriş + H3 planlar + ipuçları → 3 tip, max_tokens=2000"""
    tip = _dest_type(city, is_turkey)

    if tip == "A":   # Ülke bazlı
        h3_blocks = f"""\
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>3 Günlük {city} — Hızlı Tur</strong></h3><!-- /wp:heading -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>5 Günlük {city} — İdeal Plan</strong></h3><!-- /wp:heading -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>7 Günlük {city} — Derinlemesine</strong></h3><!-- /wp:heading -->"""
        plan_instr = f"""\
H3: 3 Günlük (80-100 kw): Başkent + en önemli 1-2 şehir. Sabah→akşam akışı. Pratik ipucu.
H3: 5 Günlük (80-100 kw): Başkent + 2-3 şehir. Gün gün anlat. Rezervasyon/bilet uyarısı.
H3: 7 Günlük (80-100 kw): Başkent + bölgesel turlar + küçük kasabalar. Kim için 7 gün şart?"""

    elif tip == "C":   # Küçük şehir
        h3_blocks = f"""\
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>1 Günlük {city} — Günübirlik Yeterli</strong></h3><!-- /wp:heading -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>2-3 Günlük {city} — Çevreyle Birlikte</strong></h3><!-- /wp:heading -->"""
        plan_instr = f"""\
H3: 1 Günlük (80-100 kw): Şehir merkezi + ana meydan. Nereden gidilir, sabah→akşam akışı.
H3: 2-3 Günlük (80-100 kw): Şehir + çevre gezisi/ada. Akşam kalınmaya değer mi? Çevre köyler."""

    else:   # TİP B — büyük şehir
        h3_blocks = f"""\
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>1-2 Günlük {city} — Hızlı Tur</strong></h3><!-- /wp:heading -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>3 Günlük {city} — İdeal Plan</strong></h3><!-- /wp:heading -->
<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading"><strong>4-5 Günlük {city} — Detaylı Keşif</strong></h3><!-- /wp:heading -->"""
        plan_instr = f"""\
H3: 1-2 Günlük (80-100 kw): Ana turistik noktalar. Sabah erken başla, sıra/kalabalık uyarısı.
H3: 3 Günlük (3 ayrı gün paragrafı, 80-100 kw/gün): Gün 1 ana noktalar / Gün 2 müze+semt / Gün 3 çevre.
H3: 4-5 Günlük (80-100 kw): Tüm müzeler + çevre geziler + gizli noktalar. Kim için 5 gün gerekli?"""

    prompt = f"""Şehir: {city} ({city_en}), {country}
Destinasyon tipi: {"Ülke bazlı (Tip A)" if tip=="A" else "Küçük şehir (Tip C)" if tip=="C" else "Büyük şehir (Tip B)"}
{f"Veriler: {context}" if context else ""}

Birebir bu H2 başlığıyla başla:
<!-- wp:heading --><h2 class="wp-block-heading"><strong>{city} Gezi Planı</strong> 🗓</h2><!-- /wp:heading -->

GİRİŞ PARAGRAFI (70-90 kw):
  Kaç gün ayırmalı — net, somut gerekçe (büyüklük, yoğunluk, mesafeler).
  "Bu kadar günde ancak bunlar yetişir" beklenti ayarı.
  Konaklama semti önerisi + 1 cümle gerekçe.

Ardından birebir bu H3 başlıklarını kullan, her birinin altına ilgili plan paragrafını yaz:
{h3_blocks}

{plan_instr}

Son olarak SEYAHAT İPUÇLARI (1-2 paragraf, 60-80 kw toplam):
  Sabah erken başlamanın önemi. Online bilet/rezervasyon uyarısı.
  Ulaşım taktikleri. Yemek için turistik tuzakları kaçınma önerisi."""
    raw = ask_gpt_mini_strict(prompt,
                         system=SYS_WHERE_PLAN.replace("{city}", city),
                         max_tokens=2000, temperature=0.80)
    return mechanical_only(raw, section_label="Gezi Planı")


def _gen_kapanis(city: str, city_en: str, country: str, guide_url: str) -> str:
    """Kapanış: 2 paragraf, başlıksız → GPT üretir, Sonnet polish eder. max_tokens=800"""
    prompt = f"""Şehir: {city} ({city_en}), {country}
Gezi rehberi URL: {guide_url}

2 başlıksız kapanış paragrafı yaz. "Ben" dili zorunlu. LİSTE YASAK.

Para 1 — GENEL DEĞERLENDİRME VE BEKLENTİ AYARI (100-120 kw):
  Destinasyonun en güçlü yanları — somut, kişisel, anlatıya yedirilerek.
  Eksiler açıkça: kalabalık mı, pahalı mı, ulaşımı zor mu?
  Net cümle: kime hitap eder, kime etmez.
  YASAK: "muhteşem", "harika", "eşsiz", "sonuç olarak herkes gitmeli"

Para 2 — PRATİK İPUÇLARI VE VEDA (80-100 kw):
  <strong>Kaç gün</strong> kalmalı (bold).
  <strong>Ne zaman</strong> gitmeli — mevsim/ay (bold).
  2-3 somut pratik ipucu: bilet, sabah erken, ayakkabı, yerel yemek, vb.
  Gezi rehberi linki: <a href="{guide_url}">{city} gezi rehberi</a>
  Samimi veda cümlesiyle kapat ("Hadi bakalım", "İyi yolculuklar" tarzı).

FORMAT: Sadece Gutenberg HTML paragrafları."""
    raw = ask_gpt_mini_strict(prompt,
                         system=SYS_WHERE_KAPANIS.replace("{guide_url}", guide_url).replace("{city}", city),
                         max_tokens=800, temperature=0.85)
    return ask_claude_polish(raw, section_label="Kapanış")


# ═══════════════════════════════════════════════════════════════════════════════
# ANA FONKSİYON
# ═══════════════════════════════════════════════════════════════════════════════

def generate_where(post: dict) -> tuple:
    """
    WHERE mode — 6 GPT bölüm + 2 Sonnet polish + 1 schema.
    GPT başarısızsa RuntimeError fırlatır (fallback YOK).
    Döndürür: (wp_title, html_content, yoast_meta)
    """
    raw_title    = post.get('title', {})
    title_str    = raw_title.get('rendered', '') if isinstance(raw_title, dict) else str(raw_title)
    title_str    = _html_mod.unescape(re.sub(r'<[^>]+>', '', title_str)).strip()
    html_content = (post.get('content', {}) or {}).get('rendered', '') or ''
    post_slug_raw = post.get('slug', '')

    # ── Şehir tespiti ─────────────────────────────────────────────────────────
    city = None
    if post_slug_raw:
        c = _city_from_slug(post_slug_raw)
        if c:
            city = c
    if not city and title_str:
        clean_t = re.sub(r'\s*\(20\d{2}\)', '', title_str).strip()
        _strip = re.compile(
            r"(?:'[a-züışğçöA-ZÜIŞĞÇÖa-z]+)?\s+"
            r"(?:Nerede|Nasıl Gidilir|Nasıl Bir Yer|Gezilecek Yerler|"
            r"Gezi Rehberi|Seyahat Rehberi|Gezi Plan[ıi]|Hakkında|Rehberi)",
            re.IGNORECASE
        )
        m = _strip.search(clean_t)
        if m:
            city = re.sub(r"'[a-züışğçöA-ZÜIŞĞÇÖ]{1,4}$", '', clean_t[:m.start()]).strip()
        elif ':' in clean_t or '–' in clean_t:
            city = re.split(r'[:\-–]', clean_t)[0].strip()
        else:
            words = clean_t.split()
            city = ' '.join(words[:2]) if len(words) > 1 and words[1][0].isupper() else words[0]
    city = city or 'Bilinmiyor'

    meta = _CITY_META.get(city)
    city_en, country, country_en, city_flag = meta if meta else (city, 'Bilinmiyor', 'Unknown', '🌍')
    is_turkey = (country_en.lower() == 'turkey')

    try:
        from schema_engine import tr_abl as _ta, tr_loc as _tl
        dest_abl, dest_loc = _ta(city), _tl(city)
    except ImportError:
        dest_abl, dest_loc = city + "'a", city + "'da"

    guide_slug = _slugify(city) + '-gezi-rehberi'
    guide_url  = f'https://yoldaolmak.com/{guide_slug}/'
    post_slug  = _slugify(city) + '-nerede-nasil-gidilir'

    # ── Başlıklar ─────────────────────────────────────────────────────────────
    expected_title = f'{city} Nasıl Bir Yer? Nerede, Nasıl Gidilir ve Gezi Planı'
    existing_clean = re.sub(r'\s*\(\d{4}\)\s*$', '', title_str).strip()
    wp_title = existing_clean if existing_clean == expected_title else expected_title

    # DÜZELTME: TR → "?" (soru işareti), Yabancı → city_flag (önceki kod tersiydi)
    nasil_baslik = (f"{city} Nasıl Bir Yer?"
                    if is_turkey else
                    f"{city} Nasıl Bir Yer {city_flag}")

    # ── Konsol başlığı ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f'🗺️  WHERE ENGINE v4.1  —  6 bölüm GPT + 2 Sonnet polish')
    print("=" * 60)
    print(f'📍 Şehir  : {city} ({city_en}) {city_flag}')
    print(f'🌍 Ülke   : {country} ({country_en})')
    print(f'🇹🇷 TR iç  : {"Evet" if is_turkey else "Hayır"}')
    print(f'📝 İçerik : {len(html_content):,} karakter')
    print(f'📋 H1     : {wp_title}')
    print(f'📋 H2[1]  : {nasil_baslik}')
    print(f'🔧 Cache  : KAPALI (test modu)')

    ctx = _context(html_content, city)
    sections = {}

    # DOĞRU H SIRASI:
    # Giriş (başlıksız) → Nerede H2 → Nasıl Bir Yer H2 → Nasıl Gidilir H2+H3 → Gezi Planı H2+H3 → Kapanış

    # ── [1/6] Giriş ───────────────────────────────────────────────────────────
    c0 = get_session_cost()
    print('\n  [1/6] Giriş + Kişisel Bakış... (GPT-mini + Haiku polish)')
    sections['intro'] = _gen_intro(city, city_en, country, ctx)
    _token_log("Giriş", c0, get_session_cost())

    # ── [2/6] Nerede (H2) ─────────────────────────────────────────────────────
    c0 = get_session_cost()
    print(f'  [2/6] {city} Nerede... (GPT-mini, mechanical)')
    sections['nerede'] = _gen_nerede(city, city_en, country, guide_url, ctx, is_turkey)
    _token_log("Nerede", c0, get_session_cost())

    # ── [3/6] Nasıl Bir Yer (H2) ─────────────────────────────────────────────
    c0 = get_session_cost()
    print(f'  [3/6] {nasil_baslik}... (GPT-mini + Haiku polish p1-2)')
    sections['nasil'] = _gen_nasil_bir_yer(city, city_en, country, nasil_baslik, ctx, is_turkey)
    _token_log("Nasıl Bir Yer", c0, get_session_cost())

    # ── [4/6] Nasıl Gidilir (H2 + H3) ────────────────────────────────────────
    c0 = get_session_cost()
    print(f'  [4/6] {dest_abl} Nasıl Gidilir... (GPT-mini, mechanical)')
    sections['gidilir'] = _gen_nasil_gidilir(city, city_en, country, dest_abl, ctx, is_turkey)
    _token_log("Nasıl Gidilir", c0, get_session_cost())

    # ── [5/6] Gezi Planı (H2 + H3'ler) ──────────────────────────────────────
    tip = _dest_type(city, is_turkey)
    tip_label = {"A": "ülke/3-5-7 gün", "B": "şehir/1-2-3-5 gün", "C": "küçük/1-2-3 gün"}[tip]
    c0 = get_session_cost()
    print(f'  [5/6] {city} Gezi Planı... (GPT-mini, mechanical, {tip_label})')
    sections['plan'] = _gen_gezi_plani(city, city_en, country, ctx, is_turkey)
    _token_log("Gezi Planı", c0, get_session_cost())

    # ── [6/6] Kapanış ─────────────────────────────────────────────────────────
    c0 = get_session_cost()
    print(f'  [6/6] Kapanış... (GPT-mini + Haiku polish)')
    sections['kapanis'] = _gen_kapanis(city, city_en, country, guide_url)
    _token_log("Kapanış", c0, get_session_cost())

    # ── Schema + FAQ ──────────────────────────────────────────────────────────
    from schema_engine import generate_schema_block
    summary_text = _strip_html(html_content) or _strip_html(sections['intro'])
    c0 = get_session_cost()
    print('  [+] Schema + FAQ... (GPT-mini, max 1400t)')
    schema_block = generate_schema_block(
        city=city, city_en=city_en,
        country=country, country_en=country_en,
        post_summary=summary_text,
        post_slug=post_slug,
        is_turkey_dest=is_turkey,
        mode='where'
    )
    _token_log("Schema", c0, get_session_cost())

    # ── Birleştir (DOĞRU H SIRASI) ───────────────────────────────────────────
    # Giriş (başlıksız) → Nerede H2 → Nasıl Bir Yer H2 → Nasıl Gidilir H2+H3 → Gezi Planı H2+H3 → Kapanış
    today = datetime.date.today()
    full_html = (
        sections['intro'].strip()
        + f'\n\n{SEP}\n\n'
        + sections['nerede'].strip()
        + f'\n\n{SEP}\n\n'
        + sections['nasil'].strip()
        + f'\n\n{SEP}\n\n'
        + sections['gidilir'].strip()
        + f'\n\n{SEP}\n\n'
        + sections['plan'].strip()
        + f'\n\n{SEP}\n\n'
        + sections['kapanis'].strip()
        + f'\n\n{SEP}\n\n'
        + schema_block
        + f'\n\n<!-- SON GÜNCELLEME: {today.strftime("%B %Y")} -->\n'
        + f'<!-- META: {city} nerede nasil gidilir {today.year} -->'
    )

    # ── Post-processing ───────────────────────────────────────────────────────
    print('\n🔧 Post-processing...')
    full_html = _clean_artifacts(full_html)
    full_html = _fix_bold(full_html)
    full_html = _ensure_wp_wrap(full_html)

    # ── Başlık audit ──────────────────────────────────────────────────────────
    _print_heading_audit(full_html, city, nasil_baslik, dest_abl)

    # ── Agent kalite döngüsü (v3.0) ──────────────────────────────────────────
    from agent_loop import run_with_quality_gate, format_agent_report
    from content_validator import print_audit_report
    loop_result = run_with_quality_gate(
        html=full_html, mode='where', city=city, post_id=post.get("id", 0),
        max_retries=2, pass_threshold=82, verbose=True,
    )
    full_html = loop_result['html']
    print(format_agent_report(loop_result))

    # ── Toplam maliyet raporu ─────────────────────────────────────────────────
    total = get_session_cost()
    print(f'\n💰 TOPLAM MALİYET: ~${total.get("estimated_usd", 0):.4f}')
    print(f'   Sonnet in:{total.get("input",0):,} out:{total.get("output",0):,} | '
          f'Haiku in:{total.get("haiku_input",0):,} out:{total.get("haiku_output",0):,}')

    # ── Yoast meta ────────────────────────────────────────────────────────────
    try:
        from schema_engine import tr_loc as _tl2
        geo_loc = _tl2(country)
    except ImportError:
        geo_loc = country + "'da"

    yoast_meta = {
        'title':   f'{city} Nasıl Bir Yer? Nerede, Nasıl Gidilir ve Gezi Planı',
        'desc':    (f'{city} nerede, nasıl gidilir? {geo_loc} yer alan {city}, '
                    f"İstanbul'dan uçuşla ulaşım, gezi planı ve pratik bilgiler."),
        'focuskw': city.lower() + ' nerede nasıl gidilir',
    }

    print(f'\n📋 Yoast SEO:')
    print(f'   Title : {yoast_meta["title"]}')
    print(f'   KW    : {yoast_meta["focuskw"]}')
    print("=" * 60 + "\n")

    return wp_title, full_html, yoast_meta


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT RAPORU
# ═══════════════════════════════════════════════════════════════════════════════

def _print_heading_audit(html: str, city: str, nasil_baslik: str, dest_abl: str) -> None:
    def _get_h(lvl):
        return [re.sub(r'<[^>]+>', '', m).strip()
                for m in re.findall(rf'<h{lvl}[^>]*>(.*?)</h{lvl}>', html, re.DOTALL)]

    h2s = _get_h(2)
    h3s = _get_h(3)
    required_h2 = [nasil_baslik, f'{city} Nerede', 'Nasıl Gidilir', f'{city} Gezi Planı']
    required_h3 = ['Ucuz', 'Günlük']

    print('\n── BAŞLIK AUDİT ──────────────────────────────────')
    print(f'  H2 sayısı : {len(h2s)} (min 4)')
    for h in h2s:
        print(f'    ✓ {h}')
    print(f'  H3 sayısı : {len(h3s)} (min 3)')
    for h in h3s:
        print(f'    ✓ {h}')

    missing_h2 = [r for r in required_h2 if not any(r[:12] in h for h in h2s)]
    missing_h3 = [r for r in required_h3 if not any(r[:6] in h for h in h3s)]
    for m in missing_h2:
        print(f'    ❌ EKSİK H2: {m}')
    for m in missing_h3:
        print(f'    ❌ EKSİK H3: {m}')
    if not missing_h2 and not missing_h3:
        print('  ✅ Tüm zorunlu başlıklar mevcut')
    print('──────────────────────────────────────────────────')
