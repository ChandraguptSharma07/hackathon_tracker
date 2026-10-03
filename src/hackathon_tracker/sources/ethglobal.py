"""ETHGlobal: Ethereum hackathons (in-person city events plus online ones like ETHOnline).
Next.js app router page; events sit in the inline RSC payload next to meetups and summits."""

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
        )
    return list(seen.values())


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
