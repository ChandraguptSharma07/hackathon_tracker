"""lu.ma: where many in-person AI lab and startup hackathons are posted. The public discover
search is location-biased, so it is queried around a list of tech hubs and the results are
narrowed to events whose names look like hackathons."""

import re

import httpx

from ..models import Hackathon
from ..parsing import to_utc

NAME = "luma"
API = "https://api.lu.ma/discover/get-paginated-events"

# (label, latitude, longitude)
HUBS = [
    ("San Francisco", 37.77, -122.42), ("New York", 40.71, -74.01), ("Boston", 42.36, -71.06),
    ("Seattle", 47.61, -122.33), ("Los Angeles", 34.05, -118.24), ("Austin", 30.27, -97.74),
    ("Toronto", 43.65, -79.38), ("London", 51.51, -0.13), ("Paris", 48.86, 2.35),
    ("Berlin", 52.52, 13.40), ("Amsterdam", 52.37, 4.90), ("Zurich", 47.37, 8.54),
    ("Bengaluru", 12.97, 77.59), ("Delhi", 28.61, 77.21), ("Mumbai", 19.08, 72.88),
    ("Singapore", 1.35, 103.82), ("Tokyo", 35.68, 139.69), ("Sydney", -33.87, 151.21),
    ("Dubai", 25.20, 55.27), ("São Paulo", -23.55, -46.63),
]

HACKATHON_NAME = re.compile(
    r"hack|buildathon|datathon|ideathon|makeathon|codefest|game ?jam|build sprint", re.I)
NOT_HACKATHON = re.compile(
    r"meetup|happy hour|mixer|networking|watch party|office hours|info session|demo night"
    r"|hacktoberfest|workshop|growth hack", re.I)


def is_hackathon(name: str) -> bool:
    return bool(HACKATHON_NAME.search(name)) and not NOT_HACKATHON.search(name)


def parse(payload: dict) -> list[Hackathon]:
    out = []
    for entry in payload.get("entries", []):
        e = entry.get("event") or {}
        name = (e.get("name") or "").strip()
        if not name or not e.get("url") or e.get("visibility") not in (None, "public"):
            continue
        if not is_hackathon(name):
            continue
        geo = e.get("geo_address_info") or {}
        online = e.get("location_type") == "online"
        calendar = entry.get("calendar") or {}
        hosts = [h.get("name") for h in entry.get("hosts") or [] if h.get("name")]
        city = geo.get("city")
        out.append(Hackathon(
            id=f"{NAME}:{e.get('api_id') or e['url']}",
            source=NAME,
            title=name,
            url=f"https://lu.ma/{e['url']}",
            organizer=calendar.get("name") if calendar.get("name") and calendar.get(
                "name") != "Personal" else ", ".join(hosts[:3]) or None,
            image_url=e.get("cover_url"),
            starts_at=to_utc(e.get("start_at")),
            ends_at=to_utc(e.get("end_at")),
            mode="online" if online else "in_person",
            location=None if online else ", ".join(
                x for x in (city, geo.get("region"), geo.get("country")) if x) or None,
            city=city,
            country=geo.get("country"),
            participants=entry.get("guest_count") or None,
        ))
    return out


def fetch(client: httpx.Client) -> list[Hackathon]:
    found: dict[str, Hackathon] = {}
    errors = 0
    for _, lat, lon in HUBS:
        try:
            r = client.get(API, params={"query": "hackathon", "pagination_limit": 50,
                                        "latitude": lat, "longitude": lon})
            r.raise_for_status()
        except httpx.HTTPError:
            errors += 1  # one hub failing is fine; all failing is not
            continue
        for h in parse(r.json()):
            found.setdefault(h.id, h)
    if errors == len(HUBS):
        raise RuntimeError("every lu.ma hub request failed")
    return list(found.values())
