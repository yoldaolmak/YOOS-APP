#!/usr/bin/env python3
"""
test_acik_gorevler.py
Madde 12'deki açık görevlere karşı regresyon testleri.
Bağımlılık yok (no network, no WP).
"""
import sys
import re
import ast
import importlib.util
import types

PASS, FAIL = 0, 0

def ok(name):
    global PASS
    PASS += 1
    print(f"   ✅ {name}")

def fail(name, detail=""):
    global FAIL
    FAIL += 1
    d = f" — {detail}" if detail else ""
    print(f"   ❌ {name}{d}")

# ════════════════════════════════════════════════════════════════════
# Stub dış bağımlılıklar (network/WP olmadan import çalışsın)
# ════════════════════════════════════════════════════════════════════
import unittest.mock as mock

WP_STUB = types.ModuleType("wp")
WP_STUB.update_post_complete = mock.MagicMock()
WP_STUB.save_as_draft = mock.MagicMock(return_value={"id": 99, "link": "http://test"})
WP_STUB.get_post_categories = mock.MagicMock(return_value=[5])
WP_STUB.get_category_slug = mock.MagicMock(return_value="turkiye")
WP_STUB.get_category_path = mock.MagicMock(return_value="turkiye/akdeniz")
WP_STUB.delete_post_comments = mock.MagicMock(return_value=0)
WP_STUB.update_yoast_meta = mock.MagicMock(return_value=True)
sys.modules.setdefault("wp", WP_STUB)

for mod in ["anthropic", "openai", "dotenv", "requests"]:
    m = types.ModuleType(mod)
    if mod == "dotenv":
        m.load_dotenv = lambda: None
    if mod == "requests":
        m.Session = mock.MagicMock
        m.exceptions = mock.MagicMock()
    sys.modules.setdefault(mod, m)

urllib3_mod = types.ModuleType("urllib3")
urllib3_mod.disable_warnings = lambda *a, **kw: None
urllib3_mod.exceptions = types.SimpleNamespace(InsecureRequestWarning=Warning)
sys.modules.setdefault("urllib3", urllib3_mod)
for sub in ["urllib3.util", "urllib3.util.retry"]:
    sm = types.ModuleType(sub)
    if sub == "urllib3.util.retry":
        sm.Retry = mock.MagicMock
    sys.modules.setdefault(sub, sm)
adapters_mod = types.ModuleType("requests.adapters")
adapters_mod.HTTPAdapter = mock.MagicMock
sys.modules.setdefault("requests.adapters", adapters_mod)

# claude.py + openai_engine.py stub
for mod in ["claude", "openai_engine"]:
    m = types.ModuleType(mod)
    m.ask_claude = mock.MagicMock(return_value="<p>test</p>")
    sys.modules.setdefault(mod, m)

# ════════════════════════════════════════════════════════════════════
# GÖREV 4: extract_dest — kenar vakaları
# ════════════════════════════════════════════════════════════════════
print("\n── GÖREV 4: extract_dest kenar vakaları ──────────────────────────")

# Modülü dinamik yükle (mock'lar hazır)
spec = importlib.util.spec_from_file_location("editor", "/home/claude/editor.py")
editor_mod = importlib.util.module_from_spec(spec)
# Gereksiz dış çağrıları mock'la
with mock.patch.dict(sys.modules, {"claude": sys.modules["claude"],
                                    "openai_engine": sys.modules["openai_engine"]}):
    try:
        spec.loader.exec_module(editor_mod)
        extract_dest = editor_mod.extract_dest

        cases = [
            ("Dubrovnik Nerede",                "Dubrovnik"),
            ("Dubrovnik'e Nasıl Gidilir",       "Dubrovnik"),
            ("Belem Gezilecek Yerler",           "Belem"),
            ("Split Hakkında",                  "Split"),
            ("İstanbul&#8217;da Gezilecek",     "İstanbul"),
            ("Rovinj Gezi Rehberi",             "Rovinj"),
            ("Marakeş Nerede Nasıl Gidilir",    "Marakeş"),
            ("Prag Rehberi",                    "Prag"),
            ("Aix-en-Provence Hakkında",        "Aix-en-Provence"),
            ("Tallinn",                         "Tallinn"),        # Tetikleyici kelime yok
        ]

        for title, expected in cases:
            result = extract_dest(title)
            if result == expected:
                ok(f'extract_dest("{title}") → "{result}"')
            else:
                fail(f'extract_dest("{title}")', f'beklenen "{expected}", aldık "{result}"')

    except Exception as e:
        fail("editor.py import", str(e))

