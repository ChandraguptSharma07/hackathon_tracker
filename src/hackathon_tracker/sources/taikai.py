"""TAIKAI: European hackathons and open-innovation challenges. Next.js pages-router site;
the listing is in __NEXT_DATA__'s Apollo cache, with nested objects stored by reference."""

import json
import re
from datetime import UTC, datetime

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
        dates = sorted(d for s in c.get("steps") or [] if (d := to_utc(ref(s).get("startDate"))))
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
            registration_note="Selection required"
            if c.get("allowedParticipants") == "SELECTED" else None,
        ))
    return out


def challenge_details(page: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return {}
    props = json.loads(m.group(1))["props"].get("pageProps") or {}
    return (props.get("challengeProps") or {}).get("challengeBySlug") or {}


def enrich(h: Hackathon, details: dict, now: datetime) -> Hackathon:
    """Apply a challenge page's explicit participant registration window."""
    opens = to_utc(details.get("startParticipantRegistrationDate"))
    closes = to_utc(details.get("endParticipantRegistrationDate"))
    if closes:
        h.registration_deadline = closes
    if opens and opens > now:
        h.registration_note = f"Registration opens {opens:%b %d}"
    if details.get("registrationDomainsWhiteList"):
        h.registration_note = "Only some email domains may register"
    return h


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(URL)
    r.raise_for_status()
    challenges = parse(r.text)
    now = datetime.now(UTC)
    for h in challenges:  # the listing has no registration window; each page does
        try:
            page = client.get(h.url)
            page.raise_for_status()
            enrich(h, challenge_details(page.text), now)
        except (httpx.HTTPError, ValueError, KeyError):
            continue
    return challenges
