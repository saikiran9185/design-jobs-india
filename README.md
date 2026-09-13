# Design Jobs India

### → **[saikiran9185.github.io/design-jobs-india](https://saikiran9185.github.io/design-jobs-india/)**

Design jobs, internships and freelance work across India, **collected** from company job
boards and public job APIs into one filterable place. It is not a job board — companies
never register here. Nothing is posted; everything is pulled, and it refreshes itself
every morning at 08:00 IST.

Open the link. Nothing to install.

---

## Running it locally

Only needed if you want to add sources, change the company list, or upload your own CSVs.

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

**Competitions, challenges and hackathons.** Unstop competitions, **MyGov / Innovate India**
(the government's design challenges, logo and mascot contests, reel and poster competitions)
via their RSS feeds, and **Devfolio** for Indian student hackathons with live deadlines.
Filter them with the **Show** chips at the top of the sidebar.

**What cannot be collected: Instagram.** Many Indian studios post openings only to Instagram
stories. There is no public API for that, Meta's Graph API does not expose other accounts'
posts, and scraping gets blocked and banned. Those go in by hand through CSV upload or a
pull request — there is no honest automated route.

**Your own uploads.** Drag a CSV in. Jobs you found on Instagram, WhatsApp or a studio's
own site live alongside everything else. Only a `title` column is required; `company`,
`location`, `url`, `salary`, `job_type`, `description`, `posted_at` are all optional.
Uploads skip the design filter — if you added it, it stays.

---

## Verified and reported listings

There is no gatekeeper. Every card has **✓ verify** and **⚠ report** buttons that open a
pre-filled GitHub issue — anyone with a free GitHub account can submit one. A workflow
tallies the issue tracker daily into `site/data/flags.json` and the site shows the counts.

Because the store is the repo's own issue tracker, every claim is public, attributable and
reversible. Nothing is hidden in a private database.

Reported listings are hidden by default (unless verifications outnumber reports). The single
most useful thing to report: any "internship" that asks you to pay a registration, training
or security fee. That is the most common scam in Indian design hiring and it is never
legitimate.

---

## Honest limitation: India coverage

**Solved, mostly.** Adding Unstop and Instahyre took India from 10 jobs to over 2,000,
because Western ATS platforms simply are not what Indian companies use. Naukri requires a
captcha and Indeed returns 403, so both are out; Keka and Darwinbox publish no open API.

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

## How the hosted version works

GitHub Pages cannot run Python, so the published site is pure HTML/JS reading two JSON files.
GitHub Actions does the work:

| Workflow | When | What |
|---|---|---|
| `refresh.yml` | daily 08:00 IST + on push | ingest → export → commit `site/data/*.json` → deploy Pages |
| `probe.yml` | 1st of each month | re-probe ATS tokens, open a PR if anything moved |

Run either by hand from the **Actions** tab.

**To add API keys to the hosted build:** repo **Settings → Secrets and variables → Actions →
New repository secret**. Names: `RAPIDAPI_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`,
`JOOBLE_API_KEY`. The workflow picks them up on the next run.

On the live site your stars, applied marks and outreach notes are saved in **your browser
only** — they are never uploaded and never visible to anyone else. Export CSV to keep a copy.

Running `ingest` locally never loses your stars or notes either — jobs are upserted by ID.

---

## Contact details

`config/companies.yaml` holds the directory. `./run.sh contacts` visits each studio's own
website and extracts **only role mailboxes on their own domain** — `careers@`, `hr@`,
`hello@`, `info@`. It never invents an address, and it deliberately skips named individuals'
addresses: a person's own email is not ours to publish, and a careers inbox is the right
place for a placement enquiry anyway.

Addresses that turn out to be a global office rather than the India desk are moved to
`email_global_office` with a note, so you do not email Ogilvy Germany about a Delhi drive.

About half of Indian studios publish no email at all — they use a contact form. Those stay
blank for you to fill in as you find them.
