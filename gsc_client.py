"""
gsc_client.py — Google Search Console API Wrapper
example.com trafik verisi çekme modülü

Kurulum:
  pip install google-auth google-auth-httplib2 google-api-python-client

.env gereksinimleri:
  GSC_CREDENTIALS_FILE=/path/to/service_account.json
  GSC_SITE_URL=https://example.com/
"""

import os
import json
import datetime
from typing import Optional


def _get_service():
    """GSC API service objesi döndür."""
    creds_file = os.environ.get("GSC_CREDENTIALS_FILE", "")
    if not creds_file or not os.path.exists(creds_file):
        raise FileNotFoundError(
            f"GSC credentials bulunamadı: '{creds_file}'\n"
            "Google Cloud Console'dan service account JSON indirip "
            ".env dosyasına GSC_CREDENTIALS_FILE=/path/to/file.json ekle."
        )

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        service = build("searchconsole", "v1", credentials=credentials)
        return service
    except ImportError:
        raise ImportError(
            "Google API kütüphaneleri eksik.\n"
            "pip install google-auth google-auth-httplib2 google-api-python-client"
        )


def fetch_page_performance(
    months: int = 12,
    min_impressions: int = 100,
    row_limit: int = 500
) -> list[dict]:
    """
    Sayfa bazında GSC performans verisi çek.

    Döndürür: [
        {
            "url": "https://example.com/prag-gezi-rehberi",
            "clicks": 1240,
            "impressions": 18500,
            "ctr": 0.067,
            "position": 6.2
        },
        ...
    ]
    """
    service = _get_service()
    site_url = os.environ.get("GSC_SITE_URL", "https://example.com/")

    end_date = datetime.date.today() - datetime.timedelta(days=3)  # GSC 3 gün gecikme
    start_date = end_date - datetime.timedelta(days=30 * months)

    request_body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page"],
        "rowLimit": row_limit,
        "startRow": 0
    }

    print(f"   📡 GSC API sorgulanıyor: {start_date} → {end_date}")
    response = service.searchanalytics().query(
        siteUrl=site_url,
        body=request_body
    ).execute()

    rows = response.get("rows", [])
    print(f"   ✅ {len(rows)} sayfa verisi alındı")

    results = []
    for row in rows:
        impressions = row.get("impressions", 0)
        if impressions < min_impressions:
            continue

        results.append({
            "url": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": impressions,
            "ctr": round(row.get("ctr", 0), 4),
            "position": round(row.get("position", 99), 1)
        })

    return results


def fetch_historical_comparison(months_recent: int = 3) -> list[dict]:
    """
    Şimdiki vs geçmiş dönem karşılaştırması için iki ayrı sorgu yap.
    Trafik kaybını hesapla.

    Döndürür: [
        {
            "url": "...",
            "clicks_now": 120,
            "clicks_before": 450,
            "click_loss": -330,
            "position_now": 8.2,
            "position_before": 4.1
        },
        ...
    ]
    """
    service = _get_service()
    site_url = os.environ.get("GSC_SITE_URL", "https://example.com/")

    today = datetime.date.today() - datetime.timedelta(days=3)

    # Şimdiki dönem
    now_end = today
    now_start = today - datetime.timedelta(days=30 * months_recent)

    # Geçmiş dönem (aynı uzunlukta, 1 yıl önce)
    past_end = today - datetime.timedelta(days=365)
    past_start = past_end - datetime.timedelta(days=30 * months_recent)

    def _query(start, end):
        resp = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["page"],
                "rowLimit": 500
            }
        ).execute()
        return {row["keys"][0]: row for row in resp.get("rows", [])}

    print(f"   📡 Şimdiki dönem: {now_start} → {now_end}")
    now_data = _query(now_start, now_end)
    print(f"   📡 Geçmiş dönem:  {past_start} → {past_end}")
    past_data = _query(past_start, past_end)

    results = []
    all_urls = set(now_data.keys()) | set(past_data.keys())

    for url in all_urls:
        now = now_data.get(url, {})
        past = past_data.get(url, {})

        clicks_now = now.get("clicks", 0)
        clicks_before = past.get("clicks", 0)
        click_loss = clicks_now - clicks_before

        results.append({
            "url": url,
            "clicks_now": clicks_now,
            "clicks_before": clicks_before,
            "click_loss": click_loss,
            "impressions_now": now.get("impressions", 0),
            "position_now": round(now.get("position", 99), 1),
            "position_before": round(past.get("position", 99), 1)
        })

    # En yüksek kayıptan sırala
    results.sort(key=lambda x: x["click_loss"])
    return results


def save_gsc_cache(data: list, filename: str = "gsc_cache.json"):
    """GSC verisini yerel cache'e kaydet (API kotasını korur)."""
    cache_path = os.path.join(os.path.dirname(__file__), filename)
    cache = {
        "fetched_at": datetime.datetime.now().isoformat(),
        "data": data
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"   💾 GSC cache kaydedildi: {cache_path}")
    return cache_path


def load_gsc_cache(filename: str = "gsc_cache.json", max_age_hours: int = 12) -> Optional[list]:
    """Cache tazeyse yükle, eskiyse None döndür."""
    cache_path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(cache_path):
        return None

    with open(cache_path, encoding="utf-8") as f:
        cache = json.load(f)

    fetched_at = datetime.datetime.fromisoformat(cache["fetched_at"])
    age_hours = (datetime.datetime.now() - fetched_at).total_seconds() / 3600

    if age_hours > max_age_hours:
        print(f"   ⚠️  GSC cache {age_hours:.1f} saat eski, yenileniyor...")
        return None

    print(f"   ✅ GSC cache kullanılıyor ({age_hours:.1f} saat önce)")
    return cache["data"]
