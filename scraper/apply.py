"""Step 8: fill Experis application forms. DRY RUN by default: the final APPLY is never clicked.
Run: python -m scraper.apply --job-id 410607           # dry run on one job
     python -m scraper.apply --limit 2                 # dry run on the 2 best matches (score >= 70)
Submitting needs ALL of: --submit, a non-fictional applicant with a real email,
accept_privacy_policy: true in config/applicant.yaml, and typing 'y' for each job.
"""
import argparse
import random
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml

from scraper.db import DB_PATH
from scraper.log import get_logger
from scraper.matcher import load_jobs, load_profile, rank_jobs

APPLICANT_PATH = Path("config/applicant.yaml")
SHOT_DIR = Path("screenshots")                          # git-ignored
TEXT_FIELDS = {"First Name": "first_name", "Last Name": "last_name",
               "Email": "email", "PhoneNumber": "phone"}       # form label -> applicant.yaml key
CHECKBOXES = {"promotional": "promotional_emails", "SMS": "sms_messages"}   # word in label -> consent key

APPLICATIONS = """
CREATE TABLE IF NOT EXISTS applications (
    job_id      TEXT PRIMARY KEY,
    status      TEXT,          -- dry_run | submitted | failed
    detail      TEXT,
    screenshot  TEXT,
    updated_at  TEXT
)"""


