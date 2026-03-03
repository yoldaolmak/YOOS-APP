```python
import os
import re
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


def extract_code_block(response: str) -> tuple[str, str]:
    pattern = r'FILE:\s*(\S+)\s*.*?```python\s*\n(.*?)\n```'
    match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
    if match:
        filename = match.group(1)
        code = match.group(2)
        return filename, code
    
    pattern = r'```python\s*\n(.*?)\n```'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return None, match.group(1)
    
    return None, None


def create_backup(filepath: str):
    if not os.path.exists(filepath):
        return
    backup_path = filepath + '.backup'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   💾 Backup oluşturuldu: {backup_path}")


def get_file_stats(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {'size': 0, 'lines': 0}
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return {
        'size': len(content),
        'lines': len(content.splitlines())
    }


def train_command(args):
    if not args.input:
        print("\n❌ Hata: --input parametresi gerekli")
        print("   Kullanım: python clawdbot.py train --input instructions.txt")
        return
    
    if not os.path.exists(args.input):
        print(f"\n❌ Hata: Dosya bulunamadı: {args.input}")
        return
    
    print("\n" + "=" * 70)
    print("🎓 NATURAL LANGUAGE TRAINING ENGINE")
    print("=" * 70)
    
    with open(args.input, 'r', encoding='utf-8') as f:
        instructions = f.read()
    
    print(f"   📄 Instructions: {args.input}")
    print(f"   📏 Instruction length: {len(instructions)} characters")
    
    api_key = os.getenv('CLAUDE_API_KEY')
    if not api_key:
        print("\n❌ Hata: CLAUDE_API_KEY bulunamadı (.env dosyasını kontrol edin)")
        return
    
    print("\n   🤖 Claude API'ye gönderiliyor...")
    
    client = Anthropic(api_key=api_key)
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{
                "role": "user",
                "content": instructions
            }]
        )
        
        response_text = response.content[0].text
        print(f"   ✅ Claude response alındı ({len(response_text)} karakter)")
        
    except Exception as e:
        print(f"\n❌ Claude API hatası: {e}")
        return
    
    target_file, code = extract_code_block(response_text)
    
    if not code:
        print("\n❌ Hata: Response'da Python kod bloğu bulunamadı")
        print("\n📋 Claude Response (ilk 500 karakter):")
        print(response_text[:500])
        return
    
    if not target_file:
        print("\n⚠️  Uyarı: Target dosya belirtilmemiş")
        print("   Instructions'da 'FILE: <filename>' formatı kullanın")
        print("\n📋 Claude Response (ilk 500 karakter):")
        print(response_text[:500])
        return
    
    print(f"\n   🎯 Target dosya: {target_file}")
    
    old_stats = get_file_stats(target_file)
    
    create_backup(target_file)
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(code)
    
    new_stats = get_file_stats(target_file)
    
    print("\n" + "=" * 70)
    print("✅ DOSYA GÜNCELLENDİ")
    print("=" * 70)
    print(f"   📁 Dosya: {target_file}")
    print(f"   📊 Eski boyut: {old_stats['size']:,} karakter")
    print(f"   📊 Yeni boyut: {new_stats['size']:,} karakter")
    print(f"   📊 Fark: {new_stats['size'] - old_stats['size']:+,} karakter")
    print(f"   📝 Eski satır: {old_stats['lines']:,}")
    print(f"   📝 Yeni satır: {new_stats['lines']:,}")
    print(f"   📝 Fark: {new_stats['lines'] - old_stats['lines']:+,} satır")
    print("=" * 70)
```