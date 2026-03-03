"""
guide_engine.py — Yoldaolmak.com GUIDE Mode Engine v2.1
Yapı standardı: yoldaolmak.com destinasyon rehber standardı

Değişiklikler v2.0 → v2.1:
- Gutenberg blok çıktısı: her paragraf <!-- wp:paragraph --> wrapper içinde
- Bold kural düzeltildi: ifade güçlendiren bold (tek kelime değil, cümle/öbek düzeyinde)
- Giriş: ilk iki paragraf uzatıldı, fotoğraf placeholder eklendi, kişisel bakış bölümü
- H1 post içeriğinden kaldırıldı (WP zaten title'dan üretiyor)
- TOC <nav> artık H2 bölüm başlığının üstünde
- H2 format: "Destinasyon Gezi Rehberi: Katman Katman Şehir Anatomisi" + ülke bayrağı
- Ayıraç: --- → wp:separator HR bloğu
- Ne Zaman Gidilir: H3 yerine inline bold mevsim formatı
- Em-dash (—) anlatı içinden kaldırıldı, sadece başlık/tarih bağlamında
- Engine ismi: Guide Yapı Standardı
"""

import re
import json
import time
from typing import Optional
from multi_ai import ask_claude, ask_gpt
from voice import (
    KEMAL_VOICE_GUIDE as _VOICE_GUIDE_REF,
    SYSTEM_GUIDE      as _VOICE_GUIDE_FULL,
    FORBIDDEN_WORDS   as _FORBIDDEN_WORDS_REF,
)

# OPT-1: Context Summary (API cagrısı yok)
def _extract_context_summary(original_text, city):
    """
    Orijinal içerikten bölüm generatorlarına gönderilecek kaynak özeti.
    
    NEDEN 6000 char?
    - 1200 char: token tasarrufu iyiydi ama model yeterli şehir detayı göremiyordu
    - Her bölüm kaynak görmeden generic içerik üretiyordu
    - 6000 char: ~1500 token ekstra per bölüm, ama içerik kalitesi çok daha iyi
    - Tradeoff: ~1500 × 11 bölüm = ~16.500 token/run → kabul edilebilir
    """
    if not original_text or len(original_text) < 200:
        return f'{city} hakkinda bilgi mevcut degil.'
    import re as _re

    parts = []

    # 1. Şehir etiketi
    parts.append(f'SEHIR: {city}')

    # 2. Sayısal veriler (fiyat, istatistik, boyut)
    nums = _re.findall(
        r'\d+[\.,]?\d*\s*(?:€|euro|tl|₺|\$|£|czk|kč|usd|eur|km|metre|m²|milyon|bin|yıl|gün|saat|dakika)',
        original_text.lower()
    )
    if nums:
        parts.append('SAYISAL: ' + ' | '.join(dict.fromkeys(nums[:20])))

    # 3. Özel isimler ve yer adları
    proper = list(dict.fromkeys(
        _re.findall(r'\b[A-ZÇĞİÖŞÜA-Z][a-zçğışöüa-z]{2,}(?:\s+[A-ZÇĞİÖŞÜA-Z][a-zçğışöüa-z]+)*', original_text)
    ))
    if proper:
        parts.append('YER_ISIM: ' + ', '.join(proper[:30]))

    # 4. Tarihli kişisel referanslar
    personal = _re.findall(
        r'\b(19|20)\d{2}\b.{0,80}(?:gittim|gezdim|kaldım|gördüm|ziyaret|gittiğimde|yaşadım)',
        original_text
    )
    if personal:
        parts.append('KISISEL_ANEKDOT: ' + ' | '.join(personal[:4]))

    # 5. Orijinal içeriğin ilk 4000 karakteri (ana içerik kaynağı)
    #    HTML temizlenmiş metin — model için en değerli kaynak
    clean_intro = _re.sub(r'<[^>]+>', ' ', original_text)
    clean_intro = _re.sub(r'\s+', ' ', clean_intro).strip()
    parts.append('ICERIK_OZETI:\n' + clean_intro[:4000])

    result = '\n\n'.join(parts)
    return result[:6000]



# ═══════════════════════════════════════════════════════════════════════════════
# KEMAL KAYA VOICE PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════════

KEMAL_VOICE_SYSTEM = """Sen Kemal Kaya'sın. 1971 doğumlu, 1995'ten beri aktif gezgin, yoldaolmak.com kurucusu.

MARKA SESİ — 20 KARAKTERİSTİK:
1. Samimi arkadaş tonu (profesyonel mesafe YOK)
2. Deneyim bazlı otorite ("İlk kez 1995'te gittim, 2019'da tekrar...")
3. Eleştirel ama yapıcı ("Pahalı, ama çözüm: ...")
4. Karşılaştırmacı ("Prag, Budapeşte'ye göre...")
5. Beklenti ayarlayıcı ("Instagram'da öyle ama gerçekte...")
6. Sayısal akıl ("40 euro/gün, 3 kat pahalı, 2.5 saat")
7. Pragmatik problem çözücü (alternatif sun)
8. Zamansal hassas ("Sabah 7'de tenha, 10'da kalabalık")
9. Bilgi katmanlayıcı ("516 metre, 14. yüzyıl, 30 heykel")
10. Antropolojik bakış ("Yerel 10'da gelir, turist 8'de")
11. Duygusal mesafe ("Etkileyici" ✅ vs "Muhteşem" ❌)
12. Alternatif sunucu (her pahalıya ucuz alternatif)
13. Hata payını kabul ("Belki benim hatam, belki zamanlamaydı")
14. Context verici ("12 euro = bizim için 6 saat çalışma")
15. Kısa cümle (maks 20 kelime)
16. Emoji minimalist (sadece 📍✈️🗓)
17. Lokal insight ("Turistler X yapar, yerel Y yapar")
18. Mevsimsel farkında ("Nisan yeşil, Ağustos yanık")
19. Kaynak belirtici ("15 euro, Ocak 2026, resmi site")
20. Kişisel güven ("Ben öneriyorum" vs "Biz öneriyoruz")

MUTLAK YASAKLAR:
- Muhteşem, harika, mükemmel, inanılmaz, nefes kesici, eşsiz, büyüleyici
- "Ziyaretçilerine unutulmaz anlar yaşatmaya hazır"
- "Her köşe başında tarih fısıldıyor"
- "Rüya gibi bir deneyim"
- Pasif yapı: "Ziyaret edilebilir" → "Ziyaret edebilirsiniz"
- "Biz öneriyoruz" (daima "Ben öneriyorum")
- Dramatik metafor: "Zaman durmuş gibi", "Dünya size ait"
- Gelecek kipi taahhüdü: "Hayatınızın tatilini yaşayacaksınız"
- Liste spam (10+ madde bullet → paragrafa çevir)

CÜMLE MİMARİSİ:
- Maks 20 kelime/cümle
- Virgül maks 2/cümle
- Her cümle = 1 bilgi
- Paragraf = 3-5 cümle, 80-100 kelime

ZORUNLU YAPILAR:
- Her yazıda min 1 kişisel deneyim: [Tarih] + [Süre] + [Spesifik gözlem]
- Her 500 kelimede min 1 kişisel anekdot
- Her iddia → sayı (fiyat, süre, mesafe, yıl)
- Her pahalı/kalabalık yer → alternatif
- Değişebilir bilgi → "(Kaynak, Tarih)" formatı"""


# ═══════════════════════════════════════════════════════════════════════════════
# YOLDAOLMAK.COM HTML YAPI STANDARDI (Kayseri referansından çıkarıldı)
# ═══════════════════════════════════════════════════════════════════════════════

