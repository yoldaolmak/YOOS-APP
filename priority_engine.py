"""
priority_engine.py — Yoldaolmak.com İçerik Önceliklendirme Motoru v2.0
POST-ID-AWARE — Kuyruk item'ları hem URL (display) hem post_id (operasyon) içerir.

Değişiklikler v1 → v2:
- build_queue() sonunda URL → post_id resolve eder (WP API batch lookup)
- Kuyruk item'larında post_id alanı: int veya None (resolve edilememiş)
- mark_processed() post_id veya url ile çağrılabilir
- get_next_batch() sadece post_id'si çözülmüş item'ları döndürür (opsiyonel filtre)
- detect_content_type() artık URL pattern bazlı (slug'dan içerik tipi — post_id gelmeden)
"""

import re
import json
import datetime
import os
from typing import Optional


# ─── CONTENT TYPE DETECTION (URL/slug pattern bazlı) ──────────────────────────

DESTINATION_GUIDE_PATTERNS = [
    r'gezi.rehber', r'seyahat.rehber', r'gezgin.rehber',
    r'nasil.gidilir', r'gezi.rehberi'
]
THINGS_TO_DO_PATTERNS = [
    r'yapilacak', r'aktivite', r'gezilecek.yerler', r'ne.yapilir'
]
PLACES_TO_VISIT_PATTERNS = [
    r'gorulmesi', r'gorulebilecek', r'ziyaret.edilecek', r'gidilecek'
]

EXCLUDED_URL_PATTERNS = [
    r'/author/', r'/tag/', r'/category/', r'/page/\d',
    r'\?', r'/feed/', r'sitemap', r'wp-'
]


def detect_content_type(url: str) -> str:
    """URL pattern'den içerik tipini çıkar."""
    url_lower = url.lower()
    for p in DESTINATION_GUIDE_PATTERNS:
        if re.search(p, url_lower):
            return "Destination_Guide"
    for p in THINGS_TO_DO_PATTERNS:
        if re.search(p, url_lower):
            return "Things_To_Do"
    for p in PLACES_TO_VISIT_PATTERNS:
        if re.search(p, url_lower):
            return "Places_To_Visit"
    slug = url_lower.rstrip('/').split('/')[-1]
    if len(slug) > 4 and '-' in slug:
        return "Destination_Guide"
    return "Destination_Guide"


def is_excluded(url: str) -> bool:
    for p in EXCLUDED_URL_PATTERNS:
        if re.search(p, url):
            return True
    return False


# ─── 5 KRİTER PUANLAMA MATRİSİ ───────────────────────────────────────────────

def score_traffic_loss(click_loss: int) -> int:
    """K1: Trafik kaybı büyüklüğü (0-40 puan)"""
    loss = abs(min(click_loss, 0))
    if loss >= 1000: return 40
    if loss >= 500:  return 30
    if loss >= 200:  return 20
    if loss >= 100:  return 10
    return 5


def score_current_position(position: float) -> int:
    """K2: Mevcut SERP konumu (0-25 puan) — 4-10 arası en değerli"""
    if 4 <= position <= 10:  return 25
    if 11 <= position <= 20: return 20
    if position < 4:         return 15
    if 21 <= position <= 30: return 8
    return 2


def score_content_type(url: str) -> int:
    """K3: İçerik tipi stratejik değeri (0-20 puan)"""
    ct = detect_content_type(url)
    if ct == "Destination_Guide": return 20
    if ct == "Things_To_Do":      return 18
    if ct == "Places_To_Visit":   return 15
    return 8


def score_staleness(last_modified: Optional[str] = None) -> int:
    """K4: İçerik eskiliği (0-10 puan) — WP modified tarihinden"""
    if last_modified:
        try:
            dt = datetime.datetime.fromisoformat(last_modified)
            age_months = (datetime.datetime.now() - dt).days / 30
            if age_months >= 24: return 10
            if age_months >= 12: return 7
            if age_months >= 6:  return 4
            return 1
        except Exception:
            pass
    return 5  # bilinmiyor, orta puan


def score_competition(position: float, impressions: int) -> int:
    """K5: Rekabet tahmini (0-5 puan)"""
    if position <= 15 and impressions >= 5000: return 5
    if position <= 20 and impressions >= 2000: return 3
    return 1


# ─── ANA ÖNCELİKLENDİRME ─────────────────────────────────────────────────────

