"""ATS match score (0-100), Jobscan-style, computed on the TEXT EXTRACTED FROM THE PDF (what an ATS parses).

  keywords   50  weighted coverage of the JD's hard-skill keywords (sales motions, tools, partner types, domain)
  title      15  the JD's role title appears in the CV (headline / summary)
  soft       10  coverage of the JD's soft-skill keywords
  experience 10  years asked in the JD vs Ryan's 5+
  education   5  degree present when the JD asks for one
  format     10  standard headings, contact details, one column, text extractable

Every lexicon term carries evidence:
  yes      Ryan's CV or confirmed answers back it up -> may appear in a tailored CV
  pending  Ryan said it is true but the detail is not in yet -> NOT written; scored separately as "if confirmed"
  no       not true -> never written; listed so the cover letter / interview can address it
"""
import re
import subprocess

# (canonical, kind, regex, evidence, skills-section phrase)
LEX = [
    # ---- sales motions ----
    ("business development", "hard", r"business development|\bbd\b", "yes", "Business Development"),
    ("B2B sales", "hard", r"\bb2b\b", "yes", "B2B Sales"),
    ("enterprise sales", "hard", r"enterprise (sales|accounts?|customers?|clients?|deals?|software sales)|large enterprises?", "yes", "Enterprise Sales"),
    ("full-cycle sales", "hard", r"full[- ]cycle|end[- ]to[- ]end sales|(entire|full) sales (cycle|process)|sales cycle", "yes", "Full-Cycle Sales"),
    ("new business", "hard", r"new[- ](business|logos?|customers?|accounts?)|net[- ]new|greenfield|hunt(er|ing)", "yes", "New Business Acquisition"),
    ("closing", "hard", r"\bclos(e|ed|ing) (deals?|business|new|\w+ in)|deal clos|\bclosed\b|\bclosing\b", "yes", "Deal Closing"),
    ("outbound prospecting", "hard", r"outbound|prospect(ing)?|cold (call|outreach|email)", "yes", "Outbound Prospecting"),
    ("pipeline generation", "hard", r"pipeline (generation|build|creation)|(build|generate|create) (a |your )?(strong |healthy |robust )?pipeline|self[- ]sourc", "yes", "Pipeline Generation"),
    ("pipeline management", "hard", r"pipeline (management|hygiene|review)|manag\w* (the |your |a )?pipeline", "yes", "Pipeline Management"),
    ("discovery", "hard", r"discovery", "yes", "Discovery Calls"),
    ("consultative selling", "hard", r"consultative|solution(s)?[- ]selling|value[- ]based selling|value selling", "yes", "Consultative / Solution Selling"),
    ("negotiation", "hard", r"negotiat", "yes", "Contract Negotiation"),
    ("multi-stakeholder", "hard", r"multi[- ]?stakeholder|multiple stakeholders|buying committee|multi[- ]threaded", "yes", "Multi-stakeholder Deals"),
    ("executive engagement", "hard", r"c[- ]?level|c[- ]suite|executive (level|relationships?|stakeholders?|presentations?|engagement)|senior (decision|executives?|leaders)", "yes", "Executive Presentations & Engagement"),
    ("account management", "hard", r"account management|manag\w* (a )?(portfolio|book) of|account plann|territory plann|account plans?", "yes", "Account Management & Planning"),
    ("cross-sell", "hard", r"cross[- ]sell", "yes", "Cross-Selling"),
    ("upsell / expansion", "hard", r"upsell|up[- ]sell|expansion|expand (existing|accounts|relationships|footprint)|land and expand", "pending", "Upsell & Account Expansion"),
    ("renewals / retention", "hard", r"renewal|retention|retain", "yes", "Renewals & Retention"),
    ("quota attainment", "hard", r"quota|(sales|revenue) targets?|exceed\w* targets?|over[- ]?achiev", "yes", "Quota Attainment (115%+ in 2025)"),
    ("forecasting", "hard", r"forecast", "pending", "Sales Forecasting"),
    ("proposals / RFP", "hard", r"\brfp\b|\brfi\b|tender|proposal", "yes", "Proposals & Tenders"),
    ("business case", "hard", r"business case|\broi\b|value (case|realization)", "yes", "Business Case Development"),
    ("market sizing", "hard", r"market (sizing|analysis|research|intelligence|mapping)|\btam\b", "yes", "Market Sizing & Analysis"),
    ("go-to-market", "hard", r"go[- ]to[- ]market|\bgtm\b", "no", "Go-to-Market Planning"),
    ("sales methodology", "hard", r"meddp?icc?|\bbant\b|\bspin\b|challenger|command of the message|sandler|value selling framework|sales methodolog", "pending", "MEDDIC / BANT / SPIN"),
    # ---- partnerships ----
    ("channel partnerships", "hard", r"channel|partner(ship)?s? (program|ecosystem|network)", "yes", "Channel Partnerships"),
    ("partner management", "hard", r"partner (management|relationships?|manager|success)|manag\w* partners?|strategic partnerships?|partnerships", "yes", "Partner Management"),
    ("partner recruitment", "hard", r"recruit\w* (new )?partners?|partner (recruitment|acquisition|onboarding)|onboard\w* (new )?partners?|sign\w* (new )?partners?", "yes", "Partner Recruitment & Onboarding"),
    ("co-selling / joint plans", "hard", r"co[- ]sell|joint (business|sales|go[- ]to[- ]market|account) plan|joint (selling|pipeline)|partner[- ]sourced|partner[- ]led", "yes", "Co-selling & Joint Sales Planning"),
    ("QBR", "hard", r"\bqbrs?\b|quarterly business review|business reviews", "yes", "Quarterly Business Reviews"),
    ("partner enablement", "hard", r"enablement|enable (partners|the channel)", "no", "Partner Enablement"),
    ("resellers / distributors", "hard", r"resell|\bvars?\b|distribut(or|ion)|\bvad\b", "pending", "Resellers & Distributors"),
    ("system integrators / GSIs", "hard", r"system integrators?|\bg?sis?\b|consulting partners", "pending", "System Integrators"),
    ("alliances", "hard", r"alliances?", "pending", "Strategic Alliances"),
    ("MSP / managed services", "hard", r"managed services?|\bmsps?\b|\bmssps?\b", "yes", "Managed Services"),
    ("affiliates", "hard", r"affiliate", "no", "Affiliate Programs"),
    # ---- tools ----
    ("CRM", "hard", r"\bcrm\b", "yes", "CRM (Salesforce, HubSpot)"),
    ("Salesforce", "hard", r"salesforce|\bsfdc\b", "yes", "Salesforce"),
    ("HubSpot", "hard", r"hubspot", "yes", "HubSpot"),
    ("Excel / analytics", "hard", r"excel|power ?bi|tableau|data[- ]driven|analytic", "yes", "Power BI & Advanced Excel"),
    ("AI tools", "hard", r"\bai\b|artificial intelligence|genai|generative|llm|chatgpt|claude", "yes", "AI Sales Workflows (ChatGPT, Claude)"),
    # ---- domain / market ----
    ("cloud", "hard", r"\bcloud\b", "yes", "Cloud & Managed Services Solutions"),
    ("AWS / GCP / Azure", "hard", r"\baws\b|amazon web services|\bgcp\b|google cloud|azure", "pending", "AWS / GCP / Azure"),
    ("SaaS", "hard", r"\bsaas\b|software[- ]as[- ]a[- ]service|subscription software", "no", "SaaS"),
    ("software sales", "hard", r"software (sales|solutions)|selling software|enterprise software|technology sales|tech sales", "yes", "Technology Sales (IT Solutions)"),
    ("IT infrastructure", "hard", r"infrastructure|network(ing)?\b|it solutions|\bit services", "yes", "IT & Network Infrastructure"),
    ("cybersecurity", "hard", r"cyber ?security|threat|\bsoc\b|security (solutions|products|platform)", "no", "Cybersecurity"),
    ("payments / fintech", "hard", r"payments?|fintech|merchant", "no", "Payments"),
    ("adtech", "hard", r"ad ?tech|programmatic|advertis", "no", "AdTech"),
    ("crypto / web3", "hard", r"crypto|web3|blockchain|digital assets?", "no", "Crypto"),
    ("public sector", "hard", r"public sector|government|\bgov\b|ministr|state[- ]owned|\bbumn\b|\bsoe\b", "no", "Public Sector"),
    ("healthcare", "hard", r"healthcare|hospital", "yes", "Healthcare"),
    ("Indonesia market", "hard", r"indonesia|jakarta", "yes", "Indonesia Market"),
    ("SEA / APAC markets", "hard", r"southeast asia|\bsea\b|asean|apac|asia[- ]pacific|\bapj\b|regional", "pending", "Southeast Asia Markets"),
    ("Bahasa Indonesia", "hard", r"bahasa|indonesian", "yes", "Bahasa Indonesia (Native)"),
    ("English", "hard", r"\benglish\b", "yes", "English (Professional)"),
    ("travel", "hard", r"travel", "pending", "Regional Travel"),
    # ---- soft skills ----
    ("communication", "soft", r"communicat|presentation skills|written and verbal", "yes", "Communication"),
    ("cross-functional collaboration", "soft", r"cross[- ]functional|collaborat|work closely with", "yes", "Cross-functional Collaboration"),
    ("leadership", "soft", r"\blead(ership)?\b|mentor|coach", "yes", "Team Leadership"),
    ("relationship building", "soft", r"relationship[- ]build|build\w* (strong |trusted |long[- ]term )?relationships|trusted advisor", "yes", "Relationship Building"),
    ("problem solving", "soft", r"problem[- ]solv|creative|resourceful", "yes", "Problem Solving"),
    ("self-starter", "soft", r"self[- ]start|self[- ]motivat|autonom|ownership|independent", "yes", "Self-starter / Ownership"),
    ("strategic thinking", "soft", r"strategic (thinking|mindset|planning)|strategic", "yes", "Strategic Planning"),
    ("resilience", "soft", r"resilien|grit|tenac|persist", "no", "Resilience"),
]
COMPILED = [(c, k, re.compile(rx, re.I), ev, phrase) for c, k, rx, ev, phrase in LEX]
TERM = {c: (k, rx, ev, phrase) for c, k, rx, ev, phrase in COMPILED}

