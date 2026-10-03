"""Devpost: undocumented JSON API behind devpost.com/hackathons. Hosts most corporate
hackathons (OpenAI, Amazon, Google…) on <name>.devpost.com subdomains."""

import httpx

from ..models import Hackathon
from ..parsing import parse_date_range, parse_money, to_usd

NAME = "devpost"
API = "https://devpost.com/api/hackathons"
PER_PAGE = 40  # server caps at 40
MAX_PAGES = 25


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for h in payload.get("hackathons", []):
        if h.get("invite_only"):
            continue
        starts, ends = parse_date_range(h.get("submission_period_dates"))
        place = (h.get("displayed_location") or {})
        online = place.get("icon") == "globe" or place.get("location") == "Online"
        amount, currency = parse_money(h.get("prize_amount"))
        thumb = h.get("thumbnail_url") or None
        out.append(Hackathon(
            id=f"{NAME}:{h['id']}",
            source=NAME,
            title=h["title"].strip(),
            url=h["url"],
            organizer=h.get("organization_name") or None,
            image_url=f"https:{thumb}" if thumb and thumb.startswith("//") else thumb,
            starts_at=starts,
            ends_at=ends,
            registration_deadline=ends,
            mode="online" if online else "in_person",
            location=None if online else place.get("location"),
            prize_amount=amount or None,
            prize_currency=currency if amount else None,
            prize_usd=to_usd(amount, currency),
            themes=[t["name"] for t in h.get("themes", [])],
            participants=h.get("registrations_count"),
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    out: list[Hackathon] = []
    for page in range(1, MAX_PAGES + 1):
        r = client.get(API, params={
            "status[]": ["upcoming", "open"], "page": page, "per_page": PER_PAGE})
        r.raise_for_status()
        payload = r.json()
        out.extend(parse(payload))
        total = payload.get("meta", {}).get("total_count", 0)
        if page * PER_PAGE >= total or not payload.get("hackathons"):
            break
    return out
