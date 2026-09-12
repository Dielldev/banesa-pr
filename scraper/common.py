"""Shared HTTP + parsing helpers for the Pristina apartment scrapers."""
import gzip
import html as _html
import io
import random
import re
import ssl
import threading
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_throttle = threading.Semaphore(6)
_last = [0.0]
_lock = threading.Lock()


def fetch(url, tries=3, timeout=30):
    """GET a URL, returning decoded text or None. Polite: capped concurrency + jitter."""
    for attempt in range(tries):
        with _throttle:
            with _lock:
                gap = time.time() - _last[0]
                if gap < 0.12:
                    time.sleep(0.12 - gap)
                _last[0] = time.time()
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "sq,en;q=0.8",
                "Accept-Encoding": "gzip",
            })
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                    raw = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                    return raw.decode("utf-8", "replace")
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
                if attempt == tries - 1:
                    return None
                time.sleep(1.5 * (attempt + 1) + random.random())
    return None


def text(s):
    """Strip tags and unescape entities into a single clean line."""
    if not s:
        return ""
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


# --- field extraction -------------------------------------------------------

def parse_price(s):
    """'119 000 EUR' / '€119,000' / '119.000' -> 119000.0, else None."""
    if not s:
        return None
    s = _html.unescape(s)
    if re.search(r"\b(muaj|month|/mo|qera|qira)\b", s, re.I):
        return None
    m = re.search(r"(\d[\d\s.,]{2,})", s)
    if not m:
        return None
    n = m.group(1).strip()
    # thousands separators may be space, dot or comma; decimals are irrelevant here
    n = re.sub(r"[^\d]", "", n)
    if not n:
        return None
    v = float(n)
    return v if 5_000 <= v <= 5_000_000 else None


def parse_area(s):
    """Pull a plausible m2 figure out of free text."""
    if not s:
        return None
    s = _html.unescape(s)
    pats = [
        r"(\d{2,4}(?:[.,]\d+)?)\s*(?:m2|m²|m\^2|metra katror|m\s*2\b)",
        r"(?:sipërfaqja|siperfaqja|surface|madhësia|madhesia)\D{0,12}(\d{2,4})",
    ]
    for p in pats:
        for m in re.finditer(p, s, re.I):
            v = float(m.group(1).replace(",", "."))
            if 15 <= v <= 600:
                return v
    return None


WORD_NUM = {
    "nje": 1, "një": 1, "dy": 2, "tre": 3, "tri": 3, "kater": 4, "katër": 4,
    "pese": 5, "pesë": 5, "gjashte": 6, "gjashtë": 6,
}


def parse_rooms(s):
    """Bedroom count from Albanian/English phrasings, digits or words."""
    if not s:
        return None
    s = _html.unescape(s)
    m = re.search(r"(\d)\s*(?:\+\s*1|dhoma\s*(?:t[eë]\s*)?gjumi|dhoma|dhomash|bedroom)", s, re.I)
    if m:
        v = int(m.group(1))
        if 0 < v <= 8:
            return v
    words = "|".join(WORD_NUM)
    m = re.search(r"\b(%s)\s+dhoma?\s*(?:t[eë]\s*)?(?:gjumi|fjetjes)" % words, s, re.I)
    if m:
        return WORD_NUM[m.group(1).lower()]
    if re.search(r"\bgarsonier|\bstudio\b", s, re.I):
        return 0
    return None


def parse_floor(s):
    if not s:
        return None
    s = _html.unescape(s)
    m = re.search(r"(?:kati|kat|floor)\D{0,4}(\d{1,2})", s, re.I)
    if m:
        v = int(m.group(1))
        if 0 <= v <= 40:
            return v
    if re.search(r"përdhes|perdhes|ground", s, re.I):
        return 0
    return None


