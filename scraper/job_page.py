"""Step 3c (part 1): read one Experis job page and return its fields as a dict.
Test: python -m scraper.job_page https://www.experis.com/en/job/410607/data-engineer
"""
import json
import sys

import requests
from bs4 import BeautifulSoup

from scraper.sitemap import HEADERS, JOB_URL    # reuse what step 3a already defined

BASE = "https://www.experis.com"


def fetch_html(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def find_job_posting(soup):
    """The schema.org JobPosting from the ld+json block(s), or {} if missing."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text())
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def find_jss_job(soup):
    """The job record inside __JSS_STATE__: the first dict that has a 'jobItemID' key."""
    tag = soup.find("script", id="__JSS_STATE__")
    if tag is None:
        return {}
    stack = [json.loads(tag.string or tag.get_text())]
    while stack:                                  # walk the nested data until we find it
        node = stack.pop()
        if isinstance(node, dict):
            if "jobItemID" in node:
                return node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return {}


def html_to_text(html):
    """'<p>What's the Job?</p><ul><li>...' -> plain text, one line per block."""
    return BeautifulSoup(html or "", "html.parser").get_text("\n", strip=True)


def salary_text(posting):
    """baseSalary -> 'USD 58-70 HOUR', or None when the job lists no pay."""
    base = posting.get("baseSalary") or {}
    value = base.get("value") or {}
    if not isinstance(value, dict):
        return None
    low = value.get("minValue") or value.get("value")
    if not low:
        return None
    high = value.get("maxValue")
    amount = f"{low}-{high}" if high else f"{low}"
    return f"{base.get('currency', '')} {amount} {value.get('unitText', '')}".strip()


def as_text(value):
    """employmentType can be a list like ['CONTRACTOR'] -> 'CONTRACTOR'."""
    return ", ".join(value) if isinstance(value, list) else value


def parse_job_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    posting = find_job_posting(soup)
    jss = find_jss_job(soup)
    job_item_id = jss.get("jobItemID")
    return {
        "job_id": jss.get("jobID") or JOB_URL.search(url).group(1),
        "job_item_id": job_item_id,
        "title": jss.get("jobTitle") or posting.get("title"),
        "location": jss.get("jobLocation"),
        "job_type": as_text(posting.get("employmentType")) or jss.get("jobType"),
        "posted_at": jss.get("publishfromDate") or posting.get("datePosted"),
        "valid_through": posting.get("validThrough"),
        "salary": salary_text(posting),
        "description": html_to_text(posting.get("description")),
        "url": url,
        "apply_url": f"{BASE}/en/candidate/jobapply?id={job_item_id}" if job_item_id else None,
    }


def main():
    url = sys.argv[1]
    job = parse_job_page(fetch_html(url), url)
    for key, value in job.items():
        shown = value[:300] + "..." if isinstance(value, str) and len(value) > 300 else value
        print(f"{key:14} {shown!r}")
    missing = [k for k, v in job.items() if not v]
    print("[job_page] empty fields:", missing or "none")


if __name__ == "__main__":
    main()
