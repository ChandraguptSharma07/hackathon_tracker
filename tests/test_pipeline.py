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
