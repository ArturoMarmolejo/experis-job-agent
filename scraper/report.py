"""Step 5: daily report -> HTML page + CSV + JSON with ranked jobs and apply links.
Run: python -m scraper.report [--min-score 50]
"""
import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from scraper.matcher import load_profile, rank_jobs

REPORT_DIR = Path("data/reports")        # inside data/ -> git-ignored
FIELDS = ["score", "new", "job_id", "title", "location", "posted", "why", "url", "apply_url"]

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Experis job report {day}</title>
<style>
 body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 32px; color: #1f2d4d; }}
 h1 {{ margin-bottom: 4px; }}
 .summary, .foot {{ color: #555; }}
 table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
 th {{ text-align: left; background: #1f2d4d; color: #fff; padding: 8px; }}
 td {{ padding: 8px; border-bottom: 1px solid #e3e7ee; vertical-align: top; }}
 .score {{ font-weight: bold; font-size: 18px; }}
 tr.high .score {{ color: #1e8e3e; }}
 tr.mid .score {{ color: #2f6db5; }}
 tr.low .score {{ color: #888; }}
 .badge {{ background: #e8710a; color: #fff; border-radius: 4px; padding: 1px 6px;
           font-size: 11px; margin-left: 6px; }}
 .id {{ color: #888; font-size: 12px; }}
 .why {{ font-size: 13px; color: #444; }}
 a.apply {{ background: #2f6db5; color: #fff; padding: 6px 12px; border-radius: 4px;
            text-decoration: none; white-space: nowrap; }}
</style></head><body>
<h1>Experis job report: {day}</h1>
<p class="summary">{count} matching jobs (score &ge; {min_score}) &middot; <b>{new_count} new</b>
in the last 24 h &middot; profile: config/profile.md (fictional test persona)</p>
<table>
<tr><th>Score</th><th>Job</th><th>Location</th><th>Posted</th><th>Why it matches</th><th></th></tr>
{rows}
</table>
<p class="foot">Generated {generated}. Applying is manual: "Apply" opens Experis's own form.</p>
</body></html>"""

ROW = """<tr class="{cls}">
 <td class="score">{score}</td>
 <td><a href="{url}" target="_blank">{title}</a>{badge}<div class="id">#{job_id}</div></td>
 <td>{location}</td>
 <td style="white-space: nowrap">{posted}</td>
 <td class="why">{why}</td>
 <td><a class="apply" href="{apply_url}" target="_blank">Apply</a></td>
</tr>"""


def build_rows(min_score):
    """Ranked jobs as plain dicts (one per report line)."""
    profile = load_profile()
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = []
    for score, job, why in rank_jobs(profile):
        if score < min_score:
            continue
        rows.append({
            "score": score,
            "new": datetime.fromisoformat(job["first_seen_at"]) >= since,
            "job_id": job["job_id"],
            "title": job["title"],
            "location": job["location"] or "",
            "posted": (job["posted_at"] or "")[:10],
            "why": why,
            "url": job["url"],
            "apply_url": job["apply_url"] or job["url"],
        })
    return rows


def write_html(rows, path, day, min_score):
    lines = []
    for r in rows:
        lines.append(ROW.format(
            cls="high" if r["score"] >= 75 else "mid" if r["score"] >= 60 else "low",
            score=r["score"],
            url=escape(r["url"]),
            title=escape(r["title"]),
            badge='<span class="badge">NEW</span>' if r["new"] else "",
            job_id=escape(r["job_id"]),
            location=escape(r["location"]),
            posted=escape(r["posted"]),
            why=escape(r["why"]),
            apply_url=escape(r["apply_url"]),
        ))
    path.write_text(PAGE.format(
        day=day, count=len(rows), min_score=min_score,
        new_count=sum(r["new"] for r in rows), rows="\n".join(lines),
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    ), encoding="utf-8")


def write_csv(rows, path):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows, path):
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=int, default=50, help="leave out weaker matches")
    args = parser.parse_args()

    rows = build_rows(args.min_score)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    base = REPORT_DIR / f"report_{day}"
    write_html(rows, base.with_suffix(".html"), day, args.min_score)
    write_csv(rows, base.with_suffix(".csv"))
    write_json(rows, base.with_suffix(".json"))

    print(f"[report] {len(rows)} jobs (score >= {args.min_score}), "
          f"{sum(r['new'] for r in rows)} new in the last 24 h")
    print(f"[report] wrote {base}.html / .csv / .json")


if __name__ == "__main__":
    main()