IS_RENT = re.compile(r"\b(me qera|me qira|jepet me|for rent|qera|qira)\b", re.I)
IS_SALE = re.compile(r"\b(në shitje|ne shitje|shitet|for sale|per shitje|për shitje)\b", re.I)


def looks_like_rental(*parts):
    blob = " ".join(p for p in parts if p)
    return bool(IS_RENT.search(blob)) and not IS_SALE.search(blob)


# --- Albanian relative/short dates -----------------------------------------

MONTHS = {"jan": 1, "shk": 2, "mar": 3, "pri": 4, "maj": 5, "qer": 6,
          "korr": 7, "gush": 8, "sht": 9, "tet": 10, "nën": 11, "nen": 11, "dhj": 12}


def parse_posted(s, today=None):
    """'Dje 11:38' / 'Sot 09:15' / '09 korr 16:42' -> ISO date string, or None."""
    import datetime
    if not s:
        return None
    today = today or datetime.date.today()
    s = s.strip().lower()
    if s.startswith("sot"):
        return today.isoformat()
    if s.startswith("dje"):
        return (today - datetime.timedelta(days=1)).isoformat()
    m = re.match(r"(\d{1,2})\s+([a-zë]+)", s)
    if m:
        day, mon = int(m.group(1)), m.group(2)
        for pref, num in MONTHS.items():
            if mon.startswith(pref):
                year = today.year
                try:
                    d = datetime.date(year, num, day)
                except ValueError:
                    return None
                if d > today:            # month in the future => last year
                    d = datetime.date(year - 1, num, day)
                return d.isoformat()
    return None


def all_areas(s):
    """Every plausible m2 figure in the text, in order of appearance."""
    if not s:
        return []
    out = []
    for m in re.finditer(r"(\d{2,4}(?:[.,]\d+)?)\s*(?:m2|m²|m\^2)", _html.unescape(s), re.I):
        v = float(m.group(1).replace(",", "."))
        if 15 <= v <= 600 and v not in out:
            out.append(v)
    return out


# --- scope guards -----------------------------------------------------------

OTHER_MUNI = re.compile(
    r"\b(podujev|obiliq|obili[cç]|lipjan|ferizaj|gjilan|prizren|pej[eë]|mitrovic|"
    r"vushtrri|drenas|gllogoc|skenderaj|rahovec|malishev|suharek|shtime|ka[cç]anik|"
    r"hani i elezit|kamenic|\bviti\b|de[cç]an|junik|istog|klin[eë]|gra[cç]anic|"
    r"fush[eë] ?kosov|fushkosov|shterpc|shtrpce|novo ?berd|ranillug|partesh|kllokot|"
    r"mamush|dragash|zve[cç]an|zubin potok|leposaviq)", re.I)


def mentions_other_municipality(text_blob):
    return bool(OTHER_MUNI.search(text_blob or ""))


PER_M2_TEXT = re.compile(
    r"(?:[cç]mimi\s*[:\-]?\s*)?(\d[\d.,]{1,7})\s*(?:€|eur)\s*(?:/|per\b|për\b)\s*m\s*2?|"
    r"(?:[cç]mimi\s*[:\-]?\s*)(\d[\d.,]{1,7})\s*(?:€|eur)?\s*(?:/|per\b|për\b)\s*m",
    re.I)


def parse_per_m2(s):
    """A price the ad itself states per square metre, e.g. 'ÇMIMI: 1360€ për m2'."""
    if not s:
        return None
    m = PER_M2_TEXT.search(_html.unescape(s))
    if not m:
        return None
    n = re.sub(r"[^\d]", "", m.group(1) or m.group(2) or "")
    if not n:
        return None
    v = float(n)
    return v if 300 <= v <= 7000 else None


def fetch_bytes(url, tries=2, timeout=25):
    """Binary GET for images."""
    for attempt in range(tries):
        with _throttle:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                    return r.read()
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
                if attempt == tries - 1:
                    return None
                time.sleep(1.0)
    return None
