"""The submit safety rails. No browser, no network."""
import pytest

from scraper.apply import can_submit

REAL = {"fictional": False, "email": "me@realmail.com", "consent": {"accept_privacy_policy": True}}


def test_without_submit_flag_it_is_always_a_dry_run():
    assert can_submit(REAL, False) == (False, "dry run (no --submit)")


def test_real_consenting_applicant_can_submit():
    assert can_submit(REAL, True)[0] is True


@pytest.mark.parametrize("change, reason_word", [
    ({"fictional": True}, "fictional"),
    ({"email": "jordan.reyes@example.com"}, "placeholder"),
    ({"consent": {"accept_privacy_policy": False}}, "accept_privacy_policy"),
    ({"consent": None}, "accept_privacy_policy"),
])
def test_submit_is_refused(change, reason_word):
    allowed, reason = can_submit({**REAL, **change}, True)
    assert allowed is False and reason_word in reason


def test_missing_fictional_flag_counts_as_fictional():
    applicant = {k: v for k, v in REAL.items() if k != "fictional"}
    assert can_submit(applicant, True)[0] is False
