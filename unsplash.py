import os
import requests
from dotenv import load_dotenv

load_dotenv()

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
UNSPLASH_URL = "https://api.unsplash.com/search/photos"

def search_unsplash_image(query, orientation="landscape"):
    """
    Unsplash'tan görsel ara
    
    Args:
        query (str): Arama terimi (örn: "Melbourne city")
        orientation (str): landscape, portrait, squarish
    
    Returns:
        dict: Görsel bilgileri (url, alt_text, credit)
    """
    headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
    params = {
        "query": query,
        "per_page": 1,
        "orientation": orientation
    }
    
    try:
        response = requests.get(UNSPLASH_URL, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data['results']:
            photo = data['results'][0]
            return {
                "url": photo['urls']['regular'],  # 1080px genişlik
                "url_full": photo['urls']['full'],  # Tam boyut
                "alt_text": photo['alt_description'] or query,
                "photographer": photo['user']['name'],
                "photographer_url": photo['user']['links']['html'],
                "download_url": photo['links']['download_location']
            }
        else:
            return None
    
    except Exception as e:
        print(f"Unsplash API hatası: {e}")
        return None

def generate_image_html(image_data, caption=None):
    """
    Görsel için Gutenberg HTML bloğu oluştur
    """
    if not image_data:
        return ""
    
    caption_text = caption or image_data['alt_text']
    credit = f"Fotoğraf: <a href='{image_data['photographer_url']}' target='_blank' rel='nofollow'>{image_data['photographer']}</a> / Unsplash"
    
    return f"""
<!-- wp:image -->
<figure class="wp-block-image">
  <img src="{image_data['url']}" alt="{image_data['alt_text']}" />
  <figcaption>{caption_text}<br/><small>{credit}</small></figcaption>
</figure>
<!-- /wp:image -->
"""

# Test
if __name__ == "__main__":
    result = search_unsplash_image("Melbourne city skyline")
    if result:
        print(f"Görsel bulundu: {result['url']}")
        print(f"Fotoğrafçı: {result['photographer']}")
        html = generate_image_html(result, "Melbourne şehir manzarası")
        print(html)
    else:
        print("Görsel bulunamadı")

