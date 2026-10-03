import pytest

from hackathon_tracker.models import Hackathon
from hackathon_tracker.places import find_metro, resolve, tag


def make(**kw):
    return Hackathon(id="x:1", source="x", title=kw.pop("title", "Some Hack"),
                     url="https://x.example", **kw)


@pytest.mark.parametrize("location,expected", [
    ("West Delhi, Delhi, India", "Delhi NCR"),
    ("Greater Noida, Uttar Pradesh, India", "Delhi NCR"),
    ("Gautam Buddha Nagar, Uttar Pradesh, India", "Delhi NCR"),
    ("Sohna Rural, Haryana, India", "Delhi NCR"),
    ("नई दिल्ली", "Delhi NCR"),
    ("Block 45, Sharda University,", "Delhi NCR"),
    ("Navi Mumbai, Maharashtra, India", "Mumbai"),
    ("Manali, Himachal Pradesh, India", None),
])
def test_find_metro(location, expected):
    assert find_metro(location) == expected


def test_online_events_get_no_metro():
    assert tag(make(mode="online", location="New Delhi")).metro is None


def test_title_fallback_only_without_city():
    venue_only = tag(make(title="Hack Day Teens Delhi", mode="in_person",
                          location="The Grandeur Banquet"))
    assert venue_only.metro == "Delhi NCR"
    elsewhere = tag(make(title="Delhi Coders Retreat", mode="in_person",
                         location="Manali, Himachal Pradesh", city="Manali"))
    assert elsewhere.metro is None


@pytest.mark.parametrize("text,expected", [
    ("delhi", "Delhi NCR"), ("Delhi NCR", "Delhi NCR"), ("bangalore", "Bengaluru"),
    ("atlantis", None),
])
def test_resolve(text, expected):
    assert resolve(text) == expected
