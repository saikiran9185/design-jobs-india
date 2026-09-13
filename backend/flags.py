"""Community verification, backed by GitHub Issues.

A static site has no database, but the repo's issue tracker is one: public, free,
auditable, and writable by anyone with a GitHub account. This tallies the issues
into site/data/flags.json, which the page reads to show badges.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data" / "flags.json"
REPO = os.getenv("GITHUB_REPOSITORY", "saikiran9185/design-jobs-india")
ID_RE = re.compile(r"\b([0-9a-f]{16})\b")


def fetch_issues(label: str) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    out, page = [], 1
    with httpx.Client(timeout=30.0) as client:
        while page <= 10:
            r = client.get(f"https://api.github.com/repos/{REPO}/issues",
                           params={"labels": label, "state": "all",
                                   "per_page": 100, "page": page},
                           headers=headers)
            if r.status_code != 200:
                break
            batch = [i for i in r.json() if "pull_request" not in i]
            out += batch
            if len(batch) < 100:
                break
            page += 1
    return out


def tally() -> dict:
    counts: dict[str, dict] = defaultdict(lambda: {"verified": 0, "reported": 0, "reasons": []})
    for label in ("verified", "reported"):
        for issue in fetch_issues(label):
            body = issue.get("body") or ""
            m = ID_RE.search(body) or ID_RE.search(issue.get("title") or "")
            if not m:
                continue
            entry = counts[m.group(1)]
            entry[label] += 1
            # the dropdown answer sits on the line after its heading
            if label == "reported":
                if r := re.search(r"###\s*What is wrong with it\s*\n+\s*(.+)", body):
                    entry["reasons"].append(r.group(1).strip()[:80])
    return counts


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    counts = tally()
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": REPO,
        "flags": {k: {**v, "reasons": sorted(set(v["reasons"]))} for k, v in counts.items()},
    }, indent=1))
    v = sum(1 for f in counts.values() if f["verified"])
    r = sum(1 for f in counts.values() if f["reported"])
    print(f"site/data/flags.json      {v} verified, {r} reported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
