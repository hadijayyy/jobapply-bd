#!/usr/bin/env python3
"""Build one application kit per role into job-search/applications/.

Each kit: verdict, CV variant, cover letter, form answers, apply link.
Facts come only from profile.md. Writing rules: no em dashes, no cliches.
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "applications"
OUT.mkdir(exist_ok=True)

SIG = "Ryan Hadi\nJakarta, Indonesia | +62 821 9997 5090 | ryanhadi.career@gmail.com | linkedin.com/in/ryanhadi"

# Reusable proof points, all from profile.md
P = {
 "deals": "At Sinar Mas Land (OneSmartServices) I closed IDR 10B+ in contract value across eight enterprise deals, averaging IDR 1.25B each, and finished 2025 at 115%+ of quota for smart CCTV and network infrastructure",
 "partners": "I run a program of 20 active channel partners. Quarterly business reviews and joint sales plans grew our partner-sourced pipeline 25%, from IDR 2B to IDR 2.5B, in 12 months",
 "signing": "I led a three-person BD team and signed four new channel partners, cutting proposal-to-signature time from 60 to 48 days by running Legal, Finance and Operations reviews in parallel",
 "ai": "I built AI workflows with ChatGPT and Claude for prospect research, outreach and proposal drafting. They tripled our monthly prospect research volume, doubled discovery meetings and cut proposal turnaround from several days to one",
 "siloam": "At Siloam Hospitals Group I built an outbound pipeline in HubSpot aimed at HR and procurement, with about 20 qualified prospects and 10 discovery meetings a month, which brought in 12 new corporate accounts and IDR 750M in first-year team revenue",
 "renew": "I also ran medical check-up programs for 12 corporate clients covering 1,500 employees and renewed 10 of 12 eligible contracts (83%)",
}

ROLES = [
 # id, company, role, tier, cv, apply_url, ats, hook, [proof keys], gap, notes
 dict(id="datadog", co="Datadog", role="Strategic Account Executive (Indonesia)", tier="A", cv="Enterprise",
      url="https://boards.greenhouse.io/datadog/jobs/7131726", ats="Greenhouse (embedded on careers.datadoghq.com)",
      hook="Datadog is looking for someone to win new logos in Indonesia's largest enterprises, running long, multi-stakeholder cycles.",
      proof=["deals", "siloam"],
      gap="My background is IT infrastructure and managed services rather than a SaaS vendor. The buying committees and procurement steps are the same ones I work with today.",
      ask="I would like to walk you through how I run a territory plan and relationship maps."),
 dict(id="kaltura", co="Kaltura", role="Account Executive, Media and Telecom (APAC)", tier="A", cv="AI-Sales",
      url="https://www.comeet.com/jobs/kaltura/E2.00D/account-executive---media-and-telecom-apac/57.376", ats="Comeet",
      hook="Kaltura sells a Cloud TV platform and an AI-powered customer engagement platform to telecom and media companies across Southeast Asia.",
      proof=["ai", "deals"],
      gap="I have not sold into telecom or media yet. I am a native Bahasa Indonesia speaker with a closing record in enterprise IT and a habit of using AI to prospect faster.",
      ask="I would be glad to discuss how I would build a first-year pipeline in the region."),
 dict(id="kglobalhub", co="KGlobal Hub", role="Channel Sales Manager (Jakarta)", tier="A", cv="Channel",
      url="https://www.jobleads.com/id/job/channel-sales-manager--jakarta-pusat--ef366f5ff4806903ce89f40d0cc8c9a2f", ats="JobLeads listing (find KGlobal Hub's own apply page first)",
      hook="Your Channel Sales Manager role is about recruiting and onboarding distributors, resellers, SIs and ISVs, then running joint business plans with them.",
      proof=["partners", "signing"], gap="",
      ask="I would like to talk through how I would grow partner coverage across your territories."),
 dict(id="cloudmile", co="CloudMile", role="Cloud Growth & Partnerships Manager (Indonesia)", tier="A", cv="Channel",
      url="https://www.jobleads.com/id/job/cloud-growth-partnerships-manager-indonesia--jakarta-pusat--e48de14e0ec4c4ccc29201525fb075d16", ats="JobLeads listing (find CloudMile's own apply page first)",
      hook="CloudMile needs someone to co-sell cloud solutions with channel partners, SIs and ISVs and to open C-level conversations about modernization.",
      proof=["partners", "deals"],
      gap="OneSmartServices delivers cloud, managed services and smart city infrastructure to 110+ corporate clients, so I sell the same kind of outcome you do.",
      ask="I can share how our joint sales plans with partners worked in practice."),
 dict(id="ingram", co="Ingram Micro", role="Business Development Manager (Jakarta)", tier="A", cv="Channel",
      url="https://www.jobleads.com/id/job/business-development-manager--jakarta-pusat--e8c8e74da0aa350c6a632ff5f273fcead", ats="JobLeads listing (apply on Ingram Micro careers)",
      hook="The Business Development Manager role in Jakarta is about growing relationships with existing customers and opening new ones for advanced solutions and services.",
      proof=["partners", "deals"], gap="",
      ask="I would welcome a conversation about where I can add the most in your Jakarta team."),
 dict(id="deel", co="Deel", role="Enterprise Account Executive, ASEAN Markets", tier="A", cv="Enterprise",
      url="https://www.jobleads.com/id/job/enterprise-account-executive-asean-markets--indonesia--e568785dd8f78388a90d32fd545eeece3", ats="JobLeads listing (apply on Deel careers)",
      hook="Deel is building an ASEAN enterprise territory from scratch, selling payroll and HR software to strategic accounts.",
      proof=["siloam", "deals"],
      gap="I sold to HR and procurement buyers at Siloam and now sell to enterprise IT buyers. I have not worked at a SaaS vendor.",
      ask="I would like to show you how I would plan the first 90 days of a greenfield account list."),
 dict(id="exabytes", co="PT Exabytes Network Indonesia", role="Enterprise SaaS Solutions Account Manager", tier="A", cv="Enterprise",
      url="https://www.jobleads.com/id/job/enterprise-saas-solutions-account-manager--jakarta-selatan--e32cb8a80c6b740f2fc214e9993f6c571", ats="JobLeads listing (apply on Exabytes site)",
      hook="Exabytes is hiring a seller for high-end and strategic accounts who can explain the business value of IT and cloud solutions over long sales cycles.",
      proof=["deals", "ai"], gap="",
      ask="I would be glad to discuss the accounts you want to grow first."),
 dict(id="sensortower", co="Sensor Tower", role="SaaS Account Executive, SEA Growth and New Business", tier="A", cv="Enterprise",
      url="https://www.jobleads.com/id/job/saas-account-executive-for-sea-growth-new-business--indonesia--e485ab1ee46aadcc5ecd6e8ae79edb397", ats="JobLeads listing (apply on Sensor Tower careers)",
      hook="Sensor Tower wants a new-business seller for Indonesia and Southeast Asia who keeps a clean pipeline and closes on data-led stories.",
      proof=["siloam", "ai"],
      gap="I have not sold SaaS data platforms or worked in mobile advertising. My pipeline discipline and closing record in enterprise IT are what I would bring.",
      ask="I would like to talk about how I would approach your Indonesian accounts."),
 dict(id="groupib", co="Group-IB", role="Business Development Manager (Indonesia)", tier="A", cv="Enterprise",
      url="https://www.group-ib.com/careers/?gh_jid=5024592101", ats="Greenhouse (embedded on group-ib.com)",
      hook="Group-IB wants a quota-carrying seller to hunt new business in Indonesia and act as a trusted advisor on cybersecurity and fraud topics.",
      proof=["deals", "siloam"],
      gap="My closing record is in smart CCTV and network infrastructure rather than security software. It is enterprise selling in a security-adjacent category.",
      ask="I would like to discuss the Indonesian accounts you are targeting."),
 dict(id="pragmatike", co="Pragmatike", role="Outbound Account Executive", tier="A", cv="AI-Sales",
      url="https://jobs.ashbyhq.com/pragmatike/42adcdc4-0ae6-439d-b08f-d58ba48d18ea", ats="Ashby",
      hook="You are hiring an outbound seller who owns discovery, negotiation and pipeline in an early-stage setting.",
      proof=["siloam", "ai"],
      gap="I work from Jakarta (UTC+7), one hour behind Singapore time.",
      ask="I would welcome a short call to learn which accounts you want me to open first."),
 dict(id="supabase", co="Supabase", role="Account Executive, ASEAN", tier="A", cv="Enterprise",
      url="https://jobs.ashbyhq.com/supabase/9a48e441-16c8-488d-a056-0e132f09d65d", ats="Ashby (reCAPTCHA)",
      hook="Supabase is hiring an ASEAN seller who can run enterprise cycles with procurement and security reviews and work with AWS and regional partners.",
      proof=["deals", "partners"],
      gap="I have not sold developer tools or databases. I have sold complex IT infrastructure through partners to enterprise buyers.",
      ask="I would be glad to discuss how I would build the ASEAN pipeline."),
 dict(id="wiley", co="Wiley", role="Enterprise Business Development Manager (Indonesia)", tier="A", cv="Enterprise",
      url="https://wiley.wd1.myworkdayjobs.com/wiley_careers/job/remote-idn/enterprise-business-development-manager--indonesia_r2601160", ats="Workday (account needed)",
      hook="Wiley needs an Enterprise BDM to grow digital collections, courseware and AI-enabled offerings with senior decision-makers in Indonesia.",
      proof=["deals", "renew"],
      gap="I have not sold into universities yet. I have run solution sales with corporate procurement buyers and kept renewals high.",
      ask="I would like to discuss how I would plan the Indonesian territory."),
 dict(id="pearson", co="Pearson", role="Senior Business Development Manager (Indonesia)", tier="A", cv="Enterprise",
      url="https://pearson.jobs/virtual-mys/senior-business-development-manager/877058A6C3C54EC19E3C8A19153D6D62/job/", ats="Pearson careers",
      hook="Pearson wants a seller who can advise CHROs and learning leaders in Indonesian enterprises on workforce and skills solutions.",
      proof=["siloam", "deals"],
      gap="I sold to HR and procurement stakeholders at Siloam and now sell to enterprise IT buyers, so multi-stakeholder cycles are routine for me.",
      ask="I would welcome a conversation about the Indonesian pipeline."),
 # Tier B (stretch)
 dict(id="alibabacloud", co="Alibaba Cloud", role="Channel Business Development Manager (Jakarta)", tier="B", cv="Channel",
      url="https://www.linkedin.com/jobs/view/alibaba-cloud-intelligence-channel-business-development-manager-jakarta-indonesia-at-alibaba-cloud-4285125013", ats="LinkedIn (JD unverified, apply on careers.alibabacloud.com)",
      hook="Alibaba Cloud's channel BD role in Jakarta is about growing the partner ecosystem that takes cloud solutions to Indonesian enterprises.",
      proof=["partners", "signing"], gap="", ask="I would like to discuss how I would grow partner-led revenue in Indonesia."),
 dict(id="ampd", co="Ampd Energy", role="Business Development Manager (Indonesia)", tier="B", cv="Channel",
      url="https://jobs.lever.co/ampd-energy/fe8158ed-b98d-4281-b6cc-0b1fa443b92a", ats="Lever (hCaptcha likely)",
      hook="Ampd Energy needs a BDM to train distributors, own the CRM pipeline and close with mining, construction and industrial clients in Indonesia.",
      proof=["partners", "deals"],
      gap="I have not sold power systems to mining. I do run channel partners and long, quote-and-tender style cycles for infrastructure.",
      ask="I would like to talk about the distributors you want to enable first."),
 dict(id="okx", co="OKX", role="Affiliate Business Development Manager (Southeast Asia)", tier="B", cv="Channel",
      url="https://boards.greenhouse.io/okx/jobs/8032195003", ats="Greenhouse",
      hook="OKX wants someone to build and optimize an affiliate network in the Indonesian market.",
      proof=["partners", "ai"],
      gap="I have not worked in crypto or affiliate marketing. I recruit, onboard and manage partner networks and track the pipeline they produce.",
      ask="I would welcome a conversation about the local affiliate plan."),
 dict(id="90seconds", co="90 Seconds", role="Enterprise Growth Manager, APAC (Remote)", tier="B", cv="Enterprise",
      url="https://www.jobleads.com/sg/job/enterprise-growth-manager-apac-remote--singapore--ef1d71bd7293f9c7c60c1c4cc868ecc6f", ats="JobLeads listing (posted 30 Sep, verify it is live)",
      hook="90 Seconds wants an enterprise seller who owns the cycle from prospecting to close with brands across APAC.",
      proof=["deals", "ai"],
      gap="I have not sold video production or advertising.", ask="I would like to discuss the brands you are targeting."),
 dict(id="fyndtech", co="FyndTech", role="APAC Business Manager (Remote)", tier="B", cv="Enterprise",
      url="https://www.jobleads.com/sg/job/apac-business-manager-remote-regional-ownership--singapore--e88c8611b9b9c0f2761ed72d82f19f2c8", ats="JobLeads listing (posted 17 Aug, likely stale)",
      hook="FyndTech needs someone to own APAC client relationships and revenue targets from a remote base.",
      proof=["deals", "partners"], gap="", ask="I would welcome a conversation about regional priorities."),
 dict(id="zycus", co="Zycus", role="Enterprise SaaS Account Executive, APAC (via Talismatic)", tier="B", cv="Enterprise",
      url="https://www.jobleads.com/id/job/enterprise-saas-account-executive-apac-growth-hunter--indonesia--e34be815270061833ab18de37c61fdca1", ats="JobLeads listing (agency post, posted 28 Jul)",
      hook="Zycus is hiring an APAC seller to win net-new enterprise business through long, complex cycles.",
      proof=["deals", "siloam"],
      gap="My enterprise deals average IDR 1.25B, below the deal size in your posting. I run the same discovery and multi-stakeholder process.",
      ask="I would be glad to discuss the APAC accounts you want to open."),
 dict(id="cyberscope", co="CyberScope (TAC Security)", role="Business Development Manager, APAC", tier="B", cv="Channel",
      url="https://jobs.smartrecruiters.com/coinscope/743999982129713-business-development-manager-apac-", ats="SmartRecruiters",
      hook="CyberScope wants a BDM to grow its clients and partner list across APAC.",
      proof=["partners", "deals"],
      gap="I have not worked in cybersecurity or blockchain. I build partner lists and client pipelines for enterprise IT.",
      ask="I would welcome a short call about APAC priorities."),
 dict(id="branch", co="Branch", role="Senior Business Development Representative, APAC", tier="B", cv="AI-Sales",
      url="https://ats.rippling.com/branch/jobs/e53a670f-0cef-4225-9d9a-e57277d601a1", ats="Rippling",
      hook="Branch is hiring an outbound specialist to open senior conversations with enterprise and high-growth accounts across APAC.",
      proof=["siloam", "ai"],
      gap="This role is outbound-focused and I currently hold a BD Manager title. I am applying because outbound pipeline is where I am strongest.",
      ask="I would like to discuss how I would build target lists and account-entry plans."),
 dict(id="ampifire", co="AmpiFire", role="Account Executive (Content Marketing SaaS)", tier="B", cv="AI-Sales",
      url="https://ampifire-1738143252.teamtailor.com/jobs/8693475-account-executive-140k-usd-ote-content-marketing-saas-agency", ats="Teamtailor (US working hours)",
      hook="AmpiFire is hiring a remote closer with B2B SaaS experience and a clear commission plan.",
      proof=["ai", "siloam"],
      gap="I have not sold content marketing. The posting asks for US hours, which I would need to confirm before an interview.",
      ask="I would welcome a call to see if the hours and the territory fit."),
 dict(id="temporal", co="Temporal", role="ASEAN Partnerships Manager", tier="B", cv="Channel",
      url="https://jobs.ashbyhq.com/temporal/b23916a6-2696-4283-8504-2094c0708401", ats="Ashby (Singapore-based, 7+ yrs asked)",
      hook="Temporal wants someone to build its ASEAN partner business from zero.",
      proof=["partners", "signing"],
      gap="I have five years of experience, not seven, and I am based in Jakarta rather than Singapore.",
      ask="I would like to discuss how I would build the partner ecosystem."),
]


def letter(r):
    body = [f"Hello {r['co']} team,", "", r["hook"] + " " + "I am a Business Development Manager in Jakarta with five years of B2B sales and channel partnerships in enterprise IT and corporate healthcare.", ""]
    proofs = [P[k] for k in r["proof"]]
    body.append(proofs[0] + ". " + proofs[1] + ".")
    if r["gap"]:
        body += ["", r["gap"]]
    body += ["", r["ask"] + " My CV is attached.", "", "Best regards,", SIG]
    return "\n".join(body)


BAD = re.compile(r"—|passionate|thrilled|fast-paced|results-driven|synerg|I am writing to apply", re.I)
FORM = """## Standard form answers (from profile.md)
- Full name: Ryan Hadi
- Email: ryanhadi.career@gmail.com | Phone: +62 821 9997 5090
- Location: Jakarta, Indonesia (UTC+7)
- LinkedIn: linkedin.com/in/ryanhadi
- Languages: Indonesian (native), English (professional working proficiency)
- Work authorization: Indonesia only (citizen status to be confirmed by Ryan). Any other country: do not answer, ask Ryan.
- Salary expectation: ask Ryan, never invent (floor stated: USD 1,000/month, higher is better)
- Notice period / start date: ask Ryan (not in profile)
- Demographic / EEO questions: leave to Ryan or choose "decline to self-identify"
"""


def main():
    rows = []
    for r in ROLES:
        txt = letter(r)
        assert not BAD.search(txt), r["id"]
        words = len(txt.split())
        md = f"""# {r['co']} | {r['role']}
- Tier: {r['tier']} | CV: cv/Ryan-Hadi-CV-{r['cv']}.pdf | ATS: {r['ats']}
- Apply: {r['url']}

## Cover letter ({words} words)

{txt}

{FORM}"""
        (OUT / f"{r['id']}.md").write_text(md)
        rows.append((r["id"], words))
    print(len(rows), "kits;", "word range", min(w for _, w in rows), max(w for _, w in rows))


if __name__ == "__main__":
    main()
