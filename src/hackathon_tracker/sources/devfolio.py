"""Devfolio: search API used by devfolio.co/hackathons. India-heavy, plus web3."""

import httpx

from ..models import Hackathon
from ..parsing import strip_html, to_utc

NAME = "devfolio"
API = "https://api.devfolio.co/api/search/hackathons"
PAGE_SIZE = 50
MAX_PAGES = 10


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for hit in payload.get("hits", {}).get("hits", []):
        h = hit["_source"]
        if h.get("private") or h.get("type") != "HACKATHON":
            continue
        setting = h.get("hackathon_setting") or {}
        online = bool(h.get("is_online"))
        themes = [t["name"] if isinstance(t, dict) else str(t) for t in h.get("themes") or []]
        out.append(Hackathon(
            id=f"{NAME}:{h['uuid']}",
            source=NAME,
            title=h["name"].strip(),
            url=f"https://{h['slug']}.devfolio.co/",
            organizer=h.get("hosted_by") if isinstance(h.get("hosted_by"), str) else None,
            description=strip_html(h.get("tagline") or h.get("desc")),
            image_url=h.get("cover_img"),
            starts_at=to_utc(h.get("starts_at")),
            ends_at=to_utc(h.get("ends_at")),
            registration_deadline=to_utc(setting.get("reg_ends_at")),
            mode="online" if online else "in_person",
            location=None if online else h.get("location"),
            city=h.get("city"),
            country=h.get("country"),
            themes=themes + [f"#{t}" for t in h.get("hashtags") or []],
            participants=h.get("participants_count"),
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    out: list[Hackathon] = []
    for page in range(MAX_PAGES):
        r = client.post(API, json={"type": "application_open", "from": page * PAGE_SIZE,
                                   "size": PAGE_SIZE})
        r.raise_for_status()
        payload = r.json()
        batch = parse(payload)
        out.extend(batch)
        total = payload.get("hits", {}).get("total", {}).get("value", 0)
        if (page + 1) * PAGE_SIZE >= total or not batch:
            break
    return out
