"""HackerEarth: the events feed their browser extension uses. Mixes coding contests
and hackathons, so only hackathon URLs (or titles, some sit under /competitive/) are kept.

The feed's end is the submission deadline. Many hackathons accept new people until then,
but some close applications earlier, which only their page's timeline says.
"""

import re
from datetime import UTC, datetime, time, timedelta

import httpx

from ..models import Hackathon
from ..parsing import MONTHS, strip_html, to_utc

NAME = "hackerearth"
API = "https://www.hackerearth.com/chrome-extension/events/"


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for e in payload.get("response", []):
        url = e.get("url", "")
        if "/challenges/hackathon/" not in url and "hackathon" not in e.get("title", "").lower():
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        out.append(Hackathon(
            id=f"{NAME}:{slug}",
            source=NAME,
            title=e["title"].strip(),
            url=url,
            organizer="HackerEarth" if e.get("is_hackerearth") else None,
            description=strip_html(e.get("description")),
            image_url=e.get("thumbnail"),
            starts_at=to_utc(e.get("start_utc_tz")),
            ends_at=to_utc(e.get("end_utc_tz")),
            mode="online",
        ))
    return out


# "Oct 23 ... Applications Close" in an event page's timeline (markup varies by page).
APPLICATIONS_CLOSE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2})(?:,? (\d{4}))?"
    r"(?:(?!\b\d{1,2}\b).){0,200}?Applications? (?:Close|Deadline)", re.S)


def applications_close(page: str, start: datetime | None) -> datetime | None:
    """Date of the "Applications Close" timeline step (end of that day, UTC). Timelines
    often omit the year: take the event's, moving to the next year if that lands well
    before the event even began."""
    m = APPLICATIONS_CLOSE.search(re.sub(r"<[^>]+>", " ", page))
    if not m:
        return None
    year = int(m.group(3)) if m.group(3) else (start or datetime.now(UTC)).year
    day = datetime.combine(datetime(year, MONTHS[m.group(1).lower()], int(m.group(2))).date(),
                           time(23, 59), UTC)
    if not m.group(3) and start and day < start - timedelta(days=60):
        day = day.replace(year=year + 1)
    return day


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(API)
    r.raise_for_status()
    events = parse(r.json())
    for h in events:  # a handful of listings, so reading each page is cheap
        try:
            page = client.get(h.url)
            page.raise_for_status()
        except httpx.HTTPError:
            continue
        h.registration_deadline = applications_close(page.text, h.starts_at)
    return events
