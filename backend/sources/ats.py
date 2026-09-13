"""Applicant-tracking-system adapters.

These are the good sources: public, structured, stable, no key, no ToS fight.
Each takes a company token and returns raw postings; the caller normalises.
"""
from __future__ import annotations

import httpx

from ..normalize import build_job, is_design_role

TIMEOUT = httpx.Timeout(20.0)
UA = {"User-Agent": "DesignJobsIndia/0.1 (personal job aggregator)"}


def _get(client: httpx.Client, url: str, **kw):
    r = client.get(url, headers=UA, timeout=TIMEOUT, follow_redirects=True, **kw)
    r.raise_for_status()
    return r.json()


# --- individual ATS ---------------------------------------------------------
def greenhouse(client, token, company):
    data = _get(client, f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    for j in data.get("jobs", []):
        yield build_job(
            source="greenhouse", external_id=j.get("id"), title=j.get("title", ""),
            company=company, location=(j.get("location") or {}).get("name", ""),
            description=j.get("content", ""), url=j.get("absolute_url", ""),
            posted_at=j.get("updated_at"),
        )


def lever(client, token, company):
    data = _get(client, f"https://api.lever.co/v0/postings/{token}?mode=json")
    for j in data if isinstance(data, list) else []:
        cat = j.get("categories") or {}
        yield build_job(
            source="lever", external_id=j.get("id"), title=j.get("text", ""),
            company=company, location=cat.get("location", "") or "",
            description=j.get("descriptionPlain") or j.get("description", ""),
            url=j.get("hostedUrl", ""), job_type_hint=cat.get("commitment", "") or "",
            posted_at=j.get("createdAt"),
        )


def ashby(client, token, company):
    data = _get(client, f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")
    for j in data.get("jobs", []):
        comp = j.get("compensation") or {}
        yield build_job(
            source="ashby", external_id=j.get("id"), title=j.get("title", ""),
            company=company, location=j.get("location", "") or "",
            description=j.get("descriptionPlain") or j.get("descriptionHtml", ""),
            url=j.get("jobUrl", ""), job_type_hint=j.get("employmentType", "") or "",
            posted_at=j.get("publishedAt"),
            salary_text=str(comp.get("compensationTierSummary") or ""),
        )


def workable(client, token, company):
    data = _get(client, f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true")
    for j in data.get("jobs", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        yield build_job(
            source="workable", external_id=j.get("shortcode") or j.get("id"),
            title=j.get("title", ""), company=company, location=loc,
            country=j.get("country", "") or "",
            description=j.get("description", "") or "", url=j.get("url", ""),
            job_type_hint=j.get("employment_type", "") or "", posted_at=j.get("published_on"),
        )


def recruitee(client, token, company):
    data = _get(client, f"https://{token}.recruitee.com/api/offers/")
    for j in data.get("offers", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        yield build_job(
            source="recruitee", external_id=j.get("id"), title=j.get("title", ""),
            company=company, location=loc or j.get("location", "") or "",
            country=j.get("country", "") or "",
            description=j.get("description", "") or "",
            url=j.get("careers_url") or j.get("careers_apply_url", ""),
            job_type_hint=j.get("employment_type_code", "") or "",
            posted_at=j.get("published_at"),
        )


def smartrecruiters(client, token, company):
    data = _get(client, f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100")
    for j in data.get("content", []):
        loc = j.get("location") or {}
        where = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)
        yield build_job(
            source="smartrecruiters", external_id=j.get("id"), title=j.get("name", ""),
            company=company, location=where, country=loc.get("country", "") or "",
            description=(j.get("jobAd") or {}).get("sections", {}).get("jobDescription", {}).get("text", ""),
            url=f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}",
            job_type_hint=(j.get("typeOfEmployment") or {}).get("label", "") or "",
            posted_at=j.get("releasedDate"),
        )


ADAPTERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workable": workable,
    "recruitee": recruitee,
    "smartrecruiters": smartrecruiters,
}


def fetch_company(client: httpx.Client, ats: str, token: str, company: str,
                  design_only: bool = True) -> list[dict]:
    fn = ADAPTERS.get(ats)
    if not fn:
        return []
    jobs = list(fn(client, token, company))
    if design_only:
        jobs = [j for j in jobs if is_design_role(j["title"], j["description"])]
    return jobs


def probe(client: httpx.Client, token: str) -> str | None:
    """Try every ATS for this token. Returns the one that resolves, or None."""
    for name, fn in ADAPTERS.items():
        try:
            if list(fn(client, token, token))[:1] or True:
                # a 200 with parseable shape is enough; empty boards still count
                return name
        except Exception:
            continue
    return None