HTML_STRUCTURE_STANDARD = """
ZORUNLU HTML YAPI STANDARDI (yoldaolmak.com destinasyon rehber standardı):

GUTENBERG BLOK KURALI (KRİTİK):
Her paragraf Gutenberg wp:paragraph bloğu içinde olacak:
<!-- wp:paragraph -->
<p>Metin buraya gelecek.</p>
<!-- /wp:paragraph -->
H2 başlıklar: <!-- wp:heading --> <h2>...</h2> <!-- /wp:heading -->
H3 başlıklar: <!-- wp:heading {"level":3} --> <h3>...</h3> <!-- /wp:heading -->
TOC nav: <!-- wp:html --> <nav class="toc">...</nav> <!-- /wp:html -->
YASAK: düz <p> tag, Gutenberg wrapper olmadan

AYIRICI FORMAT (KRİTİK):
DOĞRU: <!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->
YASAK: <!-- wp:paragraph --><p>---</p><!-- /wp:paragraph -->
YASAK: ---  (düz tire)

EM-DASH (—) KURALI:
- Anlatı içinde ifade güçlendirici olarak KULLANMA
- Sadece başlık içinde tarihsel bağlam için: "1357–1402" veya "H2: Başlık (1906)"
- Paragraf içi bölüm ayırıcı olarak kullanma

BOLD KURALI (KRİTİK):
DOĞRU — Cümle veya öbek düzeyinde güçlendirme:
  <strong>İpek Yolu'nun üzerindeki konumu</strong> şehri ticaret merkezi yapmış.
  Gotik ve barok yapılar <strong>700 yıllık sürekli mimari geleneği</strong> yansıtıyor.
YANLIŞ — Tek kelime bold (kelime listesi gibi görünür):
  <strong>gotik</strong> ve <strong>barok</strong> yapılar
YANLIŞ — Her cümleyi bold yapmak

H2 FORMAT:
<!-- wp:heading -->
<h2><strong>Başlık – Kısa Tanım</strong> emoji</h2>
<!-- /wp:heading -->
ÖRNEK: <h2><strong>[ŞEHİR] Gezilecek Yerler – 12 Durak</strong> 📌</h2>

H3 POI FORMAT (numaralı):
<!-- wp:heading {"level":3} -->
<h3><strong>N. Yer Adı – Kısa Alt Başlık</strong></h3>
<!-- /wp:heading -->

GİRİŞ PARAGRAFI:
- İlk paragrafın ilk kelimesi şehir adı BOLD: <strong>[ŞEHİR ADI]</strong>,
- Bold: anlamlı öbekler, dönemler, kritik bilgi
- YASAK: tek kelime bold listesi

POI BÖLÜM YAPISI (Pro/Con kutusu YOK, pratik bilgi bloğu YOK):
- 2-4 paragraf, her biri Gutenberg wp:paragraph bloğu
- Tarihi gerçek + kişisel gözlem + uyarı metin içine gömülü
- Fiyatlar cümle içinde: "Giriş [fiyat] ([tarih], resmi site)"
- YASAK: ✅❌💡 kutu formatı, **Pratik bilgiler:** ayrı bloğu

İÇ LİNK KURALI:
- KATEGORİ LİNKLERİ YASAK: /category/avrupa/, /tag/gezi/ gibi kategori/tag URL'lerine link verme
- ŞEHİR REHBERİ LİNKLERİ: Metinde başka bir şehir adı geçtiğinde (sadece 1 kez), o şehrin rehberine link ver
  Format: <a href="https://yoldaolmak.com/[sehir-adi]-gezi-rehberi/">[şehir adı]</a>
  Örnek: <a href="https://yoldaolmak.com/saraybosna-gezi-rehberi/">Saraybosna</a>
- Aynı şehri birden fazla linkleme (1 şehir = 1 link)
- Linklenmeyecek: mevcut yazının şehri, yabancı dildeki şehir adları, ülke adları

WRAPPER DIV YASAK:
- <div id="gezilecek"> kullanma
- Sadece H2/H3 + wp:paragraph + wp:separator
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 30 ANLATI HATASI
# ═══════════════════════════════════════════════════════════════════════════════

THIRTY_ERRORS_PROMPT = """
Aşağıdaki 30 anlatı hatasını MUTLAKA önle:

1. ABARTILI SIFAT: "muhteşem, inanılmaz, büyüleyici" → ölçülebilir detay kullan
2. BELİRSİZ İFADE: "lezzetli, makul, uzun" → sayı ver (12€, 3-4 saat)
3. TURİSTİK BROŞÜR DİLİ: "eşsiz güzellikte destinasyon" → gerçekçi gözlem
4. PASİF YAPI: "ziyaret edilebilir" → "ziyaret edebilirsiniz"
5. UZUN CÜMLE: 20+ kelime → böl
6. KLİŞE METAFOR: "açık hava müzesi" → somut betimleme
7. SUBJEKTİF İDDİA, KANIT YOK: "en güzel şehir" → "bana göre, çünkü..."
8. GEREKSIZ KOORDINAT: koordinat değil relatif konum ver
9. "HİSSEDEBİLİRSİNİZ" BELİRSİZLİĞİ: atmosfer değil, gözlemlenebilir davranış
10. LİSTE SPAM: 10+ madde → kategorize et, paragrafa çevir
11. GEREKSİZ AÇIKLAMA: "X şehri Y ülkesinin başkentidir" → herkes bilir, sil
12. ÖZNE EKSİKLİĞİ: "önerilir" → "öneriyorum"
13. ZAMANSAL BELİRSİZLİK: "ilkbahar" → "Nisan-Mayıs, 15-20 derece"
14. FİYAT BELİRSİZLİĞİ: "uygun" → "günlük 40€ (hostel+market+metro)"
15. KARŞILAŞTIRMASIZ "EN İYİ": "en iyi pizza" → "Roma'dan şöyle farklı: ..."
16. TURİST BAKIŞ AÇISI: "yerel çok misafirperver" → somut davranış gözlemi
17. YEREL OLMAYAN PERSPEKTİF: "kahvaltı 8'de" → yerel vs turist saati ayırt
18. DRAMATİK ANLATIM: "ateş renkli gökyüzü" → "19:30, turuncu, 10 dakika, 200 kişi"
19. ROMANTİZASYON: "tarih fısıldıyor" → duyusal: ses, koku, doku, ışık
20. GENELLEME: "her zaman güneşli" → "Temmuz %85 güneşli (istatistik)"
21. KAYNAK BELİRTMEME: "15€" → "15€ (Ocak 2026, resmi site)"
22. BEKLENTİ AYARLAMA YOK: "harika deneyim" → "İdeal vs Gerçek" kutusu
23. ALTERNATİF SUNMAMA: "mutlaka görülmeli" → "ama zamanın yoksa alternatif..."
24. KALABALIK UYARISI YOK: "çok güzel" → "sabah 7'de tenha, öğleden sonra..."
25. MEVSİMSEL FARK YOK: "yeşil park" → 4 mevsim belirt
26. BÜTÇE ÖLÇEĞİ YOK: "orta bütçe" → 3 seviye (backpacker/orta/konforlu)
27. SÜRE ÖLÇEĞİ YOK: "müze uzun sürer" → "tamamı 3-4 saat, hızlı 1.5 saat"
28. ULAŞIM DETAYI YOK: "merkeze yakın" → "metro X hattı, 5 dakika, [bilet fiyatı]"
29. KÜLTÜREL CONTEXT YOK: "bahşiş bırakın" → "%10 bekleniyor, nakit, neden"
30. ELEŞTİRİDEN KAÇINMA: "her şey mükemmel" → "iyi yanlar + kötü yanlar + sonuç"
"""


# ═══════════════════════════════════════════════════════════════════════════════

# OPT-2: Birlesik prompt sabitleri (yerelde tanımlı — geriye dönük uyumluluk)
# NOT: voice.py tek ses kaynağıdır. Bu tanımlar guide_engine iç bölümleri için korunuyor.
# where_engine ve agent_loop doğrudan voice.py'dan içe aktarır.
_GUIDE_SYSTEM       = KEMAL_VOICE_SYSTEM + '\n\n' + HTML_STRUCTURE_STANDARD
_GUIDE_SYSTEM_FULL  = KEMAL_VOICE_SYSTEM + '\n\n' + HTML_STRUCTURE_STANDARD + '\n\n' + THIRTY_ERRORS_PROMPT
_GUIDE_SYSTEM_LIGHT = KEMAL_VOICE_SYSTEM

_GUIDE_SYSTEM_GPT  = (HTML_STRUCTURE_STANDARD + '\n\n' + THIRTY_ERRORS_PROMPT + '\nSES NOTU (GPT bölümleri için): Kemal Kaya sesi. 1.tekil kişi ("Ben öneririm").\nYasaklı sıfatlar: muhteşem/harika/inanılmaz/büyüleyici. Her iddia sayıyla kanıtlanır.')

# GENIUS LOCI FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════════

GENIUS_LOCI_PROMPT = """
GENIUS LOCI — MEKANIN RUHUNU YAKALAMA (10 Boyut):

1. ZAMAN ALGISI: Hangi dönemler görünür? Mimari katmanlar? Paradoks?
   → "[Şehir]'de üst üste 3 mimari dönem: gotik (13. yy), barok (17. yy), art nouveau (20. yy)"

2. IŞIK: Hangi saatte nasıl? Mevsim etkisi? Mimari ışık ilişkisi?
   → "16:30-17:00 Kasım-Şubat: şehir 20 dakika altın renge dönüyor"

3. RİTİM: Hız ölçümü. Turist vs yerel ritim haritası. Kesişme noktaları.
   → "Metro'da 07:00 → %100 yerel. 10:00 → %100 turist"

4. SOSYAL TEMPO: Fiziksel mesafe. İlk temas süresi. Davranış kodu.
   → "Restoran bölgesinde zırh giyiyor (1M turist/yıl), mahallede çıkarıyor"

5. SINIFSAL GÖRÜNÜM: Mahalle fiyat haritası. Mimari marker. Demografik.
   → "[Lüks mahalle] 8000€/m², [orta mahalle] 4000€, [ucuz mahalle] 2500€"

