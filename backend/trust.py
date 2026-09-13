"""Employer trust signals, computed from data this project actually owns.

Deliberately not a star rating. Inventing a 5-star score out of signals that do not
measure employee satisfaction would look authoritative and mean nothing, which is
worse than showing no rating. Scraping Glassdoor or AmbitionBox was the other
option and was rejected: republishing someone else's review corpus on a public
site is a rights problem, and it would break the moment they changed their markup.

What is shown instead is explainable, and every part of it can be checked:

  verified board   the company publishes jobs through a real ATS we can reach
  contactable      a careers mailbox on the company's own domain
  N live listings  how much they are actually hiring right now
  community        confirmations and reports from people using the site
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "data"

# Sources where a posting had to pass through a company's own hiring system.
FIRST_PARTY = {"greenhouse", "lever", "ashby", "workable", "recruitee", "smartrecruiters"}


def build(jobs: list[dict], flags: dict) -> dict:
    """One record per employer, with the reasons spelled out."""
    cfg = yaml.safe_load((ROOT / "config" / "companies.yaml").read_text()) or {}
    verified_ats, has_email = {}, {}
    for key in ("product_companies", "studios"):
        for c in cfg.get(key, []):
            name = (c.get("name") or "").strip().lower()
            if not name:
                continue
            if c.get("verified") and c.get("ats") not in (None, "unknown"):
                verified_ats[name] = c["ats"]
            if c.get("email"):
                has_email[name] = c["email"]

    agg: dict[str, dict] = defaultdict(
        lambda: {"listings": 0, "first_party": 0, "verified": 0, "reported": 0,
                 "cities": set(), "with_pay": 0})

    for j in jobs:
        name = (j.get("company") or "").strip()
        if not name:
            continue
        a = agg[name.lower()]
        a["name"] = name
        a["listings"] += 1
        if j.get("source") in FIRST_PARTY:
            a["first_party"] += 1
        if j.get("pay_inr_month"):
            a["with_pay"] += 1
        if j.get("city") and j["city"] != "India":
            a["cities"].add(j["city"])
        f = flags.get(j.get("id")) or {}
        a["verified"] += f.get("verified", 0)
        a["reported"] += f.get("reported", 0)

    out = {}
    for key, a in agg.items():
        reasons = []
        if key in verified_ats:
            reasons.append(f"publishes through {verified_ats[key]}")
        elif a["first_party"]:
            reasons.append("publishes through its own hiring system")
        if key in has_email:
            reasons.append("careers address on its own domain")
        if a["with_pay"]:
            reasons.append(f"{a['with_pay']} listing(s) state pay openly")
        if a["verified"]:
            reasons.append(f"{a['verified']} confirmation(s) from people here")

        # A company is "known" when its identity is independently checkable — not
        # a judgement about what it is like to work there.
        known = bool(key in verified_ats or a["first_party"] or key in has_email)

        out[key] = {
            "name": a.get("name", key), "listings": a["listings"],
            "cities": sorted(a["cities"])[:4],
            "verified": a["verified"], "reported": a["reported"],
            "known": known, "reasons": reasons,
        }
    return out


def main() -> int:
    jobs = json.loads((SITE / "jobs.json").read_text())["jobs"]
    flags_path = SITE / "flags.json"
    flags = json.loads(flags_path.read_text()).get("flags", {}) if flags_path.exists() else {}
    data = build(jobs, flags)
    (SITE / "employers.json").write_text(
        json.dumps({"count": len(data), "employers": data}, ensure_ascii=False,
                   separators=(",", ":")))
    known = sum(1 for v in data.values() if v["known"])
    print(f"site/data/employers.json  {len(data)} employers, {known} independently checkable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
