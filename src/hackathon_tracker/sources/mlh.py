"""MLH: season events page. Inertia.js app, so the event list is JSON inside
<script data-page="app">."""

import json
import re
from datetime import UTC, datetime

import httpx

from ..models import Hackathon
from ..parsing import to_utc

NAME = "mlh"
BASE = "https://mlh.io"

FORMATS = {"physical": "in_person", "digital": "online", "hybrid_physical": "hybrid",
           "hybrid_digital": "hybrid", "hybrid": "hybrid"}


def season(now: datetime) -> int:
    """MLH seasons run Aug-Jul and are named after the year they end in."""
    return now.year + 1 if now.month >= 8 else now.year


def parse(page: str) -> list[Hackathon]:
    m = re.search(r'<script data-page="app" type="application/json">(.*?)</script>', page, re.S)
    if not m:
        raise ValueError("MLH page data not found")
    events = json.loads(m.group(1))["props"].get("upcomingEvents", [])
    out = []
    for e in events:
        venue = e.get("venueAddress") or {}
        mode = FORMATS.get(e.get("formatType") or "")
        out.append(Hackathon(
            id=f"{NAME}:{e['slug']}",
            source=NAME,
            title=e["name"].strip(),
            url=e.get("websiteUrl") or f"{BASE}{e['url']}",
            organizer="MLH Member Event",
            image_url=e.get("backgroundUrl") or e.get("logoUrl"),
            starts_at=to_utc(e.get("startsAt")),
            ends_at=to_utc(e.get("endsAt")),
            mode=mode,
            location=None if mode == "online" else e.get("location"),
            city=venue.get("city"),
            country=venue.get("country"),
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(f"{BASE}/seasons/{season(datetime.now(UTC))}/events")
    r.raise_for_status()
    return parse(r.text)
