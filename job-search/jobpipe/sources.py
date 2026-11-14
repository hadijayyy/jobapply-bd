"""Stage 1: discover. Pulls open jobs from keyless public APIs and ATS boards. Read-only."""
import html, json, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .store import CONFIG

UA = {"User-Agent": "Mozilla/5.0 (job-scan)"}
ATS_SOURCES = ("GH:", "Lever:", "Ashby:", "SR:")


def get(url, as_text=False, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        data = r.read()
    return data.decode("utf-8", "replace") if as_text else json.loads(data)


def plain(s, limit=6000):
    s = html.unescape(s or "")
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"</(p|li|div|h\d|br)>|<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()[:limit]


def parse_date(v):
    if not v:
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            v = int(v)
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, timezone.utc)
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def job(source, title, company, loc, url, date, comp="", desc="", workplace=""):
    d = parse_date(date)
    return {"source": source, "title": (title or "").strip(), "company": (company or "").strip(),
            "location": (loc or "").strip(), "url": url or "", "posted": d.date().isoformat() if d else None,
            "comp": comp or "", "desc": plain(desc), "workplace": workplace or ""}


# ---------- keyless boards ----------
def remotive():
    out = []
    for q in CONFIG["queries"]:
        for j in get("https://remotive.com/api/remote-jobs?search=" + urllib.parse.quote(q)).get("jobs", []):
            out.append(job("Remotive", j["title"], j["company_name"], j.get("candidate_required_location"),
                           j["url"], j.get("publication_date"), j.get("salary", ""), j.get("description", "")))
    return out


def himalayas():
    out = []
    for q in CONFIG["queries"]:
        for country in ("ID", ""):
            url = "https://himalayas.app/jobs/api/search?sort=recent&q=" + urllib.parse.quote(q)
            if country:
                url += "&country=" + country
            for j in get(url).get("jobs", []):
                loc = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
                comp = f"{j.get('currency','')} {j['minSalary']}-{j.get('maxSalary','')}/{j.get('salaryPeriod','')}" if j.get("minSalary") else ""
                out.append(job("Himalayas", j["title"], j["companyName"], loc, j.get("applicationLink") or j.get("guid"),
                               j.get("pubDate"), comp, j.get("description") or j.get("excerpt", "")))
    return out


def remoteok():
    return [job("RemoteOK", j.get("position"), j.get("company"), j.get("location") or "Worldwide", j.get("url"),
                j.get("date"), desc=j.get("description", "")) for j in get("https://remoteok.com/api")
            if isinstance(j, dict) and j.get("position")]


def wwr():
    out = []
    for cat in ("remote-sales-and-marketing-jobs", "remote-management-and-finance-jobs", "remote-business-exec-management-jobs"):
        try:
            xml = get(f"https://weworkremotely.com/categories/{cat}.rss", as_text=True)
        except Exception:
            continue
        for it in ET.fromstring(xml).iter("item"):
            comp, _, title = (it.findtext("title") or "").partition(": ")
            pub = it.findtext("pubDate")
            iso = datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S").isoformat() if pub else None
            out.append(job("WeWorkRemotely", title, comp, it.findtext("region") or "Remote", it.findtext("link"), iso,
                           desc=it.findtext("description") or ""))
    return out


# ---------- ATS boards ----------
def greenhouse(tok):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs")
    return [job("GH:" + tok, j["title"], j.get("company_name") or tok, (j.get("location") or {}).get("name"),
                j["absolute_url"], j.get("first_published") or j.get("updated_at")) for j in d.get("jobs", [])]


def greenhouse_detail(j):
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", j["url"])
    if m:
        d = get(f"https://boards-api.greenhouse.io/v1/boards/{m[1]}/jobs/{m[2]}")
        j["desc"] = plain(d.get("content", ""))


def lever(tok):
    return [job("Lever:" + tok, j["text"], tok, (j.get("categories") or {}).get("location"), j["hostedUrl"],
                j.get("createdAt"), desc=j.get("descriptionPlain", "") + "\n" + j.get("additionalPlain", ""),
                workplace=j.get("workplaceType", "")) for j in get(f"https://api.lever.co/v0/postings/{tok}?mode=json")]


def ashby(tok):
    out = []
    for j in get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}?includeCompensation=true").get("jobs", []):
        loc = (j.get("location") or "") + (" (remote)" if j.get("isRemote") else "")
        sec = ", ".join(s.get("location", "") for s in j.get("secondaryLocations") or [])
        out.append(job("Ashby:" + tok, j["title"], tok, (loc + " " + sec).strip(), j["jobUrl"], j.get("publishedAt"),
                       (j.get("compensation") or {}).get("compensationTierSummary", ""), j.get("descriptionPlain", ""),
                       j.get("workplaceType", "")))
    return out


def smartrecruiters(tok):
    d = get(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=100")
    return [job("SR:" + tok, j["name"], tok, (j.get("location") or {}).get("fullLocation"),
                f"https://jobs.smartrecruiters.com/{tok}/{j['id']}", j.get("releasedDate")) for j in d.get("content", [])]


ATS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "smartrecruiters": smartrecruiters}


def _safe(fn, label):
    try:
        return fn()
    except Exception as e:  # a dead board token or timeout is normal
        print(f"  skip {label}: {type(e).__name__}", file=sys.stderr)
        return []


def fetch_all():
    tasks = [("Remotive", remotive), ("Himalayas", himalayas), ("RemoteOK", remoteok), ("WWR", wwr)]
    for kind, toks in CONFIG["boards"].items():
        for t in toks:
            tasks.append((f"{kind}:{t}", lambda k=kind, t=t: ATS[k](t)))
    jobs = []
    with ThreadPoolExecutor(8) as ex:
        for f in [ex.submit(_safe, fn, label) for label, fn in tasks]:
            jobs += f.result()
    print(f"fetched {len(jobs)} raw jobs from {len(tasks)} sources", file=sys.stderr)
    return jobs


def enrich(jobs):
    """Greenhouse list API has no description; fetch it only for the few survivors."""
    todo = [j for j in jobs if j["source"].startswith("GH:") and not j["desc"]]
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda j: _safe(lambda: greenhouse_detail(j), j["url"]), todo))
