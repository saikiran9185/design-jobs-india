"""Discover real careers/contact emails from each studio's own website.

Never invents an address. It fetches the homepage plus the usual contact and careers
paths, extracts what is actually published, and prefers hiring-related mailboxes.
Anything it cannot find stays blank for you to fill in by hand.
"""
from __future__ import annotations

import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "companies.yaml"

PATHS = ["", "/contact", "/contact-us", "/careers", "/career", "/jobs",
         "/about", "/work-with-us", "/join-us"]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
_lock = threading.Lock()

HIRING = ("career", "job", "hr", "recruit", "join", "work", "intern", "people", "talent", "apply")

# Only role mailboxes are kept. A named person's address (firstname.lastname@) is
# somebody's personal contact detail — it does not belong in a public repo, and a
# careers inbox is the right place to send a placement enquiry anyway.
ROLE_PREFIXES = (
    "career", "careers", "job", "jobs", "hr", "recruit", "recruitment", "recruiting",
    "hello", "info", "contact", "enquiry", "enquiries", "inquiry", "reachus",
    "work", "workwithus", "apply", "talent", "people", "connect", "studio",
    "mail", "office", "team", "hi", "we", "design", "admin", "support", "general",
)
PLACEHOLDER = ("user@", "name@", "email@", "yourname", "your-email", "example",
               "domain.com", "test@", "sample", "someone@", "firstname", "lastname",
               "abc@", "xyz@", "no-reply", "noreply", "donotreply")
JUNK = ("sentry.io", "wixpress", "godaddy", "squarespace", "cloudflare", "@2x", "@3x",
        ".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".css", ".js", "u003e")


def _root(host: str) -> str:
    """foo.co.uk / www.foo.com -> foo — enough to tell own-domain from someone else's."""
    host = host.replace("www.", "").lower().replace("-", "")   # cosmos-maya == cosmosmaya
    parts = host.split(".")
    return parts[-3] if len(parts) > 2 and parts[-2] in ("co", "com", "org", "net") else \
           (parts[-2] if len(parts) > 1 else host)


def acceptable(email: str, site: str) -> bool:
    if any(j in email for j in JUNK) or any(p in email for p in PLACEHOLDER):
        return False
    try:
        local, host = email.split("@")
    except ValueError:
        return False
    if _root(host) != _root(site):          # a third party's address, not theirs
        return False
    local = local.lower()
    if not any(local == r or local.startswith(r) for r in ROLE_PREFIXES):
        return False                         # named individual — deliberately skipped
    return True


def score(email: str) -> tuple:
    local = email.split("@")[0].lower()
    return (any(h in local for h in HIRING), -len(email))   # careers@ beats hello@


def emails_from(client: httpx.Client, base: str, domain: str) -> list[str]:
    found: set[str] = set()
    for path in PATHS:
        try:
            r = client.get(f"https://{base}{path}", headers=UA, timeout=12.0,
                           follow_redirects=True)
            if r.status_code != 200:
                continue
        except Exception:
            continue
        text = r.text
        # mailto: links are the reliable signal; plain text is the fallback
        for m in re.findall(r'mailto:([^"\'?>\s]+)', text) + EMAIL_RE.findall(text):
            e = m.strip().strip(".,;:").lower()
            if len(e) >= 6 and acceptable(e, domain):
                found.add(e)
        if found and path:
            break
    return sorted(found, key=score, reverse=True)


def work(entry: dict) -> dict:
    site = (entry.get("site") or "").strip().replace("https://", "").replace("http://", "").rstrip("/")
    if not site or entry.get("email"):
        return entry
    with httpx.Client(follow_redirects=True) as client:
        hits = emails_from(client, site, site)
    if hits:
        entry["email"] = hits[0]
        if len(hits) > 1:
            entry["other_emails"] = hits[1:4]
        with _lock:
            print(f"  OK   {entry['name']:26} {hits[0]}")
    else:
        with _lock:
            print(f"  --   {entry['name']:26} no published email (contact form only)")
    return entry


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text()) or {}
    studios = cfg.get("studios", [])
    targets = [s for s in studios if s.get("site") and not s.get("email")]
    print(f"Looking for published emails on {len(targets)} studio sites...\n")
    with ThreadPoolExecutor(max_workers=10) as pool:
        for fut in as_completed([pool.submit(work, s) for s in targets]):
            fut.result()          # never swallow a scraper bug silently
    got = sum(1 for s in studios if s.get("email"))
    CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False, width=200, allow_unicode=True))
    print(f"\n{got}/{len(studios)} studios have an email. The rest use a contact form — "
          f"fill those in by hand as you find them.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
