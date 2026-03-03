"""
polish_engine.py v1.0 — AŞAMA 1+2 Polish Workflow

Mevcut modlara (guide, where, schema) DOKUNMAZ.
Yalnızca --mode polish argümanıyla çalışır.

Akış:
    WP post çek
    ↓
    segment_split() → Gutenberg blokları
    ↓
    AŞAMA 1: GPT structural edit (her blok)
      • Tekrar temizle
      • Güncel olmayan bilgileri işaretle
      • EEAT eksikliklerini ekle (kaynak/tarih/fiyat)
      • İç link fırsatları işaretle
      • Schema varsa: DOKUNMA
      • Voice/ton: DOKUNMA
    ↓
    AŞAMA 2: Claude narrative polish (seçili bloklar)
      • Giriş paragrafları
      • "Ben..." kişisel anlatı blokları
      • H2 açılış paragrafları
      • Eleştirel değerlendirmeler
      • Diğer bloklar: ATLA
    ↓
    %20 değişim kontrolü (difflib)
    ↓
    Blokları birleştir
    ↓
    WP'de MEVCUT postu draft olarak güncelle (yeni post açma)
    Başlık sonuna " OK!" ekle
"""

import re
import difflib
import html as _html
from typing import Optional
from multi_ai import ask_gpt, ask_gpt_mini, ask_claude


# ═══════════════════════════════════════════════════════════════════════════════
# SİSTEM PROMPTLARI
# ═══════════════════════════════════════════════════════════════════════════════

_GPT_STRUCTURAL_SYSTEM = """Sen Kemal Kaya'nın (yoldaolmak.com) editörüsün.
Görevin: Verilen Gutenberg HTML segmentini YAPI KORUYARAK yapısal olarak düzelt.

YAPACAKLARIN:
1. Gereksiz tekrarları kaldır (aynı bilgiyi iki kez söylüyorsa → bir tane bırak)
2. Güncel olmayan bilgileri işaretle: [?GÜNCELLENMELİ: orijinal metin]
3. Kapanmış yer/hizmet → [KAPALI] marker ekle
4. EEAT eksiklerini düzelt:
   - Fiyat varsa kaynak+tarih yoksa → "(kaynak: X, tarih)" ekle veya işaretle
   - Saat/program varsa → resmi site kontrolü notu
   - İddia varsa kanıt yok → [KAYNAK EKLENMELİ] marker
5. İç link fırsatları → paragraf sonuna <!-- İÇ LİNK: /önerilen-url --> yorum ekle
6. Duplike H2/H3 başlığı varsa → [DUPLIKE BAŞLIK] işaretle

YAPAMAYACAKLARIN:
- Cümleleri sıfırdan yazma
- Ton/ses/voice değiştirme
- "Ben" dilini kaldırma veya ekleme
- Gutenberg blok yapısını bozma
- Yasak kelime ekleme (muhteşem, harika, mükemmel, büyüleyici)
- Schema/FAQ bloğuna DOKUNMA (<!-- wp:html --> içini hiç değiştirme)
- %20'den fazla içerik değiştirme

Çıktı: Düzeltilmiş Gutenberg HTML segmenti. Başka metin yok."""

_CLAUDE_NARRATIVE_SYSTEM = """Sen Kemal Kaya'sın (yoldaolmak.com, 1971 doğumlu, 25+ yıl aktif gezgin).
Görevin: Verilen paragrafı CERAHİ POLISH yap — sıfırdan YAZMA.

SADECE ŞU ZAYIF NOKTALARI GÜÇLENDIR:
• Belirsiz sıfat → somut detay ("güzel" → "sarı-turuncu ahşap cepheler, 1850'ler")
• Kanıtsız iddia → kaynak ekle veya kişisel gözlem ile destekle
• Pasif fiil → aktif ("ziyaret edilebilir" → "ziyaret edebilirsiniz")
• 20+ kelime cümle → ikiye böl
• Broşür dili → gerçekçi gözlem
• Eksik beklenti ayarı → artı + eksi dengele

DOKUNMA:
• Yapıya, başlıklara, listelere
• Sayılara ve fiyatlara (uydurma YASAK)
• Çalışan, güçlü cümlelere
• "Ben..." kişisel anlatı okla akıyorsa

YASAK KELİMELER: muhteşem, harika, mükemmel, inanılmaz, nefes kesici, büyüleyici, masalsı

Çıktı: Revize edilmiş HTML paragraf(lar). Açıklama yok, sadece HTML."""


