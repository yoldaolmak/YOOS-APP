#!/usr/bin/env python3
"""
Van (265272) yapısal onarım — hiçbir özgün cümle atılmadan.
Kaynak: mangle olmuş orijinal yedek. Çıktı: temiz, geçerli Gutenberg,
doğru sıra (H1+giriş önce → bölümler → SSS), tekrarsız.
Metni çeker, TEMİZ Gutenberg bloklarına yeniden sarar (bozuk yorumları atar).
"""
import json, re, sys, os, html as H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "backups/post-snapshots/265272_van_20260602_111133.json")

raw = json.load(open(SRC))["content"]["raw"]

def texts_of(segment):
    """Bir segmentteki <p> metinlerini (Alex notu hariç) sırayla, tekrarsız döndür."""
    out, seen = [], set()
    for p in re.findall(r"<p[^>]*>(.*?)</p>", segment, flags=re.S):
        t = H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        if not t or "Author's Note" in t:
            continue
        if t not in seen:
            seen.add(t); out.append(t)
    return out

def note_of(segment):
    """Segmentteki ilk Alex notu metnini döndür (📌 prefix korunur)."""
    for p in re.findall(r"<p[^>]*>(.*?)</p>", segment, flags=re.S):
        t = H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        if "Author's Note" in t:
            return t
    return None

# H2 segmentlerine böl, her başlık için en zengin (en uzun) kopyayı al
segs = re.split(r"(?=<!-- wp:heading -->\s*<h2)", raw)
def title_of(s):
    m = re.search(r"<h2[^>]*>(.*?)</h2>", s, flags=re.I | re.S)
    return H.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None

rich = {}
for s in segs:
    t = title_of(s)
    if t and (t not in rich or len(s) > len(rich[t])):
        rich[t] = s

# ── Giriş paragraflarını bul (H1 çevresindeki, bölüm dışı) ──
intro_paras = [
    p for p in texts_of(raw)
    if p.startswith("Van, ilk bakışta")
    or p.startswith("İzmir'den Van'a")
    or p.startswith("Bu rehberde Van Kalesi")
]

# ── Temiz Gutenberg blok üreticileri ──
def b_h1(t):  return f'<!-- wp:heading {{"level":1}} -->\n<h1 class="wp-block-heading">{t}</h1>\n<!-- /wp:heading -->'
def b_h2(t):  return f'<!-- wp:heading -->\n<h2 class="wp-block-heading">{t}</h2>\n<!-- /wp:heading -->'
def b_h3(t):  return f'<!-- wp:heading {{"level":3}} -->\n<h3 class="wp-block-heading">{t}</h3>\n<!-- /wp:heading -->'
def b_p(t):   return f'<!-- wp:paragraph -->\n<p>{t}</p>\n<!-- /wp:paragraph -->'
def b_note(t):
    body = t.replace("📌 Author's Note:", "<strong>📌 Author's Note:</strong>", 1)
    return (f'<!-- wp:quote -->\n<blockquote class="wp-block-quote">'
            f'<!-- wp:paragraph -->\n<p>{body}</p>\n<!-- /wp:paragraph --></blockquote>\n<!-- /wp:quote -->')

# ── Bölüm sırası: (kaynak başlık, çıktı başlık) ──
SECTION_ORDER = [
    ("Nasıl gidilir, nerede kalınır",        "Nasıl gidilir, nerede kalınır"),
    ("Van Gölü kıyısı",                      "Van Gölü kıyısı"),
    ("Akdamar Adası nasıl gidilir?",         "Akdamar Adası nasıl gidilir?"),
    ("Van Kalesi ve Urartu tarihi",          "Van Kalesi ve Urartu tarihi"),
    ("Muradiye Şelalesi ve çevre duraklar",  "Muradiye Şelalesi ve çevre duraklar"),
    ("Van kahvaltısı: ne, nerede yenir",     "Van kahvaltısı: ne, nerede yenir"),
    ("Mevsim ve pratik bilgiler",            "Mevsim ve pratik bilgiler"),
]

def b_list(title, items):
    lis = "".join(f"<li>{i}</li>" for i in items)
    return (f'<!-- wp:heading {{"level":3}} -->\n<h3 class="wp-block-heading">{title}</h3>\n'
            f'<!-- /wp:heading -->\n\n<!-- wp:list -->\n<ul>{lis}</ul>\n<!-- /wp:list -->')

