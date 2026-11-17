"""Helper: show where job fields live in the JSON embedded in a job page.
Usage: python scripts/explore_job_json.py /tmp/job.html 410607
"""
import json
import re
import sys

KEY_HINTS = ["reference", "title", "posted", "date", "type", "location",
             "city", "state", "apply", "description", "salary", "pay", "id"]


def walk(obj, path=""):
    """Yield (path, value) for every leaf in nested dicts/lists."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:2]):      # first 2 items show the shape
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def main(html_path, ref_number):
    html = open(html_path, encoding="utf-8").read()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        print("[explore] no __NEXT_DATA__ block; ld+json blocks:",
              html.count("application/ld+json"))
        return
    data = json.loads(m.group(1))
    print("[explore] __NEXT_DATA__ found,", len(m.group(1)), "characters")
    for path, value in walk(data):
        text = str(value)
        key = path.rsplit(".", 1)[-1].lower()
        if ref_number in text or "jobapply" in text.lower() \
                or any(h in key for h in KEY_HINTS):
            print(f"{path} = {text[:100]!r}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
