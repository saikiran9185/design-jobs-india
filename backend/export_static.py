"""Dump the database to a static JSON bundle for GitHub Pages.

Pages cannot run Python, so the published site is pure HTML/JS reading these files.
GitHub Actions runs the ingest, then this, then deploys `site/`.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import db
from .app import FX_TO_INR
from .normalize import monthly_inr as _monthly

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "data"

FIELDS = ["id", "source", "title", "company", "location", "city", "remote", "job_type",
          "discipline", "salary_min", "salary_max", "salary_currency", "salary_period",
          "url", "apply_email", "posted_at", "is_india", "kind", "deadline"]


def monthly_inr(r) -> int | None:
    """Everything is shown in rupees, so convert once here instead of in the browser."""
    return _monthly(dict(r), fx=FX_TO_INR.get(r["salary_currency"] or "INR", 1.0))


def export_jobs(conn) -> int:
    rows = conn.execute(
        f"SELECT {','.join(FIELDS)} FROM jobs WHERE hidden=0 ORDER BY posted_at DESC").fetchall()
    jobs = []
    for r in rows:
        j = {k: r[k] for k in FIELDS}
        j["discipline"] = [x for x in (r["discipline"] or "").split(",") if x]
        m = monthly_inr(r)
        j["pay_inr_month"] = m
        j["pay_inr_year"] = m * 12 if m else None
        j["description"] = None          # keep the bundle small; the link has the detail
        jobs.append(j)
    kinds: dict[str, int] = {}
    for j in jobs:
        kinds[j.get("kind") or "job"] = kinds.get(j.get("kind") or "job", 0) + 1
    (DATA / "jobs.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "india": sum(1 for j in jobs if j["is_india"]),
        "kinds": kinds,
        "jobs": jobs,
    }, ensure_ascii=False, separators=(",", ":")))
    return len(jobs)


def export_companies() -> int:
    """Contact directory — the outreach side, versioned in the repo."""
    cfg = yaml.safe_load((ROOT / "config" / "companies.yaml").read_text()) or {}
    out = []
    for kind, key in (("product", "product_companies"), ("studio", "studios")):
        for c in cfg.get(key, []):
            out.append({
                "name": c.get("name"), "city": c.get("city"), "kind": kind,
                "site": c.get("site"), "email": c.get("email"),
                "careers": c.get("careers"), "phone": c.get("phone"),
                "ats": c.get("ats") if c.get("verified") else None,
                "notes": c.get("notes"),
            })
    out.sort(key=lambda c: (c["kind"] != "studio", c.get("city") or "", c["name"]))
    (DATA / "companies.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(out), "companies": out,
    }, ensure_ascii=False, indent=1))
    return len(out)


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    db.init()
    with db.connect() as conn:
        n_jobs = export_jobs(conn)
    n_co = export_companies()
    size = (DATA / "jobs.json").stat().st_size / 1024
    print(f"site/data/jobs.json       {n_jobs:5} jobs      {size:.0f} KB")
    print(f"site/data/companies.json  {n_co:5} companies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
