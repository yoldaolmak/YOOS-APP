#!/usr/bin/env python3
"""
test_optimizasyon.py
Token optimizasyonu ve GPT eğitim talimatları için testler.
"""
import sys
import re

PASS = FAIL = 0
def ok(msg):
    global PASS; PASS += 1; print(f"   ✅ {msg}")
def fail(msg, detail=""):
    global FAIL; FAIL += 1; print(f"   ❌ {msg} {detail}")

with open("/home/claude/editor.py") as f:
    ed = f.read()

print("\n── 1. TOKEN LİMİTLERİ ──────────────────────────────────────")
# Token limit güncellemeleri kontrol

token_checks = [
    ("Giriş (WHERE)", "max_tokens=1500", "giris_raw = ask_claude_only(giris_prompt, max_tokens=1500)"),
    ("Giriş (TRAVEL)", "max_tokens=1500", "giris_raw = ask_claude_only(giris_prompt, max_tokens=1500)"),
    ("Kişisel Bakış (WHERE)", "max_tokens=800", "kisisel_raw = ask_claude_only(kisisel_prompt, max_tokens=800)"),
    ("Kişisel Bakış (TRAVEL)", "max_tokens=800", "kisisel_out_raw = ask_claude_only(kisisel_prompt, max_tokens=800)"),
    ("Nasıl Bir Yer", "max_tokens=2000", "max_tokens=2000, min_chars=500"),
    ("Nerede", "max_tokens=1200", "nerede_raw = safe_gpt(nerede_prompt, \"\", max_tokens=1200"),
    ("Nasıl Gidilir", "max_tokens=1500", "_nasil_raw = safe_gpt(nasil_gidilir_prompt, \"\", max_tokens=1500"),
    ("Gezi Planı", "max_tokens=1200", "gezi_raw = ask_gpt_only(gezi_prompt, max_tokens=1200)"),
    ("Kapanış", "max_tokens=800", "kapanis_raw = ask_gpt_only(kapanis_prompt, max_tokens=800)"),
    ("FAQ", "max_tokens=1200", "raw = ask_gpt_only(prompt, max_tokens=1200)"),
]

for name, expected, pattern in token_checks:
    if pattern in ed:
        ok(f"{name}: {expected}")
    else:
        fail(f"{name}: {expected} eksik")

print("\n── 2. BOLD DESTİNASYON ADI KURALI ─────────────────────────")
# Giriş paragrafı bold destinasyon adı direktifi

if "İLK KURAL: İlk cümle destinasyon adıyla başlar ve **bold** yapılır" in ed:
    ok("Bold destinasyon kuralı var")
else:
    fail("Bold destinasyon kuralı eksik")

if "**[Destinasyon].** [Gerçekçi gözlem" in ed:
    ok("Bold format örneği var")
else:
    fail("Bold format örneği eksik")

if "**Prag.**" in ed or "**Belem.**" in ed:
    ok("Somut bold örnekleri var")
else:
    fail("Somut bold örnekleri eksik")

print("\n── 3. BOLD KULLANIM KURALLARI ─────────────────────────────")
# Bold kullanım kuralları detaylı

bold_rules = [
    "**Destinasyon adı** (ilk geçtiği yerde ZORUNLU)",
    "**Önemli semt/mahalle adları**",
    "**Tarihi yapı, müze, meydan adları**",
    "**Sayılar, mesafeler, fiyatlar, süreler**",
]

for rule in bold_rules:
    if rule in ed:
        ok(f"Bold kural: {rule[:40]}...")
    else:
        fail(f"Bold kural eksik: {rule[:40]}...")

print("\n── 4. DRAMATİK ANLATIMDAN KAÇINMA ─────────────────────────")
# Dramatik anlatım örnekleri

dramatic_examples = [
    "Büyüleyici bir manzaraydı, nefesimi kesti.",
    "Zamanın durduğu masalsı bir yer.",
    "Cennetten bir köşe.",
]

doğru_examples = [
    "Tepeden bakınca şehrin tamamını görebiliyorsunuz.",
    "Sokakları taş döşeli, evler eski ama bakımlı.",
    "Deniz o kadar temizdi ki dibi görünüyordu.",
]

for example in dramatic_examples:
    if example in ed:
        ok(f"Dramatik örnek (YANLIŞ): {example[:30]}...")
    else:
        fail(f"Dramatik örnek eksik: {example[:30]}...")

for example in doğru_examples:
    if example in ed:
        ok(f"Gerçekçi örnek (DOĞRU): {example[:30]}...")
    else:
        fail(f"Gerçekçi örnek eksik: {example[:30]}...")

print("\n── 5. KİŞİSEL BAKIŞ FORMATI ───────────────────────────────")
# Olumlu+olumsuz+özet formatı

if "FORMAT: Olumlu gözlem + Olumsuz gözlem + Kısa özet" in ed:
    ok("Kişisel bakış format kuralı var")
else:
    fail("Kişisel bakış format kuralı eksik")

if "Prag beklediğimden daha kalabalıktı" in ed:
    ok("Prag örneği var (olumlu+olumsuz)")
else:
    fail("Prag örneği eksik")

if "Kısacası: Prag erken kalkanındır" in ed:
    ok("Kısa özet örneği var")
else:
    fail("Kısa özet örneği eksik")

print("\n── 6. YENİ YASAK CÜMLE KALIPLARI ──────────────────────────")
# BANNED_PHRASES güncellemesi

new_phrases = [
    r'dar sokakları,?\s+renkli evleriyle',
    r'açık hava müzesi',
    r'binbir gece masallarından',
    r'zaman yolculuğuna çıkar',
    r'tarihin izlerini hissed',
]

for phrase in new_phrases:
    if phrase in ed:
        ok(f"Yasak kalıp: {phrase}")
    else:
        fail(f"Yasak kalıp eksik: {phrase}")

print("\n── 7. STAVANGER ÖRNEĞİ BOLD GÜNCELLEMESİ ──────────────────")
# Stavanger örneğinde bold destinasyon adı

if "**Stavanger,**" in ed:
    ok("Stavanger örneğinde bold destinasyon")
else:
    fail("Stavanger örneğinde bold destinasyon eksik")

if "**1969'da**" in ed:
    ok("Stavanger örneğinde bold tarih")
else:
    fail("Stavanger örneğinde bold tarih eksik")

print("\n── 8. TRAINING BLOKLARI GÜNCELLEMESİ ──────────────────────")
# GIRIS_TRAINING ve GIRIS_SONRASI_TRAINING güncellemesi

if "GIRIS ANLATI MIMARISI DILI" in ed:
    ok("GIRIS_TRAINING bloğu mevcut")
else:
    fail("GIRIS_TRAINING bloğu eksik")

if "GIRIS SONRASI KISISEL BAKIS-GOZLEM-DEGERLENDIRME" in ed:
    ok("GIRIS_SONRASI_TRAINING bloğu mevcut")
else:
    fail("GIRIS_SONRASI_TRAINING bloğu eksik")

if "OLUMLU + OLUMSUZ DENGESI (ZORUNLU)" in ed:
    ok("Olumlu+olumsuz dengesi kuralı var")
else:
    fail("Olumlu+olumsuz dengesi kuralı eksik")

print("\n" + "="*60)
print(f"SONUÇ: {PASS}/{PASS+FAIL} geçti  {'✅ TÜMÜ GEÇTİ' if FAIL == 0 else f'❌ {FAIL} HATA'}")
print("="*60)
sys.exit(0 if FAIL == 0 else 1)
