#!/usr/bin/env python3
"""
Tekrar eden H2 bloklarını temizleyip postu tek temiz kapsamlı rehber yapısına indirir.
Pipeline bölümleri ezmek yerine append ettiği için biriken duplikatları siler.

Kullanım: python3 scripts/dedupe_post.py <POST_ID> --apply
(--apply yoksa sadece önizleme yapar, WP'ye yazmaz)
"""
import json, re, sys, os, base64, ssl
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def env(key):
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""

URL  = env("example_URL")
USER = env("WP_USER")
PW   = env("WP_APP_PASSWORD")
CTX  = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
AUTH = "Basic " + base64.b64encode(f"{USER}:{PW}".encode()).decode()

def wp_get(pid):
    req = urllib.request.Request(f"{URL}/wp-json/wp/v2/posts/{pid}?context=edit",
                                 headers={"Authorization": AUTH})
    return json.load(urllib.request.urlopen(req, context=CTX))

def wp_patch(pid, content):
    body = json.dumps({"content": content}).encode()
    req = urllib.request.Request(f"{URL}/wp-json/wp/v2/posts/{pid}", data=body, method="POST",
                                 headers={"Authorization": AUTH, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, context=CTX))

def clean(s): return re.sub("<[^>]+>", "", s).strip()

def segment(html):
    """H2 başlıklarına göre böl. [0]=intro, sonrası H2 blokları."""
    return re.split(r'(?=<!-- wp:heading -->\s*<h2)', html)

def h2_title(seg):
    m = re.search(r'<h2[^>]*>(.*?)</h2>', seg, re.S | re.I)
    return clean(m.group(1)) if m else None

def dedupe(html, keep_order):
    """keep_order: tutulacak H2 başlıkları (ilk görülen kopya tutulur).
    Başlıkta olmayan intro (seg 0) her zaman başa konur."""
    segs = segment(html)
    intro = segs[0] if segs and not h2_title(segs[0]) else ""
    # başlık -> ilk segment eşleşmesi (en zengini değil, ilk temiz olanı tut)
    by_title = {}
    for seg in segs:
        t = h2_title(seg)
        if t and t not in by_title:
            by_title[t] = seg
    # özel: SSS için en uzun (en zengin) kopyayı tut
    rich = {}
    for seg in segs:
        t = h2_title(seg)
        if not t: continue
        if t not in rich or len(seg) > len(rich[t]):
            rich[t] = seg
    out = [intro]
    for title in keep_order:
        src = rich if title in PREFER_RICH else by_title
        if title in src:
            out.append(src[title].rstrip() + "\n\n")
        else:
            print(f"   ⚠️  bulunamadı: {title}")
    return "".join(out).strip()

# SSS için en zengin kopya tutulsun
PREFER_RICH = {"Van Hakkında Sık Sorulan Sorular", "Sık Sorulan Sorular"}

# Van (265272) kapsamlı rehber bölüm sırası
VAN_ORDER = [
    "Nasıl gidilir, nerede kalınır",
    "Van Gölü kıyısı",
    "Akdamar Adası nasıl gidilir?",
    "Van Kalesi ve Urartu tarihi",
    "Muradiye Şelalesi ve çevre duraklar",
    "Van kahvaltısı: ne, nerede yenir",
    "Mevsim ve pratik bilgiler",
    "Van Hakkında Sık Sorulan Sorular",
]

# Hasankeyf (265274) kapsamlı rehber bölüm sırası
HASANKEYF_ORDER = [
    "Hasankeyf'e Nasıl Gidilir?",
    "Hasankeyf'in Bugünkü Yüzü Nasıl Anlaşılır?",
    "Yukarı Şehir ve Kaya Kalesi",
    "Arkeopark ve Taşınan Yapılar",
    "Eski Köprü Ayakları ve Kıyı Hattı",
    "Hasankeyf Müzesi",
    "Ne Zaman Gidilir?",
    "Nerede Kalınır, Ne Yenir?",
    "GAP Rotasına Nasıl Eklenir?",
    "Sık Sorulan Sorular",
]

ORDERS = {265272: VAN_ORDER, 265274: HASANKEYF_ORDER}

def main():
    pid = int(sys.argv[1])
    apply = "--apply" in sys.argv
    post = wp_get(pid)
    html = post["content"]["raw"]
    before_segs = segment(html)
    print(f"ÖNCE: {len(clean(html).split())} kelime, {len(before_segs)} segment")
    new_html = dedupe(html, ORDERS[pid])
    after_segs = segment(new_html)
    print(f"SONRA: {len(clean(new_html).split())} kelime, {len(after_segs)} segment")
    print("--- YENİ H2 SIRASI ---")
    for seg in after_segs:
        t = h2_title(seg)
        print("  •", t if t else "(giriş)")
    if "--save" in sys.argv:
        outp = os.path.join(ROOT, f"backups/post-snapshots/{pid}_deduped.html")
        open(outp, "w", encoding="utf-8").write(new_html)
        print("💾 HTML kaydedildi:", outp)
    if apply:
        wp_patch(pid, new_html)
        print("✅ WP'ye yazıldı (draft).")
    elif "--save" not in sys.argv:
        print("ℹ️  Önizleme — yazmak için --apply ekle.")

if __name__ == "__main__":
    main()
