import os
import time
import hashlib
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("API key bulunamadı! .env dosyasında CLAUDE_API_KEY=... set edin")

client = Anthropic(api_key=api_key)

PROMPT_CACHE = {}
CACHE_DURATION = 900

def ask_claude(prompt, max_tokens=4000, model="claude-sonnet-4-20250514", cache_prompt=None):
    if cache_prompt:
        full_prompt = f"{cache_prompt}\n\n{prompt}"
    else:
        full_prompt = prompt
    
    cache_key = hashlib.md5(full_prompt.encode('utf-8')).hexdigest()
    
    if cache_key in PROMPT_CACHE:
        cached_response, timestamp = PROMPT_CACHE[cache_key]
        elapsed = time.time() - timestamp
        
        if elapsed < CACHE_DURATION:
            remaining = int(CACHE_DURATION - elapsed)
            print(f"      💾 CACHE HIT! ({remaining}s kaldı)")
            return cached_response
        else:
            del PROMPT_CACHE[cache_key]
    
    messages = []
    
    if cache_prompt:
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": cache_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        })
        messages.append({
            "role": "assistant",
            "content": "Anladım, master kuralları cache'ledim. İçeriği bekliyorum."
        })
    
    messages.append({
        "role": "user",
        "content": prompt
    })
    
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        timeout=600.0,
        messages=messages
    )
    
    result = response.content[0].text
    PROMPT_CACHE[cache_key] = (result, time.time())
    
    return result

def clear_cache():
    global PROMPT_CACHE
    PROMPT_CACHE = {}
    print("✅ Cache temizlendi")

def get_cache_stats():
    total = len(PROMPT_CACHE)
    active = 0
    now = time.time()
    for cache_key, (_, timestamp) in PROMPT_CACHE.items():
        if now - timestamp < CACHE_DURATION:
            active += 1
    return {'total': total, 'active': active, 'expired': total - active}