def load_applicant(path=APPLICANT_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def can_submit(applicant, submit_flag):
    """The safety rails. Returns (allowed, reason). Pure function, so it is easy to test."""
    if not submit_flag:
        return False, "dry run (no --submit)"
    if applicant.get("fictional", True):                 # missing flag counts as fictional
        return False, "applicant is marked fictional"
    if str(applicant.get("email", "")).lower().endswith("@example.com"):
        return False, "email is a placeholder (example.com)"
    if not (applicant.get("consent") or {}).get("accept_privacy_policy"):
        return False, "accept_privacy_policy is not true in applicant.yaml"
    return True, "all checks passed"


def record(conn, job_id, status, detail, screenshot=None):
    conn.execute(
        "INSERT INTO applications VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(job_id) DO UPDATE SET status = excluded.status, detail = excluded.detail, "
        "screenshot = excluded.screenshot, updated_at = excluded.updated_at",
        (job_id, status, detail, screenshot,
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()


def pick_jobs(conn, job_id, limit, min_score):
    """Best matches that have an apply link and were never submitted."""
    submitted = {r[0] for r in conn.execute("SELECT job_id FROM applications WHERE status = 'submitted'")}
    if job_id:
        return [(None, j) for j in load_jobs() if j["job_id"] == job_id and job_id not in submitted]
    ranked = rank_jobs(load_profile())
    return [(score, job) for score, job, _ in ranked
            if score >= min_score and job["apply_url"] and job["job_id"] not in submitted][:limit]


def pause(low=0.6, high=1.6):
    time.sleep(random.uniform(low, high))               # human-like gaps between actions


@contextmanager
def open_browser(kind):
    """A VISIBLE browser. Camoufox = stealth Firefox; chromium = plain Playwright fallback."""
    if kind == "camoufox":
        from camoufox.sync_api import Camoufox           # imported only when used
        with Camoufox(headless=False, humanize=True, os="linux") as browser:
            yield browser.new_page()
    else:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            yield browser.new_page(viewport={"width": 1280, "height": 900})
            browser.close()


def fill_form(page, applicant, log):
    for label, key in TEXT_FIELDS.items():
        box = page.get_by_role("textbox", name=label, exact=True)
        box.click()
        box.fill("")
        box.press_sequentially(str(applicant[key]), delay=random.randint(60, 140))   # typed, not pasted
        pause()

    page.locator('input[name="CV_file_upload"]').set_input_files(applicant["resume"])
    log.info(f"uploaded {Path(applicant['resume']).name}")
    pause()

    consent = applicant.get("consent") or {}
    for word, key in CHECKBOXES.items():
        box = page.get_by_role("checkbox", name=re.compile(word, re.I))
        if box.count() == 0:
            log.warning(f"checkbox containing '{word}' not found")
            continue
        wanted = bool(consent.get(key))
        cb = box.first
        if cb.is_checked() != wanted:
            cb.dispatch_event("click")       # the real <input> is hidden under a styled box
            pause()
        if cb.is_checked() != wanted:        # never continue with the wrong consent
            raise RuntimeError(f"could not set the '{word}' checkbox to {wanted}")
    boxes = page.get_by_role("checkbox")
    for i in range(boxes.count()):                       # log the final state of every box
        cb = boxes.nth(i)
        label = cb.evaluate("e => (e.closest('label') || e.parentElement).innerText.slice(0, 50)")
        log.info(f"checkbox '{label.strip()}': checked={cb.is_checked()}")


def apply_one(page, job, applicant, allowed, conn, log):
    job_id = job["job_id"]
    page.goto(job["apply_url"], wait_until="domcontentloaded")
    page.get_by_role("textbox", name="First Name", exact=True).wait_for(timeout=20000)
    pause(1.5, 3)
    fill_form(page, applicant, log)

    button = page.get_by_role("button", name="APPLY", exact=True)   # exact: never "APPLY NOW"
    if button.count() == 0:
        raise RuntimeError("final APPLY button not found")
    button.scroll_into_view_if_needed()
    SHOT_DIR.mkdir(exist_ok=True)
    shot = SHOT_DIR / f"apply_{job_id}_{datetime.now():%Y%m%d_%H%M%S}.png"
    page.screenshot(path=str(shot), full_page=True)

    if not allowed:
        record(conn, job_id, "dry_run", "form filled, APPLY not clicked", str(shot))
        log.info(f"DRY RUN {job_id}: form filled, APPLY not clicked, screenshot {shot}")
        return
    answer = input(f"Submit application for {job_id} '{job['title']}'? Type y to send: ")
    if answer.strip().lower() != "y":
        record(conn, job_id, "dry_run", "declined at the prompt", str(shot))
        log.info(f"{job_id}: not sent (declined)")
        return
    button.click()
    page.wait_for_load_state("networkidle")
    after = SHOT_DIR / f"submitted_{job_id}_{datetime.now():%Y%m%d_%H%M%S}.png"
    page.screenshot(path=str(after), full_page=True)
    record(conn, job_id, "submitted", "APPLY clicked; check the confirmation screenshot", str(after))
    log.info(f"SUBMITTED {job_id}: confirmation screenshot {after}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", help="one specific reference number")
    parser.add_argument("--limit", type=int, default=1, help="how many top matches")
    parser.add_argument("--min-score", type=int, default=70)
    parser.add_argument("--browser", choices=["camoufox", "chromium"], default="camoufox")
    parser.add_argument("--submit", action="store_true",
                        help="really submit (still needs a real, consenting applicant)")
    args = parser.parse_args()

    log = get_logger()
    applicant = load_applicant()
    allowed, reason = can_submit(applicant, args.submit)
    if args.submit and not allowed:
        log.warning(f"--submit refused: {reason}")
    log.info(f"mode: {'SUBMIT (asks per job)' if allowed else 'DRY RUN'} ({reason})")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(APPLICATIONS)
    jobs = pick_jobs(conn, args.job_id, args.limit, args.min_score)
    log.info(f"{len(jobs)} job(s) selected")
    if jobs:
        with open_browser(args.browser) as page:
            for i, (score, job) in enumerate(jobs, 1):
                log.info(f"[{i}/{len(jobs)}] {job['job_id']} {job['title']} (score {score})")
                try:
                    apply_one(page, job, applicant, allowed, conn, log)
                except Exception as e:                    # one bad form must not stop the batch
                    record(conn, job["job_id"], "failed", str(e)[:200])
                    log.warning(f"FAILED {job['job_id']}: {e}")
                if i < len(jobs):
                    pause(20, 40)                         # long gap between applications
    conn.close()


if __name__ == "__main__":
    main()
