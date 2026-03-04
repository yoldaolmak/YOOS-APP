Yeni sayfada bağlam kaybı yaşamamak için en doğru yöntem **tek bir teknik durum dosyası üretip onu referans almak**. Böylece yeni sayfa “kaldığımız yerden” başlar. Aşağıdaki adımı aynen uygula.

---

# 1️⃣ Sistem Durum Dosyası Oluştur

Sunucuda Clawdbot kök klasörüne gir:

```bash
cd /home/ai/clawdbot
```

Yeni dosya oluştur:

```bash
nano CLAWDBOT_SYSTEM_STATE.md
```

Aşağıdaki içeriği **aynen yapıştır**.

---

# CLAWDBOT_SYSTEM_STATE.md

```markdown
# CLAWDBOT — SYSTEM STATE SNAPSHOT

## Proje Amacı
Çalışan monolitik Clawdbot rewrite sistemini bozmadan Kemal Voice odaklı RAG katmanı eklemek ve sistemi ileride Editorial Operating System mimarisine evrilebilecek şekilde güçlendirmek.

---

# 1. Core Mimari (Stabil)

Clawdbot çekirdeği aşağıdaki katmanlara sahiptir:

Decision Core  
Routing Engine  
Telemetry  
Cost Guard  
Rewrite Engines

### Modüller

model_router.py  
→ merkezi model seçimi

performance_store.py  
→ runtime telemetry (score_delta, latency)

cost_guard.py  
→ günlük bütçe koruması

agent_loop.py  
→ rewrite orchestration

audit_engine.py  
→ kalite denetimi

failure_memory.json  
→ tekrar eden hatalar

---

# 2. Decision Core Özellikleri

Routing artık:

- audit aware
- retry aware
- failure aware
- performance aware

Escalation ladder:

local_qwen_14b  
→ gpt_4o_mini  
→ claude_haiku  
→ claude_sonnet  
→ gpt_4o

---

# 3. Telemetry

runtime.db üzerinden:

avg_score_delta  
avg_latency  

model performansı hesaplanır.

performance_store.py router’a veri sağlar.

---

# 4. Cost Guard

cost_guard.py

Bütçe eşikleri:

80% → gpt_4o kapalı  
90% → claude_sonnet kapalı  
95% → sadece local_qwen + gpt_4o_mini

---

# 5. RAG Katmanı

Konum:

/home/ai/clawdbot/rag

### Pipeline

corpus  
→ chunking  
→ embedding  
→ retrieval  
→ prompt injection

---

# 6. Corpus

Dosya:

rag/data/corpus_stage1.jsonl

chunk parametreleri:

600 token chunk  
100 token overlap

metadata:

post_id  
voice_group  
year  
source

---

# 7. Embedding

Model:

BAAI/bge-small-en-v1.5

Boyut:

384

script:

build_embeddings.py

output:

corpus_embeddings.jsonl

---

# 8. Retrieval

Modül:

retrieve_context.py

Algoritma:

cosine similarity

top_k:

3

---

# 9. Prompt Entegrasyonu

rag_prompt.py

retrieval çıktısı şu başlıkla eklenir:

Kemal Voice örnekleri

---

# 10. Mevcut Durum

RAG pipeline çalışıyor.

Fake embedding kaldırıldı.  
Gerçek embedding kullanılıyor.

Vector store:

JSONL + in-memory scan

Vector DB:

henüz yok.

---

# 11. Bir Sonraki Teknik Faz

Mimari değişmeyecek.

Sadece retrieval altyapısı iyileştirilecek.

Adımlar:

1. corpus ingest genişletme
2. embedding pipeline optimize
3. Qdrant vector database kurulumu
4. retrieval Qdrant'a taşınması

Bu tamamlandıktan sonra:

centroid  
drift  

Kemal Voice stil kontrolü devreye alınacak.
```

Dosyayı kaydet.

---

# 2️⃣ Git Snapshot

Şimdi bunu Git’e ekle:

```bash
git add CLAWDBOT_SYSTEM_STATE.md
git commit -m "system snapshot before vector DB phase"
git push
```

---

# 3️⃣ Yeni Sayfada Nasıl Başlayacağız

Yeni sohbeti şu cümle ile başlat:

```
CLAWDBOT_SYSTEM_STATE.md referans alınarak devam ediyoruz.
Şu an RAG pipeline JSONL tabanlı çalışıyor.
Bir sonraki adım Qdrant vector database entegrasyonu.
```

---

# 4️⃣ Neden Bu Yöntem

Bu yöntem sayesinde:

* bağlam kaybolmaz
* sistem mimarisi sabit kalır
* yeni sayfa doğrudan teknik devam olur
* proje geçmişi Git'te belgelenir

---

# 📌 Sonuç

Yeni sayfada artık şu noktadan başlarız:

**RAG → Vector DB geçişi**

yani:

```
JSONL retrieval
→
Qdrant vector retrieval
```

---

