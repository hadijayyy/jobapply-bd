#!/usr/bin/env python3
"""Check whether job posting URLs are still live. Zero LLM tokens, no browser.

Verdicts: active | expired | uncertain.
Conservative by design (same philosophy as career-ops check-liveness): return
"expired" only on a definitive signal (404/410 from a provider API, the job is
missing from a board listing, or a hard "no longer available" phrase on the
page). Anything ambiguous is "uncertain", never "expired".

Approach and expired-phrase list adapted from career-ops-hq/career-ops
(MIT License, Copyright (c) 2026 Santiago Fernandez de Valderrama).

Used by pipeline.py (verify stage). Quick manual check:
    python3 -c "from jobpipe.liveness import check_many; print(check_many(['URL']))"
"""
import functools, json, re, threading, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (job-liveness)"}
SEG = r"[A-Za-z0-9._-]+"
HARD_EXPIRED = [re.compile(p, re.I) for p in (
    r"job (is )?no longer available", r"job.*no longer open", r"this job has expired",
    r"job posting has expired", r"no longer accepting applications",
    r"this (position|role|job) (is )?no longer", r"position (has been|is) (filled|closed)",
    r"the job you are looking for (is|has) (no longer|been)", r"this posting (has )?closed",
)]


def http(url, timeout=12, limit=600_000):
    """Return (status, body or None). Redirects are followed; errors map to status."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.status, r.read(limit).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def greenhouse(u):
    m = re.search(rf"greenhouse\.io/({SEG})/jobs/(\d+)", u)
    if not m:
        return None
    s, _ = http(f"https://boards-api.greenhouse.io/v1/boards/{m[1]}/jobs/{m[2]}")
    return "active" if s == 200 else "expired" if s in (404, 410) else "uncertain"


def lever(u):
    m = re.search(rf"jobs\.lever\.co/({SEG})/([0-9a-f-]{{36}})", u)
    if not m:
        return None
    s, _ = http(f"https://api.lever.co/v0/postings/{m[1]}/{m[2]}")
    # career-ops: a Lever API 404 is not authoritative, so only a 200 counts.
    return "active" if s == 200 else "uncertain"


_LOCK = threading.Lock()


@functools.lru_cache(maxsize=None)
def _ashby_ids(token):
    """Fetch one Ashby board once (cached). Returns a frozenset of job ids, or None if unreadable."""
    s, body = http(f"https://api.ashbyhq.com/posting-api/job-board/{token}", 40, 60_000_000)
    if s != 200 or not body:
        return None
    try:
        return frozenset(j.get("id") for j in json.loads(body).get("jobs", []))
    except ValueError:
        return None


def ashby(u):
    m = re.search(rf"jobs\.ashbyhq\.com/({SEG})/([0-9a-f-]{{36}})", u)
    if not m:
        return None
    with _LOCK:  # one fetch per board even when many URLs share it
        ids = _ashby_ids(m[1])
    if ids is None:
        return "uncertain"
    return "active" if m[2] in ids else "expired"


def smartrecruiters(u):
    m = re.search(rf"jobs\.smartrecruiters\.com/({SEG})/(\d+)", u)
    if not m:
        return None
    s, _ = http(f"https://api.smartrecruiters.com/v1/companies/{m[1]}/postings/{m[2]}")
    return "active" if s == 200 else "expired" if s in (404, 410) else "uncertain"


def generic(u):
    if re.search(r"linkedin\.com|jobleads\.com|indeed\.com", u):
        return "uncertain"  # login walls and aggregators: a 4xx here is not proof
    s, body = http(u)
    if s in (404, 410):
        return "expired"
    if s != 200 or not body:
        return "uncertain"
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    if any(p.search(text) for p in HARD_EXPIRED):
        return "expired"
    return "uncertain"  # a 200 page with no closed marker is not proof of an open job


def check(url):
    try:
        for fn in (greenhouse, lever, ashby, smartrecruiters):
            v = fn(url)
            if v:
                return v
        return generic(url)
    except Exception:
        return "uncertain"


def check_many(urls, workers=8):
    urls = list(dict.fromkeys(urls))
    with ThreadPoolExecutor(workers) as ex:
        return dict(zip(urls, ex.map(check, urls)))
