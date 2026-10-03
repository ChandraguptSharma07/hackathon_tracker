import httpx

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36 hackathon-tracker/0.1"
)


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        timeout=30,
        follow_redirects=True,
        transport=httpx.HTTPTransport(retries=2),
    )
