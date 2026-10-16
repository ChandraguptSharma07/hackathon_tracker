from datetime import UTC, datetime, timedelta

import pytest

from hackathon_tracker.models import Hackathon
from hackathon_tracker.registration import infer, is_open

NOW = datetime(2026, 10, 16, tzinfo=UTC)
START, END = NOW + timedelta(days=5), NOW + timedelta(days=20)


def make(source="x", **kw):
    kw.setdefault("starts_at", START)
    kw.setdefault("ends_at", END)
    return Hackathon(id=f"{source}:1", source=source, title="T", url="https://x.example", **kw)


def test_explicit_deadline_is_kept():
    deadline = NOW + timedelta(days=2)
    h = infer(make("unstop", registration_deadline=deadline))
    assert h.registration_deadline == deadline and not h.registration_inferred


@pytest.mark.parametrize("source,expected", [
    ("kaggle", END), ("devpost", END), ("dorahacks", END),  # join while running (online)
    ("unstop", START), ("mlh", START), ("luma", START),  # register before it starts
])
def test_source_policy(source, expected):
    h = infer(make(source))
    assert h.registration_deadline == expected and h.registration_inferred


@pytest.mark.parametrize("kw,expected", [
    ({"mode": "online"}, END), ({"kind": "competition", "mode": "in_person"}, END),
    ({"mode": "in_person"}, START), ({"mode": "hybrid"}, START),
])
def test_fallback_for_unknown_sources(kw, expected):
    assert infer(make("newsite", **kw)).registration_deadline == expected


def test_running_unstop_event_is_closed_but_kaggle_is_open():
    running = {"starts_at": NOW - timedelta(days=3)}
    assert is_open(infer(make("unstop", **running)), NOW) is False
    assert is_open(infer(make("kaggle", **running)), NOW) is True


def test_explicit_closed_flag_wins_over_future_deadline():
    h = make("luma", registration_open=False, registration_deadline=NOW + timedelta(days=9))
    assert is_open(h, NOW) is False


def test_no_evidence_is_unknown():
    assert is_open(make("x", starts_at=None, ends_at=None), NOW) is None


def test_in_person_never_late_join_even_on_late_join_sites():
    h = infer(make("devpost", mode="in_person"))
    assert h.registration_deadline == START


def test_any_late_join_listing_counts_for_merged_events():
    from hackathon_tracker.models import Listing
    h = make("cerebralvalley", mode="hybrid",
             also_on=[Listing(source="lablab", url="https://lablab.example")])
    assert infer(h).registration_deadline == END