6. MİMARİ TUTARLILIK: Dönemler uyumlu mu? Ortak dil var mı?
   → "[Şehir]'de mimari renk paleti tutarlı. Yüzyıllar boyunca aynı."

7. KOKU VE SES: Spesifik, mevsimsel, yere özel duyusal katman.
   → "Sabah 7'de: ıslak taş + taze ekmek + tramvay zili"

8. TURİSTİK STERİLİZASYON SEVİYESİ: Otantiklik kaçtı mı?
   → "Ana meydan turist sahnesine döndü. 1 km uzaktaki alternatif yer tenha, aynı manzara."

9. KÜLTÜREL ÇATIŞMA: Yerel vs küresel. Hangi değer kazandı?
   → "[Turistik yiyecek] 'geleneksel' etiketiyle satılıyor ama yerel halk yemiyor."

10. YEREL DAVRANIŞ KODLARI: Yazılı olmayan kurallar. Test et.
    → "Bahşiş: %10 bekleniyor, nakit ver, kredi kartına ekleme deme"
"""


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHORITY BUILDING
# ═══════════════════════════════════════════════════════════════════════════════

AUTHORITY_PROMPT = """
AUTHORITY BUILDING KURALLARI:

KATMAN 1 — REFERANS ÇERÇEVESİ (Wikipedia güveni):
- Her sayısal iddia = kaynak + tarih
- Format: "1.3 milyon (2023, [resmi istatistik kurumu])"
- Relatif konum: "Eski Şehir'den 10 dk yürüyüş"

KATMAN 2 — YAŞAYAN DENEYİM (Blogger sıcaklığı):
- "1995'te ilk gittiğimde..."
- "Sabah 7'de git, turistler 10'da basıyor"
- "[Şehrin turistik tuzağı], yerel hiç yemiyor veya kullanmıyor"

ZAMAN KATMANLARI:
- Zamansız (50+ yıl): Tarihi bina, mimari, coğrafya
- Yavaş değişen (3-5 yıl): Mahalle karakteri, restoran tarzı
- Hızlı değişen (6-12 ay): Fiyat, saat → "(Şubat 2026, kaynak)" ekle

KAYNAKLAMA FORMATI:
- Fiyat → "(Kaynak, Ay Yıl)" — örn: "(Booking.com, Şubat 2026)"
- İstatistik → "([Resmi kaynak], [Yıl])"
- Açılış saati → "(Son kontrol: Şubat 2026)"
- Kişisel → "Ben ... buldum" veya "Bence..."
"""


# ═══════════════════════════════════════════════════════════════════════════════
# EDİTÖR DENETİM KRİTERLERİ
# ═══════════════════════════════════════════════════════════════════════════════

EDITORIAL_CRITERIA = """
8 KRİTER — YAYINLANMA STANDARDI (her biri /10, toplam 80+):

1. ANLATI DERİNLİĞİ (≥7): Her yer için tarihçe + mimari + davranış gözlemi + neden
2. OTORİTE SEVİYESİ (≥7): Fiyat kaynaklı, sayısal, doğrulanabilir
3. KİŞİSEL BAKIŞ (≥7): Kemal'in sesi belirgin, "ben" var, deneyim tarihli
4. BİLGİ GÜVENİLİRLİĞİ (≥8): Son 12 ayda güncellendi, çelişki yok
5. SEO YAPI (≥7): H1→H2→H3 hiyerarşi, içindekiler, internal link
6. BEKLENTİ AYARLAMA (≥6): Fiyat context, kalabalık takvimi, "Instagram vs Gerçek"
7. ELEŞTİRİ CESARETİ (≥6): Turist tuzağı uyarısı, eleştirel gözlem
8. ZAMANSIZLIK (≥7): Zamansız katman güçlü, dinamik bilgi "(Şubat 2026)" ile
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION-SPECIFIC GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_intro(original_content: str, city: str = "", country: str = "") -> str:
    """
    Giriş bölümü:
    - 2 uzun paragraf (şehir ruhu + kişisel bağ)
    - Fotoğraf placeholder
    - 2-3 paragraf kişisel bakış
    Tümü Gutenberg wp:paragraph bloğu.
    """
    print("   🔵 Giriş + kişisel bakış (Claude)...")

    prompt = f"""
{_GUIDE_SYSTEM_FULL}

GÖREV: {city} Gezi Rehberi için giriş bölümü. Gutenberg blok formatında.

YAPI (bu sırayla, sırayı bozma):

1. PARAGRAF 1 — Şehir ruhu (120-150 kelime):
   - İlk kelime <strong>{city}</strong> bold
   - Şehrin fiziksel karakteri: coğrafya, dominan yapı/nehir/dağ
   - Şehrin iç çelişkisi veya paradoksu (modern vs tarihi, kalabalık vs tenha)
   - Anahtar cümlelerde bold öbek (kelime değil): <strong>ticaret yollarının kesiştiği nokta</strong> gibi
   - Minimum 5 cümle

2. PARAGRAF 2 — Tarihsel katman + kişisel bağ (120-150 kelime):
   - Tarihi dönemler veya olaylar (ama kuru liste değil, hikâye)
   - Temporal anchor: "1995'te ilk gittiğimde..." veya "2019'da..."
   - Şehrin size ne hissettirdiği (ama: abartısız, somut)
   - Minimum 5 cümle

[FOTOĞRAF YER TUTUCUSU — KENDİLİĞİNDEN GELECEK, SEN YAZMA]

3. PARAGRAF 3 — Kişisel bakış 1 (80-100 kelime):
   - Gerçek bir kişisel gözlem veya anekdot (yıl + spesifik yer + ne oldu)
   - Olumlu bir not, somut

4. PARAGRAF 4 — Kişisel bakış 2 (80-100 kelime):
   - Beklenti ayarlama: "Instagram'da böyle görünüyor, gerçekte..."
   - Turist kalabalığı veya fiyat gerçeği, sayısal

5. PARAGRAF 5 — Kişisel bakış 3 / pratik tavsiye (80-100 kelime):
   - Önerim: en az X gün, hangi mevsim, sabah kaçta kalk
   - "Ben öneriyorum" ile bitiş

BOLD KURALI — UYGULA:
DOĞRU: <strong>600 yıllık taş köprünün sabah sessizliği</strong> başka bir şeydir.
YANLIŞ: <strong>Karl</strong> Köprüsü sabah <strong>tenha</strong> oluyor.

Orijinal içerik (kaynak malzeme):
{original_content}

FORMAT — HER PARAGRAF GUTENBERG BLOĞU:
<!-- wp:paragraph -->
<p>Metin...</p>
<!-- /wp:paragraph -->

Sadece 5 wp:paragraph bloğu döndür. Fotoğraf placeholder yazma, başlık yazma.
"""
    return ask_claude(prompt, max_tokens=1024)


def generate_city_profile(original_content: str, city: str = "",
                          city_flag: str = "🌍") -> str:
    """
    Sehir profili bolumu.
    H2: 'Destinasyon Gezi Rehberi: Katman Katman Sehir Anatomisi' + ulke bayragi.
    Gutenberg blok formati. Bold obek duzeyinde.
    """
    print("   🟢 Şehir profili (GPT)...")

    prompt = f"""
{_GUIDE_SYSTEM_GPT}

GOREV: {city} sehir profili bolumu. Gutenberg blok formatinda.

H2 FORMATI:
<!-- wp:heading -->
<h2><strong>{city} Gezi Rehberi: [ŞEHRİN KARAKTERİNİ YAKALAYAN 4-6 KELİMELİK FARKLI BAŞLIK]</strong> {city_flag}</h2>
<!-- /wp:heading -->

H2 BAŞLIK KURALI:
- "Katman Katman Şehir Anatomisi" YAZMA — her şehirde aynı olur
- Şehrin özüne, tarihe veya deneyime dayalı özgün başlık yaz
- Örnekler:
  Prag → "Taş Döşeli Sokaklar ve 700 Yıllık Süreklilik"
  Bosna Hersek → "Üç Kültürün Kesişiminde Direniş ve Yeniden Doğuş"
  Dubrovnik → "Surlarla Çevrili Bir Açık Hava Sahnesi"
  Hurghada → "Mercan Resiflerinden Çöle: İki Yüzlü Bir Tatil Kenti"
- Tanımı SADECE şehre özel, tekrar edilemez yapı
- maksimum 7 kelime

5 PARAGRAF (her biri Gutenberg wp:paragraph bloku):

Para 1: Cografya ve fiziksel baglam
- {city}'in konumu, hangi nehir/dag/ova uzerinde kurulu
- Sehrin gunluk hayatla kurdugu iliski (soyut degil, gunluk gozlem)

Para 2: Gorsel doku, celisik yan yana yapi
- Modern vs tarihi, sehrin "jeolojik kesiti"
- Cumle icinde bold obek ornegi: <strong>gotik katedral ile art nouveau bina yan yana</strong>

Para 3: Tarihi katmanlar
- Kac medeniyetten iz var, kisa ve somut
- Hangi donem nerede goruluyor (mimari marker)
- Bold anlamli obek: <strong>900 yili askin sureklii iskan</strong>

Para 4: Simgesel yer ile kimlik ozeti
- 1 yer, 1 davranis gozlemi, 1 beklenti ayarlama
- Gunde kac turist, sabah/aksam farki

Para 5: Sehrin karakteri, abartisiz
- "X guzel ama Y" yapisi
- Budapes ve Viyana ile kisa karsilastirma
- Son cumle: kim icin uygun, kim icin degil

ICERMELI (SEHRE OZEL — KAYNAK GEREKTIRIR):
- {city} icin gercek nufus bilgisi (orijinal icerigi kullan, yoksa yazma)
- UNESCO veya benzeri statü varsa belirt (dogrulanmis ise)
- Yillik turist sayisi (kaynak varsa)

BOLD ORNEKLER (bunlari model al):
DOGRU: <strong>sezon zirvesinde gunde 20.000 turist alan</strong> bir sehir
YANLIS: <strong>kalabalik</strong> ve <strong>turistik</strong> bir sehir


Orijinal icerik:
{original_content}

Format: H2 bloku + 5 x wp:paragraph bloku. Toplam 350-450 kelime.
YASAK: muhtesem, harika, buyuleyici, essis, Pro/Con kutu.


YASAK ÇIKIŞ: Sarmasız <p>. Her paragraf <!-- wp:paragraph --> bloğu içinde."""
    return ask_gpt(prompt, max_tokens=1536)


