"""Step 3c (part 2): SQLite storage. One row per Experis reference number."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/jobs.db")          # data/ is in .gitignore

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id         TEXT PRIMARY KEY,   -- Experis reference number, e.g. 410607
    job_item_id    TEXT,               -- internal ID used by the apply link
    title          TEXT,
    location       TEXT,
    job_type       TEXT,
    posted_at      TEXT,
    valid_through  TEXT,
    salary         TEXT,
    description    TEXT,
    url            TEXT,
    apply_url      TEXT,
    slug           TEXT,
    lastmod        TEXT,               -- sitemap date at our last fetch (our watermark)
    first_seen_at  TEXT,               -- when WE first saved it (kept on updates)
    updated_at     TEXT                -- when WE last refreshed it
)
"""

UPSERT = """
INSERT INTO jobs (job_id, job_item_id, title, location, job_type, posted_at, valid_through,
                  salary, description, url, apply_url, slug, lastmod, first_seen_at, updated_at)
VALUES (:job_id, :job_item_id, :title, :location, :job_type, :posted_at, :valid_through,
        :salary, :description, :url, :apply_url, :slug, :lastmod, :now, :now)
ON CONFLICT(job_id) DO UPDATE SET
    job_item_id = excluded.job_item_id,  title = excluded.title,
    location = excluded.location,        job_type = excluded.job_type,
    posted_at = excluded.posted_at,      valid_through = excluded.valid_through,
    salary = excluded.salary,            description = excluded.description,
    url = excluded.url,                  apply_url = excluded.apply_url,
    slug = excluded.slug,                lastmod = excluded.lastmod,
    updated_at = excluded.updated_at
"""


def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)   # create data/ on first run
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    return conn


def known_lastmods(conn):
    """{job_id: lastmod} for every job already saved."""
    return dict(conn.execute("SELECT job_id, lastmod FROM jobs"))


def upsert_job(conn, job, slug, lastmod):
    """Insert a new job, or update it if the reference number already exists."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(UPSERT, {**job, "slug": slug, "lastmod": lastmod, "now": now})
