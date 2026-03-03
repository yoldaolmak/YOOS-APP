"""
wp.py — WordPress REST API wrapper (multi-site)

Desteklenen siteler:
  yoldaolmak  → WP_URL / WP_USER / WP_APP_PASSWORD
  gezievreni  → WP_GEZIEVRENI_URL / WP_GEZIEVRENI_USER / WP_GEZIEVRENI_PASSWORD
"""
import os
import json
import base64
import ssl
import urllib.request
import urllib.error
import urllib.parse
import html
import re
from typing import Optional, Dict, Any

# macOS'ta Python sistem sertifika store'unu kullanmıyor.
# SSL doğrulamasını bypass et (yalnızca kendi WP sunucusu için güvenli).
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Aktif site — clawdbot.py set_active_site() ile değiştirir
_active_site = "yoldaolmak"

_SITE_CONFIGS = {
    "yoldaolmak": {
        "url_env":  "WP_URL",
        "user_env": "WP_USER",
        "pass_env": "WP_APP_PASSWORD",
        "default_url": "https://yoldaolmak.com",
    },
    "gezievreni": {
        "url_env":  "WP_GEZIEVRENI_URL",
        "user_env": "WP_GEZIEVRENI_USER",
        "pass_env": "WP_GEZIEVRENI_PASSWORD",
        "default_url": "https://gezievreni.com",
    },
}


def set_active_site(site: str) -> None:
    """Aktif siteyi değiştir. 'yoldaolmak' veya 'gezievreni'."""
    global _active_site
    normalized = site.lower().strip()
    if normalized not in _SITE_CONFIGS:
        # Kısmi eşleşme: 'gezi' → 'gezievreni'
        for key in _SITE_CONFIGS:
            if normalized in key or key in normalized:
                normalized = key
                break
    _active_site = normalized
    print(f"   🌐 Aktif site: {_active_site} ({get_site_url()})")


def get_site_url() -> str:
    cfg = _SITE_CONFIGS.get(_active_site, _SITE_CONFIGS["yoldaolmak"])
    return os.environ.get(cfg["url_env"], cfg["default_url"])


def _get_wp_config():
    """Aktif siteye göre WP credentials döndür."""
    cfg = _SITE_CONFIGS.get(_active_site, _SITE_CONFIGS["yoldaolmak"])
    return {
        "url":      os.environ.get(cfg["url_env"],  cfg["default_url"]),
        "user":     os.environ.get(cfg["user_env"],  ""),
        "password": os.environ.get(cfg["pass_env"],  ""),
    }


