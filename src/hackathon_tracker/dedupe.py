"""Merge the same hackathon listed on several sites (e.g. Devpost + MLH)."""

import re
from datetime import timedelta
from difflib import SequenceMatcher

from .models import Hackathon, Listing

# Earlier wins as the primary record when two listings merge.
SOURCE_PRIORITY = ["devpost", "mlh", "cerebralvalley", "lablab", "devfolio", "unstop",
                   "hackerearth"]

NOISE_WORDS = {"the", "hackathon", "a", "an", "of", "and", "edition"}
DATE_SLACK = timedelta(days=3)


def norm_title(title: str) -> str:
    t = re.sub(r"\b(19|20)\d{2}(-\d{2,4})?\b", " ", title.lower())
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(w for w in t.split() if w not in NOISE_WORDS)


def _dates_close(a: Hackathon, b: Hackathon) -> bool | None:
    """True/False when both sides have a comparable date, None when they don't."""
    for field in ("starts_at", "ends_at"):
        x, y = getattr(a, field), getattr(b, field)
        if x and y:
            return abs(x - y) <= DATE_SLACK
    return None


def same_event(a: Hackathon, b: Hackathon, ta: str, tb: str) -> bool:
    """`a` is an already-kept record, `b` a candidate; ta/tb are their normalized titles."""
    taken = {a.source} | {l.source for l in a.also_on}
    if b.source in taken or not ta or not tb:  # at most one listing per site
        return False
    wa, wb = set(ta.split()), set(tb.split())
    if len(wa & wb) / len(wa | wb) < 0.4:  # cheap filter before SequenceMatcher
        return False
    ratio = SequenceMatcher(None, ta, tb).ratio()
    close = _dates_close(a, b)
    if close is None:
        return ratio >= 0.95
    return close and ratio >= 0.85


def merge(primary: Hackathon, other: Hackathon) -> Hackathon:
    for field, value in other:
        if getattr(primary, field) in (None, "") and value not in (None, ""):
            setattr(primary, field, value)
    primary.themes = list(dict.fromkeys(primary.themes + other.themes))
    primary.sponsors = sorted(set(primary.sponsors) | set(other.sponsors))
    if other.participants and (primary.participants or 0) < other.participants:
        primary.participants = other.participants
    known = {primary.url} | {l.url for l in primary.also_on}
    for listing in [Listing(source=other.source, url=other.url), *other.also_on]:
        if listing.url not in known:
            primary.also_on.append(listing)
            known.add(listing.url)
    return primary


def dedupe(items: list[Hackathon]) -> list[Hackathon]:
    rank = {s: i for i, s in enumerate(SOURCE_PRIORITY)}
    ordered = sorted(items, key=lambda h: rank.get(h.source, len(rank)))
    kept: list[tuple[Hackathon, str]] = []
    for h in ordered:
        t = norm_title(h.title)
        match = next((k for k, kt in kept if same_event(k, h, kt, t)), None)
        if match is not None:
            merge(match, h)
        else:
            kept.append((h, t))
    return [k for k, _ in kept]
