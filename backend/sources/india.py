"""India-native sources. These are what actually make the site useful here.

Western ATS boards barely cover India — most Indian companies never touch Greenhouse.
Unstop is the big one: thousands of design jobs, internships and competitions,
with salaries already denominated in rupees.
"""
from __future__ import annotations

import httpx

from ..normalize import build_job, is_design_role

TIMEOUT = httpx.Timeout(30.0)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Accept": "application/json"}

# Searched separately because Unstop matches on title, not category.
TERMS = ["designer", "design", "graphic design", "ui ux", "motion graphics",
         "animation", "3d artist", "video editor", "illustrator", "branding"]

CURRENCY = {"fa-rupee": "INR", "fa-dollar": "USD", "fa-euro": "EUR"}


def _unstop_page(client, kind: str, term: str, page: int) -> tuple[list, int]:
    r = client.get("https://unstop.com/api/public/opportunity/search-result",
                   params={"opportunity": kind, "searchTerm": term,
                           "per_page": 50, "page": page},
                   headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json().get("data", {})
    return d.get("data", []) or [], d.get("last_page", 1) or 1


def _skills(item: dict) -> str:
    """required_skills is a list of dicts on some records and plain strings on others."""
    out = []
    for s in item.get("required_skills") or []:
        out.append(s.get("skill_name") or s.get("skill", "") if isinstance(s, dict) else str(s))
    return " ".join(x for x in out if x)


def _unstop_job(item: dict, kind: str) -> dict | None:
    title = item.get("title", "")
    if not is_design_role(title):
        return None

    org = (item.get("organisation") or {}).get("name", "")
    detail = item.get("jobDetail") or item.get("internshipDetail") or {}

    cities = [l.get("city") for l in (item.get("locations") or []) if l.get("city")]
    cities = cities or [c for c in (detail.get("locations") or []) if c]
    location = ", ".join(dict.fromkeys(cities)) or "India"

    mode = (detail.get("type") or "").lower()          # in_office | remote | hybrid
    remote_hint = {"in_office": "onsite", "work_from_home": "remote"}.get(mode, mode)

    timing = (detail.get("timing") or "").lower()      # full_time | part_time
    hint = "internship" if kind == "internships" else timing.replace("_", " ")

    url = item.get("seo_url") or (
        "https://unstop.com/" + (item.get("public_url") or "").lstrip("/"))

    job = build_job(
        source=f"unstop-{kind}", external_id=item.get("id"), title=title,
        company=org, location=location, country="India",
        description=_skills(item) or title,
        url=url, posted_at=item.get("updated_at"),
        job_type_hint=hint, remote_hint=remote_hint,
    )

    # Unstop publishes structured pay in rupees — far better than parsing prose.
    if detail.get("show_salary") and detail.get("min_salary"):
        period = "monthly" if (detail.get("pay_in") or "").startswith("month") else "yearly"
        job.update(salary_min=int(detail["min_salary"]),
                   salary_max=int(detail["max_salary"]) if detail.get("max_salary") else None,
                   salary_currency=CURRENCY.get(detail.get("currency"), "INR"),
                   salary_period=period, salary_text=None)
    job["is_india"] = 1                                 # Unstop is an India-only platform
    job["kind"] = {"competitions": "competition"}.get(kind, "job")
    if kind == "internships":
        job["job_type"] = "internship"
    return job


def unstop(client, kinds=("jobs", "internships"), max_pages=4, **_):
    out, seen = [], set()
    for kind in kinds:
        for term in TERMS:
            try:
                items, last = _unstop_page(client, kind, term, 1)
            except Exception:
                continue
            for page in range(2, min(last, max_pages) + 1):
                try:
                    more, _ = _unstop_page(client, kind, term, page)
                    items += more
                except Exception:
                    break
            for it in items:
                if it.get("id") in seen:
                    continue
                seen.add(it.get("id"))
                if job := _unstop_job(it, kind):
                    out.append(job)
    return out


def unstop_competitions(client, **_):
    """Design competitions and hackathons — the thing LinkedIn buries."""
    return unstop(client, kinds=("competitions",), max_pages=3)


def instahyre(client, **_):
    out = []
    for page in range(3):
        try:
            r = client.get("https://www.instahyre.com/api/v1/job_search",
                           params={"job_type": 1, "limit": 100, "offset": page * 100},
                           headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            objs = r.json().get("objects", [])
        except Exception:
            break
        if not objs:
            break
        for j in objs:
            title = j.get("title", "")
            if not is_design_role(title):
                continue
            emp = j.get("employer") or {}
            locs = j.get("locations") or []
            city = ", ".join(l.get("city", {}).get("name", "") if isinstance(l, dict) else str(l)
                             for l in locs if l) or "India"
            out.append(build_job(
                source="instahyre", external_id=j.get("id"), title=title,
                company=emp.get("company_name") or emp.get("name", ""),
                location=city, country="India",
                description=" ".join(j.get("keywords") or []),
                url="https://www.instahyre.com" + (j.get("public_url") or ""),
            ))
    return out


REGISTRY = {
    "unstop":              {"fn": unstop,              "needs_key": False, "note": "India jobs + internships"},
    "unstop-competitions": {"fn": unstop_competitions, "needs_key": False, "note": "India design competitions"},
    "instahyre":           {"fn": instahyre,           "needs_key": False, "note": "India product/startup jobs"},
}
