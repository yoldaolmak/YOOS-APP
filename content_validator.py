"""
content_validator.py v2.0 — Audit Engine "Tam Yargıç"

3 Eksenli Skor (0-100):
  Authority  (35p): Veri yoğunluğu, iç link, kelime sayısı, kaynak atıf
  Narrative  (35p): 1.tekil şahıs, cümle kısalığı, duyusal detay, forbidden-word yokluğu
  Technical  (30p): H sırası, Gutenberg format, schema, H3 varlığı

Karar Sistemi:
  < 60 → full_rewrite
  60-82 → polish
  > 82 → skip

EEAT Ölçüm: Experience / Expertise / Authority / Trust
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Failure:
    code:      str
    severity:  str       # "critical" | "major" | "minor"
    detail:    str
    fix_hint:  str
    axis:      str = ""  # "authority" | "narrative" | "technical"
    gpt_fix:   bool = True


@dataclass
class EEATScore:
    experience: int
    expertise:  int
    authority:  int
    trust:      int

    @property
    def total(self) -> int:
        return self.experience + self.expertise + self.authority + self.trust

    def summary(self) -> str:
        return (f"E:{self.experience} Ex:{self.expertise} "
                f"A:{self.authority} T:{self.trust} = {self.total}/100")


@dataclass
class ValidationResult:
    score:       int
    passed:      bool
    action:      str   # "skip" | "polish" | "full_rewrite"
    failures:    List[Failure] = field(default_factory=list)
    axis_scores: dict = field(default_factory=dict)
    eeat:        Optional[EEATScore] = None
    word_count:  int = 0
    link_count:  int = 0

    def summary(self) -> str:
        counts = {"critical": 0, "major": 0, "minor": 0}
        for f in self.failures:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        a = self.axis_scores
        return (
            f"Skor:{self.score}/100 [{self.action.upper()}] "
            f"Auth:{a.get('authority',0)} Narr:{a.get('narrative',0)} Tech:{a.get('technical',0)} | "
            f"🔴{counts['critical']} 🟡{counts['major']} ⚪{counts['minor']}"
        )

    def gpt_fixable_failures(self):
        return [f for f in self.failures if f.gpt_fix]

    def needs_rewrite(self) -> bool:
        return self.action == "full_rewrite"

    def needs_polish(self) -> bool:
        return self.action == "polish"


# ── Sabitler ──────────────────────────────────────────────────────────────────

_FORBIDDEN = [
    "muhteşem", "harika", "mükemmel", "inanılmaz",
    "nefes kesici", "eşsiz", "büyüleyici", "görkemli",
    "unutulmaz", "rüya gibi", "cennet", "masalsı",
    "hayatınızın tatili", "bir açık hava müzesi",
    "her köşe başında tarih", "zaman durmuş gibi",
]

_FIRST_PERSON = [
    "gördüm", "gittim", "fark ettim", "hissettim", "tercih ederim",
    "öneririm", "söylemeliyim", "denedim", "yaşadım", "öğrendim",
    "ben ", "benim ", "bence", "bana göre",
]

_SENSORY = [
    "koku", "ışık", "ses", "doku", "renk", "sıcaklık",
    "soğuk", "gürültü", "sessiz", "parlak", "loş",
]

_DATA_RE = [
    r'\d+\s*€', r'\d+\s*km', r'\d+\s*(saat|dk|dakika)',
    r'\b\d{4}\b', r'%\d+', r'\d+[-–]\d+\s*€',
]

_WHERE_H2_ORDER = ["Nerede", "Nasıl Bir Yer", "Nasıl Gidilir", "Gezi Planı"]

_HUB_CITIES = ["paris","istanbul","roma","londra","tokyo","barselona",
               "amsterdam","berlin","viyana","prag","new york","bali"]

_FORBIDDEN_REPLACEMENTS = {
    r'\bmuhteşem\b': 'etkileyici', r'\bharika\b': 'güzel',
    r'\bmükemmel\b': 'iyi',        r'\binanılmaz\b': 'dikkat çekici',
    r'\bnefes kesici\b': 'çarpıcı', r'\beşsiz\b': 'özgün',
    r'\bbüyüleyici\b': 'ilgi çekici', r'\bgörkemli\b': 'etkileyici',
    r'\bunutulmaz\b': 'akılda kalan', r'\brüya gibi\b': 'sakin',
    r'\bcennet\b': 'ideal', r'\bmasalsı\b': 'kendine özgü',
    r'zaman durmuş gibi': 'sakin bir atmosfer var',
    r'her köşe başında tarih': 'tarihin izleri her yerde',
    r'\bziyaret edilebilir\b': 'ziyaret edebilirsiniz',
    r'\btercih edilmektedir\b': 'tercih edilir',
    r'\bbilinmektedir\b': 'biliniyor',
    r'\bgörülmektedir\b': 'görülüyor',
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _strip(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html)

def _wc(html: str) -> int:
    return len(_strip(html).split())

def _avg_sent_len(html: str) -> float:
    t = _strip(html)
    w = max(1, len(t.split()))
    s = max(1, len(re.findall(r'[.!?]+', t)))
    return w / s

def _internal_links(html: str) -> int:
    return len(re.findall(r'href="https?://yoldaolmak\.com', html, re.I))

def _data_hits(html: str) -> int:
    t = _strip(html)
    return sum(len(re.findall(p, t)) for p in _DATA_RE)

def _fp_density(html: str) -> float:
    t = _strip(html)
    wc = max(1, len(t.split()))
    cnt = sum(t.lower().count(fp) for fp in _FIRST_PERSON)
    return cnt / (wc / 100)

def _sensory_count(html: str) -> int:
    t = _strip(html).lower()
    return sum(1 for s in _SENSORY if s in t)

def _forbidden_count(html: str) -> int:
    t = _strip(html).lower()
    return sum(1 for w in _FORBIDDEN if w.lower() in t)

def _h2_list(html: str) -> list:
    return [re.sub(r'<[^>]+>', '', m).strip()
            for m in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL|re.I)]

def _h3_list(html: str) -> list:
    return [re.sub(r'<[^>]+>', '', m).strip()
            for m in re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL|re.I)]

def _word_floor(city: str, mode: str) -> int:
    if mode == "guide": return 3500
    return 2500 if any(h in city.lower() for h in _HUB_CITIES) else 2000


# ── Authority (0-35) ──────────────────────────────────────────────────────────

def _authority(html: str, city: str, mode: str):
    failures, score = [], 0
    wc = _wc(html)
    floor = _word_floor(city, mode)

    # Kelime derinliği 0-15
    if   wc >= floor:        score += 15
    elif wc >= floor * 0.85: score += 10; failures.append(Failure("LOW_WORD_COUNT","minor",f"Kelime: {wc} (hedef: {floor})","Zayıf bölümleri genişlet","authority"))
    elif wc >= floor * 0.65: score += 5;  failures.append(Failure("LOW_WORD_COUNT","major",f"Kelime düşük: {wc} (hedef: {floor})","Nerede + Nasıl Bir Yer + Plan bölümlerini genişlet","authority"))
    else: failures.append(Failure("VERY_LOW_WORD_COUNT","critical",f"Kelime kritik: {wc}","Full rewrite","authority",False))

    # Veri yoğunluğu 0-10
    dh = _data_hits(html)
    if   dh >= 15: score += 10
    elif dh >= 8:  score += 7
    elif dh >= 4:  score += 4; failures.append(Failure("LOW_DATA_DENSITY","minor",f"Somut veri: {dh}/100 (hedef:15+)","€/km/saat/tarih/% ekle","authority"))
    else:          score += 1; failures.append(Failure("NO_DATA_DENSITY","major",f"Somut veri yok: {dh} hit","Kanıtsız iddia — her bölüme veri ekle","authority"))

    # İç link 0-10
    lc = _internal_links(html)
    if   lc >= 3: score += 10
    elif lc == 2: score += 7
    elif lc == 1: score += 4; failures.append(Failure("FEW_INTERNAL_LINKS","minor",f"İç link: {lc} (min:2)","Gezi rehberi + bilet linkleri ekle","authority"))
    else:          failures.append(Failure("NO_INTERNAL_LINKS","major","İç link yok","yoldaolmak.com linkleri ekle","authority"))

    return min(35, score), failures


# ── Narrative (0-35) ──────────────────────────────────────────────────────────

def _narrative(html: str):
    failures, score = [], 0

    # 1.tekil şahıs 0-12
    fpd = _fp_density(html)
    if   fpd >= 3.0: score += 12
    elif fpd >= 1.5: score += 8
    elif fpd >= 0.5: score += 4; failures.append(Failure("LOW_FIRST_PERSON","minor",f"1.tekil: {fpd:.1f}/100kw (hedef:3+)","'gördüm','fark ettim','öneriyorum' ekle","narrative"))
    else:            failures.append(Failure("NO_FIRST_PERSON","major",f"1.tekil yok: {fpd:.1f}/100kw","Kemal Voice eksik — rewrite gerekebilir","narrative"))

    # Cümle kısalığı 0-8
    asl = _avg_sent_len(html)
    if   asl <= 14: score += 8
    elif asl <= 18: score += 6
    elif asl <= 22: score += 3; failures.append(Failure("LONG_SENTENCES","minor",f"Avg cümle: {asl:.1f}kw (hedef:<18)","Uzun cümleleri böl","narrative"))
    else:           score += 0; failures.append(Failure("VERY_LONG_SENTENCES","major",f"Cümleler çok uzun: {asl:.1f}kw","Böl, noktalama ekle","narrative"))

    # Duyusal detay 0-8
    sc = _sensory_count(html)
    if   sc >= 5: score += 8
    elif sc >= 3: score += 5
    elif sc >= 1: score += 2; failures.append(Failure("FEW_SENSORY","minor",f"Duyusal detay: {sc} (hedef:5+)","Koku/ışık/ses/doku/renk ekle","narrative"))
    else:         failures.append(Failure("NO_SENSORY","minor","Duyusal detay yok","Genius Loci paragrafına koku+ışık+ses ekle","narrative"))

    # Forbidden words 0-7
    fc = _forbidden_count(html)
    if   fc == 0: score += 7
    elif fc <= 2: score += 4; failures.append(Failure("FORBIDDEN_WORDS","minor",f"Yasak kelime: {fc}","Mechanical clean","narrative",False))
    else:         failures.append(Failure("MANY_FORBIDDEN_WORDS","major",f"Yasak kelime çok: {fc}","Mechanical + GPT polish","narrative"))

    return min(35, score), failures


# ── Technical (0-30) ──────────────────────────────────────────────────────────

def _technical(html: str, mode: str):
    failures, score = [], 0
    h2s = _h2_list(html)
    h3s = _h3_list(html)

    if mode == "where":
        # H2 sıra + varlık 0-12
        h2sc = 12
        for req in _WHERE_H2_ORDER:
            if not any(req.lower() in h.lower() for h in h2s):
                h2sc -= 4
                failures.append(Failure(f"MISSING_H2_{req.upper().replace(' ','_')}",
                    "critical",f'Eksik H2: "{req}"',f'"{req}" H2 ekle',"technical"))
        # Sıra
        fi = []
        for req in _WHERE_H2_ORDER:
            for i, h in enumerate(h2s):
                if req.lower() in h.lower(): fi.append((req, i)); break
        for a in range(len(fi)-1):
            if fi[a][1] > fi[a+1][1]:
                h2sc -= 3
                failures.append(Failure("H2_ORDER_WRONG","major",
                    f'Sıra hatalı: "{fi[a][0]}"→"{fi[a+1][0]}" (beklenen: Nerede→Nasıl Bir Yer→Gidilir→Plan)',
                    "Bölümleri doğru sıraya diz","technical"))
        score += max(0, h2sc)

        # H3 tamamlığı 0-8
        h3sc = 8
        if not any("ucuz" in h.lower() or "bilet" in h.lower() for h in h3s):
            h3sc -= 4; failures.append(Failure("MISSING_H3_BILET","major","Ucuz Uçak Bileti H3 yok","Nasıl Gidilir H3+liste ekle","technical"))
        if not any(any(x in h.lower() for x in ["günlük","gün","tur","hızlı","ideal"]) for h in h3s):
            h3sc -= 4; failures.append(Failure("MISSING_H3_PLAN","major","Gezi Planı H3'leri yok","Gezi Planı gün bazlı H3'ler ekle","technical"))
        score += max(0, h3sc)

    # Gutenberg format 0-5
    bare = len(re.findall(r'(?<!-->)\n<p[^>]*>', html))
    mdbold = len(re.findall(r'\*\*[^*]+\*\*', html))
    if bare == 0 and mdbold == 0:
        score += 5
    elif bare <= 3 and mdbold == 0:
        score += 3
    else:
        score += 1; failures.append(Failure("FORMAT_ISSUES","minor",
            f"Format: {bare} bare <p>, {mdbold} ** bold","auto_fix() çalıştır","technical",False))

    # Schema 0-5
    if any(x in html for x in ['application/ld+json','yoa-faq-schema','FAQPage','wp:html']):
        score += 5
    else:
        failures.append(Failure("MISSING_SCHEMA","minor","Schema yok","schema_engine.generate_schema_block()","technical",False))

    return min(30, score), failures


# ── EEAT ──────────────────────────────────────────────────────────────────────

def _eeat(html: str) -> EEATScore:
    t = _strip(html)
    wc = max(1, len(t.split()))
    experience = min(25, int(_fp_density(html) * 5))
    expertise  = min(25, int(_data_hits(html) * 1.5))
    authority  = min(25, int((wc / 100) + _internal_links(html) * 3))
    trust_w    = ["ama","ancak","dikkat","uyarı","değil","zor","pahalı",
                  "kalabalık","eksi","dezavantaj","öneri"]
    trust      = min(25, sum(t.lower().count(w) for w in trust_w) * 2)
    return EEATScore(experience, expertise, authority, trust)


# ── ANA VALIDATE ──────────────────────────────────────────────────────────────

def validate(html: str, mode: str = "where", city: str = "") -> ValidationResult:
    auth_sc, auth_fail = _authority(html, city, mode)
    narr_sc, narr_fail = _narrative(html)
    tech_sc, tech_fail = _technical(html, mode)

    total    = auth_sc + narr_sc + tech_sc
    failures = auth_fail + narr_fail + tech_fail
    critical = any(f.severity == "critical" for f in failures)

    if total < 60 or critical:
        action = "full_rewrite"
    elif total < 82:
        action = "polish"
    else:
        action = "skip"

    passed = action == "skip" or (total >= 70 and not critical)

    return ValidationResult(
        score=total, passed=passed, action=action, failures=failures,
        axis_scores={"authority": auth_sc, "narrative": narr_sc, "technical": tech_sc},
        eeat=_eeat(html), word_count=_wc(html), link_count=_internal_links(html),
    )


# ── AUTO FIX ──────────────────────────────────────────────────────────────────

def auto_fix(html: str) -> str:
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html, flags=re.DOTALL)
    html = re.sub(r'\n{3,}', '\n\n', html)
    for pat, rep in _FORBIDDEN_REPLACEMENTS.items():
        html = re.sub(pat, rep, html, flags=re.IGNORECASE)
    return html


# ── RAPOR ─────────────────────────────────────────────────────────────────────

def print_audit_report(result: ValidationResult, city: str = "") -> None:
    action_icon = {"skip": "OK", "polish": "FIX", "full_rewrite": "REWRITE"}
    LINE = "-" * 58
    SEP  = "=" * 58
    print(f"\n{SEP}")
    print(f"AUDIT --- {city or '?'} | [{action_icon.get(result.action, result.action.upper())}] {result.action.upper()}")
    print(LINE)
    a = result.axis_scores
    print(f"  Toplam  : {result.score}/100  (Auth:{a.get('authority',0)}/35 Narr:{a.get('narrative',0)}/35 Tech:{a.get('technical',0)}/30)")
    print(f"  Kelime  : {result.word_count}  Ic Link: {result.link_count}")
    if result.eeat:
        e = result.eeat
        print(f"  EEAT    : E:{e.experience} Ex:{e.expertise} A:{e.authority} T:{e.trust} = {e.total}/100")
    if result.failures:
        print(f"  Sorunlar ({len(result.failures)}):")
        for f in result.failures:
            sev = "[KR]" if f.severity=="critical" else "[MA]" if f.severity=="major" else "[MI]"
            mech = "" if f.gpt_fix else " [mech]"
            print(f"    {sev}[{f.axis}] {f.code}{mech}: {f.detail[:65]}")
    print(SEP)