blocks = []
# 1) Giriş: H1 + giriş paragrafları + kısa rota notu kartı
blocks.append(b_h1("Van Gezi Rehberi: Göl Kıyısı, Kale ve Kahvaltı"))
for p in intro_paras:
    blocks.append(b_p(p))
blocks.append(b_list("Van için kısa rota notu", [
    "İlk gün: kahvaltı, kale ve merkez yürüyüşü.",
    "İkinci gün: Akdamar Adası ya da Muradiye yönü.",
    "Yanınıza alın: rüzgara uygun bir üst katman ve rahat ayakkabı.",
]))

# 2) Bölümler: başlık + gövde paragrafları + Alex notu
for src_title, out_title in SECTION_ORDER:
    seg = rich.get(src_title)
    if not seg:
        print(f"  ⚠️ kaynak bölüm yok: {src_title}", file=sys.stderr)
        continue
    blocks.append(b_h2(out_title))
    for p in texts_of(seg):
        blocks.append(b_p(p))
    note = note_of(seg)
    if note:
        blocks.append(b_note(note))

# 3) SSS: HER İKİ kaynaktan tüm soru-cevapları birleştir (tekrarsız) → H3+paragraf
def norm_q(q):
    return re.sub(r"[^\wçğıöşü]", "", q.lower())

faq = []          # (soru, [cevap paragrafları])
seen_q = set()

_CARD_TITLES = ("rota notu", "yararlı", "küçük notlar", "kısa rota")
def add_faq(q, answers):
    k = norm_q(q)
    if any(c in q.lower() for c in _CARD_TITLES):   # kart başlığı, soru değil
        return
    if q and answers and k not in seen_q:
        seen_q.add(k); faq.append((q.rstrip("?").strip() + "?", answers))

# Kaynak A: H3'lü SSS segmenti
for src in ("Van Hakkında Sık Sorulan Sorular",):
    seg = rich.get(src)
    if not seg:
        continue
    for q, ans in re.findall(r"<h3[^>]*>(.*?)</h3>(.*?)(?=<h3|<!-- wp:heading|<!-- /wp:quote|$)",
                             seg, flags=re.S | re.I):
        q = H.unescape(re.sub(r"<[^>]+>", "", q)).strip()
        add_faq(q, texts_of(ans))

# Kaynak B: <strong>Soru?</strong> Cevap formatlı segment(ler)
for src in ("Sıkça Sorulan Sorular",):
    seg = rich.get(src)
    if not seg:
        continue
    for p in re.findall(r"<p[^>]*>(.*?)</p>", seg, flags=re.S):
        raw_p = H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        m = re.match(r"^(.*?\?)\s+(.+)$", raw_p, flags=re.S)
        if m and "Author's Note" not in raw_p:
            add_faq(m.group(1).strip(), [m.group(2).strip()])

blocks.append(b_h2("Van Hakkında Sık Sorulan Sorular"))
for q, answers in faq:
    blocks.append(b_h3(q))
    for a in answers:
        blocks.append(b_p(a))

# kapanış Alex notu
faq_seg = rich.get("Van Hakkında Sık Sorulan Sorular") or rich.get("Sıkça Sorulan Sorular")
note = note_of(faq_seg) if faq_seg else None
if note:
    blocks.append(b_note(note))
print(f"SSS: {len(faq)} özgün soru-cevap korundu")

out_html = "\n\n".join(blocks)

# ── Doğrulama ──
assert out_html.count("<!-- wp:") == out_html.count("<!-- /wp:"), "blok dengesi bozuk!"
# gerçek malformed: kapanış yorumu --> ile bitmiyor (örn. <!-- /wp:paragraph></blockquote>)
assert not re.search(r"/wp:\w+>", out_html), "malformed yorum var (--> eksik)!"
wc = len(re.sub(r"<[^>]+>", " ", out_html).split())
h2n = out_html.count("<h2")
print(f"ÇIKTI: {wc} kelime, {h2n} H2, bloklar dengeli ✓")

outp = os.path.join(ROOT, "backups/post-snapshots/265272_rebuilt.html")
open(outp, "w", encoding="utf-8").write(out_html)
print("💾", outp)
