"""Fallback decisions, with fake HTTP answers and a stubbed browser (no network, no browser)."""
import pytest
import requests

from scraper import fetch
from scraper.fetch import Blocked, Fetcher, looks_blocked


class FakeResponse:
    def __init__(self, status, text):
        self.status_code, self.text, self.content = status, text, text.encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


@pytest.mark.parametrize("status, text, expected", [
    (200, "<html><title>Data Engineer</title></html>", False),
    (403, "Forbidden", True),
    (503, "", True),
    (200, "<html><head><title>Just a moment...</title>", True),   # Cloudflare challenge page
    (404, "Not found", False),                                     # a real error, not a bot wall
])
def test_looks_blocked(status, text, expected):
    assert looks_blocked(status, text) is expected


def fake_http(monkeypatch, status, text):
    monkeypatch.setattr(fetch.SESSION, "get", lambda url, timeout: FakeResponse(status, text))


def test_normal_page_uses_http(monkeypatch):
    fake_http(monkeypatch, 200, "<html>ok</html>")
    assert Fetcher("auto").get("https://x") == (b"<html>ok</html>", "http")


def test_blocked_page_switches_to_browser_and_stays(monkeypatch):
    fake_http(monkeypatch, 403, "Forbidden")
    fetcher = Fetcher("auto")
    monkeypatch.setattr(fetcher, "_browser_get", lambda url: b"<html>via browser</html>")
    assert fetcher.get("https://x/1") == (b"<html>via browser</html>", "browser")
    assert fetcher.mode == "browser"                     # sticky for the rest of the run


def test_http_mode_never_opens_a_browser(monkeypatch):
    fake_http(monkeypatch, 403, "Forbidden")
    with pytest.raises(Blocked):
        Fetcher("http").get("https://x")


def test_real_errors_are_not_treated_as_blocks(monkeypatch):
    fake_http(monkeypatch, 404, "Not found")
    with pytest.raises(requests.HTTPError):
        Fetcher("auto").get("https://x")
