import os
import requests
from google import genai
from dotenv import load_dotenv
import json

# .env dosyasını yükle
load_dotenv()

# API anahtarlarını al
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")

print("=" * 60)
print("API TEST SCRIPTİ".center(60))
print("=" * 60)

# 1. Gemini API Test
print("\n📌 1. GEMINI API TEST")
print("-" * 40)

if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents='Merhaba, bugün nasılsın?'
        )
        print("✅ Gemini API bağlantısı başarılı!")
        print(f"   Cevap: {response.text}")
    except Exception as e:
        print(f"❌ Gemini API hatası: {e}")
else:
    print("❌ Gemini API anahtarı bulunamadı!")

# 2. Google Search API Test
print("\n📌 2. GOOGLE SEARCH API TEST")
print("-" * 40)

if SEARCH_API_KEY and SEARCH_ENGINE_ID:
    try:
        # Örnek arama
        search_query = "Python programlama dili"
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': SEARCH_API_KEY,
            'cx': SEARCH_ENGINE_ID,
            'q': search_query,
            'num': 3  # 3 sonuç getir
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            results = response.json()
            print(f"✅ Google Search API bağlantısı başarılı!")
            print(f"   Arama: '{search_query}'")
            print(f"   Toplam sonuç: {results.get('searchInformation', {}).get('totalResults', 'Bilinmiyor')}")
            
            # İlk 3 sonucu göster
            if 'items' in results:
                print("\n   İlk 3 sonuç:")
                for i, item in enumerate(results['items'][:3], 1):
                    print(f"   {i}. {item['title']}")
                    print(f"      {item['link']}")
        else:
            print(f"❌ Google Search API hatası: {response.status_code}")
            print(f"   {response.text}")
            
    except Exception as e:
        print(f"❌ Google Search API bağlantı hatası: {e}")
else:
    print("❌ Google Search API anahtarı veya Engine ID bulunamadı!")

print("\n" + "=" * 60)
print("TEST TAMAMLANDI".center(60))
print("=" * 60)