"""SQLite upsert on a temporary database (never the real data/jobs.db)."""
from scraper import db
from scraper.job_page import Job


def make_job(title):
    return Job(job_id="410607", title=title, url="https://www.experis.com/en/job/410607/x")


def test_upsert_updates_but_keeps_first_seen(tmp_path):
    conn = db.connect(tmp_path / "jobs.db")
    db.upsert_job(conn, make_job("Data Engineer"), "data-engineer", "2026-11-01")
    conn.execute("UPDATE jobs SET first_seen_at = '2026-01-01T00:00:00+00:00'")   # pretend: seen long ago

    db.upsert_job(conn, make_job("Senior Data Engineer"), "data-engineer", "2026-11-10")

    rows = conn.execute("SELECT title, lastmod, first_seen_at FROM jobs").fetchall()
    assert rows == [("Senior Data Engineer", "2026-11-10", "2026-01-01T00:00:00+00:00")]
    assert db.known_lastmods(conn) == {"410607": "2026-11-10"}   # one row, newest watermark
