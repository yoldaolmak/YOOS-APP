import os, time
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ═══════════════════════════════════════════════════════════════
# GÜNCEL ÇALIŞAN GEMINI MODELLERİ (Şubat 2026)
# ═══════════════════════════════════════════════════════════════
# Öncelik sırası: Hız → Maliyet → Kalite dengesi
# ═══════════════════════════════════════════════════════════════

GEMINI_MODELS = [
    # ═══════════════════════════════════════════════════════════════
    # LEGACY SDK (google-generativeai) İÇİN ÇALIŞAN MODELLER
    # API Key: AIzaSyDt... ile test edildi
    # ═══════════════════════════════════════════════════════════════
    
    # Flash modeller (hızlı + ucuz)
    "gemini-1.5-flash",                # Ana model
    "gemini-1.5-flash-002",            # Versiyon 002
    "gemini-1.5-flash-8b",             # 8B parametre versiyonu
    
    # Pro modeller (kaliteli)
    "gemini-1.5-pro",                  # Ana model
    "gemini-1.5-pro-002",              # Versiyon 002
    
    # Legacy (son çare)
    "gemini-pro",                      # Eski versiyon
    
    # NOT: 
    # - *-latest aliasları deprecated SDK'da çalışmayabilir
    # - gemini-2.0-* modelleri bu API key için mevcut değil
]

_genai  = None
_sdk    = None  # "new" | "legacy"

# ───────────────────────────────────────────────────────────────
# SDK Initialization
# ───────────────────────────────────────────────────────────────

def _init():
    """Gemini SDK'yı başlat (YENİ SDK ÖNCELİKLİ)"""
    global _genai, _sdk
    
    if _genai is not None: 
        return  # Zaten başlatılmış
    
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY .env dosyasında bulunamadı!")
    
    # 1. Önce YENİ SDK'yı dene: google-genai (önerilen)
    try:
        from google import genai
        _genai = genai.Client(api_key=GEMINI_API_KEY)
        _sdk = "new"
        print(f"      ℹ️  Gemini: google-genai (yeni SDK)")
        return
    except ImportError:
        pass
    
    # 2. ESKİ SDK'yı dene: google-generativeai (deprecated)
    try:
        import google.generativeai as genai2
        genai2.configure(api_key=GEMINI_API_KEY)
        _genai = genai2
        _sdk = "legacy"
        print(f"      ⚠️  Gemini: google-generativeai (eski SDK - deprecated)")
        print(f"      💡 Yeni SDK kur: pip install google-genai")
        return
    except Exception as e:
        raise RuntimeError(
            f"Gemini SDK bulunamadı: {e}\n"
            f"Yükleyin: pip install google-genai"
        )

# ───────────────────────────────────────────────────────────────
# Test Function (clawdbot.py tarafından kullanılıyor)
# ───────────────────────────────────────────────────────────────

def test_gemini():
    """
    Gemini bağlantısını test et
    
    Returns:
        bool: True = çalışıyor, False = hata var
    """
    try:
        _init()
        
        # Basit test prompt'u
        test_prompt = "Merhaba, bu bir test mesajıdır. Lütfen sadece 'OK' yanıtı ver."
        
        # İlk modeli dene
        if _sdk == "new":
            from google.genai import types
            r = _genai.models.generate_content(
                model=GEMINI_MODELS[0],
                contents=test_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=10,
                    temperature=0.0
                )
            )
            result = r.text
        else:
            m = _genai.GenerativeModel(GEMINI_MODELS[0])
            r = m.generate_content(
                test_prompt,
                generation_config={"max_output_tokens": 10, "temperature": 0.0}
            )
            result = r.text
        
        # Yanıt varsa başarılı
        if result and len(result.strip()) > 0:
            return True
        
        return False
    
    except Exception as e:
        # Hata detayını göster (debugging için)
        print(f"   ⚠️  Gemini test hatası: {str(e)[:100]}")
        return False

