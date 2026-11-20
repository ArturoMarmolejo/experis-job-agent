"""Step 9: one way to download pages, with a Camoufox fallback when plain HTTP is blocked.
Modes: auto (HTTP first, browser only if blocked), http (never a browser), browser (always).
"""
import random
import time

from scraper.log import get_logger
from scraper.sitemap import SESSION

BLOCK_STATUS = {403, 429, 503}                         # "go away" answers, not normal errors
CHALLENGE_MARKERS = ("<title>Just a moment", "cf-chl", "Attention Required! | Cloudflare")


class Blocked(Exception):
    """The site answered with a bot wall instead of content."""


def looks_blocked(status, text):
    """True when the answer is a bot wall (status code or a Cloudflare challenge page)."""
    return status in BLOCK_STATUS or any(marker in text for marker in CHALLENGE_MARKERS)


class Fetcher:
    def __init__(self, mode="auto"):
        self.mode = mode
        self.log = get_logger()
        self._camoufox = None                           # started only if ever needed
        self._page = None

    def get(self, url):
        """Return (body as bytes, 'http' or 'browser')."""
        if self.mode != "browser":
            resp = SESSION.get(url, timeout=30)
            if not looks_blocked(resp.status_code, resp.text):
                resp.raise_for_status()                 # 404 / 502 are real errors, not blocks
                return resp.content, "http"
            if self.mode == "http":
                raise Blocked(f"{resp.status_code} bot wall at {url} (browser fallback disabled)")
            self.log.warning(f"plain HTTP blocked ({resp.status_code}) at {url}: switching to the browser")
            self.mode = "browser"                       # sticky: don't keep knocking on a closed door
        return self._browser_get(url), "browser"

    def _browser_page(self):
        if self._page is None:
            from camoufox.sync_api import Camoufox       # imported only when the fallback is used
            self._camoufox = Camoufox(headless=False, humanize=True, os="linux")
            self._page = self._camoufox.__enter__().new_page()
            self.log.info("started the Camoufox fallback browser")
        return self._page

    def _browser_get(self, url):
        page = self._browser_page()
        for attempt in range(1, 4):
            resp = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)   # let a JS check finish
            except Exception:
                pass                                    # busy pages (chat widget) never go fully idle
            status = resp.status if resp else 0
            if not looks_blocked(status, page.content()):
                if resp and "xml" in resp.headers.get("content-type", ""):
                    return resp.body()                  # sitemap: the raw XML, not Firefox's XML viewer
                return page.content().encode("utf-8")
            self.log.warning(f"browser attempt {attempt}: still blocked at {url}")
            time.sleep(random.uniform(5, 10))           # the next attempt carries the challenge's cookie
        raise Blocked(f"still blocked after 3 browser attempts: {url}")

    def close(self):
        if self._camoufox is not None:
            self._camoufox.__exit__(None, None, None)
            self._camoufox = self._page = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