RYAN_YEARS = 5
FORMAT_HEADINGS = ("SUMMARY", "EXPERIENCE", "SKILLS", "EDUCATION")


def jd_terms(jd_text, title=""):
    """Terms the JD asks for, with weight 2 when the term is in the title or appears 2+ times."""
    out = {}
    for c, k, rx, ev, _ in COMPILED:
        n = len(rx.findall(jd_text))
        if n:
            out[c] = 2 if (n >= 2 or rx.search(title)) else 1
    return out


def role_title_core(title):
    """'Senior Account Executive - Adtech' -> 'Account Executive'. Used for the title-match points."""
    t = re.sub(r"\(.*?\)|\[.*?\]|[-–,|].*$", "", title).strip()
    t = re.sub(r"^(senior|sr\.?|lead|principal|staff|named|strategic|commercial|enterprise|regional|hunter|territory|mid[- ]market|global)\s+", "", t, flags=re.I)
    t = re.sub(r"^(senior|sr\.?|strategic|enterprise|regional|hunter|territory)\s+", "", t, flags=re.I)
    return t.strip()


def pdf_text(path):
    """Text as an ATS parser sees it. Line wraps are joined so 'Partner\nRecruitment' still matches."""
    raw = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True).stdout
    return re.sub(r"\s+", " ", raw)


