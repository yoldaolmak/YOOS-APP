"""
memory.py — Clawdbot Hafıza Katmanı

Her URL için:
- Kaç kez işlendi
- Her işlemde ne yapıldı ve skor ne oldu
- Skor trendi (artıyor/düşüyor/düz)
- Agent kararı geçmişi
- GSC trafik geçmişi
- Önerilen sonraki aksiyon

Bu katman sayesinde sistem kör otomasyon olmaktan çıkar.
Geçmişten öğrenir, tekrar eden başarısız stratejileri tespit eder.
"""

import json
import os
import datetime
from typing import Optional

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")


# ─── VERİ MODELİ ─────────────────────────────────────────────────────────────

def _empty_record(url: str) -> dict:
    """Yeni URL için boş hafıza kaydı."""
    return {
        "url": url,
        "first_seen": datetime.datetime.now().isoformat(),
        "last_updated": datetime.datetime.now().isoformat(),

        # İşlem geçmişi
        "attempts": 0,
        "history": [],      # [{date, action, score_before, score_after, draft_id, notes}]

        # Skor trendi
        "scores": [],       # [{"date": "...", "score": 72.4}]
        "score_trend": None,       # "improving" | "declining" | "flat" | "unknown"
        "score_trend_delta": None, # son 2 ölçüm farkı

        # GSC trafik geçmişi
        "gsc_snapshots": [],  # [{"date": "...", "clicks": 120, "position": 7.2}]
        "traffic_trend": None,  # "recovering" | "dropping" | "stable" | "unknown"

        # Karar hafızası
        "last_action": None,    # "editorial_rewrite" | "full_rewrite" | "skip_good" | "needs_full_rewrite"
        "last_action_date": None,
        "last_draft_id": None,
        "last_draft_title": None,

        # Agent önerisi
        "recommended_next": None,  # bir sonraki çalışmada ne yapılmalı
        "recommended_reason": None,
        "skip_until": None,        # bu tarihten önce tekrar işleme

        # Meta
        "content_type": None,
        "group": None,
        "notes": []
    }


# ─── OKUMA / YAZMA ───────────────────────────────────────────────────────────

def load_memory() -> dict:
    """Tüm hafızayı yükle. {url: record}"""
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_memory(memory: dict):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def get_record(url: str) -> dict:
    """URL için kayıt döndür. Yoksa oluştur."""
    memory = load_memory()
    if url not in memory:
        memory[url] = _empty_record(url)
        save_memory(memory)
    return memory[url]


def update_record(url: str, updates: dict):
    """Tek URL kaydını güncelle."""
    memory = load_memory()
    if url not in memory:
        memory[url] = _empty_record(url)
    memory[url].update(updates)
    memory[url]["last_updated"] = datetime.datetime.now().isoformat()
    save_memory(memory)


# ─── SKOR YÖNETİMİ ───────────────────────────────────────────────────────────

def record_audit(url: str, score: float, content_type: str = None, group: str = None):
    """Audit skoru kaydet, trendi hesapla."""
    memory = load_memory()
    if url not in memory:
        memory[url] = _empty_record(url)

    rec = memory[url]
    now = datetime.datetime.now().isoformat()

    # Skoru ekle
    rec["scores"].append({"date": now, "score": score})

    # Trendi hesapla (min 2 ölçüm gerekli)
    scores = rec["scores"]
    if len(scores) >= 2:
        last = scores[-1]["score"]
        prev = scores[-2]["score"]
        delta = last - prev
        rec["score_trend_delta"] = round(delta, 1)

        if delta >= 5:
            rec["score_trend"] = "improving"
        elif delta <= -5:
            rec["score_trend"] = "declining"
        else:
            rec["score_trend"] = "flat"
    elif len(scores) == 1:
        rec["score_trend"] = "unknown"

    if content_type:
        rec["content_type"] = content_type
    if group:
        rec["group"] = group

    rec["last_updated"] = now
    memory[url] = rec
    save_memory(memory)


# ─── AKSİYON KAYDI ───────────────────────────────────────────────────────────

def record_action(
    url: str,
    action: str,
    score_before: Optional[float] = None,
    score_after: Optional[float] = None,
    draft_id: Optional[int] = None,
    draft_title: Optional[str] = None,
    notes: str = ""
):
    """
    Bir işlem kaydı ekle.
    action: "editorial_rewrite" | "full_rewrite" | "audit_only" |
            "skip_good" | "skip_monitor" | "needs_full_rewrite"
    """
    memory = load_memory()
    if url not in memory:
        memory[url] = _empty_record(url)

    rec = memory[url]
    now = datetime.datetime.now().isoformat()

    entry = {
        "date": now,
        "action": action,
        "score_before": score_before,
        "score_after": score_after,
        "draft_id": draft_id,
        "draft_title": draft_title,
        "notes": notes
    }

    rec["history"].append(entry)
    rec["attempts"] += 1
    rec["last_action"] = action
    rec["last_action_date"] = now

    if draft_id:
        rec["last_draft_id"] = draft_id
    if draft_title:
        rec["last_draft_title"] = draft_title

    rec["last_updated"] = now
    memory[url] = rec
    save_memory(memory)


