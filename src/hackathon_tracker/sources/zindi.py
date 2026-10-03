"""Zindi: African data science competitions, via the public API behind zindi.africa.
Open competitions come first in the default ordering."""

import httpx

from ..models import Hackathon
from ..parsing import parse_money, to_usd, to_utc

NAME = "zindi"
API = "https://api.zindi.africa/v1/competitions"
PER_PAGE = 20  # larger pages are rejected
MAX_PAGES = 5


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for c in payload.get("data", []):
        if not c.get("open") or c.get("secret_code_required"):
            continue
        amount, currency = parse_money(c.get("reward"))
        org = c.get("organization")
        out.append(Hackathon(
            id=f"{NAME}:{c['id']}",
            source=NAME,
            kind="hackathon" if c.get("kind") == "hackathon" else "competition",
            title=c["title"].strip(),
            url=f"https://zindi.africa/competitions/{c['id']}",
            organizer=org.get("name") if isinstance(org, dict) else org,
            image_url=c.get("image"),
            starts_at=to_utc(c.get("start_time")),
            ends_at=to_utc(c.get("end_time")),
            registration_deadline=to_utc(c.get("entries_close_at") or c.get("end_time")),
            mode="online",
            prize_amount=amount,
            prize_currency=currency,
            prize_usd=to_usd(amount, currency),
            themes=["Beginner friendly"] if c.get("is_beginner_friendly") else [],
            participants=c.get("participations_count") or None,
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    out: list[Hackathon] = []
    for page in range(MAX_PAGES):
        r = client.get(API, params={"page": page, "per_page": PER_PAGE, "active": 1})
        r.raise_for_status()
        payload = r.json()
        batch = parse(payload)
        out.extend(batch)
        open_count = payload.get("meta", {}).get("open_count", 0)
        if len(out) >= open_count or len(batch) < len(payload.get("data", [])):
            break  # all open ones collected, or this page already hit closed ones
    return out
