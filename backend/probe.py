"""Find each company's real ATS by trying token variants against every provider.

Greenhouse hosts Razorpay at 'razorpaysoftwareprivatelimited', not 'razorpay' —
guessing does not work, so we test every candidate and keep only what answers.
Runs concurrently; a full 100-company sweep takes a few minutes.
"""
from __future__ import annotations

import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import yaml

from .sources.ats import ADAPTERS

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "companies.yaml"
WORKERS = 16
_print_lock = threading.Lock()


def variants(name: str, token: str) -> list[str]:
    base = re.sub(r"[^a-z0-9]", "", name.lower())
    cands = [token, base, f"{base}softwareprivatelimited", f"{base}technologies",
             f"{base}software", re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")]
    seen, out = set(), []
    for v in cands:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def probe_company(company: dict) -> dict:
    name, token = company["name"], company.get("token", "")
    with httpx.Client(follow_redirects=True, timeout=8.0) as client:
        for tok in variants(name, token):
            for ats_name, fn in ADAPTERS.items():
                try:
                    jobs = list(fn(client, tok, name))
                except Exception:
                    continue
                if jobs:
                    company.update(ats=ats_name, token=tok, verified=True)
                    with _print_lock:
                        print(f"  OK   {name:18} {ats_name:16} {tok:34} {len(jobs):4} roles")
                    return company
    company.update(ats="unknown", verified=False)
    return company


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text()) or {}
    companies = cfg.get("product_companies", [])
    print(f"Probing {len(companies)} companies x {len(ADAPTERS)} ATS providers "
          f"({WORKERS} at a time)...\n")

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(probe_company, c) for c in companies]
        for _ in as_completed(futures):
            pass

    found = [c for c in companies if c.get("verified")]
    cfg["product_companies"] = sorted(companies, key=lambda c: (not c.get("verified"), c["name"]))
    CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False, width=200))
    print(f"\n{len(found)}/{len(companies)} verified -> {CONFIG.relative_to(ROOT)}")
    print("The rest have no public board — they hire over email, so they sit in "
          "the Outreach tab instead.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
