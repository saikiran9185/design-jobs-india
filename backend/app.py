"""FastAPI backend + static frontend. Runs locally on your Mac, no cloud, no account."""
from __future__ import annotations

import csv
import io
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .normalize import build_job

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

# Rough FX, only so one salary slider can compare across currencies.
FX_TO_INR = {"INR": 1.0, "USD": 88.0, "EUR": 95.0, "GBP": 111.0, "AED": 24.0, "SGD": 65.0}

app = FastAPI(title="Design Jobs India", docs_url="/api/docs")


@app.on_event("startup")
def _startup() -> None:
    db.init()
    _seed_companies()


def _seed_companies() -> None:
    """Mirror companies.yaml into the DB so the outreach tab has rows on first run."""
    import yaml
    cfg_path = ROOT / "config" / "companies.yaml"
    if not cfg_path.exists():
        return
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    rows = [(c["name"], c.get("city"), c.get("site"), c.get("ats"), c.get("token"),
             int(bool(c.get("verified"))), kind)
            for kind, key in (("product", "product_companies"), ("studio", "studios"))
            for c in cfg.get(key, [])]
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO companies (name, city, site, ats, token, verified, kind) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET "
            "city=excluded.city, site=excluded.site, ats=excluded.ats, "
            "token=excluded.token, verified=excluded.verified", rows)
        conn.commit()


def _monthly_inr(row) -> int | None:
    lo, cur, per = row["salary_min"], row["salary_currency"], row["salary_period"]
    if not lo:
        return None
    inr = lo * FX_TO_INR.get(cur or "INR", 1.0)
    return int(inr / 12) if per == "yearly" else int(inr)


# --- jobs -------------------------------------------------------------------
@app.get("/api/jobs")
def list_jobs(
    q: str = "", city: str = "", remote: str = "", job_type: str = "",
    discipline: str = "", source: str = "", india: str = "", days: int = 0,
    salary_min: int = 0, has_salary: bool = False, starred: bool = False,
    applied: str = "", sort: str = "date",
    limit: int = Query(100, le=1000), offset: int = 0,
):
    where, params = ["hidden = 0"], []
    if q:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        params += [f"%{q}%"] * 3
    if city:
        where.append("(city LIKE ? OR location LIKE ?)")
        params += [f"%{city}%"] * 2
    if remote:
        where.append(f"remote IN ({','.join('?' * len(remote.split(',')))})")
        params += remote.split(",")
    if job_type:
        where.append(f"job_type IN ({','.join('?' * len(job_type.split(',')))})")
        params += job_type.split(",")
    if discipline:
        where.append("(" + " OR ".join("discipline LIKE ?" for _ in discipline.split(",")) + ")")
        params += [f"%{d}%" for d in discipline.split(",")]
    if source:
        where.append(f"source IN ({','.join('?' * len(source.split(',')))})")
        params += source.split(",")
    if india == "1":
        where.append("is_india = 1")
    elif india == "0":
        where.append("is_india = 0")
    if days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        where.append("posted_at >= ?")
        params.append(cutoff)
    if has_salary:
        where.append("salary_min IS NOT NULL")
    if starred:
        where.append("starred = 1")
    if applied in ("0", "1"):
        where.append("applied = ?")
        params.append(int(applied))

    order = {"date": "posted_at DESC", "salary": "salary_min DESC NULLS LAST",
             "company": "company ASC", "title": "title ASC"}.get(sort, "posted_at DESC")

    sql = f"SELECT * FROM jobs WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?"
    with db.connect() as conn:
        rows = conn.execute(sql, params + [limit, offset]).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where)}", params).fetchone()[0]

    jobs = []
    for r in rows:
        d = dict(r)
        d["salary_monthly_inr"] = _monthly_inr(r)
        d["discipline"] = [x for x in (r["discipline"] or "").split(",") if x]
        d["description"] = (d["description"] or "")[:600]
        jobs.append(d)

    if salary_min:                       # applied post-hoc: needs FX normalisation
        jobs = [j for j in jobs if (j["salary_monthly_inr"] or 0) >= salary_min]
    return {"total": total, "count": len(jobs), "jobs": jobs}


@app.get("/api/facets")
def facets():
    with db.connect() as conn:
        def counts(col):
            return {r[0]: r[1] for r in conn.execute(
                f"SELECT {col}, COUNT(*) FROM jobs WHERE hidden=0 AND {col} IS NOT NULL "
                f"AND {col} != '' GROUP BY {col} ORDER BY 2 DESC").fetchall()}

        disc: dict[str, int] = {}
        for (d,) in conn.execute("SELECT discipline FROM jobs WHERE hidden=0 AND discipline != ''"):
            for tag in d.split(","):
                disc[tag] = disc.get(tag, 0) + 1

        cities = {r[0]: r[1] for r in conn.execute(
            "SELECT city, COUNT(*) FROM jobs WHERE hidden=0 AND is_india=1 AND city != '' "
            "GROUP BY city ORDER BY 2 DESC LIMIT 25").fetchall()}

        return {"remote": counts("remote"), "job_type": counts("job_type"),
                "source": counts("source"),
                "discipline": dict(sorted(disc.items(), key=lambda x: -x[1])),
                "city": cities}