def generate_when_to_go(city: str = "", original_content: str = "") -> str:
    """
    Ne zaman gidilir — şehre özel mevsim bilgisi, Gutenberg blokları.
    """
    print("   🟢 Ne zaman gidilir (GPT)...")

    prompt = f"""
{_GUIDE_SYSTEM_GPT}

GÖREV: "{city} Ne Zaman Gidilir?" bölümü. Gutenberg blok formatında.

H2 FORMATI:
<!-- wp:heading -->
<h2><strong>{city} Ne Zaman Gidilir?</strong> ☀️🌧❄️</h2>
<!-- /wp:heading -->

ŞEHRE ÖZEL MEVSIM BİLGİSİ:
- Orijinal içerikten {city}'a ait iklim/mevsim bilgilerini çıkar
- {city}'ın gerçek iklimine göre yaz (deniz iklimi mi, kara iklimi mi, dağ mı?)
- Sıcaklık değerleri, yağış, turist yoğunluğu o şehire özgü olmalı

YAPI:

1. Giriş paragrafı (1 wp:paragraph):
"En güzel sezon diye bir şey yok. Her mevsimin artısı eksisi var." tarzında açılış.
Kişisel tercih ipucu ver ama detaysız, aşağıda gelecek.

2. 4 mevsim paragrafı (her biri ayrı wp:paragraph):
Format: paragraf başında bold mevsim etiketi + iki nokta + açıklama.
ÖRNEK:
<!-- wp:paragraph -->
<p><strong>İlkbahar (Nisan-Mayıs):</strong> Sıcaklık değerleri, turist durumu, fiyat. Kişisel tercih cümlesi.</p>
<!-- /wp:paragraph -->

3. Kapanış paragrafı (1 wp:paragraph):
"Ben ... tercih ediyorum, çünkü ..." — kişisel tercih.

KESİN YASAK:
- H3 başlık kullanma (mevsimler için)
- Em-dash (—) anlatı içinde
- Tek kelime bold: <strong>ideal</strong> gibi
- Başka şehrin iklim verisini kullanma

Orijinal içerik (şehre ait iklim bilgisi çıkar):
{original_content}

FORMAT: H2 bloğu + 6 × wp:paragraph, toplam 280-320 kelime.


YASAK ÇIKIŞ: Sarmasız <p>. Her paragraf <!-- wp:paragraph --> bloğu içinde.
"""
    return ask_gpt(prompt, max_tokens=1024)


def generate_attractions(original_content: str, city: str = "", is_country: bool = False) -> str:
    """
    Gezilecek yerler — şehre özel 12 POI, Gutenberg blokları.
    top3 Claude ile derinleştirilir, kalan bulk GPT'den.
    """
    print("   🟢 Gezilecek yerler [OPT-3 single-pass]...")
    # OPT-3: 2 API çağrısı → 1 (GPT bulk + Claude polish birleştirildi)
    if is_country:
        # ÜLKE REHBERİ: 8-10 şehir/bölge
        # _GUIDE_SYSTEM_FULL kullanılıyor — KEMAL_VOICE + HTML_STRUCTURE + THIRTY_ERRORS
        country_prompt = (
            f"{_GUIDE_SYSTEM_FULL}\n\n"
            f"GOREV: \"{city}\" ülke rehberi — gezilecek şehirler. Gutenberg.\n\n"
            "H2:\n<!-- wp:heading -->\n"
            f"<h2><strong>{city} Gezilecek Şehirler – Rotanı Nasıl Planlamalısın?</strong> 📍</h2>\n<!-- /wp:heading -->\n\n"
            "GIRIS (2-3 wp:paragraph, anlatı dili):\n"
            f"- {city}'da kaç gün yeterli, hangi bölgeden başlanır\n"
            "- Ülke içi ulaşım seçeneği (otobüs/tren/araç) + net tavsiye\n"
            "- Kuzey-güney veya batı-doğu rota önerisi\n\n"
            "HER ŞEHİR (8-10 adet):\n"
            '<!-- wp:heading {"level":3} --><h3><strong>N. Şehir Adı</strong></h3><!-- /wp:heading -->\n'
            "<!-- wp:paragraph --><p>Şehrin karakteri — neden gidilmeli, ne hissettiriyor</p><!-- /wp:paragraph -->\n"
            "<!-- wp:paragraph --><p>Mutlaka görülecek 2-3 yer + pratik not</p><!-- /wp:paragraph -->\n"
            "<!-- wp:paragraph --><p>Kaç gün ideal + yanına hangi şehir ekle + ulaşım süresi</p><!-- /wp:paragraph -->\n"
            '<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->\n\n'
            "KURAL: H3 sadece şehir adı — neresi olduğunu H3'te açıklama. "
            "Şehirler arası mesafe/süre ekle. Her şehir için minimum süre belirt.\n"
            f"Kaynak:\n{original_content}\n\nToplam 2000-2500 kelime."
        )
        return ask_gpt(country_prompt, max_tokens=8192)

    prompt = (
        f"{_GUIDE_SYSTEM_GPT}\n\n"
        f'GOREV: "{city} Gezilecek Yerler" — 12 yer, Gutenberg.\n\n'
        "H2:\n<!-- wp:heading -->\n"
        f'<h2><strong>{city} Gezilecek Yerler – 12 Durak</strong> 📍</h2>\n<!-- /wp:heading -->\n\n'
        "GIRIS BÖLÜMÜ (3-4 wp:paragraph, anlatı dili — başlık stili değil):\n\n"
        "Para 1 — NASIL GEZİLİR?\n"
        "- Yürüyerek mi, toplu taşıma mı, araç mı? Net tavsiye ver, gerekçe ekle\n"
        "- Kaç gün ayırmalı? Minimum + ideal + 'zamanın yoksa 1 günde' versiyonu\n"
        "- Gezi planı zor mu kolay mı? Sezon ve kalabalık faktörünü dahil et\n\n"
        "Para 2 — PRATİK LOJİSTİK\n"
        f"- City card/pass avantajlı mı? Varsa: adı + fiyatı + resmi linki (format: <a href='URL'>Kart Adı</a>)\n"
        "- Araç mı toplu taşıma mı? Net karar + kısa gerekçe\n"
        "- Turist pik zamanı ne? Sabah/akşam ziyareti avantaj sağlar mı?\n\n"
        "KURAL: Arkadaşına anlatır gibi, samimi. 'Ben öneriyorum' kullanabilirsin.\n\n"
        "HER POI (5 paragraf minimum):\n"
        '<!-- wp:heading {"level":3} --><h3><strong>N. Yer Adı – Alt Başlık</strong></h3><!-- /wp:heading -->\n'
        "<!-- wp:paragraph --><p>Tarih + boyut/yıl/rakam + neden önemli (bağlam kur)</p><!-- /wp:paragraph -->\n"
        "<!-- wp:paragraph --><p>Kişisel gözlem + kalabalık gerçeği + Instagram vs gerçek karşılaştırması</p><!-- /wp:paragraph -->\n"
        "<!-- wp:paragraph --><p>Fiyat (kaynak, tarih) + bilet/giriş detayı + ücretsiz alternatif varsa</p><!-- /wp:paragraph -->\n"
        "<!-- wp:paragraph --><p>Nasıl gidilir: en yakın metro/tramvay/durak + yürüme süresi + en iyi giriş noktası</p><!-- /wp:paragraph -->\n"
        "<!-- wp:paragraph --><p><em>Kemal'in Notu: [50-70 kelime — kişisel deneyim, beklenti ayarı, insider tavsiye]</em></p><!-- /wp:paragraph -->\n"
        '<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->\n\n'
        "YASAK: emojili kutular, ** bold\n"
        f'BITIS: "Ben {city}\'i ... yil arayla gordum..." paragraf\n\n'
        f"Kaynak:\n{original_content}\n\nToplam 2000-2500 kelime."
    )
    return ask_gpt(prompt, max_tokens=8192)
