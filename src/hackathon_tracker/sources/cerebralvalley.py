"""Cerebral Valley: AI hackathons run with the labs (Anthropic's "Built with Claude",
OpenAI, DeepMind…). Pages ship a schema.org ItemList of Events as JSON-LD.

/events lists upcoming events (hackathons plus meetups); /hackathons is mostly a
showcase of past ones. Both are read, keeping only events typed as Hackathon.

The listing's schema.org offer says "InStock" even for finished events, so registration
state comes from each upcoming event's own page (/e/<slug>) instead: registrationClosed,
capacity.isFull, approvalRequired and city "Remote".
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx

from ..models import Hackathon
from ..parsing import json_ld, next_flight, objects_with_key, strip_html, to_utc

NAME = "cerebralvalley"
URLS = ["https://cerebralvalley.ai/events", "https://cerebralvalley.ai/hackathons"]

ATTENDANCE = {"OnlineEventAttendanceMode": "online", "OfflineEventAttendanceMode": "in_person",
              "MixedEventAttendanceMode": "hybrid"}


def _names(value) -> list[str]:
    items = value if isinstance(value, list) else [value] if value else []
    return [i["name"] for i in items if isinstance(i, dict) and i.get("name")]


def _real(value: str | None) -> str | None:
    """Cerebral Valley uses "Other" as a placeholder location for unlisted venues."""
    return value if value and value.strip() not in ("Other", "TBD", "TBA") else None


def _is_hackathon(e: dict) -> bool:
    types = e.get("@type")
    types = types if isinstance(types, list) else [types]
    return "Hackathon" in types or "hack" in (e.get("name") or "").lower()


def parse(page: str) -> list[Hackathon]:
    out = []
    for block in json_ld(page):
        if block.get("@type") != "ItemList":
            continue
        for entry in block.get("itemListElement", []):
            e = entry.get("item") or {}
            if not e.get("url") or not e.get("name") or not _is_hackathon(e):
                continue
            mode = ATTENDANCE.get((e.get("eventAttendanceMode") or "").rsplit("/", 1)[-1])
            loc = e.get("location") if isinstance(e.get("location"), dict) else {}
            addr = loc.get("address") if isinstance(loc.get("address"), dict) else {}
            image = e.get("image")
            out.append(Hackathon(
                id=f"{NAME}:{e['url'].rstrip('/').rsplit('/', 1)[-1]}",
                source=NAME,
                title=e["name"].strip(),
                url=e["url"],
                organizer=", ".join(_names(e.get("organizer"))) or None,
                description=strip_html(e.get("description")),
                image_url=image[0] if isinstance(image, list) and image else image or None,
                starts_at=to_utc(e.get("startDate")),
                ends_at=to_utc(e.get("endDate")),
                mode=mode,
                location=None if mode == "online" else _real(loc.get("name")),
                city=_real(addr.get("addressLocality")),
                country=_real(addr.get("addressCountry")),
            ))
    return out


def event_details(page: str) -> dict:
    """The event record embedded in an /e/<slug> page."""
    return next((o for o in objects_with_key(next_flight(page), "approvalRequired")
                 if o.get("slug")), {})


def enrich(h: Hackathon, details: dict) -> Hackathon:
    capacity = details.get("capacity") if isinstance(details.get("capacity"), dict) else {}
    if details.get("registrationClosed") is True:
        h.registration_open, h.registration_note = False, "Registration closed"
    elif capacity.get("isFull"):
        h.registration_open, h.registration_note = False, "Full"
    elif details.get("approvalRequired"):
        h.registration_note = "Application required"
    if (details.get("city") or "").strip().lower() == "remote":
        h.mode, h.location = "online", None
        # Open remote events without an application can be joined while they run.
        if details.get("approvalRequired") is False and h.ends_at:
            h.registration_deadline = h.ends_at
    return h


def fetch(client: httpx.Client) -> list[Hackathon]:
    found: dict[str, Hackathon] = {}
    for url in URLS:
        r = client.get(url)
        r.raise_for_status()
        for h in parse(r.text):
            found.setdefault(h.id, h)
    cutoff = datetime.now(UTC) - timedelta(days=1)
    for h in found.values():
        # Only Cerebral Valley's own pages; some entries link straight to lablab.ai.
        if urlparse(h.url).hostname != "cerebralvalley.ai" or (h.ends_at and h.ends_at < cutoff):
            continue
        try:
            page = client.get(h.url)
            page.raise_for_status()
        except httpx.HTTPError:
            continue
        enrich(h, event_details(page.text))
    return list(found.values())
