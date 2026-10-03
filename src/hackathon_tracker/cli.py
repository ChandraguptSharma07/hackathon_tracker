import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from .pipeline import build_feed, load_previous, write_feed
from .places import METRO_ALIASES, resolve
from .sources import SOURCES

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"
DEFAULT_OUT = WEB_DIR / "data" / "hackathons.json"


def _fetch(args, parser) -> int:
    sources = SOURCES
    if args.only:
        names = [n.strip() for n in args.only.split(",")]
        unknown = [n for n in names if n not in SOURCES]
        if unknown:
            parser.error(f"unknown source(s): {', '.join(unknown)}")
        sources = {n: SOURCES[n] for n in names}

    feed = build_feed(sources, previous=load_previous(args.out), carry_over=bool(args.only))
    write_feed(feed, args.out)

    for name, h in feed.sources.items():
        status = "ok" if h.ok else ("STALE" if h.stale else "FAIL")
        print(f"{name:15} {status:6} {h.count:4}  {h.seconds:5.1f}s  {h.error or ''}")
    print(f"{feed.count} hackathons written to {args.out}")
    return 0 if any(h.ok for h in feed.sources.values()) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hackathon-tracker",
                                     description="Aggregate hackathon listings into one feed.")
    parser.add_argument("-v", "--verbose", action="store_true", help="show tracebacks")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch all sources and write the JSON feed")
    fetch.add_argument("--out", type=Path, default=DEFAULT_OUT)
    fetch.add_argument("--only", help="comma-separated source names, e.g. devpost,mlh")

    serve = sub.add_parser("serve", help="refresh data if old, run the site, open the browser")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="127.0.0.1",
                       help="use 0.0.0.0 to reach it from other devices on your network")
    serve.add_argument("--no-open", action="store_true", help="don't open a browser")
    serve.add_argument("--no-fetch", action="store_true", help="serve existing data only")
    serve.add_argument("--max-age", type=float, default=6,
                       help="refresh when data is older than this many hours (default 6)")
    serve.add_argument("--metro", metavar="CITY",
                       help="open on in-person events near a city, e.g. --metro delhi "
                            f"(known: {', '.join(METRO_ALIASES)})")

    sub.add_parser("sources", help="list available sources")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "sources":
        print("\n".join(SOURCES))
        return 0
    if args.command == "serve":
        query = ""
        if args.metro:
            metro = resolve(args.metro)
            if metro is None:
                parser.error(f"unknown city {args.metro!r}; known: {', '.join(METRO_ALIASES)}")
            query = urlencode({"metro": metro, "mode": "onsite"})
        from .serve import serve as run_server
        run_server(WEB_DIR, DEFAULT_OUT, host=args.host, port=args.port,
                   open_browser=not args.no_open, max_age=timedelta(hours=args.max_age),
                   fetch=not args.no_fetch, start_query=query)
        return 0
    return _fetch(args, parser)


if __name__ == "__main__":
    sys.exit(main())
