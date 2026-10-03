from datetime import UTC, datetime, timedelta

from hackathon_tracker.dedupe import dedupe, norm_title
from hackathon_tracker.models import Hackathon

START = datetime(2026, 10, 9, tzinfo=UTC)


def make(source, title, start=START, **kw):
    return Hackathon(id=f"{source}:{title}", source=source, title=title,
                     url=f"https://{source}.example/{title}", starts_at=start, **kw)


def test_norm_title():
    assert norm_title("HackRPI 2026") == "hackrpi"
    assert norm_title("The Big-Data Hackathon 2026-27") == "big data"


def test_merges_cross_listed_event():
    mlh = make("mlh", "Knight Hacks IX", city="Orlando")
    dp = make("devpost", "Knight Hacks IX", prize_usd=5000)
    out = dedupe([mlh, dp])
    assert len(out) == 1
    h = out[0]
    assert h.source == "devpost"  # higher priority wins
    assert h.city == "Orlando"  # gaps filled from the other listing
    assert [l.source for l in h.also_on] == ["mlh"]


def test_keeps_distinct_events_with_similar_names():
    out = dedupe([make("devpost", "Knight Hacks IX"), make("mlh", "HackKnight"),
                  make("mlh", "Knight Hacks IX")])
    assert len(out) == 2


def test_far_apart_dates_do_not_merge():
    out = dedupe([make("devpost", "HackRPI 2026"),
                  make("mlh", "HackRPI 2026", start=START + timedelta(days=30))])
    assert len(out) == 2


def test_same_source_never_merges():
    out = dedupe([make("cerebralvalley", "Global AI Hackathon"),
                  make("cerebralvalley", "Global AI Hackathon ")])
    assert len(out) == 2
