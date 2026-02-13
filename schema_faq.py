#!/usr/bin/env python3
# =============================================================================
# schema_faq.py  —  Clawdbot Schema + FAQ Üretici
# Kaynak: faq-schema-prompt.txt
# Kullanım:
#   python3 schema_faq.py --dest Bratislava --mode where
#   python3 schema_faq.py --dest Paris --mode polish --headline "Paris Nasıl Bir Yer?" --meta "Paris rehberi."
#   python3 schema_faq.py --dest Tokyo --mode draft --out faq_tokyo.html
# =============================================================================

import re
import json
import argparse
import sys
import os
from datetime import date

# ─── CLAUDE API ──────────────────────────────────────────────────────────────
def ask_claude(prompt: str, max_tokens: int = 2000) -> str:
    """claude.py modülü varsa kullan, yoksa doğrudan anthropic SDK."""
    try:
        from claude import ask_claude as _ac
        return _ac(prompt, max_tokens=max_tokens, model="claude-sonnet-4-20250514")
    except ImportError:
        pass
    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        print(f"⚠️  Claude API erişilemiyor: {e}")
        return ""


# =============================================================================
# SORU SETLERİ (mod bazlı)
# =============================================================================
FAQ_QUESTIONS = {

    # ── DRAFT MOD (5 soru) ───────────────────────────────────────────────────
    'draft': [
        "{dest} nerede?",
        "{dest}'a nasıl gidilir?",
        "{dest} gezisi için kaç gün yeter?",
        "{dest}'e ne zaman gidilir?",
        "{dest} pahalı mı?",
    ],

    # ── WHERE MOD (7 soru) — "gezilecek yerler" YASAK ────────────────────────
    'where': [
        "{dest} nerede, hangi bölgede?",
        "{dest}'a hangi havayolları uçuyor?",
        "{dest} havalimanından şehir merkezine nasıl gidilir?",
        "{dest} vize istiyor mu?",
        "{dest} için kaç gün yeterli?",
        "{dest}'a ne zaman gidilmeli?",
        "{dest} Türkiye saat farkı nedir?",
    ],

    # ── POLISH MOD (8 soru) ──────────────────────────────────────────────────
    'polish': [
        "{dest} nerede, nasıl bir yer?",
        "{dest}'a nasıl gidilir, en ucuz uçak bileti nasıl bulunur?",
        "{dest} gezilecek yerler nereleri?",
        "{dest} kaç günde gezilir, rota önerisi nedir?",
        "{dest}'e ne zaman gidilir, iklim nasıl?",
        "{dest} yemek kültürü nasıl, ne yenir?",
        "{dest} konaklama önerileri, hangi bölgede kalınır?",
        "{dest} bütçe: pahalı mı, günlük harcama ne kadar?",
    ],
}

# Cevap yazım kuralları (prompt'a eklenir)
_ANSWER_RULES = """\
FAQ CEVAP YAZIM KURALLARI:
- Uzunluk: 1-2 cümle, maksimum 250 karakter
- Dil: bilgilendirici, samimi, net
- BOLD kullan (<strong>): rakamlar, gün sayısı, fiyat, mevsim, süre
- YASAK kelimeler: muhteşem, harika, eşsiz, inanılmaz, nefes kesici
- YASAK işaret: "—" (tire)
- Şiirsel anlatım yasak — sadece bilgi

CEVAP ŞABLONLARI:
"NEREDE"    : "{dest}, {ülke}'nin {bölge} bölgesinde, {coğrafya} kıyısında yer alır."
"UÇUŞLAR"  : "Türkiye'den {havayolu} ile {direkt/aktarmalı} uçuşlar var. Uçuş süresi yaklaşık <strong>X saat</strong>."
"HAVALİMANI": "<strong>N dakika</strong>da {ulaşım yöntemi} ile şehir merkezine ulaşılır."
"VİZE"      : "Evet/Hayır, {vize durumu}. {süreç/ek bilgi}"
"KAÇ GÜN"  : "Ana noktalar için <strong>X-Y gün</strong> yeterli. Çevre için <strong>Z gün</strong> ayırmalısınız."
"NE ZAMAN" : "En ideal dönem <strong>Ay-Ay</strong> arası. Kış/yaz aylarında {hava durumu} yaşanabilir."
"SAAT FARKI": "Türkiye ile arasında <strong>N saat</strong> fark var / fark yoktur. {UTC zaman dilimi}"
"""


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def strip_html(text: str) -> str:
    """HTML etiketlerini temizle — schema cevapları için."""
    return re.sub(r'<[^>]+>', '', text).strip()


