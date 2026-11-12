#!/usr/bin/env python3
"""Job scanner for Ryan Hadi (BD / Partnerships / Channel / Enterprise Sales).

Pulls open jobs from public, keyless job board APIs and ATS boards, filters by
title and location, drops anything already in tracker.csv / seen.json, and
prints a ranked markdown table. It only READS job listings. It never applies.

Usage:
    python3 job-search/scan.py                # print table
    python3 job-search/scan.py --days 14      # only jobs published in last 14 days
    python3 job-search/scan.py --out new.md   # also write to a file
    python3 job-search/scan.py --check-live   # drop postings confirmed expired

Sources: Remotive, Himalayas (search API), RemoteOK, We Work Remotely (RSS),
Greenhouse / Lever / Ashby company boards listed in boards.json.
Edit boards.json to add companies (board token = the slug in the careers URL).
"""
import argparse, csv, json, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (job-scan)"}
NOW = datetime.now(timezone.utc)

TITLE_OK = re.compile(
    r"business development|partnership|partner manager|partner development|channel|alliance|"
    r"account executive|enterprise sales|enterprise account|sales manager|sales director|"
    r"head of (sales|bd|business|partner)|growth manager|strategic account|solutions sales|"
    r"\bbdm\b|\bbd manager|country manager|market development", re.I)
TITLE_NO = re.compile(
    r"intern\b|internship|junior|graduate|entry|assistant|engineer|developer|designer|analyst|"
    r"recruit|accountant|support|customer success|marketing manager|payroll|legal|"
    r"representative|\bsdr\b|\bbdr\b|commission[- ]only|freelance", re.I)
LOC_OK = re.compile(
    r"indonesia|jakarta|apac|asia|southeast|sea\b|asean|singapore|malaysia|australia|"
    r"worldwide|anywhere|global|everywhere|remote", re.I)
LOC_BAD = re.compile(
    r"\b(us|usa|u\.s\.|united states|canada|uk|united kingdom|europe|emea|eu|latam|"
    r"north america|germany|france|india|brazil|mexico|israel|dubai|uae)\b[- ]*(only|based)?", re.I)
LOC_GOOD_STRICT = re.compile(
    r"indonesia|jakarta|apac|asia|southeast|asean|singapore|malaysia|australia|"
    r"worldwide|anywhere|everywhere|global", re.I)


def get(url, as_text=False, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data.decode("utf-8", "replace") if as_text else json.loads(data)


def safe(fn, label):
    try:
        return fn()
    except Exception as e:  # network/404 on a board token is normal
        print(f"  skip {label}: {type(e).__name__}", file=sys.stderr)
        return []


def parse_date(v):
    if not v:
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            return datetime.fromtimestamp(int(v), timezone.utc)
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def job(source, title, company, loc, url, date, extra=""):
    return {"source": source, "title": title or "", "company": company or "",
            "location": loc or "", "url": url or "", "date": parse_date(date), "extra": extra}


# ---------- keyless job board APIs ----------
QUERIES = ["business development", "partnerships", "partner manager", "channel sales",
           "account executive", "enterprise sales", "alliances"]


def remotive():
    out = []
    for q in QUERIES:
        d = get("https://remotive.com/api/remote-jobs?search=" + urllib.parse.quote(q))
        for j in d.get("jobs", []):
            out.append(job("Remotive", j["title"], j["company_name"], j.get("candidate_required_location"),
                           j["url"], j.get("publication_date"), j.get("salary", "")))
    return out


def himalayas():
    out = []
    for q in QUERIES:
        for country in ("ID", ""):
            for page in (1, 2):
                url = "https://himalayas.app/jobs/api/search?sort=recent&page=%d&q=%s" % (page, urllib.parse.quote(q))
                if country:
                    url += "&country=" + country
                d = get(url)
                for j in d.get("jobs", []):
                    loc = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
                    sal = ""
                    if j.get("minSalary"):
                        sal = f"{j.get('currency','')} {j['minSalary']}-{j.get('maxSalary','')}/{j.get('salaryPeriod','')}"
                    out.append(job("Himalayas", j["title"], j["companyName"], loc,
                                   j.get("applicationLink") or j.get("guid"), j.get("pubDate"), sal))
    return out


def remoteok():
    d = get("https://remoteok.com/api")
    return [job("RemoteOK", j.get("position"), j.get("company"), j.get("location") or "Worldwide",
                j.get("url"), j.get("date")) for j in d if isinstance(j, dict) and j.get("position")]


def wwr():
    out = []
    for cat in ("remote-sales-and-marketing-jobs", "remote-management-and-finance-jobs",
                "remote-business-exec-management-jobs"):
        try:
            xml = get(f"https://weworkremotely.com/categories/{cat}.rss", as_text=True)
        except Exception:
            continue
        for it in ET.fromstring(xml).iter("item"):
            t = it.findtext("title") or ""
            comp, _, title = t.partition(": ")
            out.append(job("WeWorkRemotely", title or t, comp, it.findtext("region") or "Remote",
                           it.findtext("link"), it.findtext("pubDate") and
                           datetime.strptime(it.findtext("pubDate")[:25], "%a, %d %b %Y %H:%M:%S").isoformat()))
    return out


# ---------- ATS boards (public JSON, no key) ----------
def greenhouse(tok):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs")
    return [job("GH:" + tok, j["title"], j.get("company_name") or tok, (j.get("location") or {}).get("name"),
                j["absolute_url"], j.get("first_published") or j.get("updated_at")) for j in d.get("jobs", [])]


def lever(tok):
    d = get(f"https://api.lever.co/v0/postings/{tok}?mode=json")
    return [job("Lever:" + tok, j["text"], tok, (j.get("categories") or {}).get("location") or j.get("workplaceType"),
                j["hostedUrl"], j.get("createdAt")) for j in d]


def ashby(tok):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}?includeCompensation=true")
    out = []
    for j in d.get("jobs", []):
        loc = j.get("location") or ""
        if j.get("isRemote"):
            loc += " (remote)"
        sec = ", ".join(s.get("location", "") for s in j.get("secondaryLocations") or [])
        comp = (j.get("compensation") or {}).get("compensationTierSummary", "")
        out.append(job("Ashby:" + tok, j["title"], tok, (loc + " " + sec).strip(), j["jobUrl"],
                       j.get("publishedAt"), comp))
    return out