# ═══════════════════════════════════════════════════════════════════════════════
# SEGMENT SPLIT / MERGE
# ═══════════════════════════════════════════════════════════════════════════════

# Schema bloğunu hiç işleme — başından sonuna koru
_SCHEMA_PATTERN = re.compile(
    r'<!-- wp:html -->.*?<!-- /wp:html -->', re.DOTALL
)

def segment_split(html_content: str, max_chars: int = 1800) -> list:
    """
    HTML içeriği işlenebilir segmentlere böl.
    Gutenberg (<!-- wp:heading -->) VE raw HTML (<h2>) desteklenir.
    Schema blokları protected olarak işaretlenir.
    Büyük bölümler paragraf bazlı sub-split edilir.
    Orphan Gutenberg comment parçaları sonrakiyle birleştirilir.

    Döndürür: list[dict]
        {'html': str, 'protected': bool, 'idx': int}
    """
    # ── 1. Schema bloklarını ayır ─────────────────────────────────────────────
    parts = _SCHEMA_PATTERN.split(html_content)
    schema_blocks = _SCHEMA_PATTERN.findall(html_content)

    interleaved = []
    for i, part in enumerate(parts):
        interleaved.append(('content', part))
        if i < len(schema_blocks):
            interleaved.append(('schema', schema_blocks[i]))

    # ── 2. İçerik Gutenberg mı raw HTML mi? ──────────────────────────────────
    is_gutenberg = bool(re.search(r'<!-- wp:(paragraph|heading)', html_content, re.IGNORECASE))

    raw_segments = []  # (html, protected)

    for kind, block_text in interleaved:
        if kind == 'schema':
            raw_segments.append((block_text, True))
            continue
        if not block_text.strip():
            continue

        if is_gutenberg:
            # Gutenberg: tam blok sınırında kes
            # <!-- wp:heading ile başlayan tam blok: comment + içerik + /comment
            # Regex: tam blok = <!-- wp:heading ... --> /wp:heading --> arası
            # Strateji: tüm wp:heading bloklarını bul, aralarındaki içeriği para olarak böl

            # Gutenberg tam blok regex (heading bloğu comment'i dahil)
            block_pattern = re.compile(
                r'(<!-- wp:heading[^>]*-->.*?<!-- /wp:heading -->)',
                re.DOTALL | re.IGNORECASE
            )
            pieces = block_pattern.split(block_text)

            current = ''
            for piece in pieces:
                if not piece.strip():
                    continue
                # Heading bloğu mu?
                is_heading = bool(re.match(r'\s*<!-- wp:heading', piece, re.IGNORECASE))
                if is_heading:
                    # Önceki birikimleri kaydet
                    if current.strip():
                        raw_segments.append((current.strip(), False))
                        current = ''
                    # Heading bloğunu aç: heading + sonraki içerikle birlikte
                    raw_segments.append((piece.strip(), False))
                else:
                    # Paragraf grubu: büyükse sub-split et
                    if len(current) + len(piece) > max_chars and len(current) >= 400:
                        raw_segments.append((current.strip(), False))
                        current = piece
                    else:
                        current += ('\n' if current else '') + piece

            if current.strip():
                raw_segments.append((current.strip(), False))

        else:
            # Raw HTML: <h2> veya <h3> sınırlarında kes
            heading_re = re.compile(r'(?=<h[23][\s>])', re.IGNORECASE)
            sections = heading_re.split(block_text)
            for section in sections:
                if not section.strip():
                    continue
                if len(section) <= max_chars:
                    raw_segments.append((section.strip(), False))
                else:
                    # Büyük bölüm → <p> bazlı sub-split
                    para_re = re.compile(r'(?=<p[\s>])', re.IGNORECASE)
                    paras = [p for p in para_re.split(section) if p.strip()]
                    current = ''
                    for para in paras:
                        if len(current) + len(para) > max_chars and len(current) >= 400:
                            raw_segments.append((current.strip(), False))
                            current = para
                        else:
                            current += ('\n' if current else '') + para
                    if current.strip():
                        raw_segments.append((current.strip(), False))

    # ── 3. Paragraf-bazlı Gutenberg büyük segment sub-split ──────────────────
    final_raw = []
    for html, protected in raw_segments:
        if protected or len(html) <= max_chars:
            final_raw.append((html, protected))
            continue
        # Büyük segment → wp:paragraph bazlı böl
        para_re = re.compile(r'(?=<!-- wp:paragraph -->)', re.IGNORECASE)
        paras = [p for p in para_re.split(html) if p.strip()]
        current = ''
        for para in paras:
            if len(current) + len(para) > max_chars and len(current) >= 400:
                final_raw.append((current.strip(), False))
                current = para
            else:
                current += ('\n' if current else '') + para
        if current.strip():
            final_raw.append((current.strip(), False))

    # ── 4. idx ata ───────────────────────────────────────────────────────────
    segments = [
        {'html': h, 'protected': p, 'idx': i}
        for i, (h, p) in enumerate(final_raw)
        if h.strip()
    ]
    return segments


