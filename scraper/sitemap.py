"""Step 3a: read the Experis sitemap and list job URLs that match our keywords."""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests
import yaml

SITEMAP_URL = "https://www.experis.com/sitemap.xml"
JOB_URL = re.compile(r"/en/job/(\d+)/([^/?#]*)")   # captures (job_id, slug)
HEADERS = {"User-Agent": "Mozilla/5.0 (personal job-search script)"}


@dataclass
class SitemapJob:
    job_id: str
    slug: str
    url: str
    lastmod: str          # "2026-11-10" -> works like our watermark


def load_settings(path="config/search.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_sitemap(url=SITEMAP_URL):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()            # stop loudly on 403/500 instead of parsing an error page
    return resp.content


def child_text(node, name):
    """Text of a child tag, ignoring the XML namespace prefix."""
    for child in node:
        if child.tag.endswith(name):
            return (child.text or "").strip()
    return ""


def parse_sitemap(xml_bytes):
    root = ET.fromstring(xml_bytes)
    jobs = {}
    for node in root.iter():
        if not node.tag.endswith("url"):        # each <url> holds one <loc> + <lastmod>
            continue
        loc = child_text(node, "loc")
        m = JOB_URL.search(loc)
        if not m:
            continue                            # not a job page (articles, policies...)
        job_id, slug = m.groups()
        lastmod = child_text(node, "lastmod")
        old = jobs.get(job_id)
        if old is None or lastmod > old.lastmod:   # same ID twice -> keep the newest
            jobs[job_id] = SitemapJob(job_id, slug, loc, lastmod)
    return list(jobs.values())


def matches(slug, include, exclude):
    s = slug.lower()
    if any(word in s for word in exclude):
        return False
    return any(word in s for word in include)


def main():
    settings = load_settings()
    include = [k.lower() for k in settings["include_keywords"]]
    exclude = [k.lower() for k in settings.get("exclude_keywords", [])]

    jobs = parse_sitemap(fetch_sitemap())
    hits = sorted((j for j in jobs if matches(j.slug, include, exclude)),
                  key=lambda j: j.lastmod, reverse=True)

    print(f"[sitemap] {len(jobs)} unique jobs in sitemap, {len(hits)} match keywords")
    for j in hits[:25]:
        print(f"  {j.lastmod}  {j.job_id}  {j.slug}")


if __name__ == "__main__":
    main()
