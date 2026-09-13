"""Two-way sync with Supabase.

  pull  — approved public submissions become listings in the local database
  push  — every listing is mirrored to Supabase so the "All jobs" toggle can page
          through more than the static bundle could ever carry

Both are no-ops when the credentials are absent, so the project keeps working as a
plain static site until Supabase is connected.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from . import db
from .normalize import build_job, canon_period, sane_salary

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
# service_role bypasses row-level security. It belongs in Actions secrets and .env,
# never in anything served to a browser.
KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
BATCH = 500


def configured() -> bool:
    return bool(URL and KEY)


def _headers(extra: dict | None = None) -> dict:
    return {"apikey": KEY, "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json", **(extra or {})}


def pull_submissions() -> int:
    """Approved submissions join the main dataset, tagged so their origin is visible."""
    if not configured():
        print("  supabase: not configured, skipping pull")
        return 0
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{URL}/rest/v1/submissions",
                       params={"status": "eq.approved", "select": "*", "limit": 2000},
                       headers=_headers())
        r.raise_for_status()
        rows = r.json()

    jobs = []
    for s in rows:
        job = build_job(
            source="community", external_id=s["id"], title=s.get("title", ""),
            company=s.get("company") or "", location=s.get("location") or "",
            description=s.get("description") or "", url=s.get("url") or s.get("source_url") or "",
            posted_at=s.get("created_at"), job_type_hint=s.get("job_type") or s.get("kind") or "",
            salary_text=s.get("salary_text") or "", image=s.get("image_url"))
        job["kind"] = s.get("kind") or "job"
        job["deadline"] = s.get("deadline")
        if job.get("salary_min"):
            job["salary_period"] = canon_period(job.get("salary_period"))
            if not sane_salary(job):
                job.update(salary_min=None, salary_max=None,
                           salary_currency=None, salary_period=None)
        jobs.append(job)

    if not jobs:
        print("  supabase: no approved submissions yet")
        return 0
    with db.connect() as conn:
        n = db.upsert_jobs(conn, jobs)
        db.log_run(conn, "community", len(jobs), n, True, None)
        conn.commit()
    print(f"  supabase: {len(jobs)} approved submissions, {n} new")
    return n


def push_listings() -> int:
    """Mirror every listing so the All-jobs view can query instead of downloading."""
    if not configured():
        print("  supabase: not configured, skipping push")
        return 0
    from .app import FX_TO_INR
    from .normalize import monthly_inr

    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE hidden = 0").fetchall()

    payload = []
    for r in rows:
        d = dict(r)
        payload.append({
            "id": d["id"], "source": d["source"], "title": d["title"],
            "company": d["company"], "location": d["location"], "city": d["city"],
            "country": d["country"], "remote": d["remote"], "job_type": d["job_type"],
            "kind": d.get("kind") or "job", "discipline": d["discipline"],
            "is_design": True, "is_india": bool(d["is_india"]),
            "salary_min": d["salary_min"], "salary_max": d["salary_max"],
            "salary_currency": d["salary_currency"], "salary_period": d["salary_period"],
            "pay_inr_month": monthly_inr(d, fx=FX_TO_INR.get(d["salary_currency"] or "INR", 1.0)),
            "url": d["url"], "image": d.get("image"),
            "lat": d.get("lat"), "lng": d.get("lng"),
            "posted_at": d["posted_at"], "deadline": d.get("deadline"),
            "recurring": bool(d.get("recurring")),
        })

    sent = 0
    with httpx.Client(timeout=60.0) as client:
        for i in range(0, len(payload), BATCH):
            chunk = payload[i:i + BATCH]
            resp = client.post(f"{URL}/rest/v1/listings",
                               headers=_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
                               json=chunk)
            if resp.status_code >= 300:
                print(f"  supabase: push failed ({resp.status_code}) {resp.text[:160]}")
                break
            sent += len(chunk)
    print(f"  supabase: pushed {sent} listings")
    return sent


def main(argv: list[str]) -> int:
    if not configured():
        print("SUPABASE_URL / SUPABASE_SERVICE_KEY not set — nothing to do.")
        print("Run supabase/schema.sql, then add them to .env or Actions secrets.")
        return 0
    db.init()
    if "push" in argv:
        push_listings()
    if "pull" in argv or not argv:
        pull_submissions()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
