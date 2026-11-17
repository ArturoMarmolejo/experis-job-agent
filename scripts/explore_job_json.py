"""Helper: show where job fields live in the data embedded in a job page.
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


def show_fields(data, ref_number):
    """Print fields whose name looks job-related or whose value has the reference number."""
    for path, value in walk(data):
        text = str(value)
        key = path.rsplit(".", 1)[-1].lower()
        if ref_number in text or "jobapply" in text.lower() \
                or any(h in key for h in KEY_HINTS):
            print(f"  {path} = {text[:100]!r}")


def main(html_path, ref_number):
    html = open(html_path, encoding="utf-8").read()

    # (a) schema.org blocks: <script type="application/ld+json">
    blocks = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S)
    for i, block in enumerate(blocks):
        print(f"\n[explore] ld+json block {i}:")
        try:
            print(json.dumps(json.loads(block), indent=2)[:1500])
        except json.JSONDecodeError as e:
            print("  not valid JSON:", e, "| starts with:", block[:200])

    # (b) the page-state script: the one whose text contains "jobItemID"
    for m in re.finditer(r'<script([^>]*)>(.*?)</script>', html, re.S):
        attrs, body = m.groups()
        if '"jobItemID"' not in body:
            continue
        print(f"\n[explore] state script attributes: {attrs.strip()!r}, {len(body)} characters")
        print("  starts with:", body[:80].replace("\n", " "))
        start, end = body.find("{"), body.rfind("}")   # cut from the first { to the last }
        try:
            data = json.loads(body[start:end + 1])
        except json.JSONDecodeError as e:
            print("  could not parse as JSON:", e)
            continue
        show_fields(data, ref_number)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
