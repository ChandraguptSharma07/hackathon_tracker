"""Hack Club: community-run list of high school hackathons, with a public JSON API."""

import httpx

from ..models import Hackathon
from ..parsing import to_utc

NAME = "hackclub"
API = "https://hackathons.hackclub.com/api/events/upcoming"


def parse(payload: list[dict]) -> list[Hackathon]:
    out = []
    for e in payload:
        if not e.get("website") or not e.get("name"):
            continue
        mode = "online" if e.get("virtual") else "hybrid" if e.get("hybrid") else "in_person"
        out.append(Hackathon(
            id=f"{NAME}:{e['id']}",
            source=NAME,
            title=e["name"].strip(),
            url=e["website"],
            organizer="Hack Club" if e.get("hack_club_event") else None,
            image_url=e.get("banner") or e.get("logo"),
            starts_at=to_utc(e.get("start")),
            ends_at=to_utc(e.get("end")),
            mode=mode,
            location=None if mode == "online" else ", ".join(
                x for x in (e.get("city"), e.get("state"), e.get("country")) if x) or None,
            city=e.get("city"),
            country=e.get("countryCode") or e.get("country"),
            themes=["High school"],
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(API)
    r.raise_for_status()
    return parse(r.json())
