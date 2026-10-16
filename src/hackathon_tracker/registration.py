"""Work out until when a newcomer can still join each listing.

Sites differ: on Kaggle or Devpost you can enter while the event is running, on Unstop or
for an MLH weekend you must register before it starts. Evidence is used in this order:

1. An explicit deadline from the source (Unstop's registration end, Kaggle's entry
   deadline, Devfolio's application close…). Parsers put it in `registration_deadline`.
2. An explicit open/closed flag from the source (lu.ma sold out, lablab signups off),
   stored in `registration_open`.
3. The site's known policy: late-join sites accept people until the event ends, the
   rest until it starts.
4. Otherwise: online events and ML competitions until the end, physical ones until
   the start.

Steps 3 and 4 set `registration_inferred`, so the site can label the date an estimate.
"""

from datetime import datetime

from .models import Hackathon

# Sites where joining a running event is normal: submissions stay open to newcomers.
LATE_JOIN_SOURCES = {"devpost", "kaggle", "zindi", "dorahacks", "hackerearth", "lablab"}
# Sites where registration closes before the event starts (applications, venues).
REGISTER_FIRST_SOURCES = {"unstop", "devfolio", "mlh", "ethglobal", "luma", "cerebralvalley",
                          "hackclub", "taikai"}


def allows_late_join(h: Hackathon) -> bool:
    """Late joining needs a site that allows it (any site listing the event counts) and a
    way to take part remotely: nobody walks into a venue halfway through."""
    if h.mode == "in_person":
        return h.kind == "competition"
    sources = {h.source} | {listing.source for listing in h.also_on}
    if sources & LATE_JOIN_SOURCES:
        return True
    if sources <= REGISTER_FIRST_SOURCES:
        return False
    return h.kind == "competition" or h.mode == "online"


def infer(h: Hackathon) -> Hackathon:
    """Fill `registration_deadline` when the source gave none."""
    if h.registration_deadline is None:
        guess = h.ends_at if allows_late_join(h) else (h.starts_at or h.ends_at)
        if guess is not None:
            h.registration_deadline = guess
            h.registration_inferred = True
    return h


def is_open(h: Hackathon, now: datetime) -> bool | None:
    """True/False when known, None when there is no evidence either way."""
    if h.registration_open is False:
        return False
    if h.registration_deadline is not None:
        return h.registration_deadline >= now
    return h.registration_open
