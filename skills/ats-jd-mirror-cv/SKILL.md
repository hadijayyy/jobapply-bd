---
name: ats-jd-mirror-cv
description: Build an ATS CV where every keyword from the job post's JD appears in the CV, one page, scored against the JD. Use for any "bikin CV untuk lowongan X", tailor CV, or ATS CV request.
---

# ATS JD-Mirror CV

Goal: for one job post, produce a one-page ATS-safe CV PDF in which the JD's own wording appears, then prove it with a match score. Target: keyword match >= 90%.

Scripts and templates live in GitHub `hadijayyy/jobapply-bd`, branch `skills/job-application-pipeline`, folder `skills/ats-jd-mirror-cv/`. If they are not on disk, clone that branch first:
`git clone --depth 1 -b skills/job-application-pipeline https://github.com/hadijayyy/jobapply-bd`
Needs: `pip install reportlab`, and `pdftotext` (poppler-utils).

Master CV data: the user's latest CV (Project doc `career/master-cv.json` if present, else the latest CV they uploaded). Never invent employers, titles, dates, degrees or numbers.

## Workflow

### 1. Pull the live JD
Open the job post (WebFetch). Confirm it is still open. Save `jd_keywords.json` (see `templates/jd_keywords.example.json`) with EVERY keyword in the JD's exact wording:
- title words (e.g. "Business Development Manager", "Account Executive")
- tools (CRM names: Salesforce, HubSpot), methodologies (MEDDICC, MEDDPICC, BANT)
- product types (SaaS, cloud, CRM, BPM), buyer personas (C-level, VP, HR, department heads)
- motions (product demos, forecasting, new-logo, hunting, inbound, outbound, partner-sourced, referral, SQLs)
- segments and industries (SMB, enterprise, real estate, hospitality), languages ("Bahasa Indonesia", "English")
- generic sales words the JD uses (closing, negotiation, stakeholder management, relationship, pipeline, quota, revenue targets)

### 2. Confirm unknown keywords in ONE batch
Compare the keywords to the master CV. For every keyword the CV does not already prove, ask the user once, multiple choice (AskUserQuestion), grouped (sales scope / process / product domain). Never silently drop a JD keyword.
- Confirmed: add it.
- Product domain the user has not sold: describe it as "SaaS and IT solutions", or put it in the Fit line as "(target segment)".
- Industry or segment never sold to: "Ready to sell into ..." or "(target segment)". Never present it as past experience.

### 3. Place the keywords (mandatory placement)
| Where | Rule |
|---|---|
| Headline | Use the JD's title words: "<JD title> \| <niche from JD>" |
| Summary | Role + strength + one proof point with a number, plus the JD's top 3-5 keywords |
| Top 2 bullets | Re-ordered and reworded so the JD's most important motions appear (demos, new-logo, partners) |
| New confirmed facts | Merge into an existing bullet that already has a metric, so every bullet keeps a number |
| Skills line 1 | `<Company> Fit:` listing EVERY JD keyword in the JD's exact wording |
| Other skills rows | Sales, AI & Sales Tech, Sales Methodology, Solutions, Languages ("Bahasa Indonesia (native)") |

### 4. Build
Write `cv.json` (schema in `templates/cv.example.json`) and run:
`python3 scripts/build_cv.py cv.json Firstname-Lastname-CV-<Company>.pdf`
It auto-fits to one page (10pt down to 9.0pt) and then drops `drop_if_overflow` sections in order (Projects first). Single column, no icons, no skill bars.

### 5. Score and fix
`python3 scripts/match_jd.py <cv.pdf> jd_keywords.json`
Set `requirements_score` (0-100) to the share of hard requirements met: years, industry, languages, location, must-haves.
TOTAL = 60% keyword match + 40% requirements. If keyword match is below 90% (exit code 2), add the missing confirmed keywords and rebuild. Repeat until >= 90% or only unconfirmed or declined keywords remain.

### 6. Recruiter 6-second check (all must pass)
1. Summary names role, strength, and one proof point. No "hard-working team player".
2. Every bullet has a metric. If not, ask the user for one.
3. One page.
4. Simple ATS template: single column, no icons, skill bars or text in images.
5. JD keywords mirrored (match_jd.py >= 90%). If the JD says "Salesforce", the CV says "Salesforce" (only if true).
6. Zero typos and no em dashes (match_jd.py flags em dashes; also scan the unique word list).

### 7. Deliver
Send the PDF plus a short table: keyword %, requirements %, TOTAL, and any keyword left out and why. Keep the chat summary short. Chat in casual Bahasa Indonesia mixed with English.

## Notes
- Keep a separate CV per job post. File name: `Firstname-Lastname-CV-<Company>.pdf`.
- A high score means the CV should pass ATS filters, not a guaranteed callback. Avoid stuffing the Fit line with words the user cannot discuss in an interview.
- Everything on the CV must be something the user can explain in an interview.
