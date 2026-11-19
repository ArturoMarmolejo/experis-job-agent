# Experis Job Agent

Daily job-search automation for **Experis** (experis.com, US). Every morning it finds new or changed
jobs, scores them against a candidate profile, and writes a report with one-click Apply links.
**No browser automation:** plain HTTP requests read the site's public sitemap and the JSON embedded in each job page.

```
sitemap.xml ─▶ keyword filter ─▶ new/changed only ─▶ fetch page ─▶ Pydantic Job ─▶ SQLite
                                                                                   │
                     resume.docx + profile.md ─▶ matcher (score + why) ◀───────────┘
                                                      │
                                                      ▼
                                   data/reports/report_<date>.html / .csv / .json
```

## Features
- **Incremental:** only jobs whose sitemap `lastmod` changed are downloaded (about 1 s on a quiet day).
- **Polite:** 3–5 s between pages; follows robots.txt (no automation in `/candidate`, so applying stays manual).
- **Clean data:** a Pydantic `Job` model validates dates, locations and required fields.
- **Explainable matching:** deal-breakers, a 30-day window, title, skill and location scores, each with a reason.
- **Reports:** HTML (NEW badges, Apply buttons) plus CSV and JSON exports.
- **Scheduled:** Windows Task Scheduler runs `run_daily.sh` at 08:30, with a lock against overlapping runs.

## Setup (WSL Ubuntu)
```bash
git clone https://github.com/ArturoMarmolejo/experis-job-agent.git
cd experis-job-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
Add your own files (git-ignored):
- `config/resume.docx`: the candidate's resume
- `config/profile.md`: target titles, core skills, nice-to-have, deal-breakers, locations, `max_age_days`

## Usage
```bash
python -m scraper.run_discovery [--limit 3]   # fetch new/changed jobs into data/jobs.db
python -m scraper.matcher | head -40          # ranking + rejected jobs with reasons
python -m scraper.report [--min-score 50]     # HTML / CSV / JSON report in data/reports/
./run_daily.sh                                # full daily run (log in logs/daily_<date>.log)
```

## Daily schedule (Windows)
In **Task Scheduler**: daily at 08:30, program `wsl.exe`, arguments
`-d Ubuntu -- bash /home/<user>/experis-job-agent/run_daily.sh`.
Tick "run as soon as possible after a missed start" and untick "only on AC power".

## Project layout
| Path | Purpose |
|---|---|
| `scraper/sitemap.py` | download + parse the sitemap, dedupe, keyword filter |
| `scraper/job_page.py` | `Job` model; reads schema.org JobPosting + Sitecore `__JSS_STATE__` |
| `scraper/db.py` | SQLite table + upsert (keeps `first_seen_at`) |
| `scraper/run_discovery.py` | incremental fetch loop with delays and per-job commits |
| `scraper/matcher.py` | scoring with reasons |
| `scraper/report.py` | HTML / CSV / JSON report |
| `run_daily.sh` | locked daily run with logging |
| `scripts/explore_job_json.py` | helper used to inspect a job page's embedded data |

## Notes
- The test resume is a **fictional persona** and is never submitted to employers.
- `data/`, `logs/`, `*.db` and `config/*.docx` are git-ignored.
