#!/bin/bash

# Clawdbot Toplu İşleme Script'i
# Kullanım: bash run_batch.sh

echo "========================================================================"
echo "🤖 CLAWDBOT - TOPLU İŞLEME BAŞLIYOR"
echo "========================================================================"

# post.txt dosyasını kontrol et
if [ ! -f "post.txt" ]; then
    echo "❌ HATA: post.txt dosyası bulunamadı!"
    echo "   Lütfen Clawdbot klasörüne post.txt dosyası ekleyin."
    exit 1
fi

# Toplam post sayısı
total=$(wc -l < post.txt | tr -d ' ')
echo "📋 Toplam $total post işlenecek"
echo ""

# Sayaç
success=0
failed=0
current=0

# Her satırı oku ve işle
while IFS= read -r post_id || [ -n "$post_id" ]; do
    # Boş satırları atla
    if [ -z "$post_id" ]; then
        continue
    fi
    
    current=$((current + 1))
    
    echo "========================================================================"
    echo "📝 Post $current/$total - ID: $post_id"
    echo "========================================================================"
    
    # Clawdbot'u çalıştır
    python3 clawdbot.py run example --post "$post_id" --mode draft
    
    # Sonucu kontrol et
    if [ $? -eq 0 ]; then
        success=$((success + 1))
        echo "✅ Post $post_id başarıyla işlendi!"
    else
        failed=$((failed + 1))
        echo "❌ Post $post_id işlenirken hata oluştu!"
    fi
    
    echo ""
    echo "⏳ 5 saniye bekleniyor..."
    sleep 5
    
done < post.txt

# Özet
echo "========================================================================"
echo "🎉 TOPLU İŞLEME TAMAMLANDI!"
echo "========================================================================"
echo "📊 ÖZET:"
echo "   Toplam: $total post"
echo "   ✅ Başarılı: $success"
echo "   ❌ Başarısız: $failed"
echo "========================================================================"