def prioritize(gsc_data: list, max_results: int = 50) -> list:
    """
    GSC verisini alır, öncelik skoru hesaplar, sıralı liste döndürür.
    post_id alanı None olarak başlar — build_queue() içinde doldurulur.
    """
    scored = []

    for row in gsc_data:
        url = row.get("url", "")
        if not url or is_excluded(url):
            continue

        click_loss  = row.get("click_loss", -row.get("clicks", 0))
        position    = row.get("position_now", row.get("position", 50))
        impressions = row.get("impressions_now", row.get("impressions", 0))
        clicks_now  = row.get("clicks_now", row.get("clicks", 0))

        if clicks_now < 5 and impressions < 200:
            continue

        k1 = score_traffic_loss(click_loss)
        k2 = score_current_position(position)
        k3 = score_content_type(url)
        k4 = score_staleness(row.get("last_modified"))
        k5 = score_competition(position, impressions)
        total = k1 + k2 + k3 + k4 + k5

        scored.append({
            "priority_score":   total,
            "post_id":          None,       # build_queue() içinde doldurulur
            "url":              url,        # display / raporlama için
            "content_type":     detect_content_type(url),
            "group":            "A" if total >= 70 else ("B" if total >= 50 else "C"),
            "k1_traffic_loss":  k1,
            "k2_position":      k2,
            "k3_content_type":  k3,
            "k4_staleness":     k4,
            "k5_competition":   k5,
            "clicks_now":       clicks_now,
            "click_loss":       click_loss,
            "position_now":     position,
            "impressions":      impressions,
            "processed":        False,
            "last_audit_score": None,
            "last_processed_at": None,
        })

    scored.sort(key=lambda x: x["priority_score"], reverse=True)
    return scored[:max_results]


# ─── KUYRUK DOSYASI ───────────────────────────────────────────────────────────

QUEUE_FILE = os.path.join(os.path.dirname(__file__), "work_queue.json")


def load_queue() -> list:
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_queue(queue: list):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


# ─── BUILD QUEUE — GSC + WP ID RESOLUTION ─────────────────────────────────────

def build_queue(gsc_data: list, max_results: int = 50,
                resolve_post_ids: bool = True) -> list:
    """
    GSC verisinden öncelikli kuyruk oluşturur.
    resolve_post_ids=True ise WP API ile URL → post_id dönüşümü yapar.
    Mevcut işlenmiş kayıtları korur.
    """
    existing = {item["url"]: item for item in load_queue()}
    fresh = prioritize(gsc_data, max_results)

    # ── Post ID çözümlemesi ───────────────────────────────────────────────
    if resolve_post_ids:
        urls_to_resolve = [
            item["url"] for item in fresh
            if item["url"] not in existing or existing[item["url"]].get("post_id") is None
        ]

        if urls_to_resolve:
            print(f"\n   🔗 {len(urls_to_resolve)} URL için post ID çözümleniyor...")
            from wp import batch_url_to_post_id
            id_map = batch_url_to_post_id(urls_to_resolve, verbose=True)
        else:
            id_map = {}

        # Zaten çözülmüş olanları existing'den al
        for item in existing.values():
            if item.get("post_id") and item["url"] not in id_map:
                id_map[item["url"]] = item["post_id"]
    else:
        id_map = {item["url"]: item.get("post_id") for item in existing.values()}

    # ── Merge: fresh list + resolved IDs + existing history ───────────────
    merged = []
    for item in fresh:
        url = item["url"]

        # Post ID ata
        item["post_id"] = id_map.get(url)

        # Önceki işlem bilgilerini koru
        if url in existing and existing[url].get("processed"):
            item["processed"]        = True
            item["last_audit_score"] = existing[url].get("last_audit_score")
            item["last_processed_at"] = existing[url].get("last_processed_at")

        merged.append(item)

    save_queue(merged)

    # ── Özet ──────────────────────────────────────────────────────────────
    resolved_count  = sum(1 for x in merged if x.get("post_id"))
    unresolved_count = sum(1 for x in merged if not x.get("post_id"))
    a = sum(1 for x in merged if x["group"] == "A")
    b = sum(1 for x in merged if x["group"] == "B")
    c = sum(1 for x in merged if x["group"] == "C")

    print(f"   ✅ Kuyruk güncellendi: {len(merged)} URL")
    print(f"   🆔 Post ID çözüldü: {resolved_count} | Çözülemedi: {unresolved_count}")
    print(f"   Grup A: {a} | B: {b} | C: {c}")

    if unresolved_count > 0:
        unresolved = [x["url"] for x in merged if not x.get("post_id")][:5]
        print(f"   ⚠️  Çözülemeyen URL örnekleri: {unresolved}")

    return merged


# ─── KUYRUK OPERASYONLARI ─────────────────────────────────────────────────────

