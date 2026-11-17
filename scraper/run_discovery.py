"""Step 3c (part 3): sitemap -> keyword filter -> fetch only new/changed jobs -> SQLite.
Run: python -m scraper.run_discovery [--limit 3]
"""
import argparse
import random
import time

from scraper import db
from scraper.job_page import fetch_html, parse_job_page
from scraper.sitemap import fetch_sitemap, load_settings, matches, parse_sitemap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="fetch at most N pages (testing)")
    parser.add_argument("--min-delay", type=float, default=3.0, help="seconds between pages")
    parser.add_argument("--max-delay", type=float, default=5.0)
    args = parser.parse_args()

    settings = load_settings()
    include = [k.lower() for k in settings["include_keywords"]]
    exclude = [k.lower() for k in settings.get("exclude_keywords", [])]

    jobs = parse_sitemap(fetch_sitemap())
    hits = [j for j in jobs if matches(j.slug, include, exclude)]

    conn = db.connect()
    known = db.known_lastmods(conn)
    new = [j for j in hits if j.job_id not in known]
    changed = [j for j in hits if j.job_id in known and j.lastmod > (known[j.job_id] or "")]
    todo = sorted(new + changed, key=lambda j: j.lastmod, reverse=True)   # newest first
    if args.limit:
        todo = todo[: args.limit]

    print(f"[discovery] sitemap {len(jobs)} | match {len(hits)} | new {len(new)} "
          f"| changed {len(changed)} | fetching {len(todo)}")

    saved = failed = 0
    for i, j in enumerate(todo, 1):
        try:
            job = parse_job_page(fetch_html(j.url), j.url)
            db.upsert_job(conn, job, j.slug, j.lastmod)
            conn.commit()                 # save each job right away: a crash loses nothing
            saved += 1
            print(f"  [{i}/{len(todo)}] saved {job.job_id}  {job.title}  ({job.location})")
        except Exception as e:            # one bad page must not stop the whole run
            failed += 1
            print(f"  [{i}/{len(todo)}] FAILED {j.url}: {e}")
        if i < len(todo):
            time.sleep(random.uniform(args.min_delay, args.max_delay))   # be polite to Experis

    conn.close()
    print(f"[discovery] done: saved {saved}, failed {failed}")


if __name__ == "__main__":
    main()
