from datetime import UTC, datetime, timedelta

from hackathon_tracker.models import Hackathon
from hackathon_tracker.pipeline import Feed, build_feed

NOW = datetime(2026, 10, 4, tzinfo=UTC)


def make(source, title, days=10, **kw):
    return Hackathon(id=f"{source}:{title}", source=source, title=title,
                     url=f"https://{source}.example/{title}",
                     ends_at=NOW + timedelta(days=days), **kw)


def boom(client):
    raise RuntimeError("site down")


def test_drops_past_and_tags_sponsors():
    sources = {"a": lambda c: [make("a", "Old", days=-5),
                               make("a", "Build with Claude", organizer="Anthropic")]}
    feed = build_feed(sources, now=NOW)
    assert [h.title for h in feed.hackathons] == ["Build with Claude"]
    assert feed.hackathons[0].sponsors == ["Anthropic"]
    assert feed.hackathons[0].first_seen == NOW


def test_failed_source_reuses_previous_data():
    old = make("b", "Kept", first_seen=NOW - timedelta(days=3))
    previous = Feed(generated_at=NOW, count=1, sources={}, hackathons=[old])
    feed = build_feed({"a": lambda c: [make("a", "Fresh")], "b": boom},
                      previous=previous, now=NOW)
    assert {h.title for h in feed.hackathons} == {"Fresh", "Kept"}
    assert feed.sources["b"].stale and not feed.sources["b"].ok
    assert "site down" in feed.sources["b"].error
    kept = next(h for h in feed.hackathons if h.title == "Kept")
    assert kept.first_seen == NOW - timedelta(days=3)


def test_sorted_by_soonest_deadline():
    feed = build_feed({"a": lambda c: [make("a", "Later", days=20), make("a", "Sooner", days=2)]},
                      now=NOW)
    assert [h.title for h in feed.hackathons] == ["Sooner", "Later"]


def test_tracking_since_starts_at_first_run_and_carries_forward():
    first = build_feed({"a": lambda c: [make("a", "X")]}, now=NOW)
    assert first.tracking_since == NOW
    later = NOW + timedelta(hours=6)
    second = build_feed({"a": lambda c: [make("a", "X"), make("a", "Y")]}, previous=first,
                        now=later)
    assert second.tracking_since == NOW
    seen = {h.title: h.first_seen for h in second.hackathons}
    assert seen == {"X": NOW, "Y": later}


def test_partial_refresh_carries_other_sources():
    first = build_feed({"a": lambda c: [make("a", "A1")], "b": lambda c: [make("b", "B1")]},
                       now=NOW)
    partial = build_feed({"a": lambda c: [make("a", "A2")]}, previous=first, now=NOW,
                         carry_over=True)
    assert {h.title for h in partial.hackathons} == {"A2", "B1"}
    assert set(partial.sources) == {"a", "b"}
    fresh = build_feed({"a": lambda c: [make("a", "A2")]}, previous=first, now=NOW)
    assert {h.title for h in fresh.hackathons} == {"A2"}
