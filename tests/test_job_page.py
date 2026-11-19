"""Job page parsing and the Job model's cleaning rules, using a fake page (no network)."""
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from scraper.job_page import Job, parse_job_page

URL = "https://www.experis.com/en/job/410607/data-engineer"
LD_JSON = [
    {"@type": "WebPage"},
    {"@type": "JobPosting", "title": "Data Engineer", "employmentType": "Contract",
     "datePosted": "2026-09-08", "validThrough": "20261207T225959Z",
     "description": "<p>Our client <b>needs</b> you.</p><ul><li>Python</li></ul>"},
]
JSS_STATE = {"sitecore": {"route": {"placeholders": {"jss-main": [{"fields": {"items": {
    "jobID": "410607", "jobItemID": "2460a433-65ed-415c-9c31-5f35d8c2ccba",
    "jobTitle": "Data Engineer", "jobLocation": "San Antonio/TX/United States",
    "publishfromDate": "2026-09-08T17:01:34Z"}}}]}}}}
PAGE = f"""<html><head>
<script type="application/ld+json">{json.dumps(LD_JSON)}</script>
<script type="application/json" id="__JSS_STATE__">{json.dumps(JSS_STATE)}</script>
</head><body><h1>Data Engineer</h1></body></html>"""


def test_parse_job_page_merges_both_sources():
    job = parse_job_page(PAGE, URL)
    assert job.job_id == "410607"
    assert job.title == "Data Engineer"
    assert job.location == "San Antonio, TX"                  # cleaned
    assert job.job_type == "Contract"
    assert job.posted_at == datetime(2026, 9, 8, 17, 1, 34, tzinfo=timezone.utc)
    assert job.valid_through == datetime(2026, 12, 7, 22, 59, 59, tzinfo=timezone.utc)   # compact format
    assert job.description.startswith("Our client")           # HTML turned into text
    assert job.apply_url.endswith("?id=2460a433-65ed-415c-9c31-5f35d8c2ccba")


def test_page_without_data_is_rejected():
    with pytest.raises(ValidationError):                      # no title -> breaks the contract
        parse_job_page("<html><body>nothing here</body></html>", URL)


@pytest.mark.parametrize("raw, expected", [
    ("San Antonio/TX/United States", "San Antonio, TX"),
    ("Spring, TX", "Spring, TX"),
    ("", None),
])
def test_clean_location(raw, expected):
    assert Job(job_id="1", title="t", url="u", location=raw).location == expected


def test_placeholder_deadline_becomes_none():
    assert Job(job_id="1", title="t", url="u", valid_through="0001-01-01T00:00:00").valid_through is None