# ───────────────────────────────────────────────────────────────
# Main Ask Function
# ───────────────────────────────────────────────────────────────

def ask_gemini(prompt, max_tokens=16000):
    """
    Gemini'ye prompt gönder, yanıt al
    
    Args:
        prompt (str): Kullanıcı prompt'u
        max_tokens (int): Maksimum token sayısı
    
    Returns:
        str: Gemini'nin yanıtı
    
    Raises:
        RuntimeError: Tüm modeller başarısız olursa
    """
    _init()
    last_error = None
    
    for model in GEMINI_MODELS:
        try:
            # SDK'ya göre API çağrısı
            if _sdk == "new":
                from google.genai import types
                r = _genai.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.7
                    )
                )
                result = r.text
            else:
                # Legacy SDK
                m = _genai.GenerativeModel(model)
                r = m.generate_content(
                    prompt,
                    generation_config={
                        "max_output_tokens": max_tokens,
                        "temperature": 0.7
                    }
                )
                result = r.text
            
            # Yanıt kontrolü
            if result and len(result.strip()) > 100:
                print(f"      🟢 Gemini: {model}")
                return result.strip()
            
            last_error = f"Boş yanıt: {model}"
        
        except Exception as e:
            err = str(e)
            
            # Hata tipine göre aksiyon
            if any(x in err for x in ["404", "NOT_FOUND", "not found", "does not exist"]):
                # Model mevcut değil, sonrakini dene
                last_error = f"Model yok: {model}"
                continue
            
            elif any(x in err for x in ["429", "RATE_LIMIT", "quota", "Resource", "RESOURCE_EXHAUSTED"]):
                # Rate limit, bekle ve tekrar dene
                print(f"      ⏳ Rate limit ({model}), 20s bekleniyor...")
                time.sleep(20)
                last_error = f"Rate limit: {model}"
                continue
            
            elif any(x in err for x in ["API_KEY", "PERMISSION", "INVALID_ARGUMENT"]):
                # API key sorunu, diğer modelleri denemeye gerek yok
                raise RuntimeError(f"Gemini API Key hatası: {err[:150]}")
            
            else:
                # Bilinmeyen hata, sonraki modeli dene
                last_error = f"{model}: {err[:80]}"
                continue
    
    # Tüm modeller başarısız
    raise RuntimeError(
        f"Tüm Gemini modelleri başarısız oldu.\n"
        f"Son hata: {last_error}\n"
        f"Denenen modeller: {', '.join(GEMINI_MODELS[:3])}"
    )

# ───────────────────────────────────────────────────────────────
# Debug / Standalone Test
# ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🧪 Gemini Test Scripti\n")
    print("=" * 60)
    
    # API Key kontrolü
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY bulunamadı!")
        print("   .env dosyasını kontrol edin")
        exit(1)
    
    print(f"✅ API Key bulundu: {GEMINI_API_KEY[:20]}...")
    
    # SDK kontrolü
    try:
        _init()
        print(f"✅ SDK yüklendi: {_sdk}")
    except Exception as e:
        print(f"❌ SDK yüklenemedi: {e}")
        exit(1)
    
    # Bağlantı testi
    print("\n🔍 Gemini bağlantısı test ediliyor...")
    if test_gemini():
        print("✅ Gemini bağlantısı çalışıyor!")
    else:
        print("❌ Gemini bağlantısı başarısız")
        exit(1)
    
    # Gerçek prompt testi
    print("\n📝 Gerçek prompt testi...")
    try:
        response = ask_gemini(
            "Merhaba! Lütfen kısa bir şekilde kendini tanıt (max 2 cümle).",
            max_tokens=100
        )
        print("\n📨 Gemini Yanıtı:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print("\n✅ Test başarılı!")
    except Exception as e:
        print(f"\n❌ Test başarısız: {e}")
        exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 Tüm testler tamamlandı!")
