import argparse
import logging
import sys
from pathlib import Path

from .pipeline import build_feed, load_previous, write_feed
from .sources import SOURCES

DEFAULT_OUT = Path("web/data/hackathons.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hackathon-tracker",
                                     description="Aggregate hackathon listings into one feed.")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="fetch all sources and write the JSON feed")
    fetch.add_argument("--out", type=Path, default=DEFAULT_OUT)
    fetch.add_argument("--only", help="comma-separated source names, e.g. devpost,mlh")
    sub.add_parser("sources", help="list available sources")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "sources":
        print("\n".join(SOURCES))
        return 0

    sources = SOURCES
    if args.only:
        names = [n.strip() for n in args.only.split(",")]
        unknown = [n for n in names if n not in SOURCES]
        if unknown:
            parser.error(f"unknown source(s): {', '.join(unknown)}")
        sources = {n: SOURCES[n] for n in names}

    feed = build_feed(sources, previous=load_previous(args.out))
    write_feed(feed, args.out)

    for name, h in feed.sources.items():
        status = "ok" if h.ok else ("STALE" if h.stale else "FAIL")
        print(f"{name:15} {status:6} {h.count:4}  {h.seconds:5.1f}s  {h.error or ''}")
    print(f"{feed.count} hackathons written to {args.out}")
    return 0 if any(h.ok for h in feed.sources.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
