"""Unstop (ex-Dare2Compete): public opportunity search API. Mostly Indian college events.

Unstop does not expose the event start date in listings, only the end and the
registration window, so `starts_at` stays None.
"""

import re

import httpx

from ..models import Hackathon
from ..parsing import strip_html, to_usd, to_utc

NAME = "unstop"
API = "https://unstop.com/api/public/opportunity/search-result"
MAX_PAGES = 10

# Unstop's "hackathons" category also holds college-fest events. Drop those unless the
# title still says hack/-thon ("HackRobo" stays, "Robo Sumo" goes).
FEST_EVENT = re.compile(
    r"robo[ -]?(race|sumo|soccer|maze|wars?)|drone[ -](race|soccer)|\bbgmi\b|valorant|free ?fire"
    r"|tournament|poster|quiz|treasure hunt|debate|business plan", re.I)
HACK_WORD = re.compile(r"hack|thon\b", re.I)


def is_fest_event(title: str) -> bool:
    return bool(FEST_EVENT.search(title)) and not HACK_WORD.search(title)


CURRENCIES = {"fa-rupee": "INR", "fa-dollar": "USD", "fa-euro": "EUR", "fa-gbp": "GBP"}


def _prize(prizes: list[dict]) -> tuple[float | None, str | None]:
    total, currency = 0.0, None
    for p in prizes:
        cash = p.get("cash") or 0
        if cash:
            total += float(cash)
            currency = p.get("currencyCode") or CURRENCIES.get(p.get("currency"), "INR")
    return (total, currency) if total else (None, None)


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for o in payload.get("data", {}).get("data", []):
        if o.get("visibility") != "public" or is_fest_event(o["title"]):
            continue
        addr = o.get("address_with_country_logo") or {}
        country = (addr.get("country") or {}).get("name")
        online = o.get("region") == "online"
        regn = o.get("regnRequirements") or {}
        amount, currency = _prize(o.get("prizes") or [])
        skills = [s.get("skill_name") or s.get("skill") for s in o.get("required_skills") or []]
        out.append(Hackathon(
            id=f"{NAME}:{o['id']}",
            source=NAME,
            title=o["title"].strip(),
            url=o.get("seo_url") or f"https://unstop.com/{o['public_url']}",
            organizer=(o.get("organisation") or {}).get("name"),
            description=strip_html(o.get("details")),
            image_url=o.get("logoUrl2"),
            ends_at=to_utc(o.get("end_date")),
            registration_deadline=to_utc(regn.get("end_regn_dt")),
            mode="online" if online else "in_person",
            location=None if online else ", ".join(
                x for x in (addr.get("city"), addr.get("state"), country) if x) or None,
            city=addr.get("city"),
            country=country,
            prize_amount=amount,
            prize_currency=currency,
            prize_usd=to_usd(amount, currency),
            themes=[s for s in skills if s][:6],
            participants=o.get("registerCount"),
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    out: list[Hackathon] = []
    for page in range(1, MAX_PAGES + 1):
        r = client.get(API, params={"opportunity": "hackathons", "oppstatus": "open",
                                    "page": page, "per_page": 100})
        r.raise_for_status()
        payload = r.json()
        out.extend(parse(payload))
        if not payload.get("data", {}).get("next_page_url"):
            break
    return out
