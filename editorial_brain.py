"""
Yoldaolmak.com Editorial Brain v1.0
Centralized content constitution and validation system
"""

import re
import json
from typing import Dict, List, Any, Tuple
from datetime import datetime

EDITORIAL_BRAIN_V1 = {
    "version": "1.0.0",
    "last_updated": "2026-02-19",
    "minimum_publish_score": 80,
    
    "word_count_requirements": {
        "city_guide": {"min": 3000, "optimal": 3500, "max": 5000},
        "micro_content": {"min": 1200, "optimal": 1500, "max": 2000},
        "country_hub": {"min": 6000, "optimal": 8000, "max": 10000}
    },
    
    "mandatory_sections": {
        "city_guide": [
            {"id": "intro", "min_paragraphs": 2, "max_paragraphs": 3, "word_range": [150, 250]},
            {"id": "what_kind_of_place", "min_paragraphs": 3, "max_paragraphs": 5, "word_range": [400, 600]},
            {"id": "where_is_it", "min_paragraphs": 2, "max_paragraphs": 3, "word_range": [200, 350]},
            {"id": "how_to_get_there", "min_paragraphs": 3, "max_paragraphs": 5, "word_range": [400, 600]},
            {"id": "places_to_visit", "min_items": 10, "max_items": 20, "per_item_min_words": 150},
            {"id": "travel_plan", "min_scenarios": 2},
            {"id": "practical_info", "min_subsections": 4},
            {"id": "faq", "min_questions": 8, "max_questions": 15}
        ]
    },
    
    "heading_rules": {
        "h1_count": 1,
        "hierarchy_pattern": "^h1(>h2(>h3(>h4)?)?)?$",
        "max_depth": 4
    },
    
    "internal_linking": {
        "min_links_per_1000_words": 8,
        "max_links_per_1000_words": 12,
        "anchor_distribution": {"exact_match": 0.40, "partial_match": 0.30, "branded": 0.20, "generic": 0.10}
    },
    
    "kemal_voice_markers": {
        "first_person_singular": {"min_per_1000_words": 3, "allowed": ["ben", "benim", "bana", "bence"]},
        "forbidden_plural": ["biz", "bizim", "bize"],
        "temporal_anchors": {"min_count": 2, "pattern": r"\d{4}'?[td]e (ilk kez )?(git|ziyaret|kal)"},
        "personal_note_blocks": {"min_count": 3, "max_count": 6, "marker": "**Kemal'in Notu:**"},
        "comparative_analysis": {"min_count": 2},
        "expectation_setting": {"min_count": 3}
    },
    
    "forbidden_words": [
        "muhteşem", "harika", "mükemmel", "inanılmaz", "eşsiz", "benzersiz", 
        "olağanüstü", "nefes kesici", "büyüleyici", "etkileyici", "göz alıcı"
    ],
    
    "mandatory_critique": {
        "min_critical_sections": 3,
        "pro_con_pattern": r"✅.*?❌.*?💡",
        "tourist_trap_pattern": r"⚠️.*?Turist Tuzağı",
        "reality_check_pattern": r"Instagram'?da.*?[Gg]erçekte"
    },
    
    "genius_loci_dimensions": [
        {"id": "time_perception", "keywords": ["katman", "dönem", "yüzyıl", "tarihsel"]},
        {"id": "light", "keywords": ["güneş", "ışık", "gölge", "saat", "sabah", "akşam"]},
        {"id": "rhythm", "keywords": ["tempo", "ritim", "hız", "yavaş", "saatlik"]},
        {"id": "social_tempo", "keywords": ["mesafe", "konuşma", "etkileşim", "sosyal"]},
        {"id": "class_visibility", "keywords": ["mahalle", "semt", "sınıf", "fiyat", "zengin", "fakir"]},
        {"id": "tourist_sterilization", "keywords": ["turist", "yerel", "otantik", "steril"]}
    ],
    
    "authority_requirements": {
        "min_sourced_claims_per_1000_words": 5,
        "source_pattern": r"\([^)]+,\s*\d{4}(-\d{2})?(-\d{2})?\)",
        "price_pattern": r"\d+[€$₺].*?\([^)]+,\s*\d{4}",
        "coordinate_pattern": r"\d+\.\d+°\s*[KD],\s*\d+\.\d+°\s*[KD]",
        "min_price_source_coverage": 80,
        "turkey_excluded_sections": ["vize", "pasaport", "saat farkı", "saat dilimi"]
    },
    
    "seo_requirements": {
        "meta_title": {"min": 50, "max": 60, "pattern": r".*Gezi Rehberi.*"},
        "meta_description": {"min": 150, "max": 160},
        "required_schemas": ["TravelGuide", "FAQPage"],
        "min_images": 10,
        "max_images": 25,
        "primary_keyword_min": 3,
        "primary_keyword_max": 8
    },
    
    "timelessness_requirements": {
        "min_evergreen_percentage": 80,
        "evergreen_keywords": ["tarih", "mimari", "kültür", "coğrafya", "dönem", "yüzyıl"],
        "volatile_keywords": ["fiyat", "saat", "açılış", "yeni", "açıldı", "kapandı"],
        "forbidden_temporal_phrases": ["şu anda", "geçen yıl", "bu yıl", "yakın zamanda"],
        "dynamic_block_pattern": r"\[(price|hours|exchange)"
    }
}

