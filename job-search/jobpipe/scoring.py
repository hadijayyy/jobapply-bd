"""Stage 2: filter, score (0-100) and tier. Deterministic, so every number can be explained.

Tier A = apply. Tier B = stretch (a soft flag or a middling score). Tier C = hard blocker or weak fit.
"""
import re
from datetime import date

from .store import CONFIG

C = CONFIG
RX = lambda k: re.compile(C[k], re.I)
TITLE_OK, TITLE_NO = RX("title_include"), RX("title_exclude")
LOC_OK, LOC_BAD, LOC_GOOD = RX("location_ok"), RX("location_bad"), RX("location_good")
INDUSTRY = RX("industry_fit")
HARD = [(b["id"], b["label"], re.compile(b["pattern"], re.I)) for b in C["hard_blockers"]]
RED = [(b["id"], b["label"], re.compile(b["pattern"], re.I)) for b in C["red_flags"]]
SOFT = [(b["id"], b["label"], re.compile(b["pattern"], re.I)) for b in C["soft_flags"]]


def passes_prefilter(j, max_age_days):
    """Cheap gate before a job is stored. Title, location, age."""
    if not TITLE_OK.search(j["title"]) or TITLE_NO.search(j["title"]):
        return False
    loc = j["location"]
    if not loc or not LOC_OK.search(loc):
        return False
    if LOC_BAD.search(loc) and not LOC_GOOD.search(loc):
        return False
    if j["posted"] and (date.today() - date.fromisoformat(j["posted"])).days > max_age_days:
        return False
    return True


def years_required(text):
    """Largest 'N years ... experience' figure in the text, or None."""
    best = None
    for m in re.finditer(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|yrs)", text, re.I):
        ctx = text[max(0, m.start() - 60): m.end() + 80].lower()
        if re.search(r"experience|sales|business development|channel|partnership|account", ctx):
            n = int(m[1])
            if n <= 15:
                best = max(best or 0, n)
    return best


def family(j):
    """Which CV variant and proof points fit: channel | ai | enterprise."""
    t = j["title"].lower()
    if re.search(r"partner|channel|alliance|ecosystem", t):
        return "channel"
    if re.search(r"outbound|growth|\bai\b|new business|hunter", t):
        return "ai"
    return "enterprise"


def score(j):
    t, loc, text = j["title"].lower(), j["location"], j["title"] + "\n" + j.get("desc", "")
    parts = {}
    parts["title"] = (30 if re.search(r"partner|channel|alliance", t) else
                      26 if re.search(r"business development|enterprise|strategic", t) else
                      20 if re.search(r"account executive|sales (manager|director)|head of", t) else 12)
    parts["location"] = (25 if re.search(r"indonesia|jakarta", loc, re.I) else
                         20 if re.search(r"apac|asean|southeast|\bsea\b|asia", loc, re.I) else
                         15 if re.search(r"worldwide|anywhere|global|everywhere", loc, re.I) else
                         10 if re.search(r"remote", loc, re.I) else 8)
    age = (date.today() - date.fromisoformat(j["posted"])).days if j["posted"] else None
    parts["fresh"] = 5 if age is None else 15 if age <= 3 else 12 if age <= 7 else 8 if age <= 14 else 4
    yrs = years_required(text)
    parts["seniority"] = 10 if yrs is None else 15 if 3 <= yrs <= 5 else 8 if yrs == 6 else 5 if yrs <= 2 else 0
    parts["industry"] = 10 if INDUSTRY.search(text) else 4
    parts["comp"] = 5 if j.get("comp") else 0
    return sum(parts.values()), parts, yrs


def evaluate(j):
    """Fills score, tier, blockers, flags on the job dict. Returns True if a red flag means auto-reject."""
    text = j["title"] + "\n" + j["location"] + "\n" + j.get("desc", "")
    sc, parts, yrs = score(j)
    blockers = [label for _, label, rx in HARD if rx.search(text)]
    if yrs and yrs >= 7 and not any("7+" in b for b in blockers):
        blockers.append(f"Syarat {yrs}+ tahun")
    wp = j.get("workplace", "").lower()
    if wp in ("onsite", "on-site", "hybrid") and not re.search(r"indonesia|jakarta", j["location"], re.I):
        blockers.append("Onsite/hybrid di luar Jakarta")
    red = [label for _, label, rx in RED if rx.search(text)]
    flags = [label for _, label, rx in SOFT if rx.search(text)]
    if not j.get("desc"):
        flags.append("Deskripsi belum terbaca: cek halaman asli")
    j["score"], j["score_parts"], j["years_required"] = sc, parts, yrs
    j["blockers"], j["flags"], j["red_flags"] = sorted(set(blockers)), flags, red
    th = C["tier_threshold"]
    if blockers:
        j["tier"] = "C"
    elif sc >= th["A"] and not [f for f in flags if not f.startswith("Deskripsi")]:
        j["tier"] = "A"
    elif sc >= th["B"]:
        j["tier"] = "B"
    else:
        j["tier"] = "C"
    return bool(red)
