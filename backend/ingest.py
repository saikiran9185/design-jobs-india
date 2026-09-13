"""Run every source, normalise, dedupe, store. Entry point: `./run.sh ingest`."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

from . import db
from .normalize import canon_period, is_design_role, sane_salary
from .sources import apis, ats, events, india

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "companies.yaml"
load_dotenv(ROOT / ".env")


def load_config() -> dict:
    if not CONFIG.exists():
        return {"product_companies": [], "studios": []}
    return yaml.safe_load(CONFIG.read_text()) or {}


def clean_salaries(jobs: list[dict]) -> list[dict]:
    """Normalise the period name, and drop a salary that cannot be real."""
    for j in jobs:
        if j.get("salary_min"):
            j["salary_period"] = canon_period(j.get("salary_period"))
            if not sane_salary(j):
                j.update(salary_min=None, salary_max=None,
                         salary_currency=None, salary_period=None, salary_text=None)
    return jobs


def design_only(jobs: list[dict]) -> list[dict]:
    """Last line of defence. Sources mislabel their own categories; we re-check every row."""
    # A competition is not titled like a job — "Mascot Design Challenge 2026" passes,
    # but "Avinya Energy Startup Challenge" would not. Those sources filter themselves.
    return clean_salaries([j for j in jobs
                           if j.get("kind", "job") != "job" or is_design_role(j.get("title", ""))])


def dedupe(jobs: list[dict]) -> list[dict]:
    """Same role posted to three boards is one job. Company+title wins; keep the richest."""
    best: dict[tuple, dict] = {}
    for j in jobs:
        key = ((j.get("company") or "").lower().strip(),
               (j.get("title") or "").lower().strip())
        if not key[1]:
            continue
        cur = best.get(key)
        if cur is None:
            best[key] = j
            continue
        # prefer the record that actually has a salary, then the longer description
        score = lambda x: (x.get("salary_min") is not None, len(x.get("description") or ""))
        if score(j) > score(cur):
            best[key] = j
    return list(best.values())


def run_api_sources(conn, client, only: set[str] | None = None) -> None:
    for name, meta in {**india.REGISTRY, **events.REGISTRY, **apis.REGISTRY}.items():
        if only and name not in only:
            continue
        try:
            jobs = design_only(meta["fn"](client))
            jobs = dedupe(jobs)
            n = db.upsert_jobs(conn, jobs)
            db.log_run(conn, name, len(jobs), n, True, None)
            print(f"  {name:14} {len(jobs):5} found  {n:5} new")
        except RuntimeError as e:                     # missing key — expected, not a failure
            db.log_run(conn, name, 0, 0, True, str(e))
            print(f"  {name:14}     - skipped ({e})")
        except Exception as e:
            db.log_run(conn, name, 0, 0, False, f"{type(e).__name__}: {e}")
            print(f"  {name:14}     ! {type(e).__name__}: {e}")


def run_ats_sources(conn, client) -> None:
    cfg = load_config()
    companies = [c for c in cfg.get("product_companies", [])
                 if c.get("ats") and c["ats"] != "unknown"]
    if not companies:
        print("  (no verified ATS companies yet — run `./run.sh probe` first)")
        return
    total = 0
    for c in companies:
        try:
            jobs = ats.fetch_company(client, c["ats"], c["token"], c["name"])
            n = db.upsert_jobs(conn, dedupe(design_only(jobs)))
            total += n
            if jobs:
                print(f"  {c['name']:22} {c['ats']:16} {len(jobs):3} design roles  {n:3} new")
        except Exception as e:
            print(f"  {c['name']:22} ! {type(e).__name__}")
    db.log_run(conn, "ats", 0, total, True, None)


def main(argv: list[str]) -> int:
    only = set(argv) if argv else None
    db.init()
    with db.connect() as conn, httpx.Client(follow_redirects=True) as client:
        print("\nPublic APIs")
        run_api_sources(conn, client, only)
        if not only:
            print("\nCompany ATS boards")
            run_ats_sources(conn, client)
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        india = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_india=1").fetchone()[0]
    print(f"\n{total} jobs stored  ({india} India, {total - india} remote/global)\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
