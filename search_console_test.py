import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("SEARCH CONSOLE API TEST".center(60))
print("=" * 60)

# Servis hesabı JSON dosyasını yükle
service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")

if not service_account_path or not os.path.exists(service_account_path):
    print("❌ Servis hesabı JSON dosyası bulunamadı!")
    print(f"   Aranan: {service_account_path}")
    exit(1)

try:
    # Servis hesabı ile kimlik doğrulama
    credentials = service_account.Credentials.from_service_account_file(
        service_account_path,
        scopes=['https://www.googleapis.com/auth/webmasters.readonly']  # Sadece okuma izni
    )
    
    # Search Console API servisini oluştur
    service = build('searchconsole', 'v1', credentials=credentials)
    
    print("✅ Search Console API bağlantısı başarılı!\n")
    
    # 1. Erişilebilir siteleri listele [citation:6]
    print("📋 ERİŞİLEBİLİR SİTELER:")
    print("-" * 40)
    
    site_list = service.sites().list().execute()
    
    if 'siteEntry' in site_list:
        for site in site_list['siteEntry']:
            permission = site.get('permissionLevel', 'Bilinmiyor')
            site_url = site.get('siteUrl', 'Bilinmiyor')
            print(f"  • {site_url}")
            print(f"    İzin: {permission}")
    else:
        print("  Hiç site bulunamadı!")
    
    # 2. Örnek performans verisi çek [citation:6]
    print("\n📊 PERFORMANS VERİSİ (Son 7 gün):")
    print("-" * 40)
    
    if 'siteEntry' in site_list and site_list['siteEntry']:
        # İlk siteyi seç
        first_site = site_list['siteEntry'][0]['siteUrl']
        
        from datetime import datetime, timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        request = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'dimensions': ['query'],  # Sorgulara göre grupla
            'rowLimit': 10  # En çok 10 sonuç
        }
        
        response = service.searchanalytics().query(
            siteUrl=first_site,
            body=request
        ).execute()
        
        if 'rows' in response:
            print(f"  Toplam {len(response['rows'])} sorgu bulundu:\n")
            for row in response['rows'][:5]:  # İlk 5 sonucu göster
                query = row['keys'][0] if row['keys'] else 'Bilinmiyor'
                clicks = row.get('clicks', 0)
                impressions = row.get('impressions', 0)
                ctr = row.get('ctr', 0) * 100  # Yüzde olarak
                position = row.get('position', 0)
                
                print(f"  🔍 {query}")
                print(f"     Tıklama: {clicks}, Gösterim: {impressions}")
                print(f"     TO: %{ctr:.1f}, Pozisyon: {position:.1f}\n")
        else:
            print("  Veri bulunamadı!")
    
except Exception as e:
    print(f"❌ Hata: {e}")

print("\n" + "=" * 60)
