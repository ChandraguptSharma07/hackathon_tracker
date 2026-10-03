"""TAIKAI: European hackathons and open-innovation challenges. Next.js pages-router site;
the listing is in __NEXT_DATA__'s Apollo cache, with nested objects stored by reference."""

import json
import re

import httpx

from ..models import Hackathon
from ..parsing import to_usd, to_utc

NAME = "taikai"
URL = "https://taikai.network/hackathons"


def parse(page: str) -> list[Hackathon]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        raise ValueError("TAIKAI page data not found")
    cache = json.loads(m.group(1))["props"].get("apolloState") or {}

    def ref(obj) -> dict:
        return cache.get(obj["__ref"], {}) if isinstance(obj, dict) and "__ref" in obj else {}

    out = []
    for key, c in cache.items():
        if not key.startswith("Challenge:") or c.get("isClosed") or not c.get("isPublic", True):
            continue
        org = ref(c.get("organization"))
        if not org.get("slug") or not c.get("slug"):
            continue
        dates = sorted(d for d in (to_utc(ref(s).get("startDate")) for s in c.get("steps") or [])
                       if d)
        decimals = c.get("prizeDecimals") or 0
        amount = (c.get("prize") or 0) / (10 ** decimals) or None
        currency = ref(c.get("prizeCurrency")).get("name") if amount else None
        out.append(Hackathon(
            id=f"{NAME}:{c['slug']}",
            source=NAME,
            title=c["name"].strip(),
            url=f"https://taikai.network/{org['slug']}/hackathons/{c['slug']}",
            organizer=org.get("name"),
            description=c.get("shortDescription"),
            image_url=ref(c.get("cardImageFile")).get("url"),
            starts_at=dates[0] if dates else None,
            ends_at=dates[-1] if dates else None,
            prize_amount=amount,
            prize_currency=currency,
            prize_usd=to_usd(amount, currency),
            themes=[t for t in (ref(i).get("title") for i in c.get("industries") or []) if t],
            participants=c.get("participantsCount") or None,
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
