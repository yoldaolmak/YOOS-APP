from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("📋 KULLANILABİLİR MODELLER:")
print("=" * 50)

try:
    # Modelleri listele
    models = client.models.list()
    
    for model in models:
        print(f"\n📌 {model.name}")
        # Desteklenen metodları görmek için
        if hasattr(model, 'supported_actions'):
            print(f"   Desteklenen metodlar: {model.supported_actions}")
            
except Exception as e:
    print(f"Hata: {e}")
    
    # Alternatif listeleme metodu
    print("\n🔍 Alternatif metod deneniyor...")
    try:
        # v1beta API'yi dene
        models = client.models.list()
        for model in models:
            print(f"📌 {model.name}")
    except Exception as e2:
        print(f"Alternatif metod da hata verdi: {e2}")
