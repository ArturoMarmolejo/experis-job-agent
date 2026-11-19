"""Sitemap parsing and keyword filtering, using a tiny fake sitemap (no network)."""
from scraper.sitemap import matches, parse_sitemap

SITEMAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.experis.com/en/job/410607/data-engineer</loc><lastmod>2026-09-08</lastmod></url>
  <url><loc>https://www.experis.com/en/job/410607/data-engineer</loc><lastmod>2026-11-10</lastmod></url>
  <url><loc>https://www.experis.com/en/job/399832/senior-nodejs-engineer-backend-</loc><lastmod>2026-10-27</lastmod></url>
  <url><loc>https://www.experis.com/insights/articles/some-article</loc><lastmod>2026-10-01</lastmod></url>
</urlset>"""


def test_keeps_only_job_pages_and_newest_duplicate():
    jobs = {j.job_id: j for j in parse_sitemap(SITEMAP)}
    assert set(jobs) == {"410607", "399832"}          # the article is ignored
    assert jobs["410607"].lastmod == "2026-11-10"     # same ID twice -> newest wins
    assert jobs["410607"].slug == "data-engineer"


def test_matches_include_and_exclude():
    assert matches("azure-data-engineer", ["data-engineer"], [])
    assert not matches("certified-dental-assistant", ["data-engineer"], ["dental"])
    assert not matches("data-engineer-sales", ["data-engineer"], ["sales"])   # exclude wins
