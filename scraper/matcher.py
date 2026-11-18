"""Step 4: score every saved job against the candidate profile (+ resume check).
Run: python -m scraper.matcher [--min-score 0] [--top 30]
"""
import argparse
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import docx

from scraper.db import DB_PATH

PROFILE_PATH = Path("config/profile.md")
RESUME_PATH = Path("config/resume.docx")


def norm(text):
    """Lowercase + unify separators: 'Full-Stack/Node.js' -> 'full stack nodejs'."""
    text = (text or "").lower().replace(".", "")
    text = re.sub(r"[-/–—(),:;|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has(text, term, whole_word=True):
    """Is `term` a word in `text`? (both normalized)
    whole_word=False also accepts a longer word that starts with it: 'react' -> 'reactjs'."""
    pattern = r"(?<![a-z0-9])" + re.escape(term) + (r"(?![a-z0-9])" if whole_word else "")
    return re.search(pattern, text) is not None


def load_profile(path=PROFILE_PATH):
    """profile.md -> {'target titles': [...], 'core skills': [...], ...}"""
    sections, current = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current and line.startswith("- "):
            sections[current].append(norm(line[2:]))
    return sections


def max_age_days(profile, default=30):
    for item in profile.get("search window", []):
        m = re.search(r"max_age_days\D*(\d+)", item)
        if m:
            return int(m.group(1))
    return default


def resume_text(path=RESUME_PATH):
    return norm(" ".join(p.text for p in docx.Document(path).paragraphs))


def warn_unbacked_skills(profile, resume):
    """Every skill we match on should be backed by the resume."""
    for skill in profile.get("core skills", []) + profile.get("nice to have", []):
        if not has(resume, skill, whole_word=False):
            print(f"[matcher] warning: profile skill '{skill}' is not in the resume")


def score_job(job, profile, cutoff):
    """Return (score 0-100, reason text)."""
    title = norm(job["title"])
    desc = norm(job["description"])
    text = title + " " + desc
    fully_remote = "fully remote" in desc or "100% remote" in desc
    place = norm(job["location"]) + " " + title + (" remote" if fully_remote else "")       # 'remote' may only be in the description

    for bad in profile.get("deal-breakers in the title", []):
        if has(title, bad):                              # whole word: 'java' != 'javascript'
            return 0, f"deal-breaker in title: {bad}"
    posted = job["posted_at"]
    if posted and datetime.fromisoformat(posted) < cutoff:
        return 0, f"too old (posted {posted[:10]})"

    score, reasons = 0, []
    titles = [t for t in profile.get("target titles", []) if has(title, t, whole_word=False)]
    if titles:
        score += 40
        reasons.append(f"title~{titles[0]}")
    core = [s for s in profile.get("core skills", []) if has(text, s, whole_word=False)]
    score += min(len(core), 8) * 5
    nice = [s for s in profile.get("nice to have", []) if has(text, s, whole_word=False)]
    score += min(len(nice), 4) * 2.5
    locs = [l for l in profile.get("locations", []) if has(place, l)]
    if locs:
        score += 10
        reasons.append(f"loc~{locs[0]}")
    if core:
        reasons.append("core: " + ", ".join(core))
    if nice:
        reasons.append("nice: " + ", ".join(nice))
    return round(score), "; ".join(reasons) or "no match"


def load_jobs(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row                       # rows behave like dicts: job["title"]
    rows = conn.execute("SELECT job_id, title, location, description, posted_at, "
                        "first_seen_at, url, apply_url FROM jobs").fetchall()
    conn.close()
    return rows


def rank_jobs(profile):
    """[(score, job, why), ...] best first. The report step will reuse this."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days(profile))
    results = [(*score_job(job, profile, cutoff), job) for job in load_jobs()]
    results = [(score, job, why) for score, why, job in results]
    return sorted(results, key=lambda r: r[0], reverse=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=int, default=1, help="hide jobs below this score")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    profile = load_profile()
    warn_unbacked_skills(profile, resume_text())
    results = rank_jobs(profile)
    kept = [r for r in results if r[0] >= args.min_score]
    rejected = [r for r in results if r[0] == 0]

    print(f"[matcher] {len(results)} jobs | kept {len(kept)} | rejected {len(rejected)} "
          f"| window {max_age_days(profile)} days")
    for score, job, why in kept[: args.top]:
        print(f"  {score:3}  {job['job_id']}  {job['title'][:42]:42}  "
              f"{(job['location'] or '-')[:16]:16}  {why[:70]}")
    print("[matcher] rejected:")
    for _, job, why in rejected:
        print(f"       {job['job_id']}  {job['title'][:42]:42}  -> {why}")


if __name__ == "__main__":
    main()
