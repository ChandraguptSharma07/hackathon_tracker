"""DoraHacks: web3 and AI hackathons. The site is client-rendered; this is the JSON API
its frontend calls (found in the Nuxt bundle: backend "hub" + /hackathons)."""

from datetime import UTC, datetime

import httpx

from ..models import Hackathon
from ..parsing import to_usd

NAME = "dorahacks"
API = "https://dorahacks.io/api/v1/hub/hackathons"
STATUSES = ("ongoing", "upcoming")
PAGE_SIZE = 50
MAX_PAGES = 5

VENUES = {"Virtual": "online", "IRL": "in_person", "Hybrid": "hybrid"}
PLACEHOLDERS = {"to be announced", "tba", "tbd"}


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if value else None


def _split(value: str | None) -> list[str]:
    return [t.strip() for t in (value or "").split(",") if t.strip()]


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for h in payload.get("results", []):
        if h.get("visibility") not in (0, None):
            continue
        mode = VENUES.get(h.get("venue_form") or "")
        venue = h.get("venue_name")
        if venue and venue.strip().lower() in PLACEHOLDERS:
            venue = None
        amount = h.get("bonus_price") or None
        currency = (h.get("bonus_token") or "USD").upper() if amount else None
        out.append(Hackathon(
            id=f"{NAME}:{h['id']}",
            source=NAME,
            title=h["title"].strip(),
            url=f"https://dorahacks.io/hackathon/{h.get('uname') or h['id']}",
            organizer=(h.get("owner") or {}).get("name"),
            image_url=h.get("image_url"),
            starts_at=_ts(h.get("timeline_start")),
            ends_at=_ts(h.get("timeline_end")),
            mode=mode,
            location=None if mode == "online" else venue,
            prize_amount=amount,
            prize_currency=currency,
            prize_usd=to_usd(amount, currency),
            themes=list(dict.fromkeys(_split(h.get("tags")) + _split(h.get("ecosystem"))))[:8],
            participants=h.get("hackers_count") or None,
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    found: dict[str, Hackathon] = {}
    for status in STATUSES:
        for page in range(1, MAX_PAGES + 1):
            r = client.get(API, params={"page": page, "page_size": PAGE_SIZE, "status": status})
            r.raise_for_status()
            payload = r.json()
            for h in parse(payload):
                found.setdefault(h.id, h)
            if not payload.get("next"):
                break
    return list(found.values())