def clean_ai_output(text: str) -> str:
    """```html veya ``` kod bloklarını çıkar."""
    text = re.sub(r'^```[a-z]*\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$',       '', text, flags=re.MULTILINE)
    return text.strip()


def get_questions(dest: str, mode: str) -> list[str]:
    """Moda göre soru listesi döndür — {dest} yerine geçirilmiş."""
    raw = FAQ_QUESTIONS.get(mode)
    if raw is None:
        print(f"⚠️  Bilinmeyen mod '{mode}', 'where' kullanılıyor.")
        raw = FAQ_QUESTIONS['where']
    return [q.replace('{dest}', dest) for q in raw]


# =============================================================================
# CEVAP ÜRETİCİ (Claude)
# =============================================================================

def generate_answers(dest: str, mode: str) -> list[tuple[str, str]]:
    """
    Claude'dan SORU_N / CEVAP_N formatında cevap al, parse et.
    Returns: [(soru_str, cevap_html_str), ...]
    """
    questions = get_questions(dest, mode)
    n = len(questions)

    # Örnek çıktı formatını dinamik oluştur
    format_example = "\n".join(
        f"SORU_{i}: {q}\nCEVAP_{i}: [cevap]"
        for i, q in enumerate(questions, 1)
    )

    prompt = f"""\
SEN: example.com seyahat blog yazarısın.
GÖREV: {dest} için aşağıdaki {n} soruya KISA, BİLGİLENDİRİCİ cevaplar yaz.

{_ANSWER_RULES}

SORULAR:
{chr(10).join(f"{i}. {q}" for i, q in enumerate(questions, 1))}

ÇIKTI — tam olarak aşağıdaki formatta, başka hiçbir şey ekleme:
{format_example}

JSON veya kod bloğu kullanma. Sadece SORU_N: / CEVAP_N: formatı."""

    raw = ask_claude(prompt, max_tokens=2500)
    raw = clean_ai_output(raw)

    pairs: list[tuple[str, str]] = []
    for i, q in enumerate(questions, 1):
        # CEVAP_i: ... → SORU_{i+1}: (veya satır sonu)
        pattern = rf'CEVAP_{i}:\s*(.*?)(?=\nSORU_{i+1}:|\Z)'
        m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        if m:
            ans = m.group(1).strip()
            # 250 karakter üstü: kes (HTML temizlenmiş karakter sayısı)
            if len(strip_html(ans)) > 250:
                # HTML bold'lar korunarak kes
                ans = ans[:260].rsplit(' ', 1)[0] + '...'
            pairs.append((q, ans))
        else:
            # Fallback — Claude parse edilemedi
            print(f"  ⚠️  CEVAP_{i} parse edilemedi, fallback kullanılıyor.")
            pairs.append((q,
                f"{dest} hakkında güncel bilgi için resmi kaynakları kontrol edin."))

    return pairs


# =============================================================================
# HTML FAQ ITEM'LARI
# =============================================================================

def build_faq_items_html(pairs: list[tuple[str, str]]) -> str:
    """
    Her soru-cevap için HTML div.
    Son item'da border-bottom OLMAZ.
    """
    parts = []
    last_idx = len(pairs) - 1

    for idx, (q, a) in enumerate(pairs):
        is_last = (idx == last_idx)

        if is_last:
            # Son item: sadece padding, border-bottom YOK
            div_style = 'padding:14px 0;'
        else:
            div_style = 'border-bottom:1px solid #d1e3f0;padding:14px 0;'

        parts.append(
            f'  <div style="{div_style}">\n'
            f'    <p style="font-weight:700;margin:0 0 6px;color:#0f3460;">❓ {q}</p>\n'
            f'    <p style="margin:0;color:#374151;line-height:1.6;">{a}</p>\n'
            f'  </div>'
        )

    return '\n'.join(parts)


# =============================================================================
# SCHEMA JSON-LD BLOKLARI
# =============================================================================

def build_article_schema(headline: str, meta_desc: str, today: str) -> str:
    """Article schema JSON-LD (girintili, eksiksiz)."""
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": meta_desc,
        "datePublished": today,
        "author": {
            "@type": "Person",
            "name": "Alex Rivera"
        },
        "publisher": {
            "@type": "Organization",
            "name": "example.com",
            "logo": {
                "@type": "ImageObject",
                "url": "https://example.com/logo.png"
            }
        }
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_faqpage_schema(pairs: list[tuple[str, str]]) -> str:
    """
    FAQPage schema JSON-LD.
    Cevaplarda HTML etiketleri TEMİZLENİR.
    """
    entities = [
        {
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": strip_html(a)   # HTML etiketi temizle
            }
        }
        for q, a in pairs
    ]
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# =============================================================================
# ANA FONKSİYON — Tam bloğu üret
# =============================================================================

