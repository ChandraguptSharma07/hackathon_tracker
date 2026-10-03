"""HackerEarth: the events feed their browser extension uses. Mixes coding contests
and hackathons, so only /challenges/hackathon/ URLs are kept."""

import httpx

from ..models import Hackathon
from ..parsing import strip_html, to_utc

NAME = "hackerearth"
API = "https://www.hackerearth.com/chrome-extension/events/"


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for e in payload.get("response", []):
        url = e.get("url", "")
        if "/challenges/hackathon/" not in url:
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
            registration_deadline=to_utc(e.get("end_utc_tz")),
            mode="online",
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(API)
    r.raise_for_status()
    return parse(r.json())
