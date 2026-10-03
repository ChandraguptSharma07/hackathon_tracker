"""Tag in-person events with the metro area they happen in.

Sources spell places many ways ("West Delhi", "Delhi Division", "नई दिल्ली", "Gautam Buddha
Nagar", a bare campus name), so each metro is a set of aliases: city and district names,
local-script spellings, and campuses that often appear without a city.
"""

import re

from .models import Hackathon

METRO_ALIASES: dict[str, list[str]] = {
    "Delhi NCR": [
        r"delhi", r"\bncr\b", r"gurugram", r"gurgaon", r"noida", r"ghaziabad", r"faridabad",
        r"sohna", r"gautam buddh?a? nagar", r"pitampura", r"rohini", r"okhla", r"moti nagar",
        r"sharda university", r"galgotias", r"bennett university", r"\bdtu\b", r"\bnsut\b",
        r"\bggsipu\b", r"jamia millia", r"दिल्ली", r"गुरुग्राम", r"गुड़गांव", r"नोएडा",
        r"गाज़ियाबाद", r"फरीदाबाद",
    ],
    "Bengaluru": [r"bengaluru", r"bangalore", r"ಬೆಂಗಳೂರು"],
    "Mumbai": [r"mumbai", r"bombay", r"navi mumbai", r"thane"],
    "Hyderabad": [r"hyderabad", r"secunderabad"],
    "Pune": [r"\bpune\b"],
    "Chennai": [r"chennai"],
    "SF Bay Area": [r"san francisco", r"\bsf\b", r"berkeley", r"palo alto", r"menlo park",
                    r"mountain view", r"stanford", r"san jose", r"oakland", r"sunnyvale"],
    "New York": [r"new york", r"\bnyc\b", r"brooklyn", r"manhattan"],
    "London": [r"\blondon\b"],
}

_COMPILED = {metro: re.compile("|".join(aliases), re.I) for metro, aliases in METRO_ALIASES.items()}


def find_metro(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t)
    return next((m for m, rx in _COMPILED.items() if rx.search(blob)), None) if blob else None


def resolve(name: str) -> str | None:
    """Map loose user input ("delhi", "bangalore") to a metro name."""
    return find_metro(name) or next(
        (m for m in METRO_ALIASES if m.lower() == name.strip().lower()), None)


def tag(h: Hackathon) -> Hackathon:
    """Set `metro` for events with a physical part. Place fields win; the title is a
    fallback for listings whose address is only a venue name."""
    if h.mode == "online" or h.metro:
        return h
    h.metro = find_metro(h.location, h.city)
    if h.metro is None and not h.city:
        h.metro = find_metro(h.title)
    return h
