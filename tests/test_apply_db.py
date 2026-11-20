"""applications table + job picking. In-memory database, fake rankings: no browser, no network."""
import sqlite3

from scraper import apply


def make_conn():
    conn = sqlite3.connect(":memory:")            # a throwaway database that lives only in memory
    conn.execute(apply.APPLICATIONS)
    return conn


def fake_job(job_id, apply_url="https://www.experis.com/en/candidate/jobapply?id=x"):
    return {"job_id": job_id, "title": f"Job {job_id}", "apply_url": apply_url}


def test_record_keeps_one_row_per_job():
    conn = make_conn()
    apply.record(conn, "1", "failed", "boom")
    apply.record(conn, "1", "dry_run", "ok", "shot.png")
    rows = conn.execute("SELECT job_id, status, screenshot FROM applications").fetchall()
    assert rows == [("1", "dry_run", "shot.png")]


def test_pick_skips_submitted_low_scores_and_missing_links(monkeypatch):
    ranked = [(90, fake_job("A"), ""), (85, fake_job("B"), ""),
              (80, fake_job("C", apply_url=None), ""), (60, fake_job("D"), "")]
    monkeypatch.setattr(apply, "load_profile", lambda: {})
    monkeypatch.setattr(apply, "rank_jobs", lambda profile: ranked)
    conn = make_conn()
    apply.record(conn, "A", "submitted", "sent")
    picked = apply.pick_jobs(conn, None, limit=5, min_score=70)
    assert [job["job_id"] for _, job in picked] == ["B"]   # A sent, C no link, D score too low


def test_pick_by_id_never_returns_a_submitted_job(monkeypatch):
    monkeypatch.setattr(apply, "load_jobs", lambda: [fake_job("A"), fake_job("B")])
    conn = make_conn()
    apply.record(conn, "A", "submitted", "sent")
    assert apply.pick_jobs(conn, "A", 1, 70) == []
    assert [job["job_id"] for _, job in apply.pick_jobs(conn, "B", 1, 70)] == ["B"]
