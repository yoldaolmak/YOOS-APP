import json
from collections import Counter, defaultdict

MIN_WORDS = 60
MAX_WORDS = 200
TARGET    = 120

with open("/app") as f:
    all_chunks = [json.loads(l) for l in f]

by_post = defaultdict(list)
for c in all_chunks:
    by_post[c['post_id']].append(c)

merged_chunks = []

for post_id, chunks in by_post.items():
    chunks.sort(key=lambda x: str(x['para_index']))
    buffer    = []
    buffer_wc = 0
    cidx      = 0

    def flush(buf, bwc, ci):
        if not buf:
            return 0, ci
        combined = " ".join(c['text'] for c in buf)
        wc = len(combined.split())
        if wc >= MIN_WORDS:
            merged_chunks.append({
                "post_id":     buf[0]['post_id'],
                "title":       buf[0]['title'],
                "year":        buf[0]['year'],
                "voice_group": buf[0]['voice_group'],
                "chunk_idx":   ci,
                "para_span":   str(buf[0]['para_index']) + '-' + str(buf[-1]['para_index']),
                "text":        combined,
                "word_count":  wc,
            })
            ci += 1
        return 0, ci

    for c in chunks:
        wc = c['word_count']
        if wc >= MAX_WORDS:
            buffer_wc, cidx = flush(buffer, buffer_wc, cidx)
            buffer = []
            merged_chunks.append({
                "post_id":     c['post_id'],
                "title":       c['title'],
                "year":        c['year'],
                "voice_group": c['voice_group'],
                "chunk_idx":   cidx,
                "para_span":   str(c['para_index']),
                "text":        c['text'],
                "word_count":  wc,
            })
            cidx += 1
            continue
        buffer.append(c)
        buffer_wc += wc
        if buffer_wc >= TARGET:
            buffer_wc, cidx = flush(buffer, buffer_wc, cidx)
            buffer = []
    if buffer:
        flush(buffer, buffer_wc, cidx)

out = "/app"
with open(out, "w", encoding="utf-8") as f:
    for c in merged_chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

wc_dist = Counter()
for c in merged_chunks:
    wc = c['word_count']
    if   wc < 80:  wc_dist['60-80']   += 1
    elif wc < 120: wc_dist['80-120']  += 1
    elif wc < 160: wc_dist['120-160'] += 1
    elif wc < 200: wc_dist['160-200'] += 1
    else:          wc_dist['200+']    += 1

vg  = Counter(c['voice_group'] for c in merged_chunks)
avg = sum(c['word_count'] for c in merged_chunks) // len(merged_chunks)

print(f"=== Merged Chunk Sonucu ===")
print(f"  Toplam chunk:  {len(merged_chunks)}")
print(f"  Ort. kelime:   {avg}")
print(f"  Voice Group:   {dict(vg)}")
print(f"\n  Kelime dagilimi:")
for k, v in sorted(wc_dist.items()):
    print(f"    {k}: {v}")

import random
print(f"\n=== Ornek Chunk'lar ===")
for s in random.sample(merged_chunks, 3):
    print(f"\n[{s['voice_group']}] {s['year']} | {s['title'][:50]}")
    print(f"  {s['word_count']} kelime")
    print(f"  {s['text'][:220]}...")

print(f"\nKaydedildi: {out}")
# wip: edge case when last chunk is empty