# ─── GSC SNAPSHOT ────────────────────────────────────────────────────────────

def record_gsc_snapshot(url: str, clicks: int, position: float, impressions: int = 0):
    """GSC anlık görüntüsü ekle, trafik trendini hesapla."""
    memory = load_memory()
    if url not in memory:
        memory[url] = _empty_record(url)

    rec = memory[url]
    now = datetime.datetime.now().isoformat()

    rec["gsc_snapshots"].append({
        "date": now,
        "clicks": clicks,
        "position": position,
        "impressions": impressions
    })

    # Trafik trendi (min 2 snapshot)
    snaps = rec["gsc_snapshots"]
    if len(snaps) >= 2:
        last_clicks = snaps[-1]["clicks"]
        prev_clicks = snaps[-2]["clicks"]
        change_pct = ((last_clicks - prev_clicks) / max(prev_clicks, 1)) * 100

        if change_pct >= 10:
            rec["traffic_trend"] = "recovering"
        elif change_pct <= -10:
            rec["traffic_trend"] = "dropping"
        else:
            rec["traffic_trend"] = "stable"

    rec["last_updated"] = now
    memory[url] = rec
    save_memory(memory)


# ─── AKİLLİ ÖNERİ MOTORU ────────────────────────────────────────────────────

def compute_recommendation(url: str) -> dict:
    """
    Geçmiş verilerden bir sonraki aksiyon önerisi üret.
    Döndürür: {"action": "...", "reason": "...", "skip_until": None}
    """
    rec = get_record(url)
    scores = rec.get("scores", [])
    attempts = rec.get("attempts", 0)
    trend = rec.get("score_trend", "unknown")
    traffic_trend = rec.get("traffic_trend", "unknown")
    last_action = rec.get("last_action")
    history = rec.get("history", [])

    last_score = scores[-1]["score"] if scores else None

    # ── Kural 1: Skor zaten yüksek → atla, izle ──────────────────────────────
    if last_score and last_score >= 82:
        return {
            "action": "skip_monitor",
            "reason": f"Skor {last_score}/100 — yayına hazır seviyede. 30 gün sonra kontrol et.",
            "skip_until": (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        }

    # ── Kural 2: Trafik artıyor ama skor orta → dokunma ──────────────────────
    if traffic_trend == "recovering" and last_score and 55 <= last_score < 82:
        return {
            "action": "skip_monitor",
            "reason": f"Trafik artıyor ({traffic_trend}), skor {last_score}. Doğal toparlanma izleniyor.",
            "skip_until": (datetime.datetime.now() + datetime.timedelta(days=14)).isoformat()
        }

    # ── Kural 3: 3+ deneme, skor düz veya düşüyor → tam yeniden yazım ────────
    if attempts >= 3 and trend in ("flat", "declining"):
        recent_scores = [s["score"] for s in scores[-3:]]
        avg = sum(recent_scores) / len(recent_scores)
        if avg < 70:
            return {
                "action": "full_rewrite",
                "reason": f"{attempts} deneme sonrası skor hala {avg:.0f} ortalamasında ({trend}). "
                          f"editorial_rewrite yetersiz, sıfırdan yaz.",
                "skip_until": None
            }

    # ── Kural 4: editorial_rewrite 2 kez denendi, skor artmadı ───────────────
    rewrite_attempts = [h for h in history if h.get("action") == "editorial_rewrite"]
    if len(rewrite_attempts) >= 2:
        first_score = rewrite_attempts[0].get("score_before", 0)
        last_score_after = rewrite_attempts[-1].get("score_after") or last_score
        if last_score_after and (last_score_after - first_score) < 10:
            return {
                "action": "full_rewrite",
                "reason": f"editorial_rewrite {len(rewrite_attempts)} kez denendi, "
                          f"skor {first_score}→{last_score_after} (+{last_score_after-first_score:.0f}). "
                          f"Yapısal sorun — tam yeniden yazım gerekli.",
                "skip_until": None
            }

    # ── Kural 5: Skor < 55 → direkt tam yeniden yazım ────────────────────────
    if last_score and last_score < 55:
        return {
            "action": "full_rewrite",
            "reason": f"Skor {last_score} < 55 — editorial_rewrite yetmez, sıfırdan yaz.",
            "skip_until": None
        }

    # ── Kural 6: Skor 55-81 arası → editorial_rewrite ────────────────────────
    if last_score and 55 <= last_score < 82:
        return {
            "action": "editorial_rewrite",
            "reason": f"Skor {last_score} — cerrahi düzeltme uygun.",
            "skip_until": None
        }

    # ── Varsayılan: önce audit ────────────────────────────────────────────────
    return {
        "action": "audit",
        "reason": "Henüz audit yapılmamış, önce skoru ölç.",
        "skip_until": None
    }


def update_recommendation(url: str):
    """Öneriyi hesapla ve kayıtta güncelle."""
    rec_data = compute_recommendation(url)
    update_record(url, {
        "recommended_next": rec_data["action"],
        "recommended_reason": rec_data["reason"],
        "skip_until": rec_data.get("skip_until")
    })
    return rec_data


# ─── SKIP KONTROLÜ ───────────────────────────────────────────────────────────

def should_skip(url: str) -> tuple[bool, str]:
    """Bu URL şu an işlenmeli mi? (should_process, reason)"""
    rec = get_record(url)
    skip_until = rec.get("skip_until")

    if skip_until:
        try:
            skip_dt = datetime.datetime.fromisoformat(skip_until)
            if datetime.datetime.now() < skip_dt:
                days_left = (skip_dt - datetime.datetime.now()).days
                reason = rec.get("recommended_reason", "")
                return True, f"skip_until dolmadı ({days_left} gün kaldı). {reason}"
        except Exception:
            pass

    return False, ""


# ─── RAPORLAMA ───────────────────────────────────────────────────────────────

def memory_summary() -> dict:
    """Tüm hafızanın özeti."""
    memory = load_memory()
    total = len(memory)

    if total == 0:
        return {"total": 0, "message": "Hafıza boş — henüz işlem yapılmamış."}

    # Trend dağılımı
    trends = {"improving": 0, "declining": 0, "flat": 0, "unknown": 0}
    for rec in memory.values():
        t = rec.get("score_trend", "unknown") or "unknown"
        trends[t] = trends.get(t, 0) + 1

    # Skor aralıkları
    all_scores = []
    for rec in memory.values():
        scores = rec.get("scores", [])
        if scores:
            all_scores.append(scores[-1]["score"])

    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else None
    ready = sum(1 for s in all_scores if s >= 82)
    needs_work = sum(1 for s in all_scores if s < 55)

    # Öneri dağılımı
    recommendations = {}
    for rec in memory.values():
        r = rec.get("recommended_next") or "unknown"
        recommendations[r] = recommendations.get(r, 0) + 1

    # En çok denenen ama hala düşük skor
    stubborn = [
        {"url": url, "attempts": rec["attempts"], "last_score": rec["scores"][-1]["score"] if rec.get("scores") else None}
        for url, rec in memory.items()
        if rec.get("attempts", 0) >= 3 and rec.get("scores") and rec["scores"][-1]["score"] < 70
    ]
    stubborn.sort(key=lambda x: x["attempts"], reverse=True)

    return {
        "total_urls": total,
        "avg_audit_score": avg_score,
        "publish_ready": ready,
        "needs_full_rewrite": needs_work,
        "score_trends": trends,
        "next_action_breakdown": recommendations,
        "stubborn_urls": stubborn[:5],  # 3+ deneme hala < 70
    }


def print_memory_report(url: str):
    """Tek URL için terminal raporu."""
    rec = get_record(url)
    slug = url.rstrip('/').split('/')[-1]

    print(f"\n{'─'*60}")
    print(f"🧠 HAFIZA: {slug}")
    print(f"{'─'*60}")
    print(f"  Toplam deneme  : {rec['attempts']}")
    print(f"  Skor trendi    : {rec.get('score_trend', 'bilinmiyor')}")
    print(f"  Trafik trendi  : {rec.get('traffic_trend', 'bilinmiyor')}")

    scores = rec.get("scores", [])
    if scores:
        score_line = " → ".join(str(s["score"]) for s in scores[-5:])
        print(f"  Skor geçmişi   : {score_line}")

    print(f"  Son aksiyon    : {rec.get('last_action', '-')}")
    print(f"  Son draft ID   : {rec.get('last_draft_id', '-')}")

    rec_next = rec.get("recommended_next")
    rec_reason = rec.get("recommended_reason")
    if rec_next:
        print(f"\n  ➡️  Öneri       : {rec_next}")
        print(f"     Neden       : {rec_reason}")

    skip_until = rec.get("skip_until")
    if skip_until:
        try:
            dt = datetime.datetime.fromisoformat(skip_until)
            if datetime.datetime.now() < dt:
                print(f"  ⏸️  Skip until  : {skip_until[:10]}")
        except Exception:
            pass

    if rec.get("history"):
        print(f"\n  Geçmiş:")
        for h in rec["history"][-3:]:
            date = h.get("date", "")[:10]
            action = h.get("action", "-")
            sb = h.get("score_before", "-")
            sa = h.get("score_after", "-")
            print(f"    {date} | {action:<22} | {sb} → {sa}")