def score(cv_text, jd_text, title, years_required=None, include_pending=False):
    terms = jd_terms(jd_text, title)
    hard = {c: w for c, w in terms.items() if TERM[c][0] == "hard"}
    soft = {c: w for c, w in terms.items() if TERM[c][0] == "soft"}

    def covered(c):
        if include_pending and TERM[c][2] == "pending":
            return True
        return bool(TERM[c][1].search(cv_text))

    def cov(d):
        tot = sum(d.values())
        return (sum(w for c, w in d.items() if covered(c)) / tot) if tot else 1.0

    core = role_title_core(title)
    title_hit = bool(core) and re.search(re.escape(core), cv_text, re.I)
    words = [w for w in re.findall(r"[a-z]+", core.lower()) if len(w) > 2]
    title_pts = 15 if title_hit else round(15 * sum(w in cv_text.lower() for w in words) / max(1, len(words)) * 0.6)

    if years_required is None or years_required <= RYAN_YEARS:
        exp = 10
    else:
        exp = {6: 6}.get(years_required, 0)
    asks_degree = re.search(r"bachelor|degree|university|\bba\b|\bbs\b", jd_text, re.I)
    edu = 5 if (not asks_degree or re.search(r"bachelor", cv_text, re.I)) else 0
    fmt = sum([2.5 * all(h in cv_text for h in FORMAT_HEADINGS),
               2.5 * bool(re.search(r"@\S+\.\w+", cv_text) and re.search(r"\+\d[\d ]{8,}", cv_text)),
               2.5 * bool(re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) 20\d\d", cv_text)),
               2.5 * (len(cv_text) > 1500)])
    parts = {"keywords": round(50 * cov(hard), 1), "title": title_pts, "soft": round(10 * cov(soft), 1),
             "experience": exp, "education": edu, "format": fmt}
    buckets = {"matched": sorted(c for c in terms if covered(c)),
               "missing_but_true": sorted(c for c in terms if not covered(c) and TERM[c][2] == "yes"),
               "pending_confirm": sorted(c for c in terms if not covered(c) and TERM[c][2] == "pending"),
               "missing_not_true": sorted(c for c in terms if TERM[c][2] == "no")}
    return round(sum(parts.values())), parts, buckets, core


def usable_terms(jd_text, title):
    """JD terms Ryan can truthfully claim, highest weight first. Drives the tailored CV."""
    t = jd_terms(jd_text, title)
    return [c for c, _ in sorted(t.items(), key=lambda kv: -kv[1]) if TERM[c][2] == "yes"]