def _wp_request(endpoint: str, method: str = "GET", data: dict = None) -> Any:
    """Make authenticated WordPress REST API request."""
    cfg = _get_wp_config()
    base = cfg["url"].rstrip("/")
    url = f"{base}/wp-json/wp/v2/{endpoint}"

    credentials = base64.b64encode(
        f"{cfg['user']}:{cfg['password']}".encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "User-Agent": "Clawdbot/8.3",
    }

    body = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        raise RuntimeError(f"WP API hatası {e.code}: {err[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"WP bağlantı hatası: {e.reason}")


def get_post(post_id: int) -> Optional[Dict]:
    """Fetch a WordPress post by ID."""
    try:
        post = _wp_request(f"posts/{post_id}?context=edit&_fields=id,title,content,excerpt,status,categories,tags,slug")
        return post
    except Exception as e:
        print(f"   ❌ Post {post_id} çekilemedi: {e}")
        return None


def save_as_draft(title: str, content: str, categories: list = None,
                  tags: list = None, yoast_meta: dict = None) -> Optional[int]:
    """
    Save content as a new WordPress draft post.
    yoast_meta: {"title": ..., "desc": ..., "focuskw": ...}
    Yoast SEO eklentisi aktifse meta alanlarını da set eder.
    """
    data = {
        "title":   title,
        "content": content,
        "status":  "draft",
    }
    if categories:
        data["categories"] = categories
    if tags:
        data["tags"] = tags
    if yoast_meta:
        data["meta"] = {
            "yoast_wpseo_title":    yoast_meta.get("title", ""),
            "yoast_wpseo_metadesc": yoast_meta.get("desc", ""),
            "yoast_wpseo_focuskw":  yoast_meta.get("focuskw", ""),
        }

    try:
        result = _wp_request("posts", method="POST", data=data)
        return result.get("id")
    except Exception as e:
        print(f"   ❌ Draft kaydedilemedi: {e}")
        return None


def update_post(post_id: int, title: str, content: str,
                status: str = "draft", yoast_meta: dict = None) -> bool:
    """Update an existing WordPress post."""
    data = {
        "title":   title,
        "content": content,
        "status":  status,
    }
    if yoast_meta:
        data["meta"] = {
            "yoast_wpseo_title":    yoast_meta.get("title", ""),
            "yoast_wpseo_metadesc": yoast_meta.get("desc", ""),
            "yoast_wpseo_focuskw":  yoast_meta.get("focuskw", ""),
        }
    try:
        _wp_request(f"posts/{post_id}", method="POST", data=data)
        return True
    except Exception as e:
        print(f"   ❌ Post güncellenemedi: {e}")
        return False


def strip_html(html_content: str) -> str:
    """Strip HTML tags and decode entities."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    # Decode HTML entities
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def detect_country_category(title: str, content: str) -> str:
    """Simple country detection from title/content."""
    text = (title + " " + content).lower()
    countries = {
        "prag": "cekya", "çekya": "cekya", "czech": "cekya",
        "viyana": "avusturya", "vienna": "avusturya",
        "berlin": "almanya", "münchen": "almanya",
        "paris": "fransa", "france": "fransa",
        "roma": "italya", "venice": "italya", "floransa": "italya",
        "barselona": "ispanya", "madrid": "ispanya",
        "amsterdam": "hollanda", "netherlands": "hollanda",
    }
    for keyword, country in countries.items():
        if keyword in text:
            return country
    return "avrupa"


# ─── URL → POST ID BRIDGE ─────────────────────────────────────────────────────

def extract_slug_from_url(url: str) -> str:
    """
    URL'den WordPress post slug'ını çıkar.
    https://yoldaolmak.com/bosna-hersek-gezi-rehberi/ → bosna-hersek-gezi-rehberi
    """
    url = url.rstrip('/').split('?')[0].split('#')[0]
    return url.split('/')[-1]


def get_post_id_by_slug(slug: str) -> Optional[int]:
    """
    WordPress slug'ından post ID'yi WP REST API ile çek.
    GET /wp/v2/posts?slug=<slug>&_fields=id,slug&status=any
    Bulunamazsa None döner.
    """
    if not slug:
        return None
    try:
        import urllib.parse
        encoded_slug = urllib.parse.quote(slug, safe='')
        results = _wp_request(
            f"posts?slug={encoded_slug}&_fields=id,slug,status&status=any&per_page=1"
        )
        if results and isinstance(results, list) and len(results) > 0:
            return int(results[0]["id"])
        return None
    except Exception as e:
        print(f"   ⚠️  Slug lookup başarısız ({slug}): {e}")
        return None


def url_to_post_id(url: str) -> Optional[int]:
    """
    GSC URL'sini → WordPress post ID'ye çevirir.
    Önce slug çıkarır, sonra WP API'yi sorgular.
    """
    slug = extract_slug_from_url(url)
    if not slug or '.' in slug:  # domain kökü veya .php gibi static dosya
        return None
    return get_post_id_by_slug(slug)


def batch_url_to_post_id(
    urls: list,
    cache_file: str = "url_id_cache.json",
    verbose: bool = True
) -> dict:
    """
    URL listesini toplu olarak post ID'ye çevirir.
    Cache'i kullanır — her URL için API çağrısı yapmaz.

    Döndürür: {url: post_id} — bulunamayanlar için post_id = None
    """
    import json as _json

    # Cache yükle
    cache_path = os.path.join(os.path.dirname(__file__), cache_file)
    cache: dict = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding='utf-8') as f:
                cache = _json.load(f)
        except Exception:
            cache = {}

    result = {}
    to_fetch = []

    for url in urls:
        if url in cache:
            result[url] = cache[url]
        else:
            to_fetch.append(url)

    if to_fetch:
        if verbose:
            print(f"   🔍 {len(to_fetch)} URL için WP API slug lookup...")

        import time as _time
        for i, url in enumerate(to_fetch, 1):
            post_id = url_to_post_id(url)
            result[url] = post_id
            cache[url] = post_id
            if verbose and i % 10 == 0:
                print(f"      {i}/{len(to_fetch)} tamamlandı...")
            _time.sleep(0.15)  # API rate limit için küçük bekleme

        # Cache güncelle
        with open(cache_path, 'w', encoding='utf-8') as f:
            _json.dump(cache, f, ensure_ascii=False, indent=2)

        resolved = sum(1 for v in result.values() if v is not None)
        failed = sum(1 for v in result.values() if v is None)
        if verbose:
            print(f"   ✅ Çözüldü: {resolved} | Bulunamadı: {failed}")

    return result
