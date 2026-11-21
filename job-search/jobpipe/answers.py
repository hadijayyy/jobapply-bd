"""Answers for Greenhouse application questions, resolved from apply_profile.json and the answer cache.

Nothing is guessed. A question resolves to one of:
  ("text", str) | ("pick", [option labels]) | ("skip", reason) | ("unresolved", reason)
Unresolved + required blocks the job from being submitted. AI-drafted answers (essays, one-off
questions) live in data/answers.json and are written through `pipeline.py autoapply answer`.
"""
import hashlib
import json
import re

from .store import ROOT

PROFILE = json.loads((ROOT / "apply_profile.json").read_text())
CACHE_PATH = ROOT / "data" / "answers.json"
YES, NO = [r"^yes\b"], [r"^no\b"]
DECLINE = [r"prefer not|decline|don.?t wish|do not wish|not to (say|disclose|answer|specify|self)|choose not"]
ACK = [r"acknowledge", r"^yes\b", r"agree", r"consent", r"confirm", r"accept"]

COUNTRIES = {
    "Indonesia": r"indonesia|jakarta", "Singapore": r"singapore", "Malaysia": r"malaysia|kuala lumpur",
    "Thailand": r"thailand|bangkok", "Vietnam": r"vietnam|ho chi minh|hanoi", "Philippines": r"philippines|manila",
    "Hong Kong": r"hong kong", "Japan": r"japan|tokyo", "South Korea": r"korea|seoul", "India": r"\bindia\b|bangalore|bengaluru|mumbai|gurgaon|hyderabad",
    "Australia": r"australia|sydney|melbourne", "New Zealand": r"new zealand|auckland", "China": r"china|shanghai|beijing|shenzhen", "Taiwan": r"taiwan|taipei",
    "United States": r"united states|\busa?\b|u\.s\.|new york|san francisco|austin|seattle|chicago|boston|denver|atlanta|los angeles",
    "Canada": r"canada|toronto|vancouver", "United Kingdom": r"united kingdom|\buk\b|london|manchester", "Ireland": r"ireland|dublin",
    "Germany": r"germany|berlin|munich", "France": r"france|paris", "Netherlands": r"netherlands|amsterdam", "Spain": r"spain|madrid|barcelona",
    "United Arab Emirates": r"emirates|\buae\b|dubai|abu dhabi", "Saudi Arabia": r"saudi|riyadh", "Israel": r"israel|tel aviv",
    "Brazil": r"brazil|s[aã]o paulo", "Mexico": r"mexico", "Poland": r"poland|warsaw", "Sweden": r"sweden|stockholm", "Switzerland": r"switzerland|zurich",
    "Portugal": r"portugal|lisbon", "Italy": r"italy|milan", "Turkey": r"turkey|istanbul", "Egypt": r"egypt|cairo",
}
HOME = PROFILE["country"]


def countries_in(text):
    return [c for c, rx in COUNTRIES.items() if re.search(rx, text or "", re.I)]


def job_country(job):
    """Country the role is tied to. None = remote with no country named (work from home country)."""
    found = countries_in(job.get("location", "")) or countries_in(job.get("title", ""))
    return found[0] if found else None


def is_remote(job):
    return bool(re.search(r"remote|anywhere|worldwide", job.get("location", "") + " " + job.get("workplace", ""), re.I))


def norm(label):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", label or "")).strip()


def cache_key(label, scope=""):
    return hashlib.sha1((scope + "|" + norm(label).lower()).encode()).hexdigest()[:12]


