import socket
from datetime import UTC, datetime, timedelta

from hackathon_tracker.pipeline import Feed, write_feed
from hackathon_tracker.serve import QuietHandler, _bind, feed_age


def test_bind_skips_busy_port():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        server = _bind("127.0.0.1", port, QuietHandler)
        try:
            assert server.server_port != port
        finally:
            server.server_close()


def test_feed_age(tmp_path):
    path = tmp_path / "feed.json"
    assert feed_age(path) is None
    write_feed(Feed(generated_at=datetime.now(UTC) - timedelta(hours=7), count=0, sources={},
                    hackathons=[]), path)
    assert timedelta(hours=6) < feed_age(path) < timedelta(hours=8)