def generate_food(original_content: str, city: str = "") -> str:
    """Yeme-İçme — orijinal içerikten şehre özel, Gutenberg blokları."""
    print("   🟢 Yeme-içme (GPT)...")

    prompt = f"""
{_GUIDE_SYSTEM_GPT}

GÖREV: "{city} Yeme ve İçme" bölümü. Gutenberg blok formatında.

H2 FORMATI:
<!-- wp:heading -->
<h2><strong>{city} Yeme ve İçme – Yerel Mutfaktan Samimi Notlar</strong> 🍽</h2>
<!-- /wp:heading -->

ŞEHRE ÖZEL İÇERİK ÜRETİM KURALI:
- Orijinal içerikten {city}'a ait yemek/içecek/restoran bilgilerini çıkar
- Orijinal içerikte yoksa kendi bilginden üret ama DOĞRULUĞUNDAN EMİN OL
- Kesinlikle başka şehrin yemeklerini yazma

BÖLÜMLER (her biri Gutenberg wp:paragraph bloğu içinde):

H3 1: Yerel mutfak nedir? (O şehre/ülkeye özgü, bold yemek isimleri)
H3 2: İçecek kültürü (Bira, şarap, rakı, kahve — o kültüre göre)  
H3 3: Nerede yemeli? (Semt fiyat karşılaştırması, turist bölgesi vs yerel)
H3 4: Turist tuzağı uyarısı (O şehirde gerçekten var olan tuzak)

HER PARAGRAF GUTENBERG BLOĞU:
<!-- wp:paragraph -->
<p>Metin...</p>
<!-- /wp:paragraph -->

H3 BAŞLIKLAR:
<!-- wp:heading {{"level":3}} -->
<h3><strong>Başlık</strong></h3>
<!-- /wp:heading -->

ZORUNLU BOLD ÖBEK (TEK KELİME YASAK):
DOĞRU: <strong>yerel restoranların standart fiyatı 8-15€</strong>
YANLIŞ: <strong>restoran</strong>


Orijinal içerik:
{original_content}

Format: H2 bloğu + 4 × H3 + wp:paragraph blokları, 450-550 kelime.

YASAK ÇIKIŞ: Sarmasız <p>. Her paragraf <!-- wp:paragraph --> bloğu içinde.
"""
    return ask_gpt(prompt, max_tokens=1536)


def generate_accommodation(original_content: str, city: str = "") -> str:
    """Konaklama — şehre özel mahalle analizi, Gutenberg blokları."""
    print("   🟢 Konaklama (GPT)...")

    prompt = f"""
{_GUIDE_SYSTEM_GPT}

GÖREV: "{city} Konaklama" bölümü. Gutenberg blok formatında.

H2 FORMATI:
<!-- wp:heading -->
<h2><strong>{city} Konaklama – Semt Semt Gerçekçi Değerlendirme</strong> 🏨</h2>
<!-- /wp:heading -->

ŞEHRE ÖZEL MAHALLE ANALİZİ:
- Orijinal içerikten {city}'a ait semt/mahalle bilgilerini çıkar
- {city}'ın gerçek mahallelerini kullan (başka şehrin semtlerini yazma)
- 3-4 mahalle: biri "Ben öneriyorum", biri "Bütçe dostu", biri "Tarihi atmosfer", biri "Önerilmez/Turist tuzağı"

HER MAHALLE:
<!-- wp:heading {{"level":3}} -->
<h3><strong>Mahalle Adı – Kısa Etiket</strong></h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>2 paragraf: Neden iyi/kötü, fiyat aralığı, kişisel görüş. Bold öbek kullan.</p>
<!-- /wp:paragraph -->

BÜTÇE ÖZETİ (son bir paragraf, tablo değil):
Backpacker/orta/konforlu günlük bütçe tahmini. "{city} Türkiye'den X kat pahalı" karşılaştırması.

BOLD ÖBEK KURALI:
DOĞRU: <strong>merkezi konumuyla tüm turistik yerlere yürüyüş mesafesinde</strong>
YANLIŞ: <strong>merkezi</strong> ve <strong>turistik</strong>


Orijinal içerik:
{original_content}

Format: H2 bloğu + 3-4 × H3 + wp:paragraph blokları + bütçe paragrafı, 400-500 kelime.

YASAK ÇIKIŞ: Sarmasız <p>. Her paragraf <!-- wp:paragraph --> bloğu içinde.
"""
    return ask_gpt(prompt, max_tokens=1536)


def generate_transport(original_content: str, city: str = "") -> str:
    """Nasıl Gidilir + Şehir İçi Ulaşım — şehre özel, Gutenberg blokları."""
    print("   🟢 Ulaşım (GPT)...")

    prompt = f"""
{_GUIDE_SYSTEM_GPT}

GÖREV: "{city} Nasıl Gidilir ve Şehir İçi Ulaşım" bölümü. Gutenberg blok formatında.

H2 FORMATI:
<!-- wp:heading -->
<h2><strong>{city} Nasıl Gidilir? – Türkiye'den {city}'a Ulaşım</strong> ✈️</h2>
<!-- /wp:heading -->

ŞEHRE ÖZEL ULAŞIM BİLGİSİ:
- Orijinal içerikten {city}'a ait ulaşım bilgilerini çıkar
- Havalimanı adı, şehir merkezi mesafesi, toplu taşıma seçenekleri, bilet fiyatları
- Türkiye'den direkt uçuş var mı? Hangi havayolları?
- Yanlış/hayali bilgi yazma, bilmiyorsan "kontrol edin" de

BÖLÜMLER:

H3 1: Uçak (havalimanı adı, Türkiye'den seçenekler, fiyat aralığı)
H3 2: Havalimanından Şehre (toplu taşıma + taksi, fiyat + süre + uyarı)
H3 3: Şehir İçi Ulaşım (metro/tramvay/otobüs, bilet sistemi, günlük kart)
H3 4: Yürüyüş (şehir merkezi yürüme mesafesi, zemin uyarısı)

HER PARAGRAF GUTENBERG BLOĞU:
<!-- wp:paragraph -->
<p>Metin...</p>
<!-- /wp:paragraph -->

BOLD ÖBEK:
DOĞRU: <strong>havalimanından merkeze 45 dakika, tek bilet ile</strong>
YANLIŞ: <strong>hızlı</strong> ve <strong>ucuz</strong>


Orijinal içerik:
{original_content}

Format: 2 × H2 bloğu + 4 × H3 + wp:paragraph blokları, 400-500 kelime.
"""
    return ask_gpt(prompt, max_tokens=1536)


def generate_practical(original_content: str, city: str = "") -> str:
    """Pratik bilgiler — şehre özel, Gutenberg blokları."""
    print("   🟢 Pratik bilgiler (GPT)...")

    prompt = f"""
{_GUIDE_SYSTEM_GPT}

GÖREV: "{city} Pratik Bilgiler" bölümü. Gutenberg blok formatında.

H2 FORMATI:
<!-- wp:heading -->
<h2><strong>Pratik Bilgiler – Para, Dil, Güvenlik, Vize</strong> 💡</h2>
<!-- /wp:heading -->

ŞEHRE ÖZEL BİLGİ — orijinal içerikten çıkar:
- {city}'ın para birimi ve kur bilgisi
- Konuşulan dil(ler) ve turist için durum
- Güvenlik seviyesi (Numbeo veya benzeri kaynak)
- Bahşiş kültürü o ülkede nasıl?
- Şehir kartı/müzekart varsa değerlendir
- Türk vatandaşları için vize durumu (Schengen mı, anlaşma var mı, vizesiz mi?)

HER ALT BAŞLIK:
<!-- wp:heading {{"level":3}} -->
<h3><strong>Para Birimi</strong></h3>
<!-- /wp:heading -->
<!-- wp:paragraph -->
<p>Detay...</p>
<!-- /wp:paragraph -->

BÖLÜMLER: Para Birimi, Dil, Güvenlik, Bahşiş Kültürü, Şehir Kartı (varsa), Vize

BOLD ÖBEK:
DOĞRU: <strong>Türk vatandaşları için Schengen vizesi zorunlu</strong>
YANLIŞ: <strong>vize</strong> gerekiyor

Orijinal içerik:
{original_content}

Format: H2 bloğu + 5-6 × H3 + wp:paragraph blokları, 450-550 kelime.

YASAK ÇIKIŞ: Sarmasız <p>. Her paragraf <!-- wp:paragraph --> bloğu içinde.
"""
    return ask_gpt(prompt, max_tokens=1536)


