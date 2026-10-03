"""Local launcher: refresh the feed when it is old, serve web/, and open the browser."""

import functools
import logging
import threading
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .pipeline import build_feed, load_previous, write_feed

log = logging.getLogger(__name__)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - signature from the base class
        pass

    def end_headers(self):
        # Always revalidate so a refreshed feed shows up on reload.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def feed_age(path: Path) -> timedelta | None:
    feed = load_previous(path)
    return datetime.now(UTC) - feed.generated_at if feed else None


def refresh(path: Path, background: bool = True) -> None:
    feed = build_feed(previous=load_previous(path))
    write_feed(feed, path)
    failed = [name for name, h in feed.sources.items() if not h.ok]
    note = f" ({len(failed)} source(s) failed: {', '.join(failed)})" if failed else ""
    hint = " Reload the page to see them." if background else ""
    print(f"Fetched {feed.count} listings{note}.{hint}", flush=True)


def _refresh_loop(path: Path, every: timedelta, stop: threading.Event) -> None:
    while not stop.wait(every.total_seconds()):
        try:
            refresh(path)
        except Exception:
            log.exception("scheduled refresh failed")


def _bind(host: str, port: int, handler) -> ThreadingHTTPServer:
    for candidate in range(port, port + 20):
        try:
            return ThreadingHTTPServer((host, candidate), handler)
        except OSError:
            continue
    raise OSError(f"no free port between {port} and {port + 19}")


def serve(web_dir: Path, feed_path: Path, host: str = "127.0.0.1", port: int = 8000,
          open_browser: bool = True, max_age: timedelta = timedelta(hours=6),
          fetch: bool = True, start_query: str = "") -> None:
    age = feed_age(feed_path)
    if fetch and age is None:
        print("No data yet, fetching every source (about 30 seconds)…", flush=True)
        refresh(feed_path, background=False)
    elif fetch and age > max_age:
        hours = age.total_seconds() / 3600
        print(f"Data is {hours:.0f}h old, refreshing in the background…", flush=True)
        threading.Thread(target=refresh, args=(feed_path,), daemon=True).start()

    stop = threading.Event()
    if fetch:
        threading.Thread(target=_refresh_loop, args=(feed_path, max_age, stop),
                         daemon=True).start()

    server = _bind(host, port, functools.partial(QuietHandler, directory=str(web_dir)))
    url = f"http://{host}:{server.server_port}/" + (f"?{start_query}" if start_query else "")
    print(f"Hackathon Tracker running at {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
        server.server_close()
