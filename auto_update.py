#!/usr/bin/env python3
"""
Clawdbot Otomatik Güncelleme (post.txt dosyasından toplu işleme)
Kullanım: python3 auto_update.py
"""

import os
import sys
import time
from datetime import datetime

def read_post_ids(filename='post.txt'):
    """post.txt dosyasından post ID'leri oku"""
    if not os.path.exists(filename):
        print(f"❌ HATA: {filename} dosyası bulunamadı!")
        print(f"   Lütfen Clawdbot klasörüne post.txt dosyası ekleyin.")
        print(f"   Format: Her satırda bir post ID")
        sys.exit(1)
    
    with open(filename, 'r') as f:
        post_ids = [line.strip() for line in f if line.strip()]
    
    return post_ids

def run_clawdbot(post_id, mode='where --ai gpt'):
    """Clawdbot'u çalıştır"""
    cmd = f"python3 clawdbot.py run example --post {post_id} --mode {mode}"
    return os.system(cmd)

def main():
    print("="*70)
    print("🤖 CLAWDBOT - TOPLU İŞLEME (post.txt)")
    print("="*70)
    
    post_ids = read_post_ids()
    total = len(post_ids)
    
    print(f"📋 Toplam {total} post işlenecek")
    print(f"🕐 Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    success = 0
    failed = 0
    
    for i, post_id in enumerate(post_ids, 1):
        print("="*70)
        print(f"📝 Post {i}/{total} - ID: {post_id}")
        print("="*70)
        
        result = run_clawdbot(post_id)
        
        if result == 0:
            success += 1
            print(f"✅ Post {post_id} başarıyla işlendi!")
        else:
            failed += 1
            print(f"❌ Post {post_id} işlenirken hata oluştu!")
        
        if i < total:
            print()
            print("⏳ 5 saniye bekleniyor (API rate limit)...")
            time.sleep(5)
    
    print()
    print("="*70)
    print("🎉 TOPLU İŞLEME TAMAMLANDI!")
    print("="*70)
    print(f"📊 ÖZET:")
    print(f"   Toplam: {total} post")
    print(f"   ✅ Başarılı: {success}")
    print(f"   ❌ Başarısız: {failed}")
    print(f"🕐 Bitiş: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

if __name__ == "__main__":
    main()