def generate_itinerary(city: str = "", original_content: str = "") -> str:
    """Gezi planı — şehre özel rota, Gutenberg blokları."""
    print("   🟢 Gezi planı (GPT)...")

    prompt = f"""
{_GUIDE_SYSTEM_GPT}

GÖREV: "{city} Gezi Planı" bölümü. Gutenberg blok formatında.

H2 FORMATI:
<!-- wp:heading -->
<h2><strong>Gezi Planı – 1 Gün, 3 Gün ve Zamanın Yoksa</strong> 🗓</h2>
<!-- /wp:heading -->

ŞEHRE ÖZEL ROTALAR — {city}'a ait gerçek yerler kullan:

H3 1: 1 Günlük {city}
- Saat bazlı program (07:00-09:00 arası gibi)
- "Ben 201X'te böyle yaptım..." kişisel deneyim

H3 2: 3 Günlük {city}
- Gün 1/2/3 başlıkları
- Her gün için somut öneri listesi (anlatı formunda)

H3 3: Zamanın Yoksa (4 saat veya yarım gün)
- En kritik 3-4 yer, sırayla

H3 4: Günübirlik Turlar (varsa)
- {city} yakınında günübirlik yapılabilecek 2-3 yer
- Her biri için: mesafe + süre + "değer mi?" kişisel değerlendirme

HER PARAGRAF GUTENBERG BLOĞU:
<!-- wp:paragraph -->
<p>Metin...</p>
<!-- /wp:paragraph -->


Orijinal içerik:
{original_content}

Format: H2 bloğu + 4 × H3 + wp:paragraph blokları, 500-600 kelime.
Emoji YOK (sadece 🗓 H2'de).
"""
    return ask_gpt(prompt, max_tokens=2048)


def generate_faq(original_content: str = "", city: str = "",
                 city_en: str = "", country: str = "", country_en: str = "",
                 post_slug: str = "", is_turkey_dest: bool = False) -> str:
    """
    SSS + Schema bloğu — tek wp:html kutusu olarak döner.
    Narrative H3+p SSS bölümü kaldırıldı; schema_engine bu görevi üstlendi.
    Google FAQPage rich snippet + TravelGuide JSON-LD aynı blokta.
    """
    from schema_engine import generate_schema_block
    return generate_schema_block(
        city=city, city_en=city_en,
        country=country, country_en=country_en,
        post_summary=original_content,
        post_slug=post_slug or (city.lower().replace(' ', '-') + '-gezi-rehberi'),
        is_turkey_dest=is_turkey_dest
    )


def generate_schema_json(title: str, city: str = "",
                         city_en: str = "", country_en: str = "",
                         url: str = "https://yoldaolmak.com/") -> str:
    """Schema.org markup — temiz JSON-LD, <br/> YOK."""
    import datetime
    year_month = datetime.date.today().strftime("%Y-%m")

    schema = {
        "@context": "https://schema.org",
        "@type": "TravelGuide",
        "name": title,
        "description": f"{city} gezi rehberi {datetime.date.today().year} — gezilecek yerler, fiyatlar, ulaşım, konaklama. Kemal Kaya'dan güncel bilgiler.",
        "url": url,
        "author": {
            "@type": "Person",
            "name": "Kemal Kaya",
            "url": "https://yoldaolmak.com"
        },
        "dateModified": year_month,
        "about": {
            "@type": "City",
            "name": city_en,
            "alternateName": city,
            "containedInPlace": {
                "@type": "Country",
                "name": country_en
            }
        },
        "publisher": {
            "@type": "Organization",
            "name": "Yoldaolmak.com",
            "url": "https://yoldaolmak.com"
        }
    }

    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"{city}'da kaç gün kalınır?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"{city} için minimum 4-5 gün öneriyorum. Ana meydanlar ve kaleler için 2 gün, yerel semtler ve müzeler için 2 gün daha."
                }
            },
            {
                "@type": "Question",
                "name": f"{city} pahalı mı?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"{city} için günlük bütçe rehber içinde belirtilmiştir. Orta sınıf otel ve restoranlar için Türkiye'nin 2-4 katı arası bütçe hesaplayın."
                }
            },
            {
                "@type": "Question",
                "name": f"Türk vatandaşları {city}'a nasıl gidebilir?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Güncel vize ve giriş koşulları için {city} büyükelçiliğini veya resmi turizm sitesini kontrol edin. Bilgiler değişkenlik gösterebilir."
                }
            }
        ]
    }

    return f"""<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=2)}
</script>

<script type="application/ld+json">
{json.dumps(faq_schema, ensure_ascii=False, indent=2)}
</script>"""


def generate_closing(original_content: str, city: str = "") -> str:
    """Kapanış — 2 wp:paragraph bloğu, somut ve pratik."""
    print("   🔵 Kapanış (Claude)...")

    prompt = f"""
{_GUIDE_SYSTEM}

GÖREV: {city} Gezi Rehberi için kapanış. 2 paragraf, Gutenberg blok formatında.

Paragraf 1: Şehrin kısa özeti.
"X güzel bir şehir, Y günde geziyorsunuz." Gerçekçi uyarı. Somut öneri.

Paragraf 2: Bütçe özeti + en kritik pratik ipucu.
Beklenti ayarlama: "Instagram seviyesine değil, normal bir Avrupa şehri seviyesine ayarla."

YASAK: Duygusal kapanış, em-dash (—) anlatı içinde
ZORUNLU: En az 1 sayısal veri, Kemal sesi

Orijinal içerikten kapanış varsa kullan:
{original_content}

FORMAT:
<!-- wp:paragraph -->
<p>...</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>...</p>
<!-- /wp:paragraph -->


YASAK ÇIKIŞ: Sarmasız <p>. Her paragraf <!-- wp:paragraph --> bloğu içinde."""
    return ask_claude(prompt, max_tokens=1024)


def editorial_review(full_content: str) -> dict:
    """8 kriterli editoryal denetim."""
    print("   🔵 Editoryal denetim (Claude)...")

    prompt = f"""
{EDITORIAL_CRITERIA}

Aşağıdaki içeriği 8 kriterde değerlendir. Her kriter için 1-10 puan ver.
Toplam 80+ ise yayına hazır.

İçerik (ilk 5000 karakter):
{full_content[:5000]}

ÇIKTI FORMATI (sadece JSON):
{{
  "anlati_derinligi": X,
  "otorite_seviyesi": X,
  "kisisel_bakis": X,
  "bilgi_guvenirligi": X,
  "seo_yapi": X,
  "beklenti_ayarlama": X,
  "elestiri_cesareti": X,
  "zamansizlik": X,
  "toplam": X,
  "sonuc": "yayina_hazir/revizyon_gerekli",
  "kritik_eksikler": ["eksik1", "eksik2"]
}}
"""
    try:
        response = ask_claude(prompt)
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"toplam": 0, "sonuc": "degerlendirilemedi"}


# ═══════════════════════════════════════════════════════════════════════════════
# GUTENBERG POST-PROCESSOR — AI çıktısını garanti altına alır
# ═══════════════════════════════════════════════════════════════════════════════

