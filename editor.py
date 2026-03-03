"""
editor.py — Yoldaolmak.com Editorial Orchestrator v2.0
POST-ID-ONLY architecture. All content fetched via WordPress REST API using post_id.
No URL input accepted.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from diagnostic_engine import diagnose_wordpress_post, _map_voice_analysis, _map_authority_analysis, _map_critique_analysis
from intervention_engine import InterventionEngine
from editorial_brain import audit_content


class EditorialOrchestrator:
    def __init__(self, backup_dir: str = "./backups", report_dir: str = "./reports"):
        self.intervention = InterventionEngine()
        self.backup_dir = Path(backup_dir)
        self.report_dir = Path(report_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.report_dir.mkdir(exist_ok=True)

    def fetch_post_content(self, post_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch post content from WordPress REST API by post ID.
        Returns dict with 'post_id', 'title', 'text', 'html', 'fetched_at'.
        """
        try:
            from wp import get_post, strip_html
            post = get_post(post_id)
            if not post:
                print(f"   ❌ Post {post_id} bulunamadı.")
                return None

            raw_title = post.get("title", {})
            title = raw_title.get("rendered", "") if isinstance(raw_title, dict) else str(raw_title)

            raw_content = post.get("content", {})
            html = raw_content.get("rendered", "") if isinstance(raw_content, dict) else str(raw_content)
            text = strip_html(html)

            return {
                'post_id': post_id,
                'title': title,
                'html': html,
                'text': text,
                'fetched_at': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"   ❌ WP API fetch hatası: {e}")
            return None

    def create_backup(self, content: Dict[str, Any], label: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        post_id = content.get('post_id', 'unknown')
        filename = f"backup_post{post_id}_{label}_{timestamp}.json"
        filepath = self.backup_dir / filename

        save_content = {k: v for k, v in content.items() if k != 'html'}
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_content, f, ensure_ascii=False, indent=2)

        return str(filepath)

    def run_diagnostic(self, text: str, post_id: int) -> Tuple[Optional[Dict[str, Any]], int]:
        """Run diagnostic engine on already-fetched text content."""
        diagnostic_file = self.report_dir / f"diagnostic_post{post_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        diagnostic_report = diagnose_wordpress_post(
            text=text,
            output_filepath=str(diagnostic_file),
            post_id=post_id
        )

        if not diagnostic_report.get('success', True):
            return None, 0

        score = diagnostic_report.get('audit_score', {}).get('total_score', 0)
        return diagnostic_report, score

    def run_intervention(self, diagnostic_file: str, text: str, pass_num: int) -> Tuple[str, int]:
        intervention_file = self.report_dir / f"intervention_pass{pass_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        result = self.intervention.run_intervention_pipeline(
            audit_filepath=diagnostic_file,
            original_text=text,
            output_filepath=str(intervention_file),
            use_ai="auto"
        )

        if not result['success']:
            return text, 0

        return result['modified_text'], result.get('interventions_applied', 0)

    def reaudit_content(self, text: str) -> int:
        audit_result = audit_content(text, "city_guide")
        return audit_result['summary']['total_score']

    def _text_to_html(self, text: str) -> str:
        """Markdown-benzeri metni WordPress HTML'e çevirir."""
        lines = text.split('\n')
        html_lines = []
        in_ul = False
        for line in lines:
            s = line.strip()
            if not s:
                if in_ul:
                    html_lines.append('</ul>')
                    in_ul = False
                continue
            if s.startswith('# '):
                if in_ul: html_lines.append('</ul>'); in_ul = False
                html_lines.append(f'<h1>{s[2:]}</h1>')
            elif s.startswith('## '):
                if in_ul: html_lines.append('</ul>'); in_ul = False
                html_lines.append(f'<h2>{s[3:]}</h2>')
            elif s.startswith('### '):
                if in_ul: html_lines.append('</ul>'); in_ul = False
                html_lines.append(f'<h3>{s[4:]}</h3>')
            elif s.startswith('- ') or s.startswith('* '):
                if not in_ul:
                    html_lines.append('<ul>')
                    in_ul = True
                html_lines.append(f'<li>{s[2:]}</li>')
            else:
                if in_ul: html_lines.append('</ul>'); in_ul = False
                html_lines.append(f'<p>{s}</p>')
        if in_ul:
            html_lines.append('</ul>')
        return '\n'.join(html_lines)

    def _update_wp_post(self, post_id: int, title: str, content_text: str) -> Optional[int]:
        """Düzeltilmiş içeriği mevcut WP postuna draft olarak kaydet."""
        try:
            from wp import update_post
            html_content = self._text_to_html(content_text)
            success = update_post(post_id=post_id, title=title, content=html_content, status="draft")
            return post_id if success else None
        except Exception as e:
            print(f"   WP update başarısız: {e}")
            return None

    def run_editorial_pipeline(self, post_id: int, max_passes: int = 2) -> Dict[str, Any]:
        """
        Full editorial pipeline — POST-ID-ONLY.
        Fetches content via WP API, runs diagnostic + intervention, saves back as draft.
        """
        print(f"\n{'='*70}")
        print(f"EDITORIAL PIPELINE START")
        print(f"{'='*70}\n")
        print(f"Post ID: {post_id}")
        print(f"Max Passes: {max_passes}\n")

        print(f"[STEP 1] İçerik çekiliyor (Post ID: {post_id})...")
        content = self.fetch_post_content(post_id)
        if not content:
            return {'success': False, 'error': f'Post {post_id} çekilemedi.'}
        print(f"✅ Çekildi: {len(content['text'])} karakter\n")

        original_backup = self.create_backup(content, "original")
        print(f"[BACKUP] Orijinal: {original_backup}\n")

        print(f"[STEP 2] Diagnostic çalışıyor...")
        diagnostic_report, original_score = self.run_diagnostic(content['text'], post_id)
        if not diagnostic_report:
            return {'success': False, 'error': 'Diagnostic başarısız.'}
        print(f"✅ Skor: {original_score}/100\n")

        if original_score >= 80:
            print(f"✅ Skor >= 80, müdahale gerekmiyor\n")
            original_title = content.get('title', 'Rehber')
            updated_id = self._update_wp_post(post_id, original_title, content['text'])

            print(f"{'='*70}")
            print(f"PIPELINE TAMAMLANDI (MÜDAHALESİZ)")
            print(f"{'='*70}\n")
            print(f"Final Skor: {original_score}/100")
            wp_base = os.environ.get('WP_URL', 'https://yoldaolmak.com')
            if updated_id:
                print(f"WP Post ID: {updated_id}")
                print(f"Preview: {wp_base}/?p={updated_id}&preview=true\n")
            else:
                print(f"WP güncellemesi başarısız.\n")

            return {
                'success': True,
                'original_score': original_score,
                'final_score': original_score,
                'improvement': 0,
                'total_interventions': 0,
                'post_id': updated_id,
            }

        diagnostic_file = str(list(self.report_dir.glob(f"diagnostic_post{post_id}_*.json"))[-1])

        print(f"[STEP 3] Müdahale — Geçiş 1...")
        modified_text, interventions_pass1 = self.run_intervention(diagnostic_file, content['text'], 1)
        print(f"✅ Müdahale sayısı: {interventions_pass1}\n")

        content['text'] = modified_text
        content['modified_at'] = datetime.now().isoformat()
        self.create_backup(content, "pass1")

        print(f"[STEP 4] Geçiş 1 sonrası yeniden audit...")
        score_after_pass1 = self.reaudit_content(modified_text)
        print(f"✅ Geçiş 1 sonrası skor: {score_after_pass1}/100\n")

        total_interventions = interventions_pass1

        if score_after_pass1 < 80 and max_passes >= 2:
            print(f"[STEP 5] Skor < 80, Geçiş 2 başlıyor...")

            audit_pass2_file = self.report_dir / f"audit_pass2_post{post_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            audit_result = audit_content(modified_text, "city_guide")
            dm = audit_result['detailed_metrics']
            with open(audit_pass2_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'page_info': {'word_count': len(modified_text.split())},
                    'voice_analysis': _map_voice_analysis(dm['voice']),
                    'authority_analysis': _map_authority_analysis(dm['authority']),
                    'critique_analysis': _map_critique_analysis(dm['critique']),
                    'genius_loci_analysis': dm['genius_loci'],
                    'timelessness_analysis': dm['timelessness'],
                    'seo_analysis': dm['seo'],
                    'audit_score': audit_result['summary']
                }, f, ensure_ascii=False, indent=2)

            modified_text, interventions_pass2 = self.run_intervention(str(audit_pass2_file), modified_text, 2)
            print(f"✅ Geçiş 2 müdahale sayısı: {interventions_pass2}\n")

            total_interventions += interventions_pass2

            content['text'] = modified_text
            content['modified_at'] = datetime.now().isoformat()
            self.create_backup(content, "pass2_final")

            print(f"[STEP 6] Final audit...")
            final_score = self.reaudit_content(modified_text)
            print(f"✅ Final skor: {final_score}/100\n")
        else:
            final_score = score_after_pass1
            print(f"[STEP 5] Skor >= 80 veya maksimum geçiş doldu\n")

        print(f"[STEP 7] WP Post güncelleniyor (draft)...")
        original_title = content.get('title', 'Rehber')
        updated_id = self._update_wp_post(post_id, original_title, content['text'])
        wp_base = os.environ.get('WP_URL', 'https://yoldaolmak.com')
        if updated_id:
            print(f"WP Post ID: {updated_id}")
            print(f"Preview: {wp_base}/?p={updated_id}&preview=true\n")
        else:
            print(f"WP güncellemesi başarısız.\n")

        print(f"{'='*70}")
        print(f"PIPELINE TAMAMLANDI")
        print(f"{'='*70}\n")
        print(f"Başlangıç Skoru : {original_score}/100")
        print(f"Final Skoru     : {final_score}/100")
        print(f"İyileşme        : {final_score - original_score:+d}")
        print(f"Toplam Müdahale : {total_interventions}\n")

        return {
            'success': True,
            'original_score': original_score,
            'final_score': final_score,
            'improvement': final_score - original_score,
            'total_interventions': total_interventions,
            'post_id': updated_id,
        }
