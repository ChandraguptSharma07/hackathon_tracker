"""Shared helpers for turning messy source data into clean values."""

import html
import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime, time

# Rough USD rates, only used to rank and filter by prize size. Not for accounting.
USD_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "INR": 0.012,
    "CAD": 0.73,
    "AUD": 0.66,
    "SGD": 0.74,
    "JPY": 0.0067,
    "CHF": 1.12,
}

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def to_utc(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string into an aware UTC datetime. Naive values are assumed UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def strip_html(text: str | None, limit: int = 400) -> str | None:
    """Drop tags, collapse whitespace and cut to `limit` characters."""
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text or None


def parse_money(text: str | None) -> tuple[float | None, str | None]:
    """Parse strings like "$<span>138,000</span>" or "₹ 50,000" into (amount, currency)."""
    if not text:
        return None, None
    clean = re.sub(r"<[^>]+>", "", html.unescape(text)).strip()
    match = re.search(r"\d[\d,]*(?:\.\d+)?", clean)
    if not match:
        return None, None
    amount = float(match.group().replace(",", ""))
    currency = next((code for sym, code in CURRENCY_SYMBOLS.items() if sym in clean), None)
    if currency is None:
        code = re.search(r"\b([A-Z]{3})\b", clean)
        currency = code.group(1) if code else "USD"
    return amount, currency


def to_usd(amount: float | None, currency: str | None) -> float | None:
    if not amount or not currency or currency not in USD_RATES:
        return None
    return round(amount * USD_RATES[currency], 2)


def _month_day(month: str, day: str, year: int) -> datetime | None:
    m = MONTHS.get(month[:3].lower())
    return datetime(year, m, int(day), tzinfo=UTC) if m else None


def parse_date_range(text: str | None) -> tuple[datetime | None, datetime | None]:
    """Parse Devpost-style ranges: "Aug 31 - Oct 23, 2026", "Oct 01 - 08, 2026",
    "Aug 23, 2026 - Jan 02, 2027". The end date is set to the end of that day (UTC).
    """
    if not text:
        return None, None
    text = text.strip()
    m = re.fullmatch(r"(\w{3})\w* (\d{1,2}), (\d{4}) - (\w{3})\w* (\d{1,2}), (\d{4})", text)
    if m:
        start = _month_day(m[1], m[2], int(m[3]))
        end = _month_day(m[4], m[5], int(m[6]))
    else:
        m = re.fullmatch(r"(\w{3})\w* (\d{1,2}) - (?:(\w{3})\w* )?(\d{1,2}), (\d{4})", text)
        if not m:
            return None, None
        year = int(m[5])
        start = _month_day(m[1], m[2], year)
        end = _month_day(m[3] or m[1], m[4], year)
    if end is not None:
        end = datetime.combine(end.date(), time(23, 59), tzinfo=UTC)
    if start and end and end < start:  # range crosses new year without saying so
        start = start.replace(year=start.year - 1)
    return start, end


def json_ld(page: str) -> list[dict]:
    """Every JSON-LD object embedded in an HTML page."""
    out = []
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        out.extend(data if isinstance(data, list) else [data])
    return out


def next_flight(page: str) -> str:
    """Join the React Server Components payload a Next.js app router page streams inline."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', page)
    return "".join(json.loads(f'"{c}"') for c in chunks)


def objects_with_key(text: str, key: str) -> Iterator[dict]:
    """Yield each JSON object in `text` that directly contains `"key":`.

    Walks back from every occurrence of the key to its enclosing "{" and decodes from there.
    Good enough for RSC payloads, where data objects are plain JSON inside a larger stream.
    """
    decoder = json.JSONDecoder()
    for m in re.finditer(rf'"{re.escape(key)}":', text):
        depth, i = 0, m.start()
        while i > 0:
            i -= 1
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                if depth == 0:
                    break
                depth -= 1
        try:
            obj, _ = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and key in obj:
            yield obj
