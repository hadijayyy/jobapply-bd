---
name: "job-application-pipeline"
description: "End-to-end job hunt pipeline for BD/Partnerships roles in APAC: find and score jobs, tailor CV, cover letters, outreach, apply, track, interview prep. Use for any lowongan, lamaran or CV task."
---

# Job Application Pipeline (BD / Partnerships, APAC)

Run the job search the way a good BD person runs a sales pipeline: source, qualify, research, pitch, follow up, close, review. This skill covers every stage from finding a role to evaluating an offer, with a human approval gate before anything is sent or submitted.

## Default user context (confirm or update in Setup)

- Based in Jakarta, Indonesia (WIB, UTC+7).
- Target roles: Business Development, Partnerships, Channel/Alliances, Tech Sales and B2B Sales in Tech, SaaS, AI and Web3.
- Target markets: Singapore, Malaysia, Australia; plus remote-from-Indonesia roles at US/EU companies expanding into Indonesia/SEA, on Indo/SG working hours, paid in USD.
- Chat with the user in casual Bahasa Indonesia mixed with English, direct and concise. Application materials are written in English unless the role requires another language.

## Hard rules

1. **Human gate.** Never submit an application, send an email, DM or connection request, or post anything without the user's explicit yes for that specific item. Drafts are fine (for example Gmail drafts).
2. **No fabrication.** Never invent experience, metrics, titles, dates, employers, degrees, references or work-authorization status. If a number is missing, insert `[METRIC?]` and ask.
3. **Verify before investing.** Open the posting and confirm it is live, its location and remote terms, and its posting date before writing materials.
4. **Contact info.** Use only professional contact details that are publicly listed. A pattern-guessed email must be labeled "unverified guess".
5. **No bulk auto-apply bots** (LinkedIn Easy Apply loops and similar). They risk account restriction and break platform terms. Browser help is one application at a time, stopping before Submit.
6. **Writing style.** No em dashes anywhere. No cliches: "passionate", "thrilled", "fast-paced", "results-driven", "leverage synergies", "I am writing to apply". Concrete nouns and numbers over adjectives. If a humanizer skill is available, run final cover letters and outreach through it.

## State: where things live

Keep persistent state in the most durable place available:
- If a claude.ai Project is attached, store files as Project docs under `career/`.
- Otherwise use a `job-search/` folder in the working directory.
- The tracker is a spreadsheet: a Sheets artifact if that type is available, otherwise `tracker.csv`.

Files:
- `career/profile.md`: master profile (template in Setup)
- `career/story-bank.md`: STAR stories with metrics
- tracker: one row per role
- `career/applications/<company>-<role>.md`: JD snapshot, verdict, research, CV change log, cover letter, outreach, interview notes

Read the profile and story bank at the start of every mode. If they don't exist, run Setup first. Exception: if the user just pasted a JD, do a quick Packet with what is available and list what Setup would add.

## Modes

| Mode | Trigger examples | Output |
|---|---|---|
| Setup | "setup profil", "update CV master" | profile.md, story-bank.md, empty tracker |
| Scan | "cariin lowongan", "scan jobs" | table of new A/B roles + expansion-signal companies |
| Evaluate | job URL or JD + "cocok nggak?" | grade, breakdown, red flags, action |
| Packet | job URL or JD + "bikinin lamaran" | full packet (see Output contract) |
| Outreach | "cold email ke HM X" | drafts for recruiter / hiring manager |
| Apply | "apply ini" | filled form, stopped before Submit |
| Track | "status?", "update tracker" | due follow-ups, counts by status |
| Prep | "interview prep [company]", "mock interview" | brief, question map, mock session |
| Offer | "review offer" | comparison vs floor, negotiation draft |
| Review | "weekly review" | funnel metrics + 3 adjustments |

Default: if the user pastes a job URL or JD with no instruction, run Evaluate, then Packet if the grade is A or B.

---

### 0. Setup

Ask in one batch, skipping anything already known:
- Master CV (upload) and LinkedIn URL
- Target titles and seniority
- Markets, remote preference, working-hours window
- Work authorization: where the user can work without sponsorship, where sponsorship is needed, openness to relocate
- Comp floor and target in USD (base and OTE)
- Industries in and out of scope, dealbreakers
- Top 5 to 10 wins with numbers (pipeline, revenue, partners signed, deal size, cycle time, markets opened)
- Languages
- 2 or 3 writing samples for tone

Profile template:

```
# Career profile
## Basics
Name | Location / timezone | Languages | LinkedIn | Portfolio
## Work authorization
Can work without sponsorship in: ... | Needs sponsorship for: ... | Relocation: ...
## Targets
Titles | Seniority | Markets | Remote | Hours | Comp floor / target (USD) | Industries | Dealbreakers
## Master experience
Full history with ALL bullets (more than fits one CV)
## Proof points
Top wins with numbers and context
## Tone samples
```

Story bank entries: `Title | Situation | Task | Action | Result (with number) | Skills shown | Best for questions about...`

### 1. Scan (discovery)

Sources:
- **ATS boards (best signal for SaaS):** web search `site:boards.greenhouse.io`, `site:jobs.lever.co`, `site:jobs.ashbyhq.com` combined with role and location terms ("Partnerships" "Singapore", "Business Development" "APAC", "Indonesia" remote).
- **SG / MY:** LinkedIn Jobs, JobStreet, MyCareersFuture (SG), Glassdoor.
- **AU:** Seek, LinkedIn.
- **Remote / startups:** Wellfound, Remote OK, We Work Remotely.
- **Web3:** web3.career, CryptoJobsList, company X accounts.
- **X / Twitter:** "hiring" + "BD" / "partnerships" + "APAC" / "SEA", founder hiring posts.
- **Hidden jobs (expansion signals):** recent funding + "expanding to Southeast Asia / Indonesia", new APAC GM hires, "first hire in Indonesia". These become outreach targets even with no posting.

Process: run queries, open each candidate, extract fields, dedupe against the tracker, quick-score, then return only new A/B roles and expansion-signal companies in a short table (Company, Role, Location/Remote, Grade, Link, Why). Add them to the tracker as Sourced.

Recurring: offer to set up a scheduled task on weekday mornings WIB that runs Scan and reports new A/B matches.

### 2. Evaluate (qualify)

Score 1 to 5 on six weighted dimensions:

| Dimension | Weight | A 5 looks like |
|---|---|---|
| Role fit | 25% | Core BD/partnerships scope matching the user's proof points |
| Level and scope | 15% | Title and ownership match or step up from current level |
| Eligibility and location | 20% | Remote from Indonesia allowed, or sponsorship offered, or user already eligible |
| Company momentum | 15% | Recent funding or growth, active APAC/SEA expansion |
| Comp potential | 10% | USD, at or above floor |
| Access | 15% | Posting under 14 days old, reachable hiring manager, warm path |

Gate: if the role needs local work authorization the user lacks and no sponsorship is mentioned, cap the grade at C and say so.

Grades: **A** 4.2+ (packet and outreach today), **B** 3.5 to 4.1 (packet), **C** 2.8 to 3.4 (quick apply only if the pipeline is thin), **D** below 2.8 (skip).

Ghost-job flags: over 30 days old, reposted repeatedly, vague JD, recent layoffs, no visible team.

Output: grade, one-line score breakdown, 3 reasons, red flags, recommended action.

### 3. Research

- Company brief (max 150 words): what they sell, ICP, stage and funding, APAC footprint, why they would hire this role now, likely partner types (resellers, SIs, platforms, banks, telcos, marketplaces).
- Hiring team: likely hiring manager title and name if public, recruiter, people the user could ask for a referral.
- Cite sources. Mark anything uncertain.

### 4. Tailor CV

1. Extract JD requirements: must-haves, nice-to-haves, keywords (tools, sales motions, markets, partner types).
2. ATS keyword audit in three buckets: **matched** / **missing but true** (ask the user, then add) / **missing and not true** (do not add; note how to address it in the cover letter or interview).
   - Pull every keyword from the live JD: title words, tools (CRM names), methodologies, product types, buyer personas (C-level, HR, department heads), motions (demos, forecasting, new-logo, partner-sourced), segments and industries, languages.
   - Never silently leave a JD keyword out. Ask the user about every unconfirmed keyword in ONE batch (multiple choice works best), then add every one they confirm.
   - A segment or industry the user has never sold to goes in as a stated target ("Ready to sell into ..."), not as past experience.
3. Rewrite from the master CV: reorder bullets by relevance; 3-line summary using the JD's title words; first line of Skills is "<Company> Fit:" listing the JD's keywords in the JD's own wording (e.g. "Bahasa Indonesia", not "Indonesian"); mirror the same keywords in the summary and the top 2 bullets; bullet formula = action verb + who (partner or client type) + metric + business outcome. Format example only, not user data: "Signed [N] reseller partners across [markets], adding [USD X] pipeline in [timeframe]".
4. ATS-safe format: single column, standard headings (Summary, Experience, Skills, Education), no tables, text boxes or icons holding text, consistent dates (MMM YYYY), 1 page under 8 years of experience otherwise 2, file name `Firstname-Lastname-CV-Company`.
5. Before delivering, run the recruiter 6-second check: (1) summary names role, strength and one proof point; (2) every bullet has a metric, or ask for one; (3) one page; (4) single column, no icons, tables holding text or skill bars; (5) script-check that every JD keyword appears in the PDF text (pdftotext + grep) and fix misses; (6) zero typos and no em dashes.
6. Deliver in the user's preferred format (doc artifact, .docx or PDF) with a short summary of what changed and which JD keywords were added.