def postprocess_gutenberg(html: str) -> str:
    """
    AI'nın ürettiği HTML'i Gutenberg bloklarına dönüştür.
    Zaten sarmalanmış blokları tekrar sarmaz.
    wp:html bloğu içine DOKUNMAZ (schema/CSS inline içerir).
    Bare <p>, <h2>, <h3> → wp:paragraph / wp:heading wrapper ekler.
    """
    lines = html.split('\n')
    result = []
    i = 0
    in_raw_block = False  # wp:html veya wp:shortcode içindeyiz — dokunma

    def already_wrapped() -> bool:
        """Bir önceki satırda wp: comment var mı?"""
        prev = result[-1].strip() if result else ""
        return "<!-- wp:" in prev

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Raw block başlangıcı (wp:html, wp:shortcode)
        if not in_raw_block and re.match(r'^<!-- wp:html\b', stripped):
            in_raw_block = True
            result.append(line)
            i += 1
            continue

        # Raw block bitişi
        if in_raw_block and stripped.startswith('<!-- /wp:html'):
            in_raw_block = False
            result.append(line)
            i += 1
            continue

        # Raw block içindeyiz — dokunma
        if in_raw_block:
            result.append(line)
            i += 1
            continue

        # Zaten Gutenberg bloğu — aynen geç
        if stripped.startswith("<!-- wp:") or stripped.startswith("<!-- /wp:"):
            result.append(line)
            i += 1
            continue

        # <h2> — heading bloğu
        if re.match(r'^<h2[^>]*>', stripped) and not already_wrapped():
            result.append("<!-- wp:heading -->")
            result.append(line)
            result.append("<!-- /wp:heading -->")
            i += 1
            continue

        # <h3> — heading bloğu (level 3)
        if re.match(r'^<h3[^>]*>', stripped) and not already_wrapped():
            result.append('<!-- wp:heading {"level":3} -->')
            result.append(line)
            result.append("<!-- /wp:heading -->")
            i += 1
            continue

        # <p> — paragraph bloğu
        if re.match(r'^<p[^>]*>', stripped) and not already_wrapped():
            result.append("<!-- wp:paragraph -->")
            result.append(line)
            result.append("<!-- /wp:paragraph -->")
            i += 1
            continue

        # <hr> separator — wp:separator
        if stripped in ("---", "<hr>", "<hr/>",
                        '<hr class="wp-block-separator has-alpha-channel-opacity"/>'):
            result.append('<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->')
            i += 1
            continue

        # Boş satır veya diğer
        result.append(line)
        i += 1

    return '\n'.join(result)


