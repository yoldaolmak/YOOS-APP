import os
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    _ANTHROPIC_AVAILABLE = False

try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    openai = None
    _OPENAI_AVAILABLE = False

load_dotenv()


class InterventionEngine:
    def __init__(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        if _ANTHROPIC_AVAILABLE and self.anthropic_key:
            self.claude = anthropic.Anthropic(api_key=self.anthropic_key)
        else:
            self.claude = None
        
        if _OPENAI_AVAILABLE and self.openai_key:
            openai.api_key = self.openai_key
            self.openai_client = openai
        else:
            self.openai_client = None
    
    def load_audit_report(self, filepath: str) -> Dict[str, Any]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def _nested(value, *keys, default=None):
        """
        Safely traverse nested dict OR handle flat scalar values.
        Supports both formats:
          - nested: {'temporal_anchors': {'count': 0, 'pass': False}}
          - flat:   {'temporal_anchors': 0}
        """
        if isinstance(value, dict):
            for key in keys:
                if not isinstance(value, dict):
                    return default
                value = value.get(key, default)
            return value
        # flat scalar — map common key requests
        if keys == ('pass',):
            return bool(value) if value is not None else default
        if keys == ('count',):
            return value if isinstance(value, int) else default
        return default

    def identify_missing_elements(self, audit_report: Dict[str, Any]) -> Dict[str, List[str]]:
        missing = {
            "voice": [],
            "authority": [],
            "critique": [],
            "structure": []
        }

        voice = audit_report.get('voice_analysis', {})
        ta = voice.get('temporal_anchors', {})
        if not self._nested(ta, 'pass', default=False):
            count = self._nested(ta, 'count', default=0) or 0
            needed = max(0, 2 - count)
            missing['voice'].append(f"temporal_anchor:{needed}")

        kn = voice.get('kemal_notes', {})
        if not self._nested(kn, 'pass', default=False):
            count = self._nested(kn, 'count', default=0) or 0
            needed = max(0, 3 - count)
            missing['voice'].append(f"kemal_note:{needed}")

        pv = voice.get('plural_violations', {})
        pv_count = self._nested(pv, 'count', default=0) or 0
        if pv_count > 0:
            missing['voice'].append("plural_pronoun_fix:required")

        auth = audit_report.get('authority_analysis', {})
        sc = auth.get('sourced_claims', {})
        if not self._nested(sc, 'pass', default=False):
            missing['authority'].append("sourced_claims:insufficient")

        pr = auth.get('prices', {})
        if not self._nested(pr, 'pass', default=False):
            missing['authority'].append("price_sources:insufficient")

        coords_block = auth.get('coordinates', {})
        coords = self._nested(coords_block, 'count', default=0) or 0
        poi_count = audit_report.get('page_info', {}).get('poi_count', 0) or \
                    audit_report.get('structure', {}).get('pois', {}).get('numbered_poi_count', 0)
        if poi_count > 0 and coords < poi_count:
            missing['authority'].append(f"coordinates:{poi_count - coords}_missing")

        crit = audit_report.get('critique_analysis', {})
        pcb = crit.get('pro_con_blocks', {})
        if not self._nested(pcb, 'pass', default=False):
            count = self._nested(pcb, 'count', default=0) or 0
            needed = max(0, 2 - count)
            missing['critique'].append(f"pro_con_blocks:{needed}")

        tt = crit.get('tourist_traps', {})
        if not self._nested(tt, 'pass', default=False):
            missing['critique'].append("tourist_trap_warning:1")

        return {k: v for k, v in missing.items() if v}
    
    def build_intervention_prompt(self, missing_elements: Dict[str, List[str]], original_text: str) -> str:
        instructions = []
        
        for category, items in missing_elements.items():
            for item in items:
                if item.startswith("temporal_anchor:"):
                    needed = int(item.split(':')[1])
                    instructions.append(f"Metne {needed} adet temporal anchor ekle (örn: '2019'da ilk gittiğimde...'). Mevcut metni değiştirme, sadece bu cümleleri doğal noktalara yerleştir.")
                
                elif item.startswith("kemal_note:"):
                    needed = int(item.split(':')[1])
                    instructions.append(f"Metne {needed} adet '**Kemal'in Notu:**' bloğu ekle (50-100 kelime). Gezilecek yerler bölümüne yerleştir. Kişisel gözlem/tavsiye olsun.")
                
                elif item == "plural_pronoun_fix:required":
                    instructions.append("'biz', 'bizim' gibi çoğul zamirleri 'ben', 'benim' ile değiştir.")
                
                elif item == "sourced_claims:insufficient":
                    instructions.append("Sayısal iddialara kaynak ekle. Format: '(Kaynak, YYYY-MM)'")
                
                elif item == "price_sources:insufficient":
                    instructions.append("Fiyatlara kaynak + tarih ekle. Format: '80€ (Booking.com, Şubat 2024)'")
                
                elif item.startswith("coordinates:"):
                    count = int(item.split(':')[1].split('_')[0])
                    instructions.append(f"{count} gezilecek yere koordinat ekle. Format: 'Koordinat: XX.XXXX° K, XX.XXXX° D'")
                
                elif item.startswith("pro_con_blocks:"):
                    needed = int(item.split(':')[1])
                    instructions.append(f"{needed} yer için Pro-Con bloğu ekle:\n✅ Artı: [pozitif]\n❌ Eksi: [negatif]\n💡 Alternatif: [çözüm]")
                
                elif item == "tourist_trap_warning:1":
                    instructions.append("1 turist tuzağı uyarısı ekle:\n⚠️ **Turist Tuzağı:** [ürün/yer]\nNeden: [açıklama]\nAlternatif: [yerel seçenek]")
        
        if not instructions:
            return None
        
        instruction_text = "\n- ".join([""] + instructions)
        
        prompt = f"""Sen Kemal Kaya'nın editörüsün. Yoldaolmak.com için içerik düzenliyorsun.

ORİJİNAL METİN:
{original_text[:4000]}
{'...' if len(original_text) > 4000 else ''}

GÖREV:
Metni BAŞTAN YAZMA. Sadece şunları ekle:{instruction_text}

KURALLAR:
- Mevcut metni koru, sadece eksik öğeleri ekle
- Kemal'in sesi: samimi, eleştirel, deneyim bazlı
- Temporal anchor'lar gerçekçi olsun (1995-2025 arası)
- Çoğul zamir kullanma (biz → ben)
- Her eklemeyi doğal noktalara yerleştir

ÇIKTI FORMATI:
Tüm metni ver (eski + yeni eklemeler). Markdown formatında yaz."""
        
        return prompt
    
    def _call_claude(self, prompt: str) -> Optional[str]:
        if not self.claude:
            return None
        try:
            message = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _call_gpt(self, prompt: str) -> Optional[str]:
        if not self.openai_client:
            return None
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _rule_based_intervention(self, missing: Dict[str, List[str]], original_text: str) -> str:
        """
        Rule-based fallback intervention when no AI client is available.
        Appends templated blocks for each missing element.
        Not as natural as AI output, but keeps the pipeline functional.
        """
        additions = []

        for category, items in missing.items():
            for item in items:
                if item.startswith("temporal_anchor:"):
                    needed = int(item.split(':')[1])
                    for i in range(needed):
                        additions.append(
                            f"\n2019'da ilk gittiğimde şehrin bu bölümü çok farklıydı. "
                            f"Sonraki ziyaretlerimde değişimi bizzat gördüm.\n"
                        )

                elif item.startswith("kemal_note:"):
                    needed = int(item.split(':')[1])
                    for i in range(needed):
                        additions.append(
                            f"\n**Kemal'in Notu:** Buraya ilk kez 2015'te geldim. "
                            f"O günden bu yana birkaç kez daha ziyaret ettim. "
                            f"Sabah erken saatlerde gelmeni öneririm — hem kalabalık yok, hem ışık çok daha iyi. "
                            f"Öğleden sonra turist baskısı ciddi boyutlara ulaşıyor.\n"
                        )

                elif item.startswith("pro_con_blocks:"):
                    needed = int(item.split(':')[1])
                    for i in range(needed):
                        additions.append(
                            f"\n✅ Artı: Tarihi değer yüksek, özgün mimari korunmuş.\n"
                            f"❌ Eksi: Yoğun turist sezonu boyunca aşırı kalabalık.\n"
                            f"💡 Alternatif: Sabah 7-9 arası veya kış aylarında ziyaret et.\n"
                        )

                elif item == "tourist_trap_warning:1":
                    additions.append(
                        f"\n⚠️ **Turist Tuzağı:** Meydandaki tur paketleri\n"
                        f"Neden: Standart tur acenteleri yerel güzergahları atlar, yalnızca kalabalık noktaları gösterir.\n"
                        f"Alternatif: Şehir belediyesinin ücretsiz yürüyüş turlarına katıl veya kendi temponla geş.\n"
                    )

                elif item.startswith("coordinates:"):
                    count = int(item.split(':')[1].split('_')[0])
                    additions.append(
                        f"\n[Not: {count} adet koordinat eklenmesi gerekiyor — "
                        f"Google Maps'ten doğru koordinatları alarak ekleyin. "
                        f"Format: XX.XXXX° K, XX.XXXX° D]\n"
                    )

                elif item == "sourced_claims:insufficient":
                    additions.append(
                        f"\n[Not: Sayısal iddialara kaynak eklenmeli. "
                        f"Format: (Kaynak adı, YYYY-MM)]\n"
                    )

                elif item == "price_sources:insufficient":
                    additions.append(
                        f"\n[Not: Fiyatlara kaynak ve tarih eklenmeli. "
                        f"Format: 80€ (Booking.com, Şubat 2026)]\n"
                    )

        if additions:
            return original_text + "\n\n---\n*Editoryal Eklemeler (Rule-Based Fallback)*\n" + "".join(additions)
        return original_text

    def run_intervention_pipeline(self, audit_filepath: str, original_text: str, 
                                  output_filepath: Optional[str] = None,
                                  use_ai: str = "auto") -> Dict[str, Any]:
        audit_report = self.load_audit_report(audit_filepath)
        
        if 'error' in audit_report:
            return {'success': False, 'error': audit_report['error']}
        
        missing = self.identify_missing_elements(audit_report)
        
        if not missing:
            return {
                'success': True,
                'message': 'No interventions needed',
                'missing_elements': missing,
                'modified_text': original_text,
                'interventions_applied': 0
            }
        
        prompt = self.build_intervention_prompt(missing, original_text)
        
        if not prompt:
            return {
                'success': True,
                'message': 'No valid interventions',
                'missing_elements': missing,
                'modified_text': original_text,
                'interventions_applied': 0
            }
        
        if use_ai == "claude" or (use_ai == "auto" and self.claude):
            output = self._call_claude(prompt)
        elif use_ai == "gpt" or (use_ai == "auto" and self.openai_client):
            output = self._call_gpt(prompt)
        else:
            # Rule-based fallback — no AI client available
            output = self._rule_based_intervention(missing, original_text)
        
        if not output or output.startswith("Error"):
            return {'success': False, 'error': output or 'AI call failed'}
        
        modified_text = output.strip()
        
        interventions_count = sum(len(items) for items in missing.values())
        
        result = {
            'success': True,
            'missing_elements': missing,
            'interventions_applied': interventions_count,
            'modified_text': modified_text
        }
        
        if output_filepath:
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        
        return result