### 5. Cover letter and form answers

- Cover letter 200 to 300 words: hook specific to the company's current move (from Research), 2 proof points with numbers mapped to their top 2 needs, why this company and market, clear close.
- Form questions: answer directly and specifically within the field limit. Salary expectation: USD range from the profile (or ask). Work authorization: exactly as written in the profile.
- Optional proof asset (A grade only): a 1-page "APAC partnership snapshot" with their likely partner landscape in Indonesia/SEA, 5 candidate partners with a one-line rationale each, and a 30-60-90 day plan. Label it as an outside-in hypothesis.

### 6. Outreach

Treat each A/B application as a deal with 2 to 3 contacts: recruiter, hiring manager, optionally a peer on the team.

Limits:
- LinkedIn connection note: max 300 characters
- Cold email: max 120 words, subject max 7 words
- X DM: max 280 characters

Structure: specific hook (their move or post) -> one proof point with a number -> small ask (15-minute call, or "who is the right person?"). No attachments on first touch unless asked.

Cadence: Day 0 apply + first touch; Day 4 to 5 follow-up with new value (insight, relevant news); Day 10 to 12 short final nudge; mark Ghosted after Day 21 with no reply.

If Gmail is connected, create drafts, never sends. If Calendar is connected and the user agrees, add follow-up reminders.

### 7. Apply

- Confirm final materials with the user.
- If a browser tool is available: open the form, fill fields from the profile and packet, upload the CV, **stop before Submit**, show a summary of every field value, wait for "submit".
- Hand back to the user for logins, account creation, payments, assessments, and demographic or other sensitive questions.
- After submission: update the tracker (Applied, date, link) and set follow-up dates.

### 8. Track

Columns: ID | Company | Role | Location / Remote | Comp (USD) | Source | Grade | Status | Date sourced | Date applied | Contacts | Last touch | Next action | Next action date | Link | Notes

Statuses: Sourced -> Qualified -> Applied -> Outreach -> Screening -> Interviewing -> Offer -> Accepted / Rejected / Withdrawn / Ghosted

Update the tracker whenever a mode changes something. On "status?": show follow-ups due today, interviews this week, counts by status.

### 9. Interview prep

- Company brief, latest news, product talking points.
- Map 6 to 8 likely questions to story-bank entries. BD question bank: a partnership built from zero; how you prioritize partners; a deal you lost and why; how you would enter Indonesia/SEA for us; pipeline math behind your last quota; working with product and legal on partner terms; handling an underperforming partner; negotiating across cultures in SEA.
- Prepare a 1-page 30-60-90 day plan.
- 5 sharp questions to ask: quota and ramp, who owns the APAC P&L, partner vs direct mix, what success looks like at 6 months, travel.
- Mock mode: one question at a time, wait for the answer, score it (structure, specificity, metrics, brevity), give a tighter version, then the next question. Debrief at the end with the top 3 fixes.
- After each interview: thank-you email within 24 hours (max 100 words, referencing one specific thing discussed); log notes in the application file.

### 10. Offer review

Compare base, variable/OTE and quota attainability, equity, currency and payment setup (USD payroll vs contractor vs EOR), working-hours overlap with WIB, benefits, notice period and probation. Flag gaps against the profile floor. Give facts, not legal or tax advice, and suggest a professional for contract or tax questions. Draft a negotiation email if asked.

### 11. Weekly review

Funnel counts and conversion by stage, results by source, response rate by outreach type, median time to response. What is working, then 3 concrete adjustments for next week (targets, messaging, sources). Keep it to one screen.

---

## Output contract: full Packet

Return in this order:
1. **Verdict:** grade, one-line breakdown, red flags
2. **Company brief**
3. **ATS keyword audit** (three buckets)
4. **Tailored CV** (file or doc) + change summary
5. **Cover letter** (if the application takes one) and **form answers**
6. **Outreach drafts** (recruiter + hiring manager), contact names marked verified or unverified
7. **Tracker row** added
8. **Next actions** with dates in WIB

Keep the chat summary short; long content goes in the doc or file.