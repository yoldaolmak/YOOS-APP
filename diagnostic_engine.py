"""
Yoldaolmak.com Diagnostic Engine v2.0
Bridges editorial_brain audit output to intervention_engine format.
POST-ID-ONLY — accepts plain text directly, no URL or file fetching.
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional

from editorial_brain import (
    audit_content,
    check_kemal_voice,
    check_authority_markers,
    check_critique_elements,
    check_genius_loci_coverage,
    check_timelessness,
    count_words,
    extract_headings,
    validate_heading_hierarchy,
    count_internal_links
)


def _map_voice_analysis(voice: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "temporal_anchors": {
            "count": voice.get("temporal_anchors", 0),
            "pass": voice.get("temporal_anchors_pass", False),
            "required": 2
        },
        "kemal_notes": {
            "count": voice.get("kemal_note_blocks", 0),
            "pass": voice.get("kemal_notes_pass", False),
            "required": 3
        },
        "plural_violations": {
            "count": voice.get("plural_violations", 0),
            "pass": voice.get("plural_violations", 0) == 0
        },
        "first_person": {
            "per_1000": voice.get("first_person_per_1000", 0),
            "pass": voice.get("first_person_pass", False)
        },
        "forbidden_words": {
            "count": voice.get("forbidden_word_count", 0),
            "pass": voice.get("forbidden_words_pass", True)
        }
    }


def _map_authority_analysis(authority: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sourced_claims": {
            "count": authority.get("sourced_claims", 0),
            "per_1000": authority.get("sourced_per_1000", 0),
            "pass": authority.get("sourced_claims_pass", False)
        },
        "prices": {
            "total": authority.get("total_prices", 0),
            "with_source": authority.get("prices_with_source", 0),
            "coverage_pct": authority.get("price_coverage_percentage", 0),
            "pass": authority.get("price_coverage_pass", False)
        },
        "coordinates": {
            "count": authority.get("coordinates_found", 0),
            "pass": authority.get("coordinates_found", 0) >= 2
        }
    }


def _map_critique_analysis(critique: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pro_con_blocks": {
            "count": critique.get("pro_con_blocks", 0),
            "pass": critique.get("pro_con_pass", False),
            "required": 2
        },
        "tourist_traps": {
            "count": critique.get("tourist_trap_warnings", 0),
            "pass": critique.get("tourist_trap_pass", False),
            "required": 1
        },
        "reality_checks": {
            "count": critique.get("reality_checks", 0),
            "pass": critique.get("reality_checks", 0) >= 1
        },
        "negative_keywords": {
            "count": critique.get("negative_keyword_count", 0),
            "pass": critique.get("negative_keywords_pass", False)
        }
    }


def diagnose_wordpress_post(text: str, output_filepath: Optional[str] = None,
                             post_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Main diagnostic function — POST-ID-ONLY.
    Accepts plain text content directly (already fetched from WP API).
    Optionally saves report JSON to output_filepath.

    Args:
        text: Plain text content of the WordPress post.
        output_filepath: Optional path to save the JSON report.
        post_id: Optional post ID for report metadata.
    """
    if not text or not text.strip():
        report = {'success': False, 'error': 'Empty or missing text content.'}
        if output_filepath:
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        return report

    # Run full audit
    audit = audit_content(text, 'city_guide')
    dm = audit['detailed_metrics']

    # Count POIs
    poi_count = len(re.findall(r'^###\s+\d+\.', text, re.MULTILINE))

    report = {
        'success': True,
        'post_id': post_id,
        'diagnosed_at': datetime.now().isoformat(),

        'page_info': {
            'word_count': audit['summary']['word_count'],
            'content_type': 'city_guide',
            'poi_count': poi_count
        },

        'voice_analysis': _map_voice_analysis(dm['voice']),
        'authority_analysis': _map_authority_analysis(dm['authority']),
        'critique_analysis': _map_critique_analysis(dm['critique']),

        'genius_loci_analysis': dm['genius_loci'],
        'timelessness_analysis': dm['timelessness'],
        'seo_analysis': dm['seo'],

        'audit_score': {
            'total_score': audit['summary']['total_score'],
            'verdict': audit['summary']['verdict'],
            'recommendation': audit['summary']['recommendation'],
            'criterion_scores': audit['criterion_scores'],
            'all_issues': audit['all_issues']
        },

        'raw_text': text
    }

    if output_filepath:
        save_report = {k: v for k, v in report.items() if k != 'raw_text'}
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(save_report, f, ensure_ascii=False, indent=2)
        print(f"[DIAGNOSTIC] Report saved: {output_filepath}")

    return report
