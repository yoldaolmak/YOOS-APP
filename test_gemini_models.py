#!/usr/bin/env python3
"""Test Gemini ile çalışan modelleri bul"""

import os
os.environ['GEMINI_API_KEY'] = 'AIzaSyDt6Gw8p6r5CYTCYrQsymzAo1GwyLDGp_0'

print("🧪 Gemini Model Test\n")

try:
    import google.generativeai as genai
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    
    print("✅ SDK yüklü (google-generativeai - deprecated)\n")
    
    # Test edilecek modeller
    models_to_test = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-002", 
        "gemini-1.5-flash-8b",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
        "gemini-1.5-pro-002",
        "gemini-1.5-pro-latest",
        "gemini-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
    ]
    
    print("📋 Model Testleri:\n")
    
    working_models = []
    
    for model_name in models_to_test:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                "Test",
                generation_config={"max_output_tokens": 5}
            )
            print(f"✅ {model_name}")
            working_models.append(model_name)
            
        except Exception as e:
            err = str(e)
            if '404' in err or 'not found' in err.lower():
                print(f"❌ {model_name} - 404 (mevcut değil)")
            else:
                print(f"⚠️  {model_name} - {err[:50]}")
    
    print(f"\n✅ ÇALIŞAN MODELLER ({len(working_models)}):")
    for m in working_models:
        print(f"   - {m}")
    
    if working_models:
        print(f"\n💡 ÖNERİLEN MODEL: {working_models[0]}")
    else:
        print("\n❌ Hiçbir model çalışmıyor!")

except ImportError:
    print("❌ google-generativeai yüklü değil")
    print("Kur: pip install google-generativeai")

except Exception as e:
    print(f"❌ Hata: {e}")
