"""Pristina neighbourhood (lagje) detection and focus tiers."""
import re
import unicodedata


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# canonical name -> alias patterns (already accent-folded)
HOODS = {
    "Prishtina e Re":  [r"prishtina e re", r"prishtine e re", r"prishtina re", r"prishtin[ae]s? se? re", r"lagjja e re", r"komuna e re"],
    "Mati 1":          [r"\bmati ?1\b", r"\bmati i\b(?! ?2)"],
    "Lakrishte":       [r"lakrisht"],
    "Ulpiana":         [r"ulpian"],
    "Dardania":        [r"dardani"],
    "Qafa":            [r"\bqafa\b", r"te qafa"],
    "Tophane":         [r"tophane"],
    "Pejton":          [r"pejton", r"peyton"],
    "Qendër":          [r"\bqender\b", r"\bqendra\b", r"qender te prishtines", r"\bcentre?\b", r"city center"],
    "Bregu i Diellit": [r"bregu i diellit", r"\bbregu\b", r"sunny hill"],
    "Arbëria":         [r"arberia", r"dragodan"],
    "Velania":         [r"velani"],
    "Kalabria":        [r"kalabri"],
    "Veternik":        [r"veternik"],
    "Matiçan":         [r"matican"],
    "Mati 2":          [r"\bmati ?2\b"],
    "Sofalia":         [r"sofali"],
    "Taslixhe":        [r"taslixhe", r"tasllixhe"],
    "Kodra e Trimave": [r"kodra e trimave"],
    "Fushë Kosovë":    [r"fushe ?kosov", r"fushkosov", r"f kosove"],
    "Hajvali":         [r"hajvali"],
    "Çagllavicë":      [r"cagllavic", r"caglavic"],
    "Bernicë":         [r"bernic"],
    "Kolovica":        [r"kolovic"],
    "Aktash":          [r"aktash"],
    "Dodona":          [r"dodona"],
    "Spitali":         [r"lagja e spitalit", r"lagjja e spitalit", r"te spitali"],
    "Muhaxherëve":     [r"muhaxher"],
    "Vreshtat":        [r"vreshtat"],
    "Sunny Hill":      [r"sunny hill"],
}

CORE = {"Prishtina e Re"}
NEARBY = {"Mati 1", "Lakrishte", "Ulpiana", "Dardania", "Qafa", "Tophane",
          "Pejton", "Qendër", "Bregu i Diellit", "Arbëria"}

_COMPILED = {name: [re.compile(p) for p in pats] for name, pats in HOODS.items()}


def _best_in(blob):
    """Earliest match wins; ties broken by longer (more specific) alias."""
    best = None  # (start_pos, -alias_len, name)
    for name, rxs in _COMPILED.items():
        for rx in rxs:
            m = rx.search(blob)
            if m:
                cand = (m.start(), -(m.end() - m.start()), name)
                if best is None or cand < best:
                    best = cand
    return best[2] if best else None


def detect(*parts):
    """Return (canonical_hood or None, tier). Earlier parts win: pass title first."""
    for part in parts:
        if not part:
            continue
        name = _best_in(_norm(part))
        if name:
            return name, tier_of(name)
    return None, "other"


def tier_of(name):
    if name in CORE:
        return "core"
    if name in NEARBY:
        return "nearby"
    return "other"
