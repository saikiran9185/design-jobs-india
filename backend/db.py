"""SQLite storage. One file, no server, no migrations beyond CREATE IF NOT EXISTS."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    external_id     TEXT,
    title           TEXT NOT NULL,
    company         TEXT,
    location        TEXT,
    city            TEXT,
    country         TEXT,
    remote          TEXT,            -- remote | hybrid | onsite | unknown
    job_type        TEXT,            -- fulltime | internship | freelance | contract | parttime | unknown
    discipline      TEXT,            -- comma-separated tags
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency TEXT,
    salary_period   TEXT,            -- monthly | yearly
    salary_text     TEXT,
    description     TEXT,
    url             TEXT,
    apply_email     TEXT,
    posted_at       TEXT,
    fetched_at      TEXT,
    kind            TEXT DEFAULT 'job',   -- job | competition | hackathon | event
    deadline        TEXT,
    verified        INTEGER DEFAULT 0,    -- community confirmations
    reported        INTEGER DEFAULT 0,    -- community scam reports
    is_india        INTEGER DEFAULT 0,
    starred         INTEGER DEFAULT 0,
    applied         INTEGER DEFAULT 0,
    hidden          INTEGER DEFAULT 0,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_posted   ON jobs(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company  ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_source   ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_india    ON jobs(is_india);
CREATE INDEX IF NOT EXISTS idx_jobs_kind     ON jobs(kind);

-- Outreach side: companies to approach for the college placement drive.
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    city        TEXT,
    site        TEXT,
    ats         TEXT,
    token       TEXT,
    verified    INTEGER DEFAULT 0,
    email       TEXT,
    contact     TEXT,
    kind        TEXT,              -- product | studio
    status      TEXT DEFAULT 'new',-- new | contacted | replied | confirmed | declined
    last_contact TEXT,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS source_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT,
    ran_at     TEXT,
    found      INTEGER,
    inserted   INTEGER,
    ok         INTEGER,
    error      TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


COLUMNS = [
    "id", "source", "external_id", "title", "company", "location", "city", "country",
    "remote", "job_type", "discipline", "salary_min", "salary_max", "salary_currency",
    "salary_period", "salary_text", "description", "url", "apply_email", "posted_at",
    "fetched_at", "is_india", "kind", "deadline",
]


def upsert_jobs(conn: sqlite3.Connection, jobs: list[dict]) -> int:
    """Insert new jobs, refresh fields on existing ones. Preserves starred/applied/notes."""
    if not jobs:
        return 0
    placeholders = ",".join("?" * len(COLUMNS))
    updates = ",".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "id")
    sql = (
        f"INSERT INTO jobs ({','.join(COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}"
    )
    before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.executemany(sql, [[j.get(c) for c in COLUMNS] for j in jobs])
    after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    return after - before


def log_run(conn, source: str, found: int, inserted: int, ok: bool, error: str | None) -> None:
    from datetime import datetime, timezone
    conn.execute(
        "INSERT INTO source_runs (source, ran_at, found, inserted, ok, error) VALUES (?,?,?,?,?,?)",
        (source, datetime.now(timezone.utc).isoformat(), found, inserted, int(ok), error),
    )
