"""Fetch every source, clean up, merge duplicates, and build the published feed."""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from . import sponsors
from .dedupe import dedupe
from .http import make_client
from .models import Hackathon
from .sources import SOURCES, Fetcher

log = logging.getLogger(__name__)

# Keep events that ended within this window so "just ended" ones don't vanish mid-day.
GRACE = timedelta(days=1)


class SourceHealth(BaseModel):
    ok: bool
    count: int
    seconds: float
    error: str | None = None
    stale: bool = False  # True when the previous run's data was reused


class Feed(BaseModel):
    generated_at: datetime
    count: int
    sources: dict[str, SourceHealth]
    hackathons: list[Hackathon]


def _run_source(name: str, fetch: Fetcher) -> tuple[list[Hackathon], SourceHealth]:
    start = time.monotonic()
    try:
        with make_client() as client:
            items = fetch(client)
    except Exception as exc:  # one broken site must not sink the whole feed
        log.exception("source %s failed", name)
        return [], SourceHealth(ok=False, count=0, seconds=round(time.monotonic() - start, 2),
                                error=f"{type(exc).__name__}: {exc}"[:300])
    health = SourceHealth(ok=bool(items), count=len(items),
                          seconds=round(time.monotonic() - start, 2),
                          error=None if items else "returned 0 hackathons")
    return items, health


def is_current(h: Hackathon, now: datetime) -> bool:
    last = h.ends_at or h.registration_deadline or h.starts_at
    return last is None or last >= now - GRACE


def sort_key(h: Hackathon) -> tuple:
    soonest = h.registration_deadline or h.ends_at or h.starts_at
    return (soonest is None, soonest or datetime.max.replace(tzinfo=UTC), h.title.lower())


def load_previous(path: Path) -> Feed | None:
    try:
        return Feed.model_validate_json(path.read_text())
    except (OSError, ValueError):
        return None


def build_feed(sources: dict[str, Fetcher] | None = None, previous: Feed | None = None,
               now: datetime | None = None) -> Feed:
    sources = SOURCES if sources is None else sources
    now = now or datetime.now(UTC)
    prev_items = previous.hackathons if previous else []

    with ThreadPoolExecutor(max_workers=len(sources) or 1) as pool:
        results = dict(zip(sources, pool.map(lambda kv: _run_source(*kv), sources.items())))

    collected: list[Hackathon] = []
    health: dict[str, SourceHealth] = {}
    for name, (items, h) in results.items():
        if not h.ok:
            reused = [p for p in prev_items if p.source == name]
            if reused:
                items = [p.model_copy(update={"also_on": []}) for p in reused]
                h.stale = True
        health[name] = h
        collected.extend(items)

    first_seen = {p.id: p.first_seen for p in prev_items if p.first_seen}
    for p in prev_items:  # merged records remember their secondary listings' ages too
        for listing in p.also_on:
            first_seen.setdefault(listing.url, p.first_seen)

    current = [sponsors.tag(h) for h in collected if is_current(h, now)]
    merged = dedupe(current)
    for h in merged:
        h.first_seen = first_seen.get(h.id) or first_seen.get(h.url) or now
    merged.sort(key=sort_key)
    return Feed(generated_at=now, count=len(merged), sources=health, hackathons=merged)


def write_feed(feed: Feed, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = feed.model_dump(mode="json", exclude_none=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
