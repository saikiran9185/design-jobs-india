"""Competitions, challenges, hackathons and events — the things buried by feed algorithms.

MyGov runs India's government design and innovation challenges (logo contests, mascot
design, policy hackathons). Devfolio hosts most Indian student hackathons. Unstop
competitions are handled in india.py.
"""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from ..normalize import build_job, clean_html

TIMEOUT = httpx.Timeout(30.0)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# A challenge is worth surfacing to a design student if it involves making something.
CREATIVE = ("design", "logo", "mascot", "poster", "creative", "art", "illustration",
            "animation", "film", "video", "photography", "branding", "identity",
            "ui", "ux", "graphic", "innovation", "idea", "prototype", "hackathon",
            "makeathon", "quiz", "slogan", "jingle", "essay", "content")


def _is_creative(text: str) -> bool:
    return any(k in (text or "").lower() for k in CREATIVE)


def _rss(client: httpx.Client, url: str) -> list[dict]:
    r = client.get(url, headers=UA, timeout=TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for item in root.iter("item"):
        get = lambda tag: (item.findtext(tag) or "").strip()
        out.append({"title": html.unescape(get("title")), "link": get("link"),
                    "desc": html.unescape(get("description")), "date": get("pubDate")})
    return out


def _pubdate(s: str) -> str | None:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(s, fmt).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            continue
    return None


def mygov(client, **_):
    """Government design challenges, logo contests and innovation calls."""
    out = []
    for feed, label in (("https://innovateindia.mygov.in/feed/", "MyGov Innovate India"),
                        ("https://www.mygov.in/rss.xml", "MyGov")):
        try:
            items = _rss(client, feed)
        except Exception:
            continue
        for it in items:
            blob = f"{it['title']} {it['desc']}"
            if not _is_creative(blob):
                continue
            job = build_job(
                source="mygov", external_id=it["link"], title=it["title"],
                company=label, location="India", country="India",
                description=clean_html(it["desc"]), url=it["link"],
                posted_at=_pubdate(it["date"]), job_type_hint="competition",
                remote_hint="remote")
            job["kind"] = "competition"
            job["is_india"] = 1
            out.append(job)
    return out


def devfolio(client, **_):
    """Indian student hackathons. Design tracks are common and open to non-coders."""
    r = client.get("https://devfolio.co/hackathons", headers=UA, timeout=TIMEOUT,
                   follow_redirects=True)
    r.raise_for_status()
    m = re.search(r'__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
    if not m:
        return []
    data = (json.loads(m.group(1))["props"]["pageProps"]["dehydratedState"]
            ["queries"][0]["state"]["data"])

    out = []
    for bucket in ("open_hackathons", "upcoming_hackathons", "featured_hackathons"):
        for h in data.get(bucket) or []:
            themes = " ".join(t.get("name", "") if isinstance(t, dict) else str(t)
                              for t in (h.get("themes") or []))
            job = build_job(
                source="devfolio", external_id=h.get("uuid") or h.get("slug"),
                title=h.get("name", ""), company="Devfolio",
                location="Online" if h.get("is_online") else "India", country="India",
                description=themes or "Hackathon",
                url=f"https://{h.get('slug')}.devfolio.co",
                posted_at=h.get("starts_at"), job_type_hint="hackathon",
                remote_hint="remote" if h.get("is_online") else "onsite")
            job["kind"] = "hackathon"
            job["is_india"] = 1
            job["deadline"] = h.get("ends_at")
            out.append(job)
    # de-dupe across the three buckets
    return list({j["id"]: j for j in out}.values())


REGISTRY = {
    "mygov":    {"fn": mygov,    "needs_key": False, "note": "Govt of India design challenges"},
    "devfolio": {"fn": devfolio, "needs_key": False, "note": "Indian hackathons"},
}
