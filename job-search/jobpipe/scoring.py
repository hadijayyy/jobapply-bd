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
SPONSOR, ABROAD, TITLE_GEO = RX("sponsorship_ok"), RX("abroad_onsite_loc"), RX("title_geo")
WAIVABLE = {b["id"] for b in C["hard_blockers"] if b.get("waived_by_sponsorship")}


def passes_prefilter(j, max_age_days):
    """Cheap gate before a job is stored. Title, location, age. Hand-pasted Hiring Cafe links always pass."""
    if j["source"] == "HiringCafe":
        return True
    if not TITLE_OK.search(j["title"]) or TITLE_NO.search(j["title"]):
        return False
    loc = j["location"] or ""
    # Cloudflare etc. put the country in the title and "Hybrid" in location; "Global" in a title is not a place
    if not LOC_OK.search(loc) and not TITLE_GEO.search(j["title"]):
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


def region(j):
    """global = remote with no country attached | apac | other (a country or sales territory outside APAC)."""
    loc = j["location"] + " | " + j["title"]
    if re.search(C["region_apac"], loc, re.I):
        return "apac"
    if re.search(C["region_other"], loc, re.I) or re.search(C["region_us_state"], loc):  # "Remote - TX"
        return "other"
    remote = re.search(r"remote|anywhere|worldwide|everywhere|global", loc + " " + j.get("workplace", ""), re.I)
    return "global" if remote else "other"


def score(j):
    t, loc, text = j["title"].lower(), j["location"] + " | " + j["title"], j["title"] + "\n" + j.get("desc", "")
    parts = {}
    parts["title"] = (30 if re.search(r"business development|partner|channel|alliance", t) else
                      26 if re.search(r"account executive|\bsdr\b|\bbdr\b|sales development|account manager", t) else
                      20 if re.search(r"sales|enterprise|commercial", t) else 12)
    parts["location"] = {"global": 25, "apac": 22, "other": 8}[region(j)]
    age = (date.today() - date.fromisoformat(j["posted"])).days if j["posted"] else None
    parts["fresh"] = 5 if age is None else 15 if age <= 3 else 12 if age <= 7 else 8 if age <= 14 else 4
    yrs = years_required(text)
    parts["seniority"] = 10 if yrs is None else 15 if yrs <= 5 else 8 if yrs == 6 else 0
    parts["industry"] = 10 if INDUSTRY.search(text) else 4
    parts["comp"] = 5 if j.get("comp") else 0
    return sum(parts.values()), parts, yrs


def evaluate(j):
    """Fills score, tier, blockers, flags on the job dict. Returns True if a red flag means auto-reject."""
    text = j["title"] + "\n" + j["location"] + "\n" + j.get("desc", "")
    sc, parts, yrs = score(j)
    sponsor = bool(SPONSOR.search(text))
    blockers = [label for bid, label, rx in HARD if rx.search(text) and not (sponsor and bid in WAIVABLE)]
    if yrs and yrs >= 7 and not any("7+" in b for b in blockers):
        blockers.append(f"Syarat {yrs}+ tahun")
    loc = j["location"] + " | " + j["title"]
    home = re.search(r"indonesia|jakarta", j["location"], re.I) or (
        re.search(r"indonesia|jakarta", j["title"], re.I) and not ABROAD.search(j["location"]))
    remote = re.search(r"remote|anywhere|worldwide|global", loc, re.I) or j.get("workplace", "").lower() == "remote"
    flags = [label for _, label, rx in SOFT if rx.search(text)]
    reg = region(j)
    if reg == "other" and not sponsor and C.get("outside_apac_requires_sponsorship_mention"):
        blockers.append("Luar APAC / remote terikat negara tanpa sponsor visa di JD")
    elif not home and reg != "global":
        flags.append("Luar Indonesia: sponsor visa disebut di JD" if sponsor else "Luar Indonesia: sponsor visa tidak disebut")
    j["sponsorship_mentioned"] = sponsor
    red = [label for _, label, rx in RED if rx.search(text)]
    age = (date.today() - date.fromisoformat(j["posted"])).days if j.get("posted") else None
    if age and age > 30:
        flags.append(f"Posting {age} hari (risiko ghost job, cek masih buka)")
    if not j.get("desc"):
        flags.append("Deskripsi belum terbaca: cek halaman asli")
    j["score"], j["score_parts"], j["years_required"] = sc, parts, yrs
    j["blockers"], j["flags"], j["red_flags"] = sorted(set(blockers)), flags, red
    th = C["tier_threshold"]
    if blockers:
        j["tier"] = "C"
    elif sc >= th["A"] and not [f for f in flags if not f.startswith(("Deskripsi", "Luar Indonesia: sponsor visa disebut"))]:
        j["tier"] = "A"
    elif sc >= th["B"]:
        j["tier"] = "B"
    else:
        j["tier"] = "C"
    return bool(red)
