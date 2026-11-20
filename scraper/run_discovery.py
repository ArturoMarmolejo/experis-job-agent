"""Step 3c + 9: sitemap -> keyword filter -> fetch only new/changed jobs -> SQLite.
Plain HTTP first; if Experis ever blocks it, a Camoufox browser takes over (scraper/fetch.py).
Run: python -m scraper.run_discovery [--limit 3] [--fetch auto|http|browser]
"""
import argparse
import random
import time

from scraper import db
from scraper.fetch import Fetcher
from scraper.job_page import parse_job_page
from scraper.log import get_logger
from scraper.sitemap import SITEMAP_URL, load_settings, matches, parse_sitemap


def main():
    log = get_logger()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="fetch at most N pages (testing)")
    parser.add_argument("--min-delay", type=float, default=3.0, help="seconds between pages")
    parser.add_argument("--max-delay", type=float, default=5.0)
    parser.add_argument("--fetch", choices=["auto", "http", "browser"], default="auto",
                        help="auto = plain HTTP first, browser only if blocked")
    args = parser.parse_args()

    settings = load_settings()
    include = [k.lower() for k in settings["include_keywords"]]
    exclude = [k.lower() for k in settings.get("exclude_keywords", [])]

    conn = db.connect()
    saved = failed = via_browser = 0
    with Fetcher(args.fetch) as fetcher:                 # closes the browser if one was started
        body, how = fetcher.get(SITEMAP_URL)
        jobs = parse_sitemap(body)
        hits = [j for j in jobs if matches(j.slug, include, exclude)]

        known = db.known_lastmods(conn)
        new = [j for j in hits if j.job_id not in known]
        changed = [j for j in hits if j.job_id in known and j.lastmod > (known[j.job_id] or "")]
        todo = sorted(new + changed, key=lambda j: j.lastmod, reverse=True)   # newest first
        if args.limit:
            todo = todo[: args.limit]
        log.info(f"sitemap {len(jobs)} (via {how}) | match {len(hits)} | new {len(new)} "
                 f"| changed {len(changed)} | fetching {len(todo)}")

        for i, j in enumerate(todo, 1):
            try:
                body, how = fetcher.get(j.url)
                job = parse_job_page(body.decode("utf-8", errors="replace"), j.url)
                db.upsert_job(conn, job, j.slug, j.lastmod)
                conn.commit()                            # save each job right away
                saved += 1
                via_browser += how == "browser"
                log.info(f"[{i}/{len(todo)}] saved {job.job_id}  {job.title}  ({job.location}) via {how}")
            except Exception as e:                       # one bad page must not stop the run
                failed += 1
                log.warning(f"[{i}/{len(todo)}] FAILED {j.url}: {e}")
            if i < len(todo):
                time.sleep(random.uniform(args.min_delay, args.max_delay))

    conn.close()
    log.info(f"done: saved {saved}, failed {failed}, via browser {via_browser}")


if __name__ == "__main__":
    main()
