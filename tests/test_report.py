"""Report rows (threshold, NEW flag) and HTML escaping. Fake rankings, temp files."""
from datetime import datetime, timedelta, timezone

from scraper import report


def job(job_id, first_seen):
    return {"job_id": job_id, "title": "Data Engineer", "location": None,
            "posted_at": "2026-11-18T00:00:00Z", "first_seen_at": first_seen,
            "url": f"https://www.experis.com/en/job/{job_id}/x", "apply_url": None}


def test_rows_respect_threshold_and_new_flag(monkeypatch):
    now = datetime.now(timezone.utc)
    recent, old = now.isoformat(), (now - timedelta(days=3)).isoformat()
    ranked = [(80, job("A", recent), "why"), (60, job("B", old), "why"), (40, job("C", recent), "why")]
    monkeypatch.setattr(report, "load_profile", lambda: {})
    monkeypatch.setattr(report, "rank_jobs", lambda profile: ranked)
    rows = report.build_rows(min_score=50)
    assert [(r["job_id"], r["new"]) for r in rows] == [("A", True), ("B", False)]   # C below 50
    assert rows[0]["location"] == ""                       # None becomes empty text
    assert rows[0]["apply_url"] == rows[0]["url"]          # no apply link -> job page


def test_html_escapes_job_text(tmp_path):
    rows = [{"score": 80, "new": True, "job_id": "1", "title": "<script>alert(1)</script>",
             "location": "", "posted": "", "why": "", "url": "u", "apply_url": "u"}]
    path = tmp_path / "report.html"
    report.write_html(rows, path, "2026-11-19", 50)
    html = path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
