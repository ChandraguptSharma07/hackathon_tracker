"""lablab.ai: online AI hackathons sponsored by AMD, IBM, Meta and others. Next.js app
router page, so events are JSON objects inside the inline RSC payload."""

import httpx

from ..models import Hackathon
from ..parsing import next_flight, objects_with_key, strip_html, to_utc
from ..sponsors import detect

NAME = "lablab"
URL = "https://lablab.ai/ai-hackathons"

EVENT_TYPES = {"ONLINE": "online", "HYBRID": "hybrid", "ONSITE": "in_person"}


def parse(page: str) -> list[Hackathon]:
    seen: dict[str, Hackathon] = {}
    for e in objects_with_key(next_flight(page), "startAt"):
        slug = e.get("slug")
        if not slug or e.get("type") != "HACKATHON" or e.get("deletedAt") or not e.get("active"):
            continue
        techs = [t for t in e.get("technologyList") or [] if isinstance(t, dict)]
        seen[slug] = Hackathon(
            id=f"{NAME}:{slug}",
            source=NAME,
            title=e["name"].strip(),
            url=f"https://lablab.ai/ai-hackathons/{slug}",
            description=strip_html(e.get("subtitle") or e.get("description")),
            image_url=e.get("thumbnailLink") or e.get("imageLink"),
            starts_at=to_utc(e.get("startAt")),
            ends_at=to_utc(e.get("endAt")),
            mode=EVENT_TYPES.get(e.get("eventType") or ""),
            themes=list(dict.fromkeys(t["techName"] for t in techs if t.get("techName"))),
            sponsors=detect(*((t.get("provider") or {}).get("name") for t in techs)),
            participants=(e.get("_count") or {}).get("participants"),
        )
    return list(seen.values())


def fetch(client: httpx.Client) -> list[Hackathon]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
