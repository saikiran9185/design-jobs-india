"""Public job APIs. The first four need no key; the last three read keys from .env."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from ..normalize import build_job, is_design_role

TIMEOUT = httpx.Timeout(30.0)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) DesignJobsIndia/0.1"}

DESIGN_QUERIES = ["designer", "design intern", "graphic designer", "ux designer",
                  "motion designer", "3d artist", "product designer"]


def _num(v):
    try:
        return int(float(v)) if v not in (None, "", 0) else None
    except (TypeError, ValueError):
        return None


# --- no key required --------------------------------------------------------
def remoteok(client, **_):
    r = client.get("https://remoteok.com/api", headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json()[1:]:                      # [0] is a legal notice, not a job
        if not is_design_role(j.get("position", ""), " ".join(j.get("tags") or [])):
            continue
        job = build_job(
            source="remoteok", external_id=j.get("id"), title=j.get("position", ""),
            company=j.get("company", ""), location=j.get("location", "") or "Remote",
            description=j.get("description", ""), url=j.get("url", ""),
            posted_at=j.get("date"), remote_hint="remote",
        )
        if _num(j.get("salary_min")):
            job.update(salary_min=_num(j["salary_min"]), salary_max=_num(j.get("salary_max")),
                       salary_currency="USD", salary_period="yearly")
        out.append(job)
    return out


def remotive(client, **_):
    # Their ?category=design is broken upstream — it returns Sales and DevOps roles
    # whose own `category` field says so. Pull everything and classify ourselves.
    r = client.get("https://remotive.com/api/remote-jobs", headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [
        build_job(
            source="remotive", external_id=j.get("id"), title=j.get("title", ""),
            company=j.get("company_name", ""),
            location=j.get("candidate_required_location", "") or "Remote",
            description=j.get("description", ""), url=j.get("url", ""),
            posted_at=j.get("publication_date"), job_type_hint=j.get("job_type", "") or "",
            remote_hint="remote", salary_text=j.get("salary", "") or "",
        )
        for j in r.json().get("jobs", [])
        if is_design_role(j.get("title", ""))   # their "design" category carries QA and DevOps
    ]


def arbeitnow(client, **_):
    r = client.get("https://www.arbeitnow.com/api/job-board-api", headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json().get("data", []):
        if not is_design_role(j.get("title", ""), " ".join(j.get("tags") or [])):
            continue
        posted = j.get("created_at")
        if isinstance(posted, int):
            posted = datetime.fromtimestamp(posted, timezone.utc).isoformat()
        out.append(build_job(
            source="arbeitnow", external_id=j.get("slug"), title=j.get("title", ""),
            company=j.get("company_name", ""), location=j.get("location", ""),
            description=j.get("description", ""), url=j.get("url", ""), posted_at=posted,
            job_type_hint=" ".join(j.get("job_types") or []),
            remote_hint="remote" if j.get("remote") else "",
        ))
    return out


def himalayas(client, **_):
    out, offset = [], 0
    for _page in range(5):                       # 5 x 100 is plenty
        r = client.get(f"https://himalayas.app/jobs/api?limit=100&offset={offset}",
                       headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            cats = " ".join(j.get("categories") or [])
            if not is_design_role(j.get("title", ""), cats):
                continue
            job = build_job(
                source="himalayas", external_id=j.get("guid"), title=j.get("title", ""),
                company=j.get("companyName", ""),
                location=", ".join(j.get("locationRestrictions") or []) or "Remote",
                description=j.get("description") or j.get("excerpt", ""),
                url=j.get("applicationLink", ""), posted_at=j.get("pubDate"),
                job_type_hint=j.get("employmentType", "") or "", remote_hint="remote",
            )
            if _num(j.get("minSalary")):
                job.update(salary_min=_num(j["minSalary"]), salary_max=_num(j.get("maxSalary")),
                           salary_currency=j.get("currency") or "USD",
                           salary_period=(j.get("salaryPeriod") or "yearly").lower())
            out.append(job)
        offset += 100
    return out


# --- key required -----------------------------------------------------------
def adzuna(client, **_):
    app_id, key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and key):
        raise RuntimeError("skip: ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env")
    out = []
    for q in DESIGN_QUERIES:
        r = client.get(
            "https://api.adzuna.com/v1/api/jobs/in/search/1",
            params={"app_id": app_id, "app_key": key, "what": q,
                    "results_per_page": 50, "content-type": "application/json"},
            headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            continue
        for j in r.json().get("results", []):
            job = build_job(
                source="adzuna", external_id=j.get("id"), title=j.get("title", ""),
                company=(j.get("company") or {}).get("display_name", ""),
                location=(j.get("location") or {}).get("display_name", ""), country="India",
                description=j.get("description", ""), url=j.get("redirect_url", ""),
                posted_at=j.get("created"), job_type_hint=j.get("contract_time", "") or "")
            if _num(j.get("salary_min")):
                job.update(salary_min=_num(j["salary_min"]), salary_max=_num(j.get("salary_max")),
                           salary_currency="INR", salary_period="yearly")
            out.append(job)
    return out


def jsearch(client, **_):
    """RapidAPI JSearch — aggregates Google Jobs, LinkedIn and Indeed. Best India coverage."""
    key = os.getenv("RAPIDAPI_KEY")
    if not key:
        raise RuntimeError("skip: RAPIDAPI_KEY not set in .env")
    headers = {**UA, "X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    out = []
    for q in DESIGN_QUERIES:
        r = client.get("https://jsearch.p.rapidapi.com/search",
                       params={"query": f"{q} in India", "page": "1",
                               "num_pages": "2", "country": "in"},
                       headers=headers, timeout=TIMEOUT)
        if r.status_code != 200:
            continue
        for j in r.json().get("data", []):
            loc = ", ".join(x for x in (j.get("job_city"), j.get("job_state")) if x)
            job = build_job(
                source="jsearch", external_id=j.get("job_id"), title=j.get("job_title", ""),
                company=j.get("employer_name", ""), location=loc or "India",
                country=j.get("job_country", "") or "India",
                description=j.get("job_description", ""), url=j.get("job_apply_link", ""),
                posted_at=j.get("job_posted_at_datetime_utc"),
                job_type_hint=j.get("job_employment_type", "") or "",
                remote_hint="remote" if j.get("job_is_remote") else "")
            if _num(j.get("job_min_salary")):
                job.update(salary_min=_num(j["job_min_salary"]),
                           salary_max=_num(j.get("job_max_salary")),
                           salary_currency=j.get("job_salary_currency") or "INR",
                           salary_period=(j.get("job_salary_period") or "yearly").lower())
            out.append(job)
    return out


def jooble(client, **_):
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        raise RuntimeError("skip: JOOBLE_API_KEY not set in .env")
    out = []
    for q in DESIGN_QUERIES[:4]:
        r = client.post(f"https://jooble.org/api/{key}",
                        json={"keywords": q, "location": "India", "page": "1"},
                        headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            continue
        for j in r.json().get("jobs", []):
            out.append(build_job(
                source="jooble", external_id=j.get("id"), title=j.get("title", ""),
                company=j.get("company", ""), location=j.get("location", ""), country="India",
                description=j.get("snippet", ""), url=j.get("link", ""),
                posted_at=j.get("updated"), job_type_hint=j.get("type", "") or "",
                salary_text=j.get("salary", "") or ""))
    return out


REGISTRY = {
    "remoteok":   {"fn": remoteok,   "needs_key": False, "note": "remote, global"},
    "remotive":   {"fn": remotive,   "needs_key": False, "note": "remote, design category"},
    "arbeitnow":  {"fn": arbeitnow,  "needs_key": False, "note": "remote + EU"},
    "himalayas":  {"fn": himalayas,  "needs_key": False, "note": "remote, structured salary"},
    "adzuna":     {"fn": adzuna,     "needs_key": True,  "note": "India, 250 calls/day free"},
    "jsearch":    {"fn": jsearch,    "needs_key": True,  "note": "Google/LinkedIn/Indeed via RapidAPI"},
    "jooble":     {"fn": jooble,     "needs_key": True,  "note": "India"},
}