SCORING_MATRIX = {
    "criteria": [
        {"id": "narrative_depth", "weight": 15, "max_score": 10},
        {"id": "authority_level", "weight": 20, "max_score": 10},
        {"id": "personal_voice_balance", "weight": 15, "max_score": 10},
        {"id": "information_reliability", "weight": 20, "max_score": 10},
        {"id": "seo_structure_quality", "weight": 10, "max_score": 10},
        {"id": "expectation_management", "weight": 10, "max_score": 10},
        {"id": "critique_courage", "weight": 5, "max_score": 10},
        {"id": "timelessness_potential", "weight": 5, "max_score": 10}
    ],
    "passing_score": 80,
    "excellence_score": 90
}


def count_words(text: str) -> int:
    return len(re.findall(r'\b\w+\b', text))


def extract_headings(text: str) -> List[Tuple[int, str]]:
    headings = []
    for match in re.finditer(r'^(#{1,6})\s+(.+)$', text, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        headings.append((level, title))
    return headings


def validate_heading_hierarchy(headings: List[Tuple[int, str]]) -> Dict[str, Any]:
    h1_count = sum(1 for level, _ in headings if level == 1)
    violations = []
    
    if h1_count != 1:
        violations.append(f"H1 count must be 1, found {h1_count}")
    
    prev_level = 0
    for level, title in headings:
        if level > prev_level + 1:
            violations.append(f"Heading hierarchy jump: H{prev_level} to H{level} ('{title}')")
        prev_level = level
    
    return {
        "valid": len(violations) == 0,
        "h1_count": h1_count,
        "total_headings": len(headings),
        "violations": violations
    }


def count_internal_links(text: str) -> int:
    return len(re.findall(r'\[([^\]]+)\]\((?!http)', text))


def check_kemal_voice(text: str) -> Dict[str, Any]:
    word_count = count_words(text)
    
    first_person_count = sum(text.lower().count(word) for word in EDITORIAL_BRAIN_V1["kemal_voice_markers"]["first_person_singular"]["allowed"])
    first_person_per_1000 = (first_person_count / word_count * 1000) if word_count > 0 else 0
    
    plural_violations = sum(text.lower().count(word) for word in EDITORIAL_BRAIN_V1["kemal_voice_markers"]["forbidden_plural"])
    
    temporal_anchors = len(re.findall(EDITORIAL_BRAIN_V1["kemal_voice_markers"]["temporal_anchors"]["pattern"], text))
    
    kemal_notes = text.count(EDITORIAL_BRAIN_V1["kemal_voice_markers"]["personal_note_blocks"]["marker"])
    
    forbidden_word_count = sum(text.lower().count(word) for word in EDITORIAL_BRAIN_V1["forbidden_words"])
    
    return {
        "first_person_count": first_person_count,
        "first_person_per_1000": first_person_per_1000,
        "first_person_pass": first_person_per_1000 >= EDITORIAL_BRAIN_V1["kemal_voice_markers"]["first_person_singular"]["min_per_1000_words"],
        "plural_violations": plural_violations,
        "temporal_anchors": temporal_anchors,
        "temporal_anchors_pass": temporal_anchors >= EDITORIAL_BRAIN_V1["kemal_voice_markers"]["temporal_anchors"]["min_count"],
        "kemal_note_blocks": kemal_notes,
        "kemal_notes_pass": EDITORIAL_BRAIN_V1["kemal_voice_markers"]["personal_note_blocks"]["min_count"] <= kemal_notes <= EDITORIAL_BRAIN_V1["kemal_voice_markers"]["personal_note_blocks"]["max_count"],
        "forbidden_word_count": forbidden_word_count,
        "forbidden_words_pass": forbidden_word_count <= 2
    }


def check_authority_markers(text: str) -> Dict[str, Any]:
    word_count = count_words(text)
    
    sourced_claims = len(re.findall(EDITORIAL_BRAIN_V1["authority_requirements"]["source_pattern"], text))
    sourced_per_1000 = (sourced_claims / word_count * 1000) if word_count > 0 else 0
    
    prices_with_source = len(re.findall(EDITORIAL_BRAIN_V1["authority_requirements"]["price_pattern"], text))
    total_prices = len(re.findall(r'\d+[€$₺]', text))
    price_coverage = (prices_with_source / total_prices * 100) if total_prices > 0 else 0
    
    coordinates = len(re.findall(EDITORIAL_BRAIN_V1["authority_requirements"]["coordinate_pattern"], text))
    
    return {
        "sourced_claims": sourced_claims,
        "sourced_per_1000": sourced_per_1000,
        "sourced_claims_pass": sourced_per_1000 >= EDITORIAL_BRAIN_V1["authority_requirements"]["min_sourced_claims_per_1000_words"],
        "prices_with_source": prices_with_source,
        "total_prices": total_prices,
        "price_coverage_percentage": price_coverage,
        "price_coverage_pass": price_coverage >= EDITORIAL_BRAIN_V1["authority_requirements"]["min_price_source_coverage"],
        "coordinates_found": coordinates
    }


def check_critique_elements(text: str) -> Dict[str, Any]:
    pro_con_blocks = len(re.findall(EDITORIAL_BRAIN_V1["mandatory_critique"]["pro_con_pattern"], text, re.DOTALL))
    
    tourist_traps = len(re.findall(EDITORIAL_BRAIN_V1["mandatory_critique"]["tourist_trap_pattern"], text))
    
    reality_checks = len(re.findall(EDITORIAL_BRAIN_V1["mandatory_critique"]["reality_check_pattern"], text))
    
    negative_keywords = ["pahalı", "kalabalık", "overrated", "turistik tuzak", "değmez"]
    negative_count = sum(text.lower().count(keyword) for keyword in negative_keywords)
    
    return {
        "pro_con_blocks": pro_con_blocks,
        "pro_con_pass": pro_con_blocks >= 2,
        "tourist_trap_warnings": tourist_traps,
        "tourist_trap_pass": tourist_traps >= 1,
        "reality_checks": reality_checks,
        "negative_keyword_count": negative_count,
        "negative_keywords_pass": negative_count >= 3
    }


def check_genius_loci_coverage(text: str) -> Dict[str, Any]:
    dimensions_found = []
    
    for dimension in EDITORIAL_BRAIN_V1["genius_loci_dimensions"]:
        keyword_hits = sum(text.lower().count(keyword) for keyword in dimension["keywords"])
        if keyword_hits >= 2:
            dimensions_found.append(dimension["id"])
    
    return {
        "dimensions_detected": dimensions_found,
        "dimension_count": len(dimensions_found),
        "dimension_pass": len(dimensions_found) >= 4,
        "missing_dimensions": [d["id"] for d in EDITORIAL_BRAIN_V1["genius_loci_dimensions"] if d["id"] not in dimensions_found]
    }


def check_timelessness(text: str) -> Dict[str, Any]:
    word_count = count_words(text)
    
    evergreen_count = sum(text.lower().count(keyword) for keyword in EDITORIAL_BRAIN_V1["timelessness_requirements"]["evergreen_keywords"])
    volatile_count = sum(text.lower().count(keyword) for keyword in EDITORIAL_BRAIN_V1["timelessness_requirements"]["volatile_keywords"])
    
    evergreen_percentage = (evergreen_count / (evergreen_count + volatile_count) * 100) if (evergreen_count + volatile_count) > 0 else 0
    
    dynamic_blocks = len(re.findall(EDITORIAL_BRAIN_V1["timelessness_requirements"]["dynamic_block_pattern"], text))
    
    forbidden_temporal = sum(text.lower().count(phrase) for phrase in EDITORIAL_BRAIN_V1["timelessness_requirements"]["forbidden_temporal_phrases"])
    
    has_update_date = bool(re.search(r"Son güncelleme:.*?\d{4}-\d{2}-\d{2}", text))
    
    return {
        "evergreen_keyword_count": evergreen_count,
        "volatile_keyword_count": volatile_count,
        "evergreen_percentage": evergreen_percentage,
        "evergreen_pass": evergreen_percentage >= EDITORIAL_BRAIN_V1["timelessness_requirements"]["min_evergreen_percentage"],
        "dynamic_blocks_found": dynamic_blocks,
        "dynamic_blocks_pass": dynamic_blocks >= 2,
        "forbidden_temporal_count": forbidden_temporal,
        "forbidden_temporal_pass": forbidden_temporal == 0,
        "has_update_date": has_update_date
    }


def calculate_criterion_score(metrics: Dict[str, Any], criterion_id: str) -> Tuple[int, List[str]]:
    issues = []
    
    if criterion_id == "narrative_depth":
        base_score = 5
        if metrics.get("genius_loci", {}).get("dimension_count", 0) >= 6:
            base_score += 4
        elif metrics.get("genius_loci", {}).get("dimension_count", 0) >= 4:
            base_score += 2
        
        if not metrics.get("genius_loci", {}).get("dimension_pass"):
            issues.append(f"Genius Loci boyutları eksik: {metrics.get('genius_loci', {}).get('dimension_count', 0)}/6")
        
        return base_score, issues
    
    elif criterion_id == "authority_level":
        base_score = 5
        authority = metrics.get("authority", {})
        
        if authority.get("sourced_claims_pass"):
            base_score += 2
        else:
            issues.append(f"Kaynaklı iddia yetersiz: {authority.get('sourced_per_1000', 0):.1f}/1000 kelime")
        
        if authority.get("price_coverage_pass"):
            base_score += 2
        else:
            issues.append(f"Fiyat kaynak kapsama düşük: %{authority.get('price_coverage_percentage', 0):.0f}")
        
        if authority.get("coordinates_found", 0) >= 10:
            base_score += 1
        else:
            issues.append(f"Koordinat az: {authority.get('coordinates_found', 0)}")
        
        return base_score, issues
    
    elif criterion_id == "personal_voice_balance":
        base_score = 5
        voice = metrics.get("voice", {})
        
        if voice.get("first_person_pass"):
            base_score += 2
        else:
            issues.append(f"Birinci tekil zamir az: {voice.get('first_person_per_1000', 0):.1f}/1000 kelime")
        
        if voice.get("temporal_anchors_pass"):
            base_score += 2
        else:
            issues.append(f"Temporal anchor eksik: {voice.get('temporal_anchors', 0)}/2")
        
        if voice.get("kemal_notes_pass"):
            base_score += 1
        else:
            issues.append(f"Kemal'in Notu bloğu eksik: {voice.get('kemal_note_blocks', 0)}/3-6")
        
        if voice.get("plural_violations", 0) > 0:
            base_score -= 1
            issues.append(f"Çoğul zamir ihlali: {voice.get('plural_violations', 0)} kez")
        
        if not voice.get("forbidden_words_pass"):
            base_score -= 1
            issues.append(f"Yasaklı kelime fazla: {voice.get('forbidden_word_count', 0)}/2")
        
        return max(1, base_score), issues
    
    elif criterion_id == "information_reliability":
        authority = metrics.get("authority", {})
        if authority.get("price_coverage_pass") and authority.get("sourced_claims_pass"):
            return 9, []
        elif authority.get("sourced_claims_pass"):
            issues.append("Fiyat kaynak kapsama düşük")
            return 7, issues
        else:
            issues.append("Kaynaklı iddia yetersiz")
            return 5, issues
    
    elif criterion_id == "seo_structure_quality":
        base_score = 5
        seo = metrics.get("seo", {})
        
        if seo.get("heading_hierarchy_valid"):
            base_score += 2
        else:
            issues.append(f"Başlık hiyerarşi hatası: {len(seo.get('heading_violations', []))} ihlal")
        
        if seo.get("internal_links_pass"):
            base_score += 2
        else:
            issues.append(f"İç link yetersiz: {seo.get('links_per_1000', 0):.1f}/1000 kelime")
        
        if seo.get("toc_present"):
            base_score += 1
        else:
            issues.append("İçindekiler tablosu yok")
        
        return base_score, issues
    
    elif criterion_id == "expectation_management":
        base_score = 5
        
        price_context = len(re.findall(r'\d+[€$₺].*?(TL|lira)', metrics.get("text", "")))
        if price_context >= 3:
            base_score += 2
        else:
            issues.append(f"Fiyat context az: {price_context}/3")
        
        crowd_keywords = sum(metrics.get("text", "").lower().count(kw) for kw in ["kalabalık", "tenha", "yoğun", "sessiz"])
        if crowd_keywords >= 5:
            base_score += 2
        else:
            issues.append(f"Kalabalık haritası zayıf: {crowd_keywords} referans")
        
        reality_checks = metrics.get("critique", {}).get("reality_checks", 0)
        if reality_checks >= 1:
            base_score += 1
        else:
            issues.append("Instagram vs Gerçek kontrastı yok")
        
        return base_score, issues
    
    elif criterion_id == "critique_courage":
        base_score = 5
        critique = metrics.get("critique", {})
        
        if critique.get("pro_con_pass"):
            base_score += 2
        else:
            issues.append(f"Pro-Con bloğu az: {critique.get('pro_con_blocks', 0)}/2")
        
        if critique.get("tourist_trap_pass"):
            base_score += 1
        else:
            issues.append("Turist tuzağı uyarısı yok")
        
        if critique.get("negative_keywords_pass"):
            base_score += 2
        else:
            issues.append(f"Negatif anahtar kelime az: {critique.get('negative_keyword_count', 0)}/3")
        
        return base_score, issues
    
    elif criterion_id == "timelessness_potential":
        base_score = 5
        timeless = metrics.get("timelessness", {})
        
        if timeless.get("evergreen_pass"):
            base_score += 3
        else:
            issues.append(f"Evergreen içerik düşük: %{timeless.get('evergreen_percentage', 0):.0f}")
        
        if timeless.get("dynamic_blocks_pass"):
            base_score += 1
        else:
            issues.append(f"Dynamic block az: {timeless.get('dynamic_blocks_found', 0)}/2")
        
        if timeless.get("forbidden_temporal_pass"):
            base_score += 1
        else:
            issues.append(f"Yasaklı zamansal ifade: {timeless.get('forbidden_temporal_count', 0)} kez")
        
        return base_score, issues
    
    return 5, ["Kriter değerlendirilemedi"]


def audit_content(text: str, content_type: str = "city_guide") -> Dict[str, Any]:
    word_count = count_words(text)
    headings = extract_headings(text)
    
    metrics = {
        "text": text,
        "word_count": word_count,
        "content_type": content_type,
        "voice": check_kemal_voice(text),
        "authority": check_authority_markers(text),
        "critique": check_critique_elements(text),
        "genius_loci": check_genius_loci_coverage(text),
        "timelessness": check_timelessness(text),
        "seo": {
            "heading_hierarchy_valid": validate_heading_hierarchy(headings)["valid"],
            "heading_violations": validate_heading_hierarchy(headings)["violations"],
            "h1_count": validate_heading_hierarchy(headings)["h1_count"],
            "internal_links": count_internal_links(text),
            "links_per_1000": (count_internal_links(text) / word_count * 1000) if word_count > 0 else 0,
            "internal_links_pass": 8 <= (count_internal_links(text) / word_count * 1000) <= 12 if word_count > 0 else False,
            "toc_present": "İçindekiler" in text or "## İçindekiler" in text
        }
    }
    
    criterion_scores = []
    all_issues = []
    total_weighted_score = 0
    total_weight = 0
    
    for criterion in SCORING_MATRIX["criteria"]:
        score, issues = calculate_criterion_score(metrics, criterion["id"])
        weighted_score = score * criterion["weight"]
        total_weighted_score += weighted_score
        total_weight += criterion["weight"]
        
        criterion_scores.append({
            "id": criterion["id"],
            "score": score,
            "max_score": criterion["max_score"],
            "weight": criterion["weight"],
            "weighted_score": weighted_score,
            "issues": issues
        })
        
        if issues:
            all_issues.extend(issues)
    
    total_score = int(total_weighted_score / total_weight * 10) if total_weight > 0 else 0
    
    if total_score >= 90:
        verdict = "excellence"
        recommendation = "Rehber mükemmel seviyede. Yayınla."
    elif total_score >= 80:
        verdict = "publish_ready"
        recommendation = "Rehber yayına hazır. İsteğe bağlı iyileştirmeler önerildi."
    elif total_score >= 70:
        verdict = "minor_revision"
        recommendation = "Rehber küçük revizyonlarla yayınlanabilir."
    elif total_score >= 60:
        verdict = "major_revision"
        recommendation = "Rehber büyük revizyon gerektiriyor."
    else:
        verdict = "mandatory_revision"
        recommendation = "Rehber kabul edilemez seviyede. Kapsamlı revizyon gerekli."
    
    return {
        "summary": {
            "total_score": total_score,
            "verdict": verdict,
            "recommendation": recommendation,
            "word_count": word_count,
            "audit_date": datetime.now().isoformat()
        },
        "criterion_scores": criterion_scores,
        "all_issues": all_issues,
        "detailed_metrics": {
            "voice": metrics["voice"],
            "authority": metrics["authority"],
            "critique": metrics["critique"],
            "genius_loci": metrics["genius_loci"],
            "timelessness": metrics["timelessness"],
            "seo": metrics["seo"]
        }
    }


def export_constitution_json(filepath: str = "editorial_constitution.json") -> None:
    constitution = {
        "editorial_brain": EDITORIAL_BRAIN_V1,
        "scoring_matrix": SCORING_MATRIX,
        "version": "1.0.0",
        "exported_at": datetime.now().isoformat()
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(constitution, f, ensure_ascii=False, indent=2)


def export_audit_report(audit_result: Dict[str, Any], filepath: str) -> None:
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(audit_result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sample_text = """
    # Prag Gezi Rehberi
    
    Prag'a ilk kez 1995'te gittiğimde şehir henüz turist akınına uğramamıştı. 2024'te tekrar ziyaret ettiğimde değişimi gördüm.
    
    ## Nasıl Bir Yer?
    
    Prag 1.3 milyon nüfuslu (2023, Czech Statistical Office) tarihi bir başkent. Şehir Vltava Nehri'nin iki yakasında kurulu.
    
    **Kemal'in Notu:** Sabah 7'de Karlův Most'a git, turistler 10'da basmaya başlıyor.
    
    ## Gezilecek Yerler
    
    ### 1. Prag Kalesi
    Koordinat: 50.0913° K, 14.4006° D
    
    9. yüzyılda kuruldu (Prague City Archives, 2023). Dünyanın en büyük antik kalesi.
    
    ✅ Artı: Tarihi değer yüksek
    ❌ Eksi: Aşırı kalabalık
    💡 Alternatif: Sabah 6'da git
    
    ⚠️ **Turist Tuzağı:** Trdelník
    Neden: Geleneksel değil, 1990'larda icat edildi. 5€ değmez.
    Alternatif: Větrník ye (2€, geleneksel)
    
    **Instagram'da:** Tenha, romantik
    **Gerçekte:** 500+ turist, selfie kuyruğu
    
    ## Pratik Bilgiler
    
    Metro bileti 40 Kč (DPP resmi site, Şubat 2024) = 70 TL
    
    ## SSS
    
    Prag pahalı mı? Ortalama otel 80€/gece (Booking.com, 100 otel, Şubat 2024)
    
    Son güncelleme: 2026-02-19
    """
    
    result = audit_content(sample_text)
    
    print(f"\n{'='*60}")
    print(f"YOLDAOLMAK EDİTORYAL AUDIT RAPORU")
    print(f"{'='*60}\n")
    print(f"Toplam Skor: {result['summary']['total_score']}/100")
    print(f"Karar: {result['summary']['verdict'].upper()}")
    print(f"Öneri: {result['summary']['recommendation']}")
    print(f"\nKelime Sayısı: {result['summary']['word_count']}")
    print(f"\n{'='*60}")
    print(f"KRİTER SKORLARI:")
    print(f"{'='*60}\n")
    
    for criterion in result['criterion_scores']:
        print(f"{criterion['id']:30} {criterion['score']:2}/{criterion['max_score']} (Ağırlık: {criterion['weight']:2}) = {criterion['weighted_score']:.1f}")
        if criterion['issues']:
            for issue in criterion['issues']:
                print(f"  ⚠ {issue}")
    
    export_audit_report(result, "/mnt/user-data/outputs/audit_report.json")
    export_constitution_json("/mnt/user-data/outputs/editorial_constitution.json")
    
    print(f"\n✅ Raporlar dışa aktarıldı:")
    print(f"  - /mnt/user-data/outputs/audit_report.json")
    print(f"  - /mnt/user-data/outputs/editorial_constitution.json")