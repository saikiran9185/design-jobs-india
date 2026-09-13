# Design Jobs India

A local Mac web app that **collects** design jobs, internships and freelance gigs from many
sources into one filterable place. It is not a job board — companies never register here.
Nothing is posted; everything is pulled.

```bash
./run.sh probe     # find which companies have a public job board  (run once, ~3 min)
./run.sh ingest    # pull fresh jobs from every source             (run daily)
./run.sh           # open http://localhost:8000
```

First run installs everything automatically. No account, no cloud — the database is a single
file at `data/jobs.db`.

---

## Where the jobs come from

**Company job boards (no key needed).** The good sources: public, structured, stable.
`./run.sh probe` tests all 102 companies in `config/companies.yaml` against six ATS providers
and keeps only the ones that answer.

| Provider | Verified companies |
|---|---|
| Greenhouse | Figma, Razorpay, Postman, Groww, Vercel, Databricks, Intercom, Twilio, GitLab… |
| Ashby | Notion, Linear, Snowflake, Navi, Miro, Sentry, Zapier… |
| SmartRecruiters | Swiggy, Canva, Freshworks, Unacademy, Upstox, ixigo… |
| Lever | CRED, Meesho, Zeta |
| Workable, Recruitee | supported, none matched yet |

**34 of 102 verified.** The other 68 have no public board — they hire over email, so they
appear in the **Outreach** tab instead of the job list.

**Public APIs (no key needed).** RemoteOK, Arbeitnow, Himalayas — remote and global.
Remotive is wired up but its free API currently returns only ~16 jobs total and its
`category=design` filter is broken upstream, so it contributes little.

**Optional APIs (add a key).** This is how you get real India coverage — see below.

**Your own uploads.** Drag a CSV in. Jobs you found on Instagram, WhatsApp or a studio's
own site live alongside everything else. Only a `title` column is required; `company`,
`location`, `url`, `salary`, `job_type`, `description`, `posted_at` are all optional.
Uploads skip the design filter — if you added it, it stays.

---

## Honest limitation: India coverage

Right now about **1 in 10** jobs is in India. That is not a bug, it is what free sources give:
most Indian companies use Keka, Darwinbox or Zoho Recruit, which have no public job API,
and the free remote boards are US/EU heavy.

**Two ways to fix it, both real:**

1. **Add an API key** (5 minutes). Edit `.env`, then `./run.sh ingest`.
   - **JSearch via RapidAPI** — the big one. Aggregates Google Jobs, LinkedIn and Indeed.
     Best India coverage by far. <https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch>
   - **Adzuna** — India endpoint, 250 free calls/day. <https://developer.adzuna.com/>
   - **Jooble** — India. <https://jooble.org/api/about>

2. **Add more companies.** Append to `config/companies.yaml` and re-run `./run.sh probe`.
   Every Indian studio you add also feeds the Outreach tab, so this is not wasted work.

---

## Salary

Most Indian listings publish no salary — that is normal, not a failure. The parser handles
`₹50,000 - ₹75,000`, `8-12 LPA`, `25k-40k` and `INR 6,00,000 per annum`, and normalises
everything to monthly INR so one slider compares across sources and currencies.
The **"Only jobs that list pay"** checkbox hides the rest. Exchange rates in
`backend/app.py` (`FX_TO_INR`) are approximate and only used for that comparison.

---

## The Outreach tab

For bringing companies to your college. Every company from `companies.yaml` is listed,
including the 68 with no job board. Fill in an HR email, set a status
(new → contacted → replied → confirmed / declined), leave notes. Setting "contacted"
stamps the date automatically. Everything saves as you type.

---

## Filters

Search text · India / global · city · remote / hybrid / onsite · full-time / internship /
freelance / contract · discipline (product, ux, ui, graphic, motion, 3d, brand, illustration,
game, industrial, research…) · minimum pay · posted within N days · source · starred ·
hide applied.

Star jobs to shortlist them, mark them applied, hide the rest. Export any view to CSV.

---

## How it decides what is a design job

ATS boards return *every* role a company has, so everything is classified by **title**, never
by description — matching on description pulled in DevOps and sales roles that merely mentioned
"brand" or "render". Word boundaries matter too: `internal` and `international` both contain
`intern`. Every row is re-checked centrally in `ingest.py`, so a source mislabelling its own
data cannot leak junk through.

Tune the vocabulary in `backend/normalize.py` — `DISCIPLINES`, `_DESIGN_TITLE`, `_NOT_DESIGN`.

---

## Layout

```
run.sh                  start / ingest / probe
config/companies.yaml   who to poll; `probe` rewrites this
.env                    optional API keys
backend/
  normalize.py          one Job shape; all classification and salary parsing
  db.py                 SQLite schema; upsert preserves your stars and notes
  ingest.py             runs every source, dedupes, stores
  probe.py              concurrent ATS discovery
  app.py                FastAPI: search, facets, upload, outreach, export
  sources/ats.py        Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters
  sources/apis.py       RemoteOK, Remotive, Arbeitnow, Himalayas, Adzuna, JSearch, Jooble
frontend/               vanilla HTML/CSS/JS, no build step
data/jobs.db            everything, in one file
```

## Keeping it fresh

```bash
# refresh every morning at 9
(crontab -l 2>/dev/null; echo "0 9 * * * cd ~/DesignJobsIndia && ./run.sh ingest") | crontab -
```

Re-running ingest never loses your stars, applied marks or notes — jobs are upserted by ID.