def build_schema_faq(
    dest:      str,
    mode:      str,
    headline:  str = "",
    meta_desc: str = "",
    today:     str = "",
) -> str:
    """
    Tek <!-- wp:html --> bloğu içinde:
      - Mavi tema div (#0073aa, #f0f7ff, #0f3460)
      - H3 başlık
      - FAQ item'ları (son item border-bottom'suz)
      - Article JSON-LD
      - FAQPage JSON-LD

    Returns: Gutenberg wp:html bloğu (string)
    """
    # Varsayılanlar
    if not headline:
        headline = f"{dest} Nasıl Bir Yer? Nerede, Nasıl Gidilir, Gezi Planı"
    if not meta_desc:
        meta_desc = (
            f"{dest} nerede, nasıl gidilir? "
            f"{dest} nasıl bir yer, gezilecek yerler, "
            f"gezi planı ve ulaşım rehberi."
        )
    if not today:
        today = date.today().strftime("%Y-%m-%d")

    print(f"  🤖 Claude'dan {len(get_questions(dest, mode))} FAQ cevabı alınıyor ({mode} mod)...")
    pairs = generate_answers(dest, mode)

    faq_items_html  = build_faq_items_html(pairs)
    article_json    = build_article_schema(headline, meta_desc, today)
    faqpage_json    = build_faqpage_schema(pairs)

    block = (
        '<!-- wp:html -->\n'
        '<div class="yoa-faq-schema" style="'
        'border:2px solid #0073aa;'
        'border-radius:10px;'
        'padding:24px 28px;'
        'margin:2.5em 0;'
        'background:#f0f7ff;">\n\n'

        f'  <h3 style="margin:0 0 18px;color:#0073aa;font-size:1.15em;font-weight:700;">'
        f'📋 {dest} Hakkında Sık Sorulan Sorular</h3>\n\n'

        f'{faq_items_html}\n\n'

        '  <script type="application/ld+json">\n'
        f'{article_json}\n'
        '  </script>\n\n'

        '  <script type="application/ld+json">\n'
        f'{faqpage_json}\n'
        '  </script>\n\n'

        '</div>\n'
        '<!-- /wp:html -->'
    )

    return block


# =============================================================================
# TEST FONKSİYONU
# =============================================================================

def run_tests(dest: str, block: str, mode: str, pairs: list) -> bool:
    """Kontrol listesini çalıştır, True/False döndür."""
    print("\n  📋 TEST KRİTERLERİ:")
    results = []

    def chk(label: str, ok: bool):
        results.append(ok)
        print(f"    {'✅' if ok else '❌'} {label}")

    # Yapısal
    chk("Tek <!-- wp:html --> bloğu",         block.count('<!-- wp:html -->') == 1)
    chk("<!-- /wp:html --> kapanıyor",         block.count('<!-- /wp:html -->') == 1)
    chk("Mavi tema border #0073aa",            '#0073aa' in block)
    chk("Mavi tema background #f0f7ff",        '#f0f7ff' in block)
    chk("Soru rengi #0f3460",                  '#0f3460' in block)

    # FAQ HTML
    n_q = len(FAQ_QUESTIONS.get(mode, FAQ_QUESTIONS['where']))
    chk(f"❓ emoji sayısı = {n_q}",            block.count('❓') == n_q)

    # Son item border-bottom YOK
    divs = re.findall(r'<div style="([^"]*)">\s*<p style="font-weight:700', block)
    last_ok = bool(divs) and 'border-bottom' not in divs[-1]
    chk("Son FAQ item border-bottom YOK",      last_ok)
    others_ok = all('border-bottom' in s for s in divs[:-1]) if len(divs) > 1 else True
    chk(f"Diğer {len(divs)-1} item border-bottom VAR", others_ok)

    # Schema Article
    chk('Article schema "@type"',             '"@type": "Article"' in block)
    chk('Article headline doğru',             dest in block and 'Article' in block)
    chk('Tarih formatı YYYY-MM-DD',           bool(re.search(r'"datePublished": "\d{4}-\d{2}-\d{2}"', block)))
    chk('Yazar: Alex Rivera',                  '"name": "Alex Rivera"' in block)
    chk('Yayıncı: example.com',           '"name": "example.com"' in block)
    chk('Logo URL var',                       'example.com/logo.png' in block)

    # Schema FAQPage
    chk('FAQPage schema "@type"',             '"@type": "FAQPage"' in block)
    chk(f'mainEntity {n_q} soru',            block.count('"@type": "Question"') == n_q)

    # Schema cevapları HTML temiz
    try:
        faq_m = re.search(r'"mainEntity":\s*(\[.*?\])\s*\}', block, re.DOTALL)
        if faq_m:
            entities = json.loads(faq_m.group(1))
            html_in_ans = [e for e in entities if '<' in e['acceptedAnswer']['text']]
            chk(f'Schema cevapları HTML temiz ({len(entities)} soru)',
                len(html_in_ans) == 0)
    except (json.JSONDecodeError, AttributeError):
        chk('Schema JSON parse edildi', False)

    # WHERE moduna özgü
    if mode == 'where':
        qs_lower = ' '.join(FAQ_QUESTIONS['where']).lower()
        chk("WHERE: 'gezilecek' sorusu YOK", 'gezilecek' not in qs_lower)

    # Yasak kelimeler
    banned = ['muhteşem', 'harika', 'eşsiz', 'inanılmaz', 'nefes kesici']
    found  = [w for w in banned if w in block.lower()]
    chk(f"Yasak kelime yok ({', '.join(found) if found else 'temiz'})",
        len(found) == 0)

    # Tire kontrolü
    chk("'—' tire işareti yok", '—' not in block)

    total  = len(results)
    passed = sum(results)
    print(f"\n  {'✅' if passed == total else '⚠️'} {passed}/{total} test geçti")
    return passed == total


# =============================================================================
# MAIN — Komut satırı arayüzü
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Clawdbot Schema + FAQ Üretici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Örnekler:
  python3 schema_faq.py --dest Bratislava --mode where
  python3 schema_faq.py --dest Paris --mode polish --out faq_paris.html
  python3 schema_faq.py --dest Tokyo --mode draft \\
      --headline "Tokyo Nasıl Bir Yer?" \\
      --meta "Tokyo rehberi ve gezi planı."
  python3 schema_faq.py --dest Moskova --mode where --test
        """
    )

    parser.add_argument(
        '--dest', required=True,
        help='Destinasyon adı (örn: Bratislava, Paris, Tokyo)'
    )
    parser.add_argument(
        '--mode', required=True, choices=['draft', 'where', 'polish'],
        help='Mod: draft (5 soru) | where (7 soru) | polish (8 soru)'
    )
    parser.add_argument(
        '--headline', default='',
        help='H1 başlık (boş bırakılırsa otomatik üretilir)'
    )
    parser.add_argument(
        '--meta', default='',
        help='Yoast meta açıklama (boş bırakılırsa otomatik üretilir)'
    )
    parser.add_argument(
        '--today', default=date.today().strftime("%Y-%m-%d"),
        help='Tarih (varsayılan: bugün, format: YYYY-MM-DD)'
    )
    parser.add_argument(
        '--out', default='',
        help='Çıktı dosyası (boş = stdout)'
    )
    parser.add_argument(
        '--test', action='store_true',
        help='Test kriterlerini çalıştır'
    )
    parser.add_argument(
        '--list-questions', action='store_true',
        help='Seçilen modun soru listesini göster ve çık'
    )

    args = parser.parse_args()

    # Soru listesi göster
    if args.list_questions:
        print(f"\n📋 {args.mode.upper()} mod soru seti ({args.dest}):\n")
        for i, q in enumerate(get_questions(args.dest, args.mode), 1):
            print(f"  {i}. {q}")
        sys.exit(0)

    print(f"\n🚀 Schema + FAQ Üretici")
    print(f"   Destinasyon : {args.dest}")
    print(f"   Mod         : {args.mode} ({len(FAQ_QUESTIONS.get(args.mode, []))} soru)")
    print(f"   Tarih       : {args.today}")
    if args.out:
        print(f"   Çıktı       : {args.out}")
    print()

    # Üret
    block = build_schema_faq(
        dest      = args.dest,
        mode      = args.mode,
        headline  = args.headline,
        meta_desc = args.meta,
        today     = args.today,
    )

    # Test
    if args.test:
        pairs = generate_answers.__wrapped__(args.dest, args.mode) \
            if hasattr(generate_answers, '__wrapped__') else []
        # Re-parse pairs from block for testing
        divs = re.findall(r'❓ ([^<]+)</p>', block)
        ans_raw = re.findall(r'line-height:1\.6;">([^<]*(?:<strong>[^<]*</strong>[^<]*)*)</p>', block)
        pairs_for_test = list(zip(divs, ans_raw))
        run_tests(args.dest, block, args.mode, pairs_for_test)

    # Çıktı
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(block)
        print(f"\n  💾 Kaydedildi: {args.out}  ({len(block):,} karakter)")
    else:
        print("\n" + "=" * 70)
        print(block)
        print("=" * 70)
        print(f"\n  📏 {len(block):,} karakter  |  {block.count('❓')} FAQ soru")

    return block


if __name__ == '__main__':
    main()
