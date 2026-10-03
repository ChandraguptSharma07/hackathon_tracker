"""One module per listing site. Each exposes NAME, `parse(payload)` and `fetch(client)`.

`parse` is pure (tested against saved fixtures); `fetch` does the network calls.
"""

from collections.abc import Callable

import httpx

from ..models import Hackathon
from . import cerebralvalley, devfolio, devpost, hackerearth, lablab, mlh, unstop

Fetcher = Callable[[httpx.Client], list[Hackathon]]

SOURCES: dict[str, Fetcher] = {
    m.NAME: m.fetch
    for m in (devpost, mlh, devfolio, unstop, hackerearth, cerebralvalley, lablab)
}