# ════════════════════════════════════════════════════════════════════
# GÖREV 1: wp.py — SSL / _session_for / genel→guncel
# ════════════════════════════════════════════════════════════════════
print("\n── GÖREV 1: SSL fix + genel→guncel fallback ────────────────────")

with open("/home/claude/wp.py") as f:
    wp_src = f.read()

if "_session_for" in wp_src:
    ok("_session_for fonksiyonu var")
else:
    fail("_session_for fonksiyonu eksik")

if "verify=False" in wp_src:
    ok("verify=False gezievreni için mevcut")
else:
    fail("verify=False eksik")

if "Retry" in wp_src:
    ok("Retry import/kullanım var")
else:
    fail("Retry eksik")

if "urllib3.disable_warnings" in wp_src:
    ok("InsecureRequestWarning bastırılıyor")
else:
    fail("urllib3.disable_warnings eksik")

if '"guncel"' in wp_src or "'guncel'" in wp_src:
    ok("guncel fallback var")
else:
    fail("guncel fallback eksik")

# ════════════════════════════════════════════════════════════════════
# GÖREV 2: update_yoast_meta — ayrı PATCH
# ════════════════════════════════════════════════════════════════════
print("\n── GÖREV 2: update_yoast_meta ayrı PATCH ───────────────────────")

if "def update_yoast_meta" in wp_src:
    ok("update_yoast_meta fonksiyonu wp.py'de var")
else:
    fail("update_yoast_meta fonksiyonu eksik")

if "200, 201" in wp_src:
    ok("HTTP 200/201 kontrol var")
else:
    fail("HTTP 200/201 kontrol eksik")

with open("/home/claude/editor.py") as f:
    ed_src = f.read()

if "update_yoast_meta" in ed_src and "from wp import" in ed_src:
    # import satırında var mı?
    import_line = [l for l in ed_src.splitlines() if "from wp import" in l]
    if import_line and "update_yoast_meta" in import_line[0]:
        ok("update_yoast_meta editor.py import'ında")
    else:
        fail("update_yoast_meta import satırına eklenmemiş")

    # WHERE + TRAVEL her ikisinde çağrılıyor mu?
    calls = ed_src.count("update_yoast_meta(")
    if calls >= 2:
        ok(f"update_yoast_meta {calls} kez çağrılıyor (WHERE + TRAVEL)")
    else:
        fail(f"update_yoast_meta sadece {calls} kez çağrılıyor, en az 2 bekleniyor")

# ════════════════════════════════════════════════════════════════════
# GÖREV 5: TRAVEL modu — Nasıl Gidilir direktifi
# ════════════════════════════════════════════════════════════════════
print("\n── GÖREV 5: TRAVEL Nasıl Gidilir direktifi ─────────────────────")

travel_directive = "Sadece gerçekten var olan ulaşım seçeneklerini yaz"
if travel_directive in ed_src:
    ok("TRAVEL body prompt'ta 'gerçek ulaşım' direktifi var")
else:
    fail("TRAVEL body prompt'ta ulaşım direktifi eksik")

no_train_directive = "Tren yoksa" in ed_src or "tren yoksa" in ed_src.lower()
if no_train_directive:
    ok("'Tren yoksa bölüm açma' direktifi var")
else:
    fail("'Tren yoksa bölüm açma' direktifi eksik")

# ════════════════════════════════════════════════════════════════════
# GÖREV 6: clawdbot.py header versiyonu
# ════════════════════════════════════════════════════════════════════
print("\n── GÖREV 6: clawdbot.py versiyon ───────────────────────────────")

with open("/home/claude/clawdbot.py") as f:
    cb_src = f.read()

if "v7.8" in cb_src and "v3.2" not in cb_src:
    ok("clawdbot.py header v7.8 ✓ (v3.2 kalmadı)")
elif "v7.8" in cb_src:
    fail("v7.8 var ama v3.2 hâlâ kalmış")
else:
    fail("v7.8 header yok")

# ════════════════════════════════════════════════════════════════════
# ÖZET
# ════════════════════════════════════════════════════════════════════
total = PASS + FAIL
print(f"\n{'='*60}")
print(f"GENEL SONUÇ: {PASS}/{total} geçti  {'✅ TÜMÜ GEÇTİ' if FAIL == 0 else f'❌ {FAIL} HATA'}")
print(f"{'='*60}")
sys.exit(0 if FAIL == 0 else 1)