def smartrecruiters(tok):
    d = get(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=100")
    return [job("SR:" + tok, j["name"], tok, (j.get("location") or {}).get("fullLocation"),
                f"https://jobs.smartrecruiters.com/{tok}/{j['id']}", j.get("releasedDate")) for j in d.get("content", [])]


ATS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "smartrecruiters": smartrecruiters}


def seen_urls():
    urls = set()
    f = HERE / "seen.json"
    if f.exists():
        s = json.loads(f.read_text())
        urls |= {x["url"] for x in s.get("jobs", []) + s.get("rejected", [])}
    t = HERE / "tracker.csv"
    if t.exists():
        for r in csv.DictReader(t.open()):
            urls.add(r.get("Link", ""))
    return urls


def norm(u):
    return re.sub(r"[?#].*$", "", u or "").rstrip("/").lower()


def score(j):
    s = 0
    t = j["title"].lower()
    if re.search(r"partner|channel|alliance", t): s += 3
    if re.search(r"business development|bd\b|enterprise|strategic", t): s += 2
    if re.search(r"manager|lead|head", t): s += 1
    if LOC_GOOD_STRICT.search(j["location"]): s += 2
    if re.search(r"indonesia|jakarta", j["location"], re.I): s += 3
    if re.search(r"apac|asean|southeast|asia", j["location"], re.I): s += 1
    if j["date"] and (NOW - j["date"]).days <= 7: s += 2
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--check-live", action="store_true", help="drop postings confirmed expired (ATS API check, no browser)")
    a = ap.parse_args()

    tasks = [("Remotive", remotive), ("Himalayas", himalayas), ("RemoteOK", remoteok), ("WWR", wwr)]
    boards = json.loads((HERE / "boards.json").read_text())
    for kind, toks in boards.items():
        for t in toks:
            tasks.append((f"{kind}:{t}", (lambda k=kind, t=t: ATS[k](t))))

    jobs = []
    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(safe, fn, label) for label, fn in tasks]
        for f in futs:
            jobs += f.result()
    print(f"fetched {len(jobs)} raw jobs from {len(tasks)} sources", file=sys.stderr)

    seen = {norm(u) for u in seen_urls()}
    cutoff = NOW - timedelta(days=a.days)
    keep, dup = [], set()
    for j in jobs:
        if not TITLE_OK.search(j["title"]) or TITLE_NO.search(j["title"]):
            continue
        loc = j["location"]
        if not loc or not LOC_OK.search(loc):
            continue
        if LOC_BAD.search(loc) and not LOC_GOOD_STRICT.search(loc):
            continue
        if j["date"] and j["date"] < cutoff:
            continue
        k = norm(j["url"])
        if k in seen or k in dup:
            continue
        dup.add(k)
        j["score"] = score(j)
        keep.append(j)
    keep.sort(key=lambda j: (-j["score"], j["date"] or NOW), reverse=False)
    keep = keep[: a.limit]
    if a.check_live:
        import liveness
        verdict = liveness.check_many([j["url"] for j in keep])
        dropped = [j for j in keep if verdict.get(j["url"]) == "expired"]
        keep = [j for j in keep if verdict.get(j["url"]) != "expired"]
        for j in keep:
            j["extra"] = (j["extra"] + " " if j["extra"] else "") + "[" + verdict.get(j["url"], "uncertain") + "]"
        print(f"liveness: dropped {len(dropped)} expired", file=sys.stderr)

    lines = [f"# New matches ({len(keep)}), {NOW:%Y-%m-%d}", "",
             "| Score | Date | Company | Title | Location | Pay | Source | Link |", "|---|---|---|---|---|---|---|---|"]
    for j in keep:
        d = j["date"].strftime("%Y-%m-%d") if j["date"] else "n/a"
        lines.append(f"| {j['score']} | {d} | {j['company']} | {j['title']} | {j['location'][:40]} | "
                     f"{j['extra'] or '-'} | {j['source']} | {j['url']} |")
    text = "\n".join(lines)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