def get_next_batch(limit: int = 10, require_post_id: bool = True) -> list:
    """
    Kuyruktan işlenmemiş sonraki N item'ı döndür.
    require_post_id=True: sadece post_id'si çözülmüş item'lar döner.
    """
    queue = load_queue()
    pending = [
        item for item in queue
        if not item.get("processed")
        and (not require_post_id or item.get("post_id") is not None)
    ]

    if not pending:
        if require_post_id:
            # Post ID'si olmayanlar var mı?
            no_id = [x for x in queue if not x.get("processed") and not x.get("post_id")]
            if no_id:
                print(f"   ⚠️  {len(no_id)} URL'nin post ID'si çözülemedi.")
                print(f"      `clawdbot.py queue build --re-resolve` ile yeniden dene.")
        else:
            print("   ℹ️  Tüm kuyruk işlendi.")
        return []

    return pending[:limit]


def mark_processed(identifier, audit_score: Optional[float] = None):
    """
    Kuyruktaki item'ı işlenmiş olarak işaretle.
    identifier: post_id (int) veya url (str) olabilir.
    """
    queue = load_queue()
    for item in queue:
        match = (
            (isinstance(identifier, int) and item.get("post_id") == identifier) or
            (isinstance(identifier, str) and item.get("url") == identifier)
        )
        if match:
            item["processed"] = True
            item["last_processed_at"] = datetime.datetime.now().isoformat()
            if audit_score is not None:
                item["last_audit_score"] = audit_score
            break
    save_queue(queue)


def re_resolve_missing(verbose: bool = True) -> int:
    """
    post_id = None olan kuyruk item'larını tekrar çözmeye çalış.
    Döndürür: çözülen item sayısı.
    """
    queue = load_queue()
    unresolved_urls = [x["url"] for x in queue if not x.get("post_id")]

    if not unresolved_urls:
        if verbose:
            print("   ✅ Tüm kuyruk item'larının post ID'si mevcut.")
        return 0

    if verbose:
        print(f"   🔍 {len(unresolved_urls)} URL yeniden çözümleniyor...")

    from wp import batch_url_to_post_id
    id_map = batch_url_to_post_id(unresolved_urls, verbose=verbose)

    resolved = 0
    for item in queue:
        if not item.get("post_id") and item["url"] in id_map and id_map[item["url"]]:
            item["post_id"] = id_map[item["url"]]
            resolved += 1

    save_queue(queue)
    if verbose:
        print(f"   ✅ {resolved} yeni post ID çözüldü.")
    return resolved


# ─── STATUS & EXPORT ──────────────────────────────────────────────────────────

def queue_status() -> dict:
    """Kuyruk durumu özeti."""
    queue = load_queue()
    total     = len(queue)
    processed = sum(1 for x in queue if x.get("processed"))
    pending   = total - processed
    with_id   = sum(1 for x in queue if x.get("post_id"))
    without_id = total - with_id

    group_pending = {"A": 0, "B": 0, "C": 0}
    for item in queue:
        if not item.get("processed"):
            g = item.get("group", "C")
            group_pending[g] = group_pending.get(g, 0) + 1

    avg_score = None
    scores = [x["last_audit_score"] for x in queue if x.get("last_audit_score")]
    if scores:
        avg_score = round(sum(scores) / len(scores), 1)

    return {
        "total":         total,
        "processed":     processed,
        "pending":       pending,
        "with_post_id":  with_id,
        "without_post_id": without_id,
        "group_pending": group_pending,
        "avg_audit_score": avg_score,
        "queue_file":    QUEUE_FILE,
    }


def export_queue_txt(output_path: str = "top50.txt") -> str:
    """Kuyruğu txt formatında dışa aktar."""
    queue = load_queue()
    lines = [
        f"# yoldaolmak.com — Audit Kuyruğu",
        f"# Oluşturuldu: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"# Toplam: {len(queue)} URL",
        "",
    ]

    for group in ["A", "B", "C"]:
        items = [x for x in queue if x["group"] == group]
        if not items:
            continue
        labels = {"A": "Hızlı Kazanım", "B": "Orta Vade", "C": "Uzun Vade"}
        lines.append(f"# Grup {group} — {labels[group]}")
        for item in items:
            status  = "✓" if item.get("processed") else " "
            pid     = item.get("post_id") or "?"
            score   = item.get("last_audit_score") or "-"
            pos     = item.get("position_now", "?")
            lines.append(
                f"#{status} post:{pid:<8} audit:{score:<5} pos:{pos:<5} "
                f"| {item['url']}"
            )
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"   💾 {output_path} dışa aktarıldı")
    return output_path
