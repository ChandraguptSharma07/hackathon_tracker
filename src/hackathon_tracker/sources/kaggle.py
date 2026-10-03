"""Kaggle: ML competitions, including lab-sponsored ones (Google DeepMind, OpenAI…).

Uses the same internal endpoint as kaggle.com/competitions, which needs only the XSRF
cookie the site sets on first visit, not an API key. "Getting started" practice
competitions (no deadline that matters, knowledge-only reward) are skipped.
"""

import httpx

from ..models import Hackathon
from ..parsing import strip_html, to_usd, to_utc

NAME = "kaggle"
HOME = "https://www.kaggle.com/competitions"
API = "https://www.kaggle.com/api/i/competitions.CompetitionService/ListCompetitions"
PAGE_SIZE = 50
MAX_PAGES = 5

PRACTICE_REWARDS = {"KNOWLEDGE", "KUDOS"}


def parse(payload: dict) -> list[Hackathon]:
    thumbs = payload.get("thumbnailImageUrls") or {}
    out = []
    for c in payload.get("competitions", []):
        reward = c.get("reward") or {}
        if reward.get("id") in PRACTICE_REWARDS:
            continue
        amount = reward.get("quantity") or None
        currency = reward.get("id") if amount else None
        org = c.get("organization") or {}
        out.append(Hackathon(
            id=f"{NAME}:{c['competitionName']}",
            source=NAME,
            kind="hackathon" if c.get("hackathon") else "competition",
            title=c["title"].strip(),
            url=f"https://www.kaggle.com/competitions/{c['competitionName']}",
            organizer=c.get("hostName") or org.get("name"),
            description=strip_html(c.get("briefDescription")),
            image_url=thumbs.get(str(c["id"])) or org.get("thumbnailImageUrl"),
            starts_at=to_utc(c.get("dateEnabled")),
            ends_at=to_utc(c.get("deadline")),
            registration_deadline=to_utc(c.get("deadline")),
            mode="online",
            prize_amount=amount,
            prize_currency=currency,
            prize_usd=to_usd(amount, currency),
            themes=[cat["displayName"] for cat in c.get("categories") or []
                    if cat.get("displayName") and cat.get("slug")][:5],
            participants=c.get("totalCompetitors") or None,
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    client.get(HOME).raise_for_status()  # sets the XSRF-TOKEN cookie
    token = client.cookies.get("XSRF-TOKEN")
    if not token:
        raise RuntimeError("Kaggle did not set an XSRF token")
    out: list[Hackathon] = []
    page_token = ""
    for _ in range(MAX_PAGES):
        r = client.post(API, headers={"x-xsrf-token": token}, json={
            "selector": {"listOption": "LIST_OPTION_ACTIVE", "sortOption": "SORT_OPTION_NEWEST",
                         "competitionIds": [], "tagIds": [], "excludeTagIds": [],
                         "searchQuery": ""},
            "pageToken": page_token,
            "pageSize": PAGE_SIZE,
        })
        r.raise_for_status()
        payload = r.json()
        out.extend(parse(payload))
        page_token = payload.get("nextPageToken") or ""
        if not page_token:
            break
    return out
