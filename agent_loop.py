"""
agent_loop.py v3.1 — Pattern Memory + Threshold Router + Runtime Telemetry

v3.1 yenilikleri:
  - SQLite runtime telemetry (runs, failures, engine_metrics)
  - Latency ölçümü
  - Patch sayısı takibi
  - DB hatası agent'ı düşürmez
"""

import os
import json
import re
import datetime
import sqlite3
import time
from pathlib import Path
from content_validator import validate, auto_fix
from multi_ai import ask_gpt_mini_strict, ask_claude_haiku
from rag.router.router_rag_bridge import RAGBridge

# ═══════════════════════════════════════════════════════════════════════════════
# RUNTIME TELEMETRY
# ═══════════════════════════════════════════════════════════════════════════════
rag = RAGBridge()

_RUNTIME_DB = Path(os.path.dirname(__file__)) / "runtime.db"

def _db_conn():
    return sqlite3.connect(_RUNTIME_DB)

def log_run(post_id, mode, engine, audit_score, token_cost, latency_ms, patch_count):
    try:
        with _db_conn() as conn:
            conn.execute("""
                INSERT INTO runs (post_id, mode, engine, audit_score,
                                  token_cost, latency_ms, patch_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (post_id, mode, engine, audit_score,
                  token_cost, latency_ms, patch_count))
    except Exception as e:
        print(f"[Telemetry] run log error: {e}")

def log_failures(post_id, failures, city, fixed):
    try:
        with _db_conn() as conn:
            for f in failures:
                conn.execute("""
                    INSERT INTO failures (post_id, failure_code, city, fixed)
                    VALUES (?, ?, ?, ?)
                """, (post_id, f.code, city, int(fixed)))
    except Exception as e:
        print(f"[Telemetry] failure log error: {e}")

def update_engine_metrics(engine, token_cost, latency_ms):
    try:
        with _db_conn() as conn:
            row = conn.execute("""
                SELECT total_calls, total_tokens, avg_latency
                FROM engine_metrics WHERE engine = ?
            """, (engine,)).fetchone()

            if row:
                total_calls, total_tokens, avg_latency = row
                total_calls += 1
                total_tokens += token_cost
                new_avg = ((avg_latency * (total_calls - 1)) + latency_ms) / total_calls

                conn.execute("""
                    UPDATE engine_metrics
                    SET total_calls=?, total_tokens=?, avg_latency=?, last_call=CURRENT_TIMESTAMP
                    WHERE engine=?
                """, (total_calls, total_tokens, new_avg, engine))
            else:
                conn.execute("""
                    INSERT INTO engine_metrics
                    (engine, total_calls, total_tokens, avg_latency, last_call)
                    VALUES (?, 1, ?, ?, CURRENT_TIMESTAMP)
                """, (engine, token_cost, latency_ms))
    except Exception as e:
        print(f"[Telemetry] engine metric error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE MEMORY
# ═══════════════════════════════════════════════════════════════════════════════

_MEMORY_PATH = Path(os.path.dirname(__file__)) / "failure_memory.json"
_MAX_HISTORY = 100

def _load_memory():
    if _MEMORY_PATH.exists():
        try:
            return json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
        except:
            pass
    return {}

def _save_memory(mem):
    _MEMORY_PATH.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")

def record_failures(failures, city, fixed=False):
    mem = _load_memory()
    for f in failures:
        code = f.code
        if code not in mem:
            mem[code] = {"count": 0, "cities": [], "fix_worked": 0, "fix_failed": 0}
        mem[code]["count"] += 1
        mem[code]["last_seen"] = datetime.datetime.now().isoformat()[:10]
        if city and city not in mem[code]["cities"]:
            mem[code]["cities"] = (mem[code]["cities"] + [city])[-20:]
        if fixed:
            mem[code]["fix_worked"] += 1
        else:
            mem[code]["fix_failed"] += 1

    if len(mem) > _MAX_HISTORY:
        sorted_codes = sorted(mem, key=lambda k: mem[k]["count"])
        for old in sorted_codes[:len(mem)-_MAX_HISTORY]:
            del mem[old]

    _save_memory(mem)

# ═══════════════════════════════════════════════════════════════════════════════
# ANA AGENT LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def run_with_quality_gate(html,
                          mode="where",
                          city="",
                          post_id=0,
                          engine_used="unknown",
                          max_retries=2,
                          pass_threshold=82,
                          verbose=True):

    start_time = time.time()
    patch_counter = 0
    total_tokens = 0

    html = auto_fix(html)
    result = validate(html, mode=mode, city=city)

    record_failures(result.failures, city, fixed=False)

    if result.action == "skip":
        latency = int((time.time() - start_time) * 1000)
        log_run(post_id, mode, engine_used,
                result.score, total_tokens, latency, 0)
        log_failures(post_id, result.failures, city, True)
        update_engine_metrics(engine_used, total_tokens, latency)

        return {
            "html": html,
            "passed": True,
            "score": result.score,
            "action": "skip",
            "attempts": 0,
            "final_validation": result
        }

    best_html = html
    best_score = result.score
    best_result = result

    for attempt in range(1, max_retries + 1):

        content = html
        rag_context = rag.query(content, top_k=2)
        if result.action == "full_rewrite":
            fixed_html = ask_gpt_mini_strict(content)
        else:
            fixed_html = ask_claude_haiku(content)

        patch_counter += 1
        fixed_html = auto_fix(fixed_html)
        new_result = validate(fixed_html, mode=mode, city=city)

        record_failures(result.failures, city,
                        fixed=new_result.score > result.score)

        if new_result.score > best_score:
            best_html = fixed_html
            best_score = new_result.score
            best_result = new_result

        if new_result.action == "skip":
            break

        html = fixed_html
        result = new_result

    passed = best_score >= pass_threshold
    latency = int((time.time() - start_time) * 1000)

    log_run(post_id, mode, engine_used,
            best_score, total_tokens, latency, patch_counter)

    log_failures(post_id, best_result.failures, city, passed)
    update_engine_metrics(engine_used, total_tokens, latency)

    return {
        "html": best_html,
        "passed": passed,
        "score": best_score,
        "action": best_result.action,
        "attempts": patch_counter,
        "final_validation": best_result
    }

# ═══════════════════════════════════════════════════════════════════════════════
# RAPOR FORMATLAYICI (Backward Compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def format_agent_report(loop_result: dict) -> str:
    """
    where_engine uyumluluğu için korunmuştur.
    """
    r = loop_result
    icon = "✅" if r.get("passed") else "⚠️"
    lines = [
        "\n" + "─"*50,
        "Agent Loop Raporu:",
        f"  Sonuç   : {icon} {'GEÇTİ' if r.get('passed') else 'BAŞARISIZ'}",
        f"  Skor    : {r.get('score',0)}/100",
        f"  Eylem   : {r.get('action','?').upper()}",
        f"  Deneme  : {r.get('attempts',0)}",
    ]

    fv = r.get("final_validation")
    if fv and getattr(fv, "failures", None):
        lines.append("  Kalan Sorunlar:")
        for f in fv.failures[:4]:
            lines.append(f"    - [{f.axis}] {f.code}: {f.detail[:55]}")

    lines.append("─"*50)
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def format_agent_report(loop_result: dict) -> str:
    """
    where_engine uyumluluğu için korunmuştur.
    """

    r = loop_result or {}
    passed = r.get("passed", False)
    score = r.get("score", 0)
    action = r.get("action", "?")
    attempts = r.get("attempts", 0)

    icon = "✅" if passed else "⚠️"

    lines = [
        "\n" + "─" * 50,
        "Agent Loop Raporu:",
        f"  Sonuç   : {icon} {'GEÇTİ' if passed else 'BAŞARISIZ'}",
        f"  Skor    : {score}/100",
        f"  Eylem   : {str(action).upper()}",
        f"  Deneme  : {attempts}",
    ]

    fv = r.get("final_validation")
    if fv and hasattr(fv, "failures") and fv.failures:
        lines.append("  Kalan Sorunlar:")
        for f in fv.failures[:4]:
            lines.append(
                f"    - [{getattr(f, 'axis','?')}] "
                f"{getattr(f, 'code','?')}: "
                f"{getattr(f, 'detail','')[:55]}"
            )

    lines.append("─" * 50)
    return "\n".join(lines)