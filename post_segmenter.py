import re

def smart_split(content):
    """
    İçeriği 800-1200 kelimelik parçalara böl
    
    KRİTİK: "Gezilecek Yerler" bölümü ASLA kesilmeyecek!
    - Bir sonraki H2'ye kadar tüm H3'ler tek segment'te
    - H3 sayısı ne olursa olsun (10, 20, 30...) hepsi birlikte
    
    SORUN ÇÖZÜLDÜfor: H3'ler duplicate taranıyor, içerik boş
    ÇÖZÜM: Segment logic güçlendirildi, debug eklendi
    """
    segments = []
    h2_pattern = r'(<h2[^>]*>.*?</h2>)'
    parts = re.split(h2_pattern, content, flags=re.DOTALL)
    
    current = {"content": "", "word_count": 0}
    in_gezilecek_yerler = False
    
    for i, part in enumerate(parts):
        if re.match(h2_pattern, part, flags=re.DOTALL):
            # H2 başlığı
            is_gezilecek = bool(re.search(r'Gezilecek Yerler', part, re.IGNORECASE))
            
            if in_gezilecek_yerler and not is_gezilecek:
                # "Gezilecek Yerler" bölümü BİTTİ, yeni H2 geldi
                # DEBUG: Segment'in ne içerdiğini göster
                h3_count = len(re.findall(r'<h3[^>]*>', current["content"]))
                print(f"   📦 Gezilecek Yerler segment kapatıldı: {h3_count} H3, {current['word_count']} kelime")
                
                # Mevcut segment'i kaydet
                segments.append(finalize_segment(current))
                current = {"content": part, "word_count": len(part.split())}
                in_gezilecek_yerler = False
            elif is_gezilecek:
                # "Gezilecek Yerler" BAŞLADI
                # Eğer current dolu ve büyükse, önce kaydet
                if current["content"].strip() and current["word_count"] > 800:
                    segments.append(finalize_segment(current))
                    current = {"content": part, "word_count": len(part.split())}
                else:
                    current["content"] += part
                    current["word_count"] += len(part.split())
                in_gezilecek_yerler = True
                print(f"   🎯 Gezilecek Yerler H2 bulundu, içerik toplanıyor...")
            else:
                # Normal H2
                if current["content"].strip() and current["word_count"] > 800:
                    segments.append(finalize_segment(current))
                    current = {"content": part, "word_count": len(part.split())}
                else:
                    current["content"] += part
                    current["word_count"] += len(part.split())
        else:
            # H2 arası içerik
            words = len(part.split())
            
            if in_gezilecek_yerler:
                # "Gezilecek Yerler" içindeyiz - ASLA KESME!
                current["content"] += part
                current["word_count"] += words
            else:
                # Normal bölüm - 1200 kelimede kes
                if current["word_count"] + words > 1200:
                    segments.append(finalize_segment(current))
                    current = {"content": part, "word_count": words}
                else:
                    current["content"] += part
                    current["word_count"] += words
    
    # Son segment'i ekle
    if current["content"].strip():
        segments.append(finalize_segment(current))
    
    # DEBUG: Segment listesini kontrol et
    print(f"\n   🔍 SEGMENT ANALİZİ:")
    for idx, seg in enumerate(segments, 1):
        h3_count = seg.get('h3_count', 0)
        has_gezilecek = seg.get('has_gezilecek', False)
        if has_gezilecek:
            print(f"      Segment {idx}: Gezilecek Yerler ✓ ({h3_count} H3, {seg['word_count']} kelime)")
        elif h3_count > 0:
            print(f"      Segment {idx}: {h3_count} H3, {seg['word_count']} kelime")
    print()
    
    return segments

def finalize_segment(seg):
    """
    Segment bilgilerini tamamla
    
    SORUN ÇÖZÜLDÜfor: H3 içerik boş
    ÇÖZÜM: max_tokens ÇOK YÜKSEK artırıldı (32000'e kadar)
    
    H3 sayısına göre dinamik token ayarı:
    - 30+ H3: 32000 token (MAKSİMUM)
    - 20-29 H3: 24000 token
    - 15-19 H3: 18000 token
    - 10-14 H3: 14000 token
    - 5-9 H3: 10000 token
    - 0-4 H3: 8000 token
    """
    wc = seg["word_count"]
    estimated_tokens = int(wc * 1.3)
    
    # "Gezilecek Yerler" H2'si var mı?
    has_gezilecek = bool(re.search(r'<h2[^>]*>.*?Gezilecek Yerler.*?</h2>', seg["content"], re.IGNORECASE))
    
    # H3 sayısını say
    h3_matches = re.findall(r'<h3[^>]*>.*?</h3>', seg["content"], re.DOTALL)
    h3_count = len(h3_matches)
    
    # max_tokens belirle
    if has_gezilecek:
        # "Gezilecek Yerler" - H3 sayısına göre ÇOK YÜKSEK token
        if h3_count >= 30:
            max_tokens = 32000  # 30+ H3 için MAKSİMUM
        elif h3_count >= 20:
            max_tokens = 24000  # 20-29 H3
        elif h3_count >= 15:
            max_tokens = 18000  # 15-19 H3
        elif h3_count >= 10:
            max_tokens = 14000  # 10-14 H3
        elif h3_count >= 5:
            max_tokens = 10000  # 5-9 H3
        else:
            max_tokens = 8000   # 0-4 H3
        
        # DEBUG
        print(f"   🔍 Gezilecek Yerler: {h3_count} H3, {wc} kelime → {max_tokens} token")
    elif h3_count > 5:
        # Çok H3 var (Gezilecek Yerler olmasa bile)
        max_tokens = 10000
    elif wc < 600:
        # Küçük segment
        max_tokens = 3000
    else:
        # Normal segment
        max_tokens = 4000
    
    return {
        "content": seg["content"],
        "word_count": wc,
        "estimated_tokens": estimated_tokens,
        "max_tokens": max_tokens,
        "h3_count": h3_count,
        "has_gezilecek": has_gezilecek
    }

def analyze_segments(segments):
    """Segment istatistikleri"""
    total = len(segments)
    total_words = sum(s["word_count"] for s in segments)
    total_est_tokens = sum(s["estimated_tokens"] for s in segments)
    
    return {
        "total_segments": total,
        "total_words": total_words,
        "estimated_output_tokens": total_est_tokens,
        "avg_words_per_segment": int(total_words / total) if total > 0 else 0
    }
