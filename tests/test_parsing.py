from datetime import UTC, datetime

import pytest

from hackathon_tracker.parsing import (next_flight, objects_with_key, parse_date_range,
                                       parse_money, strip_html, to_usd, to_utc)


@pytest.mark.parametrize("text,start,end", [
    ("Aug 31 - Oct 23, 2026", (2026, 8, 31), (2026, 10, 23)),
    ("Oct 01 - 08, 2026", (2026, 10, 1), (2026, 10, 8)),
    ("Aug 23, 2026 - Jan 02, 2027", (2026, 8, 23), (2027, 1, 2)),
    ("Dec 20 - Jan 10, 2027", (2026, 12, 20), (2027, 1, 10)),
])
def test_parse_date_range(text, start, end):
    s, e = parse_date_range(text)
    assert s == datetime(*start, tzinfo=UTC)
    assert e == datetime(*end, 23, 59, tzinfo=UTC)


def test_parse_date_range_garbage():
    assert parse_date_range("TBA") == (None, None)


@pytest.mark.parametrize("text,expected", [
    ("$<span data-currency-value>138,000</span>", (138000, "USD")),
    ("₹ 50,000", (50000, "INR")),
    ("€1.500", (1.5, "EUR")),
    ("2500 CAD", (2500, "CAD")),
    ("", (None, None)),
    ("Swag", (None, None)),
])
def test_parse_money(text, expected):
    assert parse_money(text) == expected


def test_to_usd():
    assert to_usd(1000, "INR") == 12
    assert to_usd(1000, "XYZ") is None
    assert to_usd(None, "USD") is None


def test_to_utc():
    assert to_utc("2026-10-02T00:00:00+05:30") == datetime(2026, 10, 1, 18, 30, tzinfo=UTC)
    assert to_utc("2026-10-02 00:00:00") == datetime(2026, 10, 2, tzinfo=UTC)
    assert to_utc("nope") is None


def test_strip_html():
    assert strip_html("<p>Hi&amp;  <b>there</b></p>") == "Hi& there"
    assert strip_html("word " * 200, limit=20).endswith("…")


def test_flight_objects():
    page = ('<script>self.__next_f.push([1,"a:{\\"x\\":{\\"startAt\\":\\"2026\\"'
            '"])</script><script>self.__next_f.push([1,",\\"slug\\":\\"s\\"}}"])</script>')
    objs = list(objects_with_key(next_flight(page), "startAt"))
    assert objs == [{"startAt": "2026", "slug": "s"}]