def load_cache():
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def save_answer(label, answer, job=None, source="ai"):
    """job=None stores a reusable answer for every form with this exact label; else only for that job."""
    c = load_cache()
    c[cache_key(label, job["id"] if job else "")] = {
        "label": norm(label)[:300], "answer": answer, "source": source,
        "scope": f"{job['company']} | {job['title']}" if job else "semua lowongan"}
    CACHE_PATH.write_text(json.dumps(c, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


def _need(key, kind="bool"):
    """Profile value that only Ryan knows. None -> unresolved."""
    v = PROFILE.get(key)
    if v is None:
        return ("unresolved", f"apply_profile.json > {key} belum diisi")
    if kind == "bool":
        return ("pick", YES if v else NO)
    return ("text", str(v))


def _years(label, options):
    yrs = PROFILE["years_experience"]["general"]
    specific = re.search(r"experience (do you have )?(with|in|selling|working)|years of [a-z ]{3,40} experience", label, re.I)
    for rx, n in PROFILE["years_experience"]["domains"].items():
        if re.search(rx, label, re.I):
            yrs, specific = n, None
            break
    generic = re.search(r"(b2b|sales|selling|business development|quota|closing|account management|professional|work|relevant|total)\W+(\w+\W+){0,3}experience", label, re.I)
    if specific and not generic:
        return ("unresolved", "tahun pengalaman di bidang spesifik: tidak ada di profil")
    if not options:
        return ("text", str(yrs))
    for o in options:  # first range containing yrs: "4+ Years", "3-5", "0-1 Years", "5"
        nums = [int(x) for x in re.findall(r"\d+", o)]
        if not nums:
            continue
        lo, hi = nums[0], (nums[1] if len(nums) > 1 else (99 if re.search(r"\+|more|over|above", o, re.I) else nums[0]))
        if re.search(r"less than|under|<", o, re.I):
            lo, hi = 0, nums[0] - 1
        if lo <= yrs <= hi:
            return ("pick", ["^" + re.escape(o) + "$"])
    return ("unresolved", "tidak ada opsi rentang tahun yang cocok")


def _auth(label, job):
    """(authorized, needs_sponsorship) for the country the question or the job is about."""
    named = [c for c in countries_in(label)]
    target = named[0] if named else job_country(job)
    if re.search(r"country (in which |where )?you (currently )?(reside|live)|current location|country of residence", label, re.I):
        target = HOME
    home = target in (None, HOME)
    return home, (not home and PROFILE["work_authorization"]["needs_sponsorship_outside"])


def resolve(label, options, job, files, required=False, prior=None):
    """options: list of option labels ([] for free text). files: {"cv": path, "cover": path|None}."""
    L, prior = norm(label), prior or {}
    s = lambda rx: re.search(rx, L, re.I)
    P = PROFILE
    cached = load_cache()
    for scope in (job["id"], ""):
        hit = cached.get(cache_key(L, scope))
        if hit:
            return ("pick", ["^" + re.escape(a) + "$" for a in hit["answer"]]) if isinstance(hit["answer"], list) and options else \
                   ("pick", ["^" + re.escape(str(hit["answer"])) + "$"]) if options else ("text", str(hit["answer"]))
    if s(r"^if (you )?(answered |selected |said )?[\"“']?(yes|so|other)|^if applicable"):
        if s(r"other") and s(r"country") and prior.get("country_other"):
            return ("text", HOME)
        return ("skip", "follow-up dari jawaban 'No'")
    if s(r"preferred (first )?name|name you.d prefer|^first name"):
        return ("text", P["first_name"])
    if s(r"last name|surname|family name"):
        return ("text", P["last_name"])
    if s(r"legal name|pronoun|middle name"):
        return ("skip", "opsional")
    if s(r"^e-?mail( address)?$"):
        return ("text", P["email"])
    if s(r"^(phone|mobile)( number)?$"):
        return ("text", P["phone_full"])
    if s(r"linkedin|personal website or blog"):
        return ("text", P["linkedin"])
    if s(r"^website|portfolio|github|twitter|other links"):
        return ("skip", "tidak ada")
    if s(r"family members|relatives?|personal relationship|related to (any|an) (current )?employee|know anyone"):
        return _need("relatives_or_relationship_at_company")
    if s(r"outside business activit|conflict of interest"):
        return _need("outside_business_activities")
    if s(r"employment agreements|post-employment restrictions|non-?compete|non-?solicit|restrictive covenant"):
        return _need("bound_by_non_compete")
    if s(r"whatsapp|text/sms|sms|text message"):
        return _need("opt_in_whatsapp_sms")
    if s(r"email me about other|job alerts?|marketing (emails?|communications?)|newsletter"):
        return _need("opt_in_job_alert_emails")
    if s(r"retain (your|my) data|future (opportunities|roles|openings|positions)|talent (pool|community)|consent to .{0,40}using your data to evaluate"):
        return _need("opt_in_talent_pool") if options else ("skip", "opsional")
    if s(r"(authori[sz]ed|eligible|entitled|right) to work") and s(r"sponsor") and options and not any(len(o) > 6 for o in options):
        return ("unresolved", "pertanyaan ganda (hak kerja DAN sponsor) dengan opsi Yes/No: ambigu")
    if s(r"citizen|permanent resident|\bpr\b of|green card"):
        ok = any(c == HOME for c in countries_in(L))
        return ("pick", YES if ok else [r"^no$", r"^no\b(?!.*(citizen|resident))", r"^no\b"])
    if s(r"source of your right to work|basis.{0,30}right to work|work authori[sz]ation status"):
        home, _ = _auth(L, job)
        return ("pick", [r"citizen"] if home else [r"require sponsorship|need sponsorship|do not (currently )?have"])
    if s(r"sponsor|immigration|work (permit|visa)|employment pass|visa (support|status)"):
        _, sponsor = _auth(L, job)
        return ("pick", YES if sponsor else NO)
    if s(r"(authori[sz]ed|eligible|entitled|legally (able|permitted)|right) to work|work authori[sz]ation"):
        home, _ = _auth(L, job)
        return ("pick", YES if home else NO)
    if s(r"(current|most recent) (or previous |or most recent )?(company|employer)|who is your current"):
        return ("text", P["current_company"])
    if s(r"current (or previous |or most recent )?(job )?title|current role"):
        return ("text", P["current_title"])
    if s(r"zip|postal"):
        return _need("postal_code", "text")
    if s(r"country.{0,40}(anticipate|plan to|would like to) work"):
        c = job_country(job) or HOME
        return ("pick", ["^" + re.escape(c) + "$"]) if options else ("text", c)
    if s(r"country.{0,30}(reside|based|live)|country of residence|where are you (currently )?(located|based)|current location|city.{0,20}(reside|live|based)"):
        if options:
            return ("pick", ["^" + HOME + "$", r"^other"])
        return ("text", f"{P['city']}, {HOME}" if s(r"city|where are you|location") else HOME)
    if s(r"(cities|locations|offices?).{0,30}(available|willing|prefer|able) to work|which (office|location)"):
        want = [o for o in options if re.search(re.escape(o.split(",")[0]), job.get("location", ""), re.I)]
        return ("pick", ["^" + re.escape(o) + "$" for o in want]) if want else ("unresolved", "tidak ada opsi kota yang cocok dengan lokasi lowongan")
    if s(r"languages? (you|do you) speak|language proficiency|which languages"):
        return ("pick", ["bahasa indonesia|indonesian", r"^english"]) if options else ("text", "Indonesian (native), English (professional working proficiency)")
    if s(r"(fluent|proficient|professional).{0,30}english|english.{0,30}(fluen|proficien)"):
        return ("pick", YES) if options else ("text", "Yes, professional working proficiency")
    if s(r"how did you (first |initially |originally )?(hear|find|learn)|where did you (hear|find|learn)|source of (application|referral)"):
        return ("pick", [r"direct to careers", r"^(?!college).*career(s)? ?(page|site|website)", r"company (web)?site", r"greenhouse", r"job board", r"^other"]) if options else ("text", P["how_heard"])
    if s(r"remote location, do you plan to work remotely|intend to work remotely"):
        return ("pick", [r"^yes"] if is_remote(job) else [r"office"])
    if s(r"relocat"):
        return ("pick", YES if P["work_authorization"]["open_to_relocation"] else NO) if options else ("text", "Yes, open to relocation with visa sponsorship")
    if s(r"(commute|work from|come into|be in|on-?site|hybrid|in[- ]office|in[- ]person).{0,60}(office|days|week|site)") and options:
        home = job_country(job) in (None, HOME)
        return ("pick", YES) if (home or P["work_authorization"]["open_to_relocation"]) else ("unresolved", "pertanyaan hadir di kantor")
    m = re.search(r"are you (currently )?(based|located|living|residing) in ([^?]+)\?", L, re.I)
    if m and options:
        return ("pick", YES if re.search(r"indonesia|jakarta", m[3], re.I) else NO)
    if s(r"by initialing|your initials"):
        return ("text", P["first_name"][0] + P["last_name"][0])
    if s(r"deloitte"):
        return ("pick", [r"^no"])
    if s(r"(previously|ever|in the past|currently|presently|have you).{0,60}(employed|worked|work(ing)? (at|for)|consulted|employee|contractor|intern|interview|applied)|former employee"):
        return ("pick", NO) if options else ("text", "No")
    if s(r"gender|race|ethnic|veteran|disabilit|sexual orientation|transgender|lgbt|hispanic"):
        if P["demographics"] == "decline":
            return ("pick", DECLINE) if required else ("skip", "demografi: tidak diisi")
    if s(r"accommodat|accessible and inclusive|adjustments"):
        return ("skip", "opsional") if not required else ("pick", NO) if options else ("text", "No")
    if s(r"at least 18|18 years (of age|or older)|over (the age of )?18"):
        return ("pick", YES if P["over_18"] else NO)
    if s(r"years? of .{0,60}experience|how many years|how long have you"):
        return _years(L, options)
    if s(r"salary|compensation|expected (pay|base|ote)|pay expectations?|remuneration"):
        if options or s(r"number|amount|figure|numeric|per (year|month|annum)|annual|usd|sgd|\$"):
            return _need("salary_number", "text")
        return ("text", P["salary_text"])
    if s(r"notice period|when (can|could|would) you (start|join)|earliest start|start date|availability to start"):
        return ("unresolved", "opsi notice period perlu dipilih") if options and not any(re.search(r"month|30|4 weeks", o, re.I) for o in options) else \
               ("pick", [r"1 month|one month|30 days|4 weeks"]) if options else ("text", f"{P['notice_period']} notice period")
    if s(r"willing(ness)? to travel|travel (up to|required|\d+%)"):
        return _need("willing_to_travel")
    if s(r"certify|true and (correct|complete|accurate)|accurate and complete"):
        return ("pick", ACK) if options else ("text", f"{P['first_name']} {P['last_name']}")
    if s(r"privacy|personal data|personal information|acknowledge|i (understand|agree|consent|have read)|terms|gdpr|data processing"):
        return ("pick", ACK) if options else ("skip", "tidak ada opsi")
    if files.get(L.lower()):
        return ("text", files[L.lower()])
    return ("unresolved", "pertanyaan baru: belum ada aturan atau jawaban tersimpan")


def choose(options, patterns, multi=False):
    """Option labels matching the patterns. Single: first pattern that matches wins. Multi: one option per pattern."""
    got = []
    for rx in patterns:
        hit = [o for o in options if re.search(rx, o.strip(), re.I)]
        hit = [o for o in hit if o not in got]
        if hit:
            got.append(hit[0])
            if not multi:
                return got
    return got
