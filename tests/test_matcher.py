"""Matching rules: normalizing, whole-word checks, scoring. Pure functions, no files."""
from datetime import datetime, timedelta, timezone

import pytest

from scraper.matcher import has, norm, score_job


def test_norm_unifies_separators():
    assert norm("Full-Stack/Node.js Developer") == "full stack nodejs developer"


@pytest.mark.parametrize("text, term, whole_word, expected", [
    ("javascript typescript engineer", "java", True, False),   # the big trap
    ("full stack java developer", "java", True, True),
    ("senior reactjs developer", "react", False, True),        # skills may match a longer word
    ("pyspark and airflow", "spark", False, False),            # ...but only at the start
    ("full stack c++ python developer", "c++", True, True),
])
def test_has(text, term, whole_word, expected):
    assert has(text, term, whole_word=whole_word) is expected


PROFILE = {
    "target titles": ["data engineer"],
    "core skills": ["python", "sql"],
    "nice to have": ["etl"],
    "deal-breakers in the title": ["java", "manager"],
    "locations": ["charlotte nc"],
}
CUTOFF = datetime(2026, 11, 19, tzinfo=timezone.utc) - timedelta(days=30)


def job(title, description="", location="", posted="2026-11-15T00:00:00Z"):
    return {"title": title, "description": description, "location": location, "posted_at": posted}


def test_deal_breaker_rejects():
    score, why = score_job(job("Java Full Stack Developer"), PROFILE, CUTOFF)
    assert score == 0 and "java" in why


def test_javascript_is_not_java():
    score, _ = score_job(job("JavaScript Data Engineer"), PROFILE, CUTOFF)
    assert score > 0


def test_old_job_rejected():
    score, why = score_job(job("Data Engineer", posted="2026-09-01T00:00:00Z"), PROFILE, CUTOFF)
    assert score == 0 and "too old" in why


def test_score_breakdown():
    score, why = score_job(job("Data Engineer", "Python, SQL and ETL pipelines", "Charlotte, NC"),
                           PROFILE, CUTOFF)
    # title 40 + 2 core skills (10) + 1 nice-to-have (2.5) + location (10) = 62.5 -> 62
    assert score == 62
    assert "title~data engineer" in why and "loc~charlotte nc" in why