def fix_bold_markdown(html: str) -> str:
    """
    AI'nın Markdown bold'u (**kelime**) HTML <strong>'e dönüştür.
    Bazı modeller Gutenberg içinde **metin** formatını bırakabiliyor.
    """
    # **metin** → <strong>metin</strong>
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    return html


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN GUIDE GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_guide(post: dict) -> tuple[str, str]:
    """
    Ana fonksiyon: WP post dict alır, (title, html_content) döndürür.
    Guide Yapı Standardı — v2.1
    """
    from wp import strip_html

    # ── Türkçe slug yardımcısı ───────────────────────────────────────────────
    def _slugify(text: str) -> str:
        """Türkçe metni URL slug'ına çevir."""
        text = text.replace('İ', 'i').replace('I', 'i')
        return (text.lower()
                .replace(' ', '-')
                .replace('ı', 'i').replace('ş', 's').replace('ğ', 'g')
                .replace('ü', 'u').replace('ö', 'o').replace('ç', 'c')
                .replace('â', 'a').replace('î', 'i').replace('û', 'u'))

    # ── Post verisi ───────────────────────────────────────────────────────────
    raw_title = post.get("title", {})
    title_str = raw_title.get("rendered", "") if isinstance(raw_title, dict) else str(raw_title)

    raw_content = post.get("content", {})
    html_content = raw_content.get("rendered", "") if isinstance(raw_content, dict) else str(raw_content)
    original_text = strip_html(html_content)

    # ── Post slug (en güvenilir kaynak — engine tarafından değiştirilmez) ────
    # Önceki hatalı run title'ı "Prag Gezi Rehberi" yazmış olabilir.
    # Slug ise WP tarafından ilk oluşturulurken set edilir, update_post() değiştirmez.
    post_slug_raw = post.get("slug", "")  # örn: "bosna-hersek-gezi-rehberi"

    # ── CITY_META tablosu ─────────────────────────────────────────────────────
    # city (Türkçe) → (city_en, country_tr, country_en, flag)
    # NOT: Bu blok city_from_slug() fonksiyonu için önce tanımlanmalı.

    # ── Şehir → ülke/dil eşleştirme tablosu ─────────────────────────────────
    # city (Türkçe) → (city_en, country_tr, country_en, flag)
    CITY_META = {
        # Balkanlar
        "Bosna Hersek":   ("Bosnia and Herzegovina", "Bosna Hersek",    "Bosnia and Herzegovina", "🇧🇦"),
        "Saraybosna":     ("Sarajevo",               "Bosna Hersek",    "Bosnia and Herzegovina", "🇧🇦"),
        "Mostar":         ("Mostar",                 "Bosna Hersek",    "Bosnia and Herzegovina", "🇧🇦"),
        "Dubrovnik":      ("Dubrovnik",              "Hırvatistan",     "Croatia",                "🇭🇷"),
        "Zagreb":         ("Zagreb",                 "Hırvatistan",     "Croatia",                "🇭🇷"),
        "Split":          ("Split",                  "Hırvatistan",     "Croatia",                "🇭🇷"),
        "Belgrad":        ("Belgrade",               "Sırbistan",       "Serbia",                 "🇷🇸"),
        "Kotor":          ("Kotor",                  "Karadağ",         "Montenegro",             "🇲🇪"),
        "Tiran":          ("Tirana",                 "Arnavutluk",      "Albania",                "🇦🇱"),
        "Üsküp":          ("Skopje",                 "Kuzey Makedonya", "North Macedonia",        "🇲🇰"),
        # Orta Avrupa
        "Prag":           ("Prague",                 "Çek Cumhuriyeti", "Czech Republic",         "🇨🇿"),
        "Brno":           ("Brno",                   "Çek Cumhuriyeti", "Czech Republic",         "🇨🇿"),
        "Viyana":         ("Vienna",                 "Avusturya",       "Austria",                "🇦🇹"),
        "Budapeşte":      ("Budapest",               "Macaristan",      "Hungary",                "🇭🇺"),
        "Varşova":        ("Warsaw",                 "Polonya",         "Poland",                 "🇵🇱"),
        "Krakow":         ("Krakow",                 "Polonya",         "Poland",                 "🇵🇱"),
        "Berlin":         ("Berlin",                 "Almanya",         "Germany",                "🇩🇪"),
        "Münih":          ("Munich",                 "Almanya",         "Germany",                "🇩🇪"),
        "Leipzig":        ("Leipzig",                "Almanya",         "Germany",                "🇩🇪"),
        # Batı Avrupa
        "Paris":          ("Paris",                  "Fransa",          "France",                 "🇫🇷"),
        "Lizbon":         ("Lisbon",                 "Portekiz",        "Portugal",               "🇵🇹"),
        "Madrid":         ("Madrid",                 "İspanya",         "Spain",                  "🇪🇸"),
        "Barselona":      ("Barcelona",              "İspanya",         "Spain",                  "🇪🇸"),
        "Amsterdam":      ("Amsterdam",              "Hollanda",        "Netherlands",            "🇳🇱"),
        # Güney Avrupa
        "Roma":           ("Rome",                   "İtalya",          "Italy",                  "🇮🇹"),
        "Floransa":       ("Florence",               "İtalya",          "Italy",                  "🇮🇹"),
        "Venedik":        ("Venice",                 "İtalya",          "Italy",                  "🇮🇹"),
        "Atina":          ("Athens",                 "Yunanistan",      "Greece",                 "🇬🇷"),
        "Selanik":        ("Thessaloniki",           "Yunanistan",      "Greece",                 "🇬🇷"),
        # Türkiye
        "İstanbul":       ("Istanbul",               "Türkiye",         "Turkey",                 "🇹🇷"),
        "Kapadokya":      ("Cappadocia",             "Türkiye",         "Turkey",                 "🇹🇷"),
        # Orta Doğu / Asya
        "Bali":           ("Bali",                   "Endonezya",       "Indonesia",              "🇮🇩"),
        "Tokyo":          ("Tokyo",                  "Japonya",         "Japan",                  "🇯🇵"),
        "Bkk":            ("Bangkok",                "Tayland",         "Thailand",               "🇹🇭"),
        "Bangkok":        ("Bangkok",                "Tayland",         "Thailand",               "🇹🇭"),
        "Dubai":          ("Dubai",                  "BAE",             "UAE",                    "🇦🇪"),
    }

    # ── Şehirden slug çıkarma: CITY_META → slug reverse lookup ─────────────
    # Önce CITY_META'da slug eşleştir: her şehrin slug'ını hesapla, post slug ile karşılaştır
    # Bu yaklaşım title'dan bağımsızdır — engine hatalı title yazmış olsa bile çalışır.
    def _city_from_slug(raw_slug: str) -> str:
        """Post slug'ından şehir adını CITY_META üzerinden çıkar."""
        import re as _re
        city_slug = _re.sub(r'[-_]gezi[-_]rehberi.*$', '', raw_slug.lower())
        for city_name in CITY_META:
            if _slugify(city_name) == city_slug:
                return city_name
        # CITY_META'da yoksa: slug → insan okunabilir (bosna-hersek → Bosna Hersek)
        return city_slug.replace('-', ' ').title()

    # ── Şehir tespiti: 1. SLUG, 2. TITLE ─────────────────────────────────────
    city = None

    # 1. Öncelik: post slug (güvenilir, engine tarafından asla değiştirilmez)
    if post_slug_raw:
        city_from_slug = _city_from_slug(post_slug_raw)
        if city_from_slug and city_from_slug.lower() not in ("", "unknown", "bilinmiyor"):
            city = city_from_slug

    # 2. Fallback: post title (slug yoksa veya "gezi-rehberi" içermiyorsa)
    if not city and title_str:
        import re as _re2
        city_match = _re2.match(r'^(.+?)\s+Gezi Rehberi', title_str, _re2.IGNORECASE)
        if city_match:
            city = city_match.group(1).strip()

    # 3. Son fallback: title'ın ilk kısmı
    if not city:
        city = (title_str.split(":")[0].strip() if title_str else "Bilinmiyor")

    post_slug = _slugify(city) + "-gezi-rehberi"

    # ── CITY_META lookup ─────────────────────────────────────────────────────
    meta = CITY_META.get(city)
    if meta:
        city_en, country, country_en, city_flag = meta
    else:
        city_en    = city
        country    = "Bilinmiyor"
        country_en = "Unknown"
        city_flag  = "🌍"

    # MADDE 8: Ülke/şehir ayrımı
    # city == country_tr → ülke rehberi (Bosna Hersek, Polonya vb.)
    is_country = (city.lower() == country.lower()) or (city_en.lower() == country_en.lower())

    # Türkiye destinasyonu tespiti (FAQ'da vize/kur/saat farkı yasak)
    is_turkey_dest = (country_en.lower() == "turkey")

    print("\n" + "=" * 65)
    print("📖 GUIDE ENGINE v2.1 — Guide Yapı Standardı")
    print("=" * 65)
    print(f"📌 Post slug  : {post_slug_raw}")
    print(f"🏙️  Şehir     : {city}")
    print(f"📝 Orijinal içerik: {len(original_text):,} karakter")
    print("=" * 65)

    # ── Bölümleri üret ──────────────────────────────────────────────────────

    # OPT-1: Tek seferlik context ozeti
    context_summary = _extract_context_summary(original_text, city)

    intro = generate_intro(context_summary, city=city, country=country)
    time.sleep(1)

    city_profile = generate_city_profile(context_summary, city=city, city_flag=city_flag)
    time.sleep(1)

    when_to_go = generate_when_to_go(city=city, original_content=context_summary)
    time.sleep(1)

    attractions = generate_attractions(context_summary, city=city, is_country=is_country)
    time.sleep(1)

    food = generate_food(context_summary, city=city)
    time.sleep(1)

    accommodation = generate_accommodation(context_summary, city=city)
    time.sleep(1)

    transport = generate_transport(context_summary, city=city)
    time.sleep(1)

    practical = generate_practical(context_summary, city=city)
    time.sleep(1)

    itinerary = generate_itinerary(city=city, original_content=context_summary)
    time.sleep(1)

    faq = generate_faq(
        original_content=context_summary,
        city=city, city_en=city_en,
        country=country, country_en=country_en,
        post_slug=post_slug,
        is_turkey_dest=is_turkey_dest
    )
    time.sleep(1)

    closing = generate_closing(context_summary, city=city)
    time.sleep(1)

    # Schema + FAQ bloğu generate_faq() içinde üretildi (schema_engine).
    # Ayrıca generate_schema_json() çağrısı YOK — ikincil çakışma önlendi.

    # ── İçindekiler tablosu ─────────────────────────────────────────────────
    # TOC: H2 bölüm başlığının ÜSTÜNDE yer alır

    # # MADDE 4: TOC kaldırıldı — üretilmiyor
    # # toc = f"""<!-- wp:html -->
    # <nav class="toc">
    # <strong>İçindekiler</strong>
    # <ol>
    # <li><a href="#sehir-profili">{city} Gezi Rehberi</a></li>
    # <li><a href="#ne-zaman">Ne Zaman Gidilir?</a></li>
    # <li><a href="#gezilecek">Gezilecek Yerler</a></li>
    # <li><a href="#yeme-icme">Yeme-İçme</a></li>
    # <li><a href="#konaklama">Konaklama</a></li>
    # <li><a href="#nasil-gidilir">Nasıl Gidilir?</a></li>
    # <li><a href="#ulasim">Şehir İçi Ulaşım</a></li>
    # <li><a href="#gezi-plani">Gezi Planı</a></li>
    # <li><a href="#pratik">Pratik Bilgiler</a></li>
    # <li><a href="#sss">Sık Sorulan Sorular</a></li>
    # </ol>
    # </nav>
    # <!-- /wp:html -->"""

    # Gutenberg separator — tüm bölüm aralarında bu format
    SEP = "<!-- wp:separator --><hr class=\"wp-block-separator has-alpha-channel-opacity\"/><!-- /wp:separator -->"

    # Fotoğraf placeholder — giriş sonrası
    photo_placeholder = f"""<!-- wp:image -->
<figure class="wp-block-image"><!-- {city} ana fotoğrafı buraya gelecek --></figure>
<!-- /wp:image -->"""

    # ── Yeni başlık ─────────────────────────────────────────────────────────

    import datetime
    year = datetime.date.today().year
    # MADDE 1: SEO Title — Mevcut post başlığı korunur (Google'da test edilmiş),
    # sadece yıl güncellenir. Başlık yoksa şehir-odaklı format üretilir.
    raw_original_title = post.get("title", {})
    if isinstance(raw_original_title, dict):
        orig_title_text = raw_original_title.get("rendered", "")
    else:
        orig_title_text = str(raw_original_title)

    # HTML entity ve tag temizle
    import html as _html
    orig_title_text = _html.unescape(re.sub(r'<[^>]+>', '', orig_title_text)).strip()

    # Yıl güncelle: (2024) → (2026) veya sonuna ekle
    year_replaced = re.sub(r'\(20\d{2}\)', f'({year})', orig_title_text)
    if year_replaced != orig_title_text:
        new_title = year_replaced  # Yıl güncellendi, kalan korundu
    elif orig_title_text and len(orig_title_text) > 10:
        new_title = f"{orig_title_text} ({year})"  # Başlık var ama yıl yoktu
    else:
        new_title = f"{city} Gezi Rehberi: Gezilecek Yerler, Güncel Fiyatlar ve Pratik Bilgiler ({year})"  # fallback

    # ── Assembly — H1 YOK (WP title'dan geliyor), TOC > H2 > içerik ────────

    full_html = f"""{intro}

{photo_placeholder}

{SEP}

{city_profile}

{SEP}

{when_to_go}

{SEP}

{attractions}

{SEP}

{food}

{SEP}

{accommodation}

{SEP}

{transport}

{SEP}

{itinerary}

{SEP}

{practical}

{SEP}

{closing}

{SEP}

{faq}

<!-- SON GÜNCELLEME: {datetime.date.today().strftime("%B %Y")} -->
<!-- META: {city} gezi rehberi {year} — gezilecek yerler, fiyatlar, ulaşım, konaklama. Kemal Kaya'dan güncel bilgiler. -->
"""

    # OPT-4: editorial_review kaldirildi (-1 API/run). Kullan: clawdbot.py audit --post

    # ── Post-processing: Gutenberg + Markdown bold garanti ──────────────────
    print("🔧 Post-processing: Gutenberg blokları + bold düzeltme...")
    full_html = fix_bold_markdown(full_html)
    full_html = postprocess_gutenberg(full_html)

    # Kontrol: kaç bare <p> kaldı (sarmalanamayan)?
    # wp:html bloğu içindeki <p> tagları hariç tutulur (schema/CSS inline)
    html_for_count = re.sub(r'<!-- wp:html -->.*?<!-- /wp:html -->', '',
                            full_html, flags=re.DOTALL)
    total_p_tags = len(re.findall(r'<p[ >]', html_for_count))
    total_wp_p   = len(re.findall(r'<!-- wp:paragraph -->', html_for_count))
    bare_p = total_p_tags - total_wp_p
    if bare_p > 0:
        print(f"   ⚠️  {bare_p} sarmalanmamış <p> kaldı (toplam {total_p_tags} <p>, {total_wp_p} wrapper) — manuel kontrol önerilir")
    else:
        print("   ✅ Tüm paragraflar Gutenberg bloğu içinde")

    # Markdown bold kontrolü
    remaining_md = len(re.findall(r'\*\*', full_html))
    if remaining_md:
        print(f"   ⚠️  {remaining_md//2} çift ** işareti hâlâ mevcut — manuel kontrol")
    else:
        print("   ✅ Markdown bold temizlendi, tüm <strong> HTML")

    word_count = len(full_html.split())
    print(f"📝 Üretilen içerik: ~{word_count:,} kelime")

    # ── Agent döngüsü: validate → patch (gerekirse) → validate ──────────────
    from agent_loop import run_with_quality_gate, format_agent_report
    loop_result = run_with_quality_gate(
        html=full_html,
        mode='guide',
        city=city,
        max_retries=2,
        pass_threshold=70,
        verbose=True,
    )
    full_html = loop_result['html']
    print(format_agent_report(loop_result))

    return new_title, full_html