def merge_segments(segments: list) -> str:
    """Segmentleri sırasıyla birleştir."""
    return '\n\n'.join(s['html'] for s in sorted(segments, key=lambda x: x['idx']))


# ═══════════════════════════════════════════════════════════════════════════════
# DEĞİŞİM ORANI KONTROLÜ
# ═══════════════════════════════════════════════════════════════════════════════

def change_ratio(original: str, modified: str) -> float:
    """
    difflib.SequenceMatcher ile karakter bazlı benzerlik oranı.
    Döndürür: 0.0 (aynı) → 1.0 (tamamen farklı)
    """
    if not original and not modified:
        return 0.0
    if not original or not modified:
        return 1.0
    ratio = difflib.SequenceMatcher(None, original, modified).ratio()
    return round(1.0 - ratio, 4)


def _safe_edit(original_seg: dict, edited_html: str,
               max_ratio: float = 0.20, label: str = '') -> dict:
    """
    Değişim oranı max_ratio'dan büyükse orijinal segmenti döndür.
    Küçükse edited_html ile güncelle.
    """
    ratio = change_ratio(original_seg['html'], edited_html)
    if ratio > max_ratio:
        print(f"      ⚠️  Aşırı değişim ({ratio:.1%} > {max_ratio:.0%}) [{label}] — orijinal korundu")
        return original_seg.copy()
    seg = original_seg.copy()
    seg['html'] = edited_html
    seg['change_ratio'] = ratio
    return seg


# ═══════════════════════════════════════════════════════════════════════════════
# AŞAMA 1 — GPT STRUCTURAL EDIT
# ═══════════════════════════════════════════════════════════════════════════════

