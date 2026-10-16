"""ETHGlobal: Ethereum hackathons (in-person city events plus online ones like ETHOnline).
Next.js app router page; events sit in the inline RSC payload next to meetups and summits."""

from datetime import datetime

import httpx

from ..models import Hackathon
from ..parsing import next_flight, objects_with_key, to_utc

NAME = "ethglobal"
URL = "https://ethglobal.com/events"

MEDIUMS = {"physical": "in_person", "virtual": "online", "hybrid": "hybrid"}


def parse(page: str) -> list[Hackathon]:
    seen: dict[str, Hackathon] = {}
    for e in objects_with_key(next_flight(page), "startTime"):
        slug = e.get("slug")
        if not slug or e.get("type") != "hackathon" or e.get("status") in ("finished", "cancelled"):
            continue
        city = e.get("city") if isinstance(e.get("city"), dict) else {}
        country = (city.get("country") or {}).get("name") if city else None
        mode = MEDIUMS.get(e.get("medium") or "")
        tagline = e.get("tagline")
        flags = e.get("flags") if isinstance(e.get("flags"), dict) else {}
        applying = flags.get("enableHackerApplications")
        seen[slug] = Hackathon(
            id=f"{NAME}:{slug}",
            source=NAME,
            title=e["name"].strip(),
            url=f"https://ethglobal.com/events/{slug}",
            organizer="ETHGlobal",
            description=tagline if isinstance(tagline, str) else None,
            image_url=e.get("squareLogoFullUrl"),
            starts_at=to_utc(e.get("startTime")),
            ends_at=to_utc(e.get("endTime")),
            registration_deadline=to_utc(e.get("signupDeadline")),
            mode=mode,
            location=None if mode == "online" else ", ".join(
                x for x in (city.get("name"), country) if x) or None,
            city=city.get("name"),
            country=country,
            themes=["Ethereum", "Web3"],
            registration_open=applying if isinstance(applying, bool) else None,
            registration_note="Application required",
        )
    return list(seen.values())


def apply_deadline(page: str) -> datetime | None:
    """The event page's "Deadline to Apply" schedule item. It often differs from the
    listing's signupDeadline (earlier for ETHGlobal Mumbai 2026: Oct 23 vs Nov 3)."""
    for item in objects_with_key(next_flight(page), "slug"):
        if item.get("slug") == "deadline-to-apply" and item.get("startTime"):
            return to_utc(item["startTime"])
    return None


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(URL)
    r.raise_for_status()
    events = parse(r.text)
    for h in events:  # only upcoming hackathons are kept, so this is a handful of pages
        try:
            # No raise_for_status: event pages currently answer 500 while still serving
            # the full page. apply_deadline() returns None for anything unusable.
            page = client.get(h.url)
        except httpx.HTTPError:
            continue
        deadline = apply_deadline(page.text)
        if deadline and (h.registration_deadline is None or deadline < h.registration_deadline):
            h.registration_deadline = deadline  # the earlier of the two is the safe one
    return events
