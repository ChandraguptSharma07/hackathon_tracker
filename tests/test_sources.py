from datetime import UTC, datetime

import pytest

from hackathon_tracker.sources import (cerebralvalley, devfolio, devpost, dorahacks, ethglobal,
                                       hackclub, hackerearth, kaggle, lablab, luma, mlh, taikai,
                                       unstop, zindi)


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


def test_ethglobal_keeps_only_upcoming_hackathons(fixture):
    items = ethglobal.parse(fixture("ethglobal.html"))  # fixture: future, finished, meetup
    assert [h.id for h in items] == ["ethglobal:mumbai"]
    h = items[0]
    assert (h.mode, h.city, h.country) == ("in_person", "Mumbai", "India")
    assert h.registration_deadline == datetime(2026, 11, 3, 18, 29, tzinfo=UTC)


def test_dorahacks(fixture):
    items = dorahacks.parse(fixture("dorahacks.json"))
    assert len(items) == 3
    weex = items[0]
    assert weex.url == "https://dorahacks.io/hackathon/weex-ai-wars2"
    assert (weex.mode, weex.prize_usd) == ("online", 200000)
    assert weex.ends_at == datetime(2026, 10, 12, 15, 59, tzinfo=UTC)
    assert items[1].mode == "in_person" and "SMU" in items[1].location
    assert items[2].url == "https://dorahacks.io/hackathon/2349"  # no slug, falls back to id


def test_luma_keeps_hackathon_names_only(fixture):
    items = luma.parse(fixture("luma.json"))  # fixture includes a meetup
    assert [h.title for h in items] == ["DevDay Exchange Community Hackathon: New Delhi",
                                        "neatHack"]
    assert items[0].url == "https://lu.ma/6t5uk4lo"
    assert items[0].location == "New Delhi, Delhi, India"


@pytest.mark.parametrize("name,expected", [
    ("Agentic AI Hackathon 2.0 - SF", True),
    ("Reap x 65labs Agentic Buildathon", True),
    ("HACKTOBERFEST MEETUP 2026", False),
    ("growth hacking workshop + build evening", False),
    ("AI Builders Happy Hour", False),
])
def test_luma_name_filter(name, expected):
    assert luma.is_hackathon(name) is expected


def test_hackclub(fixture):
    items = hackclub.parse(fixture("hackclub.json"))
    assert len(items) == 3
    assert items[0].location == "Sunnyvale, California, United States"
    assert items[0].country == "US"
    assert items[2].mode == "online" and items[2].location is None


def test_taikai_resolves_apollo_refs_and_skips_closed(fixture):
    items = taikai.parse(fixture("taikai.html"))  # fixture: one open, one closed
    assert len(items) == 1
    h = items[0]
    assert h.url == ("https://taikai.network/spacexai/hackathons/"
                     "spacexai-digital-transformation-lab")
    assert h.organizer == "SpaceXAI"
    assert (h.prize_amount, h.prize_currency) == (3500, "USD")
    assert h.starts_at == datetime(2026, 9, 15, 23, tzinfo=UTC)
    assert h.ends_at == datetime(2026, 10, 27, 16, tzinfo=UTC)


def test_kaggle_skips_practice_and_marks_kind(fixture):
    items = kaggle.parse(fixture("kaggle.json"))  # fixture: practice, cash prize, hackathon
    assert [h.id for h in items] == ["kaggle:rsna-knee-abnormality-detection",
                                     "kaggle:gemma-4-developer-agent-paper"]
    rsna, gemma = items
    assert rsna.kind == "competition" and gemma.kind == "hackathon"
    assert rsna.prize_usd == 77000
    assert rsna.image_url == "https://example.com/thumb.png"
    assert gemma.organizer == "Google DeepMind"


def test_zindi_keeps_open_and_parses_spaced_prize(fixture):
    items = zindi.parse(fixture("zindi.json"))  # fixture: two open, one closed
    assert len(items) == 2
    assert all(h.kind == "competition" for h in items)
    assert (items[0].prize_amount, items[0].prize_currency) == (25000, "USD")


@pytest.mark.parametrize("title,dropped", [
    ("Junior Robo Sumo", True), ("Junior Robo-Race", True),
    ("Valorant Tournament – Battle Zone", True),
    ("Poster Exhibition", True), ("HackRobo 2.0", False), ("Startupathon", False),
    ("Competitive Programming Hackathon", False),
])
def test_unstop_fest_events(title, dropped):
    assert unstop.is_fest_event(title) is dropped
