"""Content type registry — structural templates per genre."""

CONTENT_TYPES = {
    "travel_blog": {
        "label": "Seyahat Blogu / Travel Blog",
        "structure": [
            "Giriş — kişisel an veya atmosfer",
            "Neden bu yer?",
            "Ne gördüm, ne yaşadım",
            "Pratik notlar",
            "Son not / öneri",
        ],
        "tone": "birinci şahıs, içten, okuyucuya siz/sen",
        "length": "800-1500 kelime",
    },
    "travel_guide": {
        "label": "Seyahat Rehberi / Travel Guide",
        "structure": [
            "Genel bakış",
            "Nasıl gidilir",
            "Ne zaman gidilir",
            "Gezilecek yerler",
            "Nerede kalınır / yenir",
            "Pratik bilgiler",
        ],
        "tone": "otoriter, tavsiye eden, bilgi odaklı",
        "length": "1500-3000 kelime",
    },
    "magazine": {
        "label": "Dergi Yazısı / Magazine Article",
        "structure": [
            "Çarpıcı giriş (anekdot veya sahne)",
            "Konu / tez",
            "Derinlemesine anlatı",
            "Uzman / tanık sesi",
            "Kapanış",
        ],
        "tone": "hikayeci, derinlikli, okuyucuyu çeken",
        "length": "1200-2500 kelime",
    },
    "news": {
        "label": "Haber / News",
        "structure": [
            "5N1K girişi",
            "Bağlam",
            "Detaylar",
            "Alıntı / kaynak",
            "Arka plan",
        ],
        "tone": "nesnel, yalın, doğrudan",
        "length": "400-800 kelime",
    },
    "story": {
        "label": "Hikaye / Story",
        "structure": [
            "Sahne kurma",
            "Karakter / çatışma",
            "Gelişme",
            "Dönüm noktası",
            "Kapanış",
        ],
        "tone": "anlatıcı, görsel, duygusal",
        "length": "1000-3000 kelime",
    },
    "column": {
        "label": "Köşe Yazısı / Column",
        "structure": [
            "Tetikleyici olay / gözlem",
            "Yazar görüşü",
            "Argüman / örnek",
            "Sonuç / çağrı",
        ],
        "tone": "fikir sahibi, kışkırtıcı, özgün",
        "length": "500-900 kelime",
    },
}


def list_types() -> dict:
    return {k: v["label"] for k, v in CONTENT_TYPES.items()}


def get(content_type: str) -> dict:
    return CONTENT_TYPES.get(content_type, CONTENT_TYPES["travel_blog"])