def gpt_structural_edit(segment: dict, city: str = '') -> dict:
    """
    Bir segmenti GPT-4o-mini ile yapısal olarak düzelt.
    Protected (schema) ve kısa (<= 150 char) segmentlere dokunma.
    """
    if segment.get('protected'):
        return segment

    original_html = segment['html']
    if len(original_html.strip()) <= 150:
        return segment  # heading-only veya çok kısa — API çağrısı yapma

    city_ctx = f"İçerik şehri: {city}. " if city else ""

    char_limit = len(original_html)
    prompt = f"""{city_ctx}Bu Gutenberg HTML segmentinde SADECE şunları yap (başka hiçbir şey):
1. Yasak kelime varsa (muhteşem/harika/eşsiz/büyüleyici) → daha somut ifadeyle değiştir
2. Fiyat varsa kaynak+tarih yoksa → [KAYNAK?] marker ekle
3. İç link fırsatı → paragraf sonuna <!-- İÇ LİNK: /url --> yorum ekle

KESİNLİKLE YAPMA:
- Cümle yeniden yazma
- Yapı değiştirme
- Yeni paragraf ekleme
- Bloğu küçültme (giriş={char_limit} karakter → çıkış da ~{char_limit} karakter olmalı)

SEGMENT:
{original_html}

Sadece minimal düzeltilmiş HTML döndür (boyut ±%10):"""

    # max_tokens: segment boyutuna orantılı, min 300 max 1500
    max_tok = max(300, min(1500, len(original_html) // 4))

    try:
        # Phase 1: GPT-4o-mini — structural edit için 4o şart değil
        edited = ask_gpt_mini(prompt, system=_GPT_STRUCTURAL_SYSTEM, max_tokens=max_tok)
        edited = re.sub(r'^```(?:html)?\s*', '', edited.strip())
        edited = re.sub(r'\s*```$', '', edited)
        return _safe_edit(segment, edited.strip(), max_ratio=0.35, label=f'mini seg#{segment["idx"]}')
    except Exception as e:
        print(f"      ❌ GPT-mini structural edit hatası (seg#{segment['idx']}): {e}")
        return segment


# ═══════════════════════════════════════════════════════════════════════════════
# AŞAMA 2 — CLAUDE NARRATIVE POLISH SEÇİMİ VE UYGULAMASI
# ═══════════════════════════════════════════════════════════════════════════════

# Kişisel anlatı kalıpları
_PERSONAL_PATTERNS = re.compile(
    r'\b(Ben |Benim |Ben\'|gittiğimde|gördüm|anladım|hissettim|fark ettim|'
    r'öneriyorum|düşünüyorum|bence|bana göre|ilk gittiğimde)',
    re.IGNORECASE
)

# Eleştirel/uyarı kalıpları
_CRITICAL_PATTERNS = re.compile(
    r'\b(dikkat|uyarı|not:|önemli|dezavantaj|sorun|pahalı|kalabalık|'
    r'avoid|skip|önermiyorum|tavsiye etmem)',
    re.IGNORECASE
)

def needs_narrative_polish(segment: dict, is_first_two: bool = False) -> bool:
    """
    Segmentin Claude narrative polish'e ihtiyacı var mı?
    Kriterler (herhangi biri yeterliyse True):
    1. İlk 2 wp:paragraph bloğu (giriş)
    2. "Ben..." kişisel anlatı içeriyor
    3. H2 başlığı var (H2 açılış paragrafı → ilk paragraf işlenecek)
    4. Eleştirel/uyarı dili içeriyor
    """
    if segment.get('protected'):
        return False
    html = segment['html']
    if len(html.strip()) < 50:
        return False
    if is_first_two:
        return True
    if _PERSONAL_PATTERNS.search(html):
        return True
    if _CRITICAL_PATTERNS.search(html):
        return True
    if re.search(r'<h2[^>]*>', html):
        return True
    return False


def claude_narrative_polish(segment: dict, city: str = '') -> dict:
    """
    Seçilmiş segmenti Claude Sonnet ile narrative polish yap.
    H2 içeriyorsa: başlığa dokunma, sadece ilk paragrafı polish et.
    """
    if segment.get('protected'):
        return segment

    original_html = segment['html']

    # H2 içeriyorsa başlık + ilk paragrafı ayır
    # Başlığa dokunma, sadece paragraf içini polish et
    h2_match = re.search(r'(<!-- wp:heading[^>]*-->.*?<!-- /wp:heading -->)', original_html, re.DOTALL)
    if h2_match:
        heading_block = h2_match.group(1)
        remainder = original_html[h2_match.end():].strip()
        # İlk paragrafı çıkar
        p_match = re.search(
            r'(<!-- wp:paragraph -->.*?<!-- /wp:paragraph -->)',
            remainder, re.DOTALL
        )
        if not p_match:
            return segment  # paragraf yok — atla
        first_para = p_match.group(1)
        rest_after_first = remainder[p_match.end():]
        target_for_polish = first_para
        prefix = heading_block + '\n'
        suffix = ('\n' + rest_after_first) if rest_after_first.strip() else ''
    else:
        # Başlık yok — tüm içeriği polish et
        target_for_polish = original_html
        prefix = ''
        suffix = ''

    city_ctx = f"Şehir: {city}. " if city else ""
    prompt = f"""{city_ctx}Aşağıdaki Gutenberg HTML paragrafını cerrahi polish yap.
Zayıf noktaları güçlendir ama sıfırdan yazma. %20'den fazla değiştirme.
Çıktı: Sadece revize edilmiş HTML paragraf.

PARAGRAF:
{target_for_polish}"""

    # max_tokens: segment boyunun yarısı, min 300 max 1200
    max_tok_c = max(300, min(1200, len(target_for_polish) // 3))

    try:
        polished = ask_claude(prompt, system=_CLAUDE_NARRATIVE_SYSTEM, max_tokens=max_tok_c)
        polished = re.sub(r'^```(?:html)?\s*', '', polished.strip())
        polished = re.sub(r'\s*```$', '', polished)
        polished_full = prefix + polished.strip() + suffix
        return _safe_edit(segment, polished_full, max_ratio=0.35, label=f'Claude seg#{segment["idx"]}')
    except Exception as e:
        print(f"      ❌ Claude narrative polish hatası (seg#{segment['idx']}): {e}")
        return segment


# ═══════════════════════════════════════════════════════════════════════════════
# BAŞLIK DURUM YÖNETİMİ
# ═══════════════════════════════════════════════════════════════════════════════

def update_title_status(title: str) -> str:
    """
    Başlık sonuna sırayla durum ekle:
    1. ilk polish  → "Başlık OK!"
    2. ikinci      → "Başlık OK! ✅"
    3. üçüncü      → "Başlık OK! ✔️"
    """
    title = title.strip()
    if title.endswith(' OK! ✔️'):
        return title   # üçüncü zaten — daha fazla ekleme
    elif title.endswith(' OK! ✅'):
        return title + ' ✔️'
    elif title.endswith(' OK!'):
        return title + ' ✅'
    else:
        return title + ' OK!'


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA KONTROL
# ═══════════════════════════════════════════════════════════════════════════════

def has_schema(html_content: str) -> bool:
    """İçerikte schema/FAQ bloğu var mı?"""
    return bool(_SCHEMA_PATTERN.search(html_content)) or 'FAQPage' in html_content


# ═══════════════════════════════════════════════════════════════════════════════
# ANA ORKESTRATÖR
# ═══════════════════════════════════════════════════════════════════════════════

def run_polish(post: dict, dry_run: bool = False) -> dict:
    """
    Polish workflow ana fonksiyonu.

    post    : WP API'den gelen post dict (id, title, content dahil)
    dry_run : True → WP'ye yazma, sadece diff raporu bas

    Döndürür:
        {
          'original_title'   : str,
          'new_title'        : str,
          'original_content' : str,
          'new_content'      : str,
          'total_change'     : float,   # 0.0-1.0
          'segments_total'   : int,
          'segments_edited'  : int,     # değişen segment sayısı
          'phase1_edits'     : int,
          'phase2_edits'     : int,
          'saved'            : bool,
          'post_id'          : int | None,
        }
    """
    # ── Başlangıç ─────────────────────────────────────────────────────────────
    raw_title     = post.get('title', {})
    original_title = (raw_title.get('rendered', '') if isinstance(raw_title, dict)
                      else str(raw_title)).strip()
    import html as _h
    import re as _re
    original_title = _h.unescape(_re.sub(r'<[^>]+>', '', original_title)).strip()

    raw_content    = post.get('content', {})
    if isinstance(raw_content, dict):
        # context=edit ile content.raw gelir (Gutenberg block comment dahil)
        # Yoksa content.rendered (block comment yok, sadece HTML)
        original_html = (raw_content.get('raw') or raw_content.get('rendered', '')).strip()
    else:
        original_html = str(raw_content).strip()
    post_id        = post.get('id')

    # Şehir tahmini başlıktan
    city = _re.split(r'\s+(?:Gezilecek|Nerede|Gezi|Rehberi|Hakkında)',
                     original_title)[0].strip()

    print(f"\n  Şehir/konu : {city}")
    print(f"  Başlık     : {original_title}")
    print(f"  İçerik     : {len(original_html):,} karakter")
    print(f"  Schema     : {'✅ Var' if has_schema(original_html) else '❌ Yok (polish eklemez)'}")

    # ── Segmentlere böl ───────────────────────────────────────────────────────
    segments = segment_split(original_html)
    print(f"\n  📦 {len(segments)} segment oluşturuldu")

    phase1_edits = 0
    phase2_edits = 0

    # ── AŞAMA 1: GPT Structural Edit ──────────────────────────────────────────
    print("\n  ── AŞAMA 1: GPT Structural Edit ──────────────────────")
    edited_segments = []
    for i, seg in enumerate(segments):
        if seg['protected']:
            print(f"    Seg #{seg['idx']:02d}: 🔒 Schema — atlandı")
            edited_segments.append(seg)
            continue

        print(f"    Seg #{seg['idx']:02d}: GPT ({len(seg['html'])} karakter)...", end=' ', flush=True)
        edited = gpt_structural_edit(seg, city=city)
        r = edited.get('change_ratio', 0.0)
        if r > 0.001:
            phase1_edits += 1
            print(f"✏️  {r:.1%} değişim")
        else:
            print("—")
        edited_segments.append(edited)

    # ── AŞAMA 2: Claude Narrative Polish (B+C: sadece giriş bölümü) ───────────
    print("\n  ── AŞAMA 2: Claude Narrative Polish (giriş) ──────────")

    # İlk H2 öncesindeki segmentleri bul → bunlar giriş bölümü
    intro_idx_limit = None
    for seg in edited_segments:
        if seg.get('protected'):
            continue
        if re.search(r'<h2[^>]*>', seg['html']):
            intro_idx_limit = seg['idx']
            break

    # intro_idx_limit yoksa (H2 hiç yok) → ilk 3 segment
    if intro_idx_limit is None:
        intro_idx_limit = min(3, len(edited_segments))

    para_count = 0
    final_segments = []
    for i, seg in enumerate(edited_segments):
        if seg.get('protected'):
            print(f"    Seg #{seg['idx']:02d}: 🔒 Schema — atlandı")
            final_segments.append(seg)
            continue

        # Giriş bölümü mü? (ilk H2'ye kadar, kısa segmentler hariç)
        is_intro = (seg['idx'] < intro_idx_limit and
                    len(seg['html'].strip()) > 150)

        if is_intro:
            print(f"    Seg #{seg['idx']:02d}: Claude ✍️  ({len(seg['html'])} karakter)...", end=' ', flush=True)
            polished = claude_narrative_polish(seg, city=city)
            r = polished.get('change_ratio', 0.0)
            if r > 0.001:
                phase2_edits += 1
                print(f"✅ {r:.1%} değişim")
            else:
                print("— (değişim yok)")
            final_segments.append(polished)
        else:
            print(f"    Seg #{seg['idx']:02d}: — atlandı")
            final_segments.append(seg)

    # ── Birleştir ve toplam değişimi hesapla ─────────────────────────────────
    new_html  = merge_segments(final_segments)
    total_chg = change_ratio(original_html, new_html)
    new_title = update_title_status(original_title)

    # phase1 + phase2 toplamı = gerçek değişen segment sayısı
    segments_edited = phase1_edits + phase2_edits

    # ── Rapor ─────────────────────────────────────────────────────────────────
    print(f"\n  ── POLISH RAPORU ─────────────────────────────────────")
    print(f"    Toplam segment : {len(final_segments)}")
    print(f"    Değişen segment: {segments_edited}")
    print(f"    Aşama 1 düzelt : {phase1_edits}")
    print(f"    Aşama 2 polish : {phase2_edits}")
    print(f"    Toplam değişim : {total_chg:.1%} (limit: 35%)")
    print(f"    Yeni başlık    : {new_title}")

    if total_chg > 0.35:
        print(f"    ⚠️  Toplam değişim %35 limitini aştı ({total_chg:.1%})")

    # ── WP'ye kaydet ──────────────────────────────────────────────────────────
    saved = False
    if not dry_run and post_id:
        from wp import update_post
        print(f"\n  💾 WP post #{post_id} güncelleniyor (draft)...")
        saved = update_post(
            post_id=post_id,
            title=new_title,
            content=new_html,
            status='draft',
        )
        if saved:
            import os
            wp_url = os.environ.get('WP_URL', 'https://yoldaolmak.com')
            print(f"  ✅ Kaydedildi: {wp_url}/wp-admin/post.php?post={post_id}&action=edit")
        else:
            print("  ❌ Kaydetme başarısız")
    elif dry_run:
        print("\n  ℹ️  DRY-RUN — WP'ye yazılmadı")

    return {
        'original_title'  : original_title,
        'new_title'       : new_title,
        'original_content': original_html,
        'new_content'     : new_html,
        'total_change'    : total_chg,
        'segments_total'  : len(final_segments),
        'segments_edited' : segments_edited,
        'phase1_edits'    : phase1_edits,
        'phase2_edits'    : phase2_edits,
        'saved'           : saved,
        'post_id'         : post_id,
    }
