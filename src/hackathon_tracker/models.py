from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["online", "in_person", "hybrid"]
Kind = Literal["hackathon", "competition"]  # competition = ML/data contest (Kaggle, Zindi)


class Listing(BaseModel):
    """Where else a merged hackathon was found."""

    source: str
    url: str


class Hackathon(BaseModel):
    """One hackathon, normalized from any source.

    All datetimes are timezone-aware UTC. Fields a source does not provide stay None.
    """

    id: str  # "<source>:<source-specific id>"
    source: str
    title: str
    url: str
    kind: Kind = "hackathon"
    organizer: str | None = None
    description: str | None = None
    image_url: str | None = None

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # Last moment a newcomer can join. Explicit from the source, or estimated by
    # registration.infer() (then registration_inferred is True).
    registration_deadline: datetime | None = None
    registration_inferred: bool = False
    registration_open: bool | None = None  # explicit flag from the source, when it has one
    registration_note: str | None = None  # e.g. "Waitlist", "Approval required"

    mode: Mode | None = None
    location: str | None = None
    city: str | None = None
    country: str | None = None
    metro: str | None = None  # e.g. "Delhi NCR", set for events with a physical part

    prize_amount: float | None = None
    prize_currency: str | None = None
    prize_usd: float | None = None  # approximate, from fixed rates

    themes: list[str] = Field(default_factory=list)
    sponsors: list[str] = Field(default_factory=list)  # detected companies, e.g. "OpenAI"
    participants: int | None = None

    also_on: list[Listing] = Field(default_factory=list)
    first_seen: datetime | None = None
