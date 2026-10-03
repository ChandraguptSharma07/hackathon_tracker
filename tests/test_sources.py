from datetime import UTC, datetime

import pytest

from hackathon_tracker.sources import (cerebralvalley, devfolio, devpost, hackerearth, lablab,
                                       mlh, unstop)


def test_devpost(fixture):
    items = devpost.parse(fixture("devpost.json"))
    assert len(items) == 4
    h = items[0]
    assert h.id == "devpost:30992"
    assert h.title == "Build, Ship, Shape: Amazon Developer Hackathon"
    assert h.organizer == "Amazon"
    assert h.mode == "online" and h.location is None
    assert h.starts_at == datetime(2026, 8, 31, tzinfo=UTC)
    assert h.ends_at == datetime(2026, 10, 23, 23, 59, tzinfo=UTC)
    assert (h.prize_amount, h.prize_currency, h.prize_usd) == (138000, "USD", 138000)
    assert "Machine Learning/AI" in h.themes


def test_mlh(fixture):
    items = mlh.parse(fixture("mlh.html"))
    assert len(items) == 3
    h = items[0]
    assert h.id == "mlh:bigred-hacks-2026"
    assert h.url == "https://www.bigredhacks.com/"
    assert h.mode == "in_person"
    assert (h.city, h.country) == ("Ithaca", "US")
    assert h.starts_at == datetime(2026, 10, 2, 20, 30, tzinfo=UTC)


def test_mlh_missing_data_raises():
    with pytest.raises(ValueError):
        mlh.parse("<html></html>")


@pytest.mark.parametrize("month,expected", [(10, 2027), (7, 2026), (8, 2027), (1, 2026)])
def test_mlh_season(month, expected):
    assert mlh.season(datetime(2026, month, 1, tzinfo=UTC)) == expected


def test_devfolio(fixture):
    items = devfolio.parse(fixture("devfolio.json"))
    assert len(items) == 3
    h = items[0]
    assert h.url == "https://hackverse-19.devfolio.co/"
    assert h.mode == "in_person"
    assert h.country == "India"
    assert h.registration_deadline == datetime(2026, 10, 4, 18, 29, tzinfo=UTC)
    assert h.participants == 196


def test_unstop(fixture):
    items = unstop.parse(fixture("unstop.json"))
    assert len(items) == 3
    h = items[0]
    assert h.organizer.startswith("Netaji Subhas")
    assert h.starts_at is None  # Unstop listings carry no start date
    assert (h.prize_amount, h.prize_currency) == (100000, "INR")
    assert h.prize_usd == pytest.approx(1200)
    assert h.location == "West Delhi, Delhi, India"


def test_hackerearth_keeps_only_hackathons(fixture):
    payload = fixture("hackerearth.json")
    payload["response"].append({"title": "Monthly Easy", "url":
                                "https://www.hackerearth.com/challenges/competitive/x/"})
    items = hackerearth.parse(payload)
    assert len(items) == 3
    assert all("/challenges/hackathon/" in h.url for h in items)
    assert items[0].starts_at == datetime(2026, 8, 16, 18, 30, tzinfo=UTC)


def test_cerebralvalley_skips_non_hackathons(fixture):
    items = cerebralvalley.parse(fixture("cerebralvalley.html"))
    titles = [h.title for h in items]
    assert "GPT-6 Astra Hackathon" in titles
    assert not any("Summer School" in t for t in titles)
    astra = items[titles.index("GPT-6 Astra Hackathon")]
    assert astra.organizer.startswith("OpenAI")
    assert (astra.city, astra.mode) == ("London", "in_person")


def test_lablab_reads_split_rsc_payload(fixture):
    items = lablab.parse(fixture("lablab.html"))
    assert len(items) == 3  # one event split across two push() chunks still decodes
    amd = next(h for h in items if h.id == "lablab:amd-developer-hackathon-act-iii")
    assert amd.mode == "hybrid"
    assert amd.participants == 4531