@app.get("/api/stats")
def stats():
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) total, SUM(is_india) india, SUM(salary_min IS NOT NULL) with_salary, "
            "SUM(starred) starred, SUM(applied) applied FROM jobs WHERE hidden=0").fetchone()
        runs = conn.execute(
            "SELECT source, MAX(ran_at) ran_at, found, ok, error FROM source_runs "
            "GROUP BY source ORDER BY ran_at DESC").fetchall()
    return {**dict(row), "runs": [dict(r) for r in runs]}


@app.post("/api/jobs/{job_id}/{field}")
def toggle(job_id: str, field: str, value: int = 1):
    if field not in ("starred", "applied", "hidden"):
        raise HTTPException(400, "field must be starred, applied or hidden")
    with db.connect() as conn:
        conn.execute(f"UPDATE jobs SET {field} = ? WHERE id = ?", (value, job_id))
        conn.commit()
    return {"ok": True}


@app.post("/api/jobs/{job_id}/notes")
def set_notes(job_id: str, payload: dict):
    with db.connect() as conn:
        conn.execute("UPDATE jobs SET notes = ? WHERE id = ?", (payload.get("notes", ""), job_id))
        conn.commit()
    return {"ok": True}


# --- upload -----------------------------------------------------------------
@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Add jobs you found yourself — Instagram, WhatsApp, a studio's site.

    CSV needs a `title` column. Optional: company, location, url, description,
    salary, job_type, posted_at.
    """
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    try:
        rows = list(csv.DictReader(io.StringIO(raw)))
    except Exception as e:
        raise HTTPException(400, f"could not parse CSV: {e}")
    if not rows:
        raise HTTPException(400, "CSV is empty")
    if "title" not in {k.lower() for k in (rows[0] or {})}:
        raise HTTPException(400, "CSV must have a 'title' column")

    jobs = []
    for i, r in enumerate(rows):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        if not r.get("title"):
            continue
        jobs.append(build_job(
            source="upload", external_id=r.get("url") or f"{file.filename}:{i}",
            title=r["title"], company=r.get("company", ""), location=r.get("location", ""),
            description=r.get("description", ""), url=r.get("url", ""),
            posted_at=r.get("posted_at") or None, job_type_hint=r.get("job_type", ""),
            salary_text=r.get("salary", "")))
    with db.connect() as conn:
        n = db.upsert_jobs(conn, jobs)
        db.log_run(conn, "upload", len(jobs), n, True, file.filename)
        conn.commit()
    return {"parsed": len(jobs), "new": n}


# --- outreach ---------------------------------------------------------------
@app.get("/api/companies")
def list_companies(status: str = "", kind: str = ""):
    where, params = ["1=1"], []
    if status:
        where.append("status = ?")
        params.append(status)
    if kind:
        where.append("kind = ?")
        params.append(kind)
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM companies WHERE {' AND '.join(where)} ORDER BY kind, name",
            params).fetchall()
    return {"companies": [dict(r) for r in rows]}


@app.post("/api/companies/{company_id}")
def update_company(company_id: int, payload: dict):
    allowed = {"email", "contact", "status", "notes", "city", "site"}
    fields = {k: v for k, v in payload.items() if k in allowed}
    if not fields:
        raise HTTPException(400, f"nothing to update; allowed: {sorted(allowed)}")
    if fields.get("status") == "contacted":
        fields["last_contact"] = datetime.now(timezone.utc).isoformat()
    sets = ",".join(f"{k}=?" for k in fields)
    with db.connect() as conn:
        conn.execute(f"UPDATE companies SET {sets} WHERE id=?",
                     list(fields.values()) + [company_id])
        conn.commit()
    return {"ok": True}


@app.post("/api/companies")
def add_company(payload: dict):
    if not payload.get("name"):
        raise HTTPException(400, "name is required")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO companies (name, city, site, email, contact, kind, notes) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(name) DO NOTHING",
            (payload["name"], payload.get("city"), payload.get("site"), payload.get("email"),
             payload.get("contact"), payload.get("kind", "studio"), payload.get("notes")))
        conn.commit()
    return {"ok": True}


@app.get("/api/export.csv")
def export_csv(starred: bool = False):
    where = "hidden=0" + (" AND starred=1" if starred else "")
    with db.connect() as conn:
        rows = conn.execute(f"SELECT * FROM jobs WHERE {where} ORDER BY posted_at DESC").fetchall()
    buf = io.StringIO()
    cols = ["title", "company", "location", "remote", "job_type", "discipline",
            "salary_min", "salary_max", "salary_currency", "salary_period",
            "url", "apply_email", "source", "posted_at"]
    w = csv.writer(buf)
    w.writerow(cols)
    w.writerows([[r[c] for c in cols] for r in rows])
    return JSONResponse(content=buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=design-jobs.csv"})


@app.post("/api/ingest")
def trigger_ingest():
    """Kick off a refresh. Fire-and-forget; watch the terminal for progress."""
    subprocess.Popen([sys.executable, "-m", "backend.ingest"], cwd=ROOT)
    return {"ok": True, "message": "Refresh started — watch the terminal."}


# --- frontend ---------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND), name="static")
