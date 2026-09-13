"""Turn wildly different source payloads into one Job shape, and tag it so filters work."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

# --- design detection -------------------------------------------------------
# ATS endpoints return every role a company has. Keep only design.
DISCIPLINES: dict[str, tuple[str, ...]] = {
    "ux":          ("ux", "user experience", "interaction design", "ixd", "usability"),
    "ui":          ("ui design", "ui/ux", "ui designer", "visual design", "interface design"),
    "product":     ("product design", "product designer"),
    "graphic":     ("graphic design", "graphic designer", "layout", "print design"),
    "brand":       ("brand", "branding", "identity design", "visual identity"),
    "motion":      ("motion design", "motion graphic", "animator", "animation", "after effects", "vfx"),
    "3d":          ("3d design", "3d artist", "blender", "cgi", "modeling", "modelling", "render"),
    "illustration":("illustrator", "illustration"),
    "industrial":  ("industrial design", "product design engineer", "cmf", "furniture"),
    "web":         ("web design", "webflow", "figma to code", "frontend design"),
    "game":        ("game design", "game artist", "level design"),
    "research":    ("design research", "ux research", "user research"),
    "content":     ("content design", "ux writ", "copywrit"),
    "fashion":     ("fashion design", "textile", "apparel design"),
    "interior":    ("interior design", "spatial design", "exhibition design"),
    "service":     ("service design",),
}

_GENERIC_DESIGN = ("design", "designer", "creative", "artist", "animator", "illustrator")

# Titles containing "design" that are NOT design jobs.
_NOT_DESIGN = (
    "design engineer", "hardware design", "chip design", "circuit design", "vlsi",
    "network design", "solution design", "system design", "database design",
    "instructional design", "design verification", "rtl", "mechanical design",
    "civil", "structural design", "sales", "account manager", "recruiter",
)


def detect_disciplines(title: str, description: str = "") -> list[str]:
    """Tag from the TITLE. A long job description mentions everything and tags nothing well."""
    t = (title or "").lower()
    if not _title_is_design(t):
        return []
    tags = [name for name, kws in DISCIPLINES.items() if any(k in t for k in kws)]
    if tags:
        return tags
    if any(k in t for k in ("video editor", "videographer", "compositor", "vfx")):
        return ["motion"]
    # Only fall back to the description when the title is a bare "Designer"/"Artist".
    if _title_is_design(t):
        hay = (description or "").lower()[:1200]
        return [name for name, kws in DISCIPLINES.items() if any(k in hay for k in kws)]
    return []


_DESIGN_TITLE = re.compile(
    r"\b(design|designer|designers|ux|ui|ixd|creative|art\s*direct\w*|artist|"
    r"animator|animation|illustrator|illustration|motion|graphics?|"
    r"typograph\w*|brand\s*identity|visualiser|visualizer|3d|cgi|vfx|"
    r"video\s*editor|videographer|photographer|retoucher|compositor|"
    r"storyboard\w*|concept\s*art\w*|layout\s*artist|editorial)\b", re.I)


def _title_is_design(title: str) -> bool:
    t = (title or "").lower()
    if any(bad in t for bad in _NOT_DESIGN):
        return False
    return bool(_DESIGN_TITLE.search(t))


def is_design_role(title: str, description: str = "") -> bool:
    """Title decides. Description-based matching pulled in sales and DevOps roles."""
    return _title_is_design(title)


# --- job type ---------------------------------------------------------------
_TYPE_PATTERNS = (
    ("internship", re.compile(r"\b(intern|interns|internship|trainee|apprentice\w*)\b", re.I)),
    ("freelance",  re.compile(r"\b(freelance\w*|gig|project[- ]based|per[- ]project)\b", re.I)),
    ("contract",   re.compile(r"\b(contract|contractor|contractual|temporary|fixed[- ]term)\b", re.I)),
    ("parttime",   re.compile(r"\b(part[- ]?time)\b", re.I)),
    ("fulltime",   re.compile(r"\b(full[- ]?time|permanent)\b", re.I)),
)


def detect_job_type(title: str, description: str = "", hint: str = "") -> str:
    """Title and the source's own type field are trusted; the description is not.

    "internal" and "international" both contain "intern" — word boundaries matter.
    """
    for field in (hint or "", title or ""):
        for label, pat in _TYPE_PATTERNS:
            if pat.search(field):
                return label
    # Description is a last resort, and only for internships/freelance, which are
    # usually stated in the first lines.
    head = (description or "")[:300]
    for label, pat in _TYPE_PATTERNS[:2]:
        if pat.search(head):
            return label
    return "fulltime"


# --- remote -----------------------------------------------------------------
def detect_remote(location: str, description: str = "", hint: str = "") -> str:
    hay = f"{hint} {location} {description}".lower()
    if "hybrid" in hay:
        return "hybrid"
    if any(k in hay for k in ("remote", "work from home", "wfh", "anywhere", "distributed")):
        return "remote"
    if any(k in hay for k in ("on-site", "onsite", "in office", "in-office", "on site")):
        return "onsite"
    return "onsite" if location.strip() else "unknown"


# --- India ------------------------------------------------------------------
INDIA_CITIES = (
    "india", "bengaluru", "bangalore", "mumbai", "bombay", "delhi", "new delhi",
    "gurugram", "gurgaon", "noida", "hyderabad", "chennai", "madras", "pune",
    "kolkata", "calcutta", "ahmedabad", "jaipur", "chandigarh", "indore", "kochi",
    "cochin", "trivandrum", "thiruvananthapuram", "coimbatore", "surat", "nagpur",
    "lucknow", "bhopal", "vadodara", "mysore", "mysuru", "goa", "manipal", "ncr",
    "maharashtra", "karnataka", "telangana", "tamil nadu", "kerala", "gujarat",
    "rajasthan", "haryana", "punjab", "west bengal", "uttar pradesh",
)


def detect_india(location: str, country: str = "", company: str = "") -> bool:
    hay = f"{location} {country} {company}".lower()
    return any(c in hay for c in INDIA_CITIES)


# Same city, different spellings — collapse them or the city filter splits in two.
CITY_ALIASES = {
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru",
    "bombay": "Mumbai", "mumbai": "Mumbai",
    "madras": "Chennai", "chennai": "Chennai",
    "calcutta": "Kolkata", "kolkata": "Kolkata",
    "gurgaon": "Gurugram", "gurugram": "Gurugram",
    "new delhi": "New Delhi", "delhi": "New Delhi", "ncr": "New Delhi",
    "cochin": "Kochi", "kochi": "Kochi",
    "mysore": "Mysuru", "mysuru": "Mysuru",
    "trivandrum": "Thiruvananthapuram", "thiruvananthapuram": "Thiruvananthapuram",
}


def detect_city(location: str) -> str:
    low = (location or "").lower()
    # longest alias first, so "new delhi" wins over "delhi"
    for alias in sorted(CITY_ALIASES, key=len, reverse=True):
        if alias in low:
            return CITY_ALIASES[alias]
    for c in INDIA_CITIES:
        if c in low and c not in ("india", "ncr") and len(c) > 3:
            return c.title()
    return (location or "").split(",")[0].strip()


# --- salary -----------------------------------------------------------------
_LPA = re.compile(r"(?:₹|inr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|–)?\s*(\d+(?:\.\d+)?)?\s*(?:lpa|lakhs?\s*(?:per|/)?\s*(?:annum|year|yr)?|l\s*p\s*a)", re.I)
_RANGE = re.compile(r"(?:₹|inr|rs\.?)\s*(\d[\d,]*)(?:\s*(?:-|to|–)\s*(?:₹|inr|rs\.?)?\s*(\d[\d,]*))?", re.I)
_K = re.compile(r"(\d+)\s*k\s*(?:-|to|–)\s*(\d+)\s*k", re.I)


def parse_salary(text: str) -> dict:
    """Best-effort INR parse. Most Indian listings publish nothing — null is the normal case."""
    out = {"salary_min": None, "salary_max": None, "salary_currency": None,
           "salary_period": None, "salary_text": None}
    if not text:
        return out
    try:
        return _parse_salary(text, out)
    except (ValueError, TypeError, OverflowError):
        return out          # an unparseable salary is a missing salary, never a crash


def _parse_salary(text: str, out: dict) -> dict:
    t = text[:400]

    if m := _LPA.search(t):
        lo = float(m.group(1)) * 100_000
        hi = float(m.group(2)) * 100_000 if m.group(2) else None
        out.update(salary_min=int(lo), salary_max=int(hi) if hi else None,
                   salary_currency="INR", salary_period="yearly", salary_text=m.group(0).strip())
        return out

    if m := _K.search(t):
        out.update(salary_min=int(m.group(1)) * 1000, salary_max=int(m.group(2)) * 1000,
                   salary_currency="INR", salary_period="monthly", salary_text=m.group(0).strip())
        return out

    if m := _RANGE.search(t):
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", "")) if m.group(2) else None
        if lo < 1000:                      # too small to be a salary
            return out
        period = "monthly" if lo < 500_000 else "yearly"
        if re.search(r"per\s*(month|annum|year)|/\s*(month|year)|monthly|annually", t, re.I):
            period = "monthly" if re.search(r"month", t, re.I) else "yearly"
        out.update(salary_min=lo, salary_max=hi, salary_currency="INR",
                   salary_period=period, salary_text=m.group(0).strip())
    return out


# Sources publish "annual", "annually", "per year" and "yearly" for the same thing,
# and some publish an hourly rate that must not be read as a salary.
PERIOD_ALIASES = {
    "annual": "yearly", "annually": "yearly", "year": "yearly", "yr": "yearly",
    "month": "monthly", "monthly": "monthly", "mo": "monthly",
    "hour": "hourly", "hourly": "hourly", "hr": "hourly",
    "week": "weekly", "weekly": "weekly", "day": "daily", "daily": "daily",
}
HOURS_PER_MONTH = 160          # 40h x 4 weeks, for comparing an hourly rate to a salary

# Plausible monthly INR for a design role. Anything outside this is a parse artefact.
MIN_MONTHLY_INR = 3_000
MAX_MONTHLY_INR = 4_000_000


def canon_period(period: str | None) -> str:
    p = (period or "").strip().lower()
    return PERIOD_ALIASES.get(p, p or "yearly")


def to_monthly(amount: float, period: str) -> float:
    period = canon_period(period)
    if period == "yearly":
        return amount / 12
    if period == "hourly":
        return amount * HOURS_PER_MONTH
    if period == "weekly":
        return amount * 4.33
    if period == "daily":
        return amount * 22
    return amount


def monthly_inr(job: dict, fx: float = 1.0) -> int | None:
    """Normalise to monthly INR so one slider can compare everything."""
    lo = job.get("salary_min")
    if not lo:
        return None
    return int(to_monthly(lo * fx, job.get("salary_period")))


def sane_salary(job: dict) -> bool:
    """Reject parse artefacts. RemoteOK publishes 10,000-750,000 on the same posting."""
    lo, hi = job.get("salary_min"), job.get("salary_max")
    if not lo or lo <= 0:
        return False
    if hi and (hi < lo or hi > lo * 25):      # a 25x band is not a real salary range
        return False
    monthly = to_monthly(lo, job.get("salary_period"))
    fx = {"USD": 88.0, "EUR": 95.0, "GBP": 111.0, "AED": 24.0, "SGD": 65.0}.get(
        job.get("salary_currency") or "INR", 1.0)
    return MIN_MONTHLY_INR <= monthly * fx <= MAX_MONTHLY_INR


# --- assembly ---------------------------------------------------------------
def make_id(source: str, external_id: str, title: str = "", company: str = "") -> str:
    raw = f"{source}:{external_id or ''}:{title.lower().strip()}:{(company or '').lower().strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def clean_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
                .replace("&quot;", '"'))
    return re.sub(r"\s+", " ", text).strip()


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def build_job(*, source, external_id, title, company=None, location="", country="",
              description="", url="", posted_at=None, job_type_hint="",
              remote_hint="", salary_text="") -> dict:
    """The single funnel every source passes through."""
    desc = clean_html(description)
    location = (location or "").strip()
    email = EMAIL_RE.search(desc)
    job = {
        "id": make_id(source, external_id, title, company),
        "source": source,
        "external_id": str(external_id) if external_id is not None else None,
        "title": (title or "").strip(),
        "company": (company or "").strip() or None,
        "location": location,
        "city": detect_city(location),
        "country": country or ("India" if detect_india(location, country) else ""),
        "remote": detect_remote(location, desc, remote_hint),
        "job_type": detect_job_type(title, desc, job_type_hint),
        "discipline": ",".join(detect_disciplines(title, desc)),
        "description": desc[:4000],
        "url": url,
        "apply_email": email.group(0) if email else None,
        "posted_at": posted_at or datetime.now(timezone.utc).isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_india": int(detect_india(location, country, company or "")),
        "kind": "job",
        "deadline": None,
    }
    job.update(parse_salary(salary_text or desc))
    return job
