# Hackathon Tracker

One page for every open and upcoming hackathon (and ML competition), so you don't have to
check a dozen sites.

## Quick start

```sh
./launch
```

That's it. On first run it installs dependencies, fetches every source (about 30 seconds),
starts the site at http://127.0.0.1:8000 and opens your browser. While it runs it refreshes the
data every 6 hours; if the data is already older than that when you start it, it refreshes in the
background and you just reload the page. Needs [uv](https://docs.astral.sh/uv/).

Options pass straight through: `./launch --port 9000`, `./launch --no-open`,
`./launch --no-fetch`, `./launch --host 0.0.0.0` (open it from your phone on the same network).

Listings are pulled from public data on:

| Source | How | Strong on |
| --- | --- | --- |
| Devpost | JSON API | Corporate hackathons (OpenAI, Amazon, Google…), online events |
| MLH | Embedded page JSON | Student hackathons, North America and Europe |
| Devfolio | Search API | India, web3 |
| Unstop | Public search API | Indian college hackathons |
| HackerEarth | Events feed | Online hackathons |
| Cerebral Valley | JSON-LD | AI lab hackathons (Anthropic, OpenAI, DeepMind) |
| lablab.ai | Next.js payload | Online AI hackathons (AMD, IBM, Meta…) |
| lu.ma | Discover search around 20 tech hubs | In-person AI and startup hackathons (incl. lab-run ones) |
| ETHGlobal | Next.js payload | Ethereum hackathons |
| DoraHacks | JSON API behind the site | Web3 and AI hackathons |
| TAIKAI | Next.js Apollo cache | European hackathons and innovation challenges |
| Hack Club | JSON API | High school hackathons |
| Kaggle | Site's own listing endpoint (no API key) | ML competitions, lab-sponsored ones (Google DeepMind…) |
| Zindi | JSON API | African data science competitions |

Kaggle and Zindi entries are tagged as ML competitions and can be filtered by Type.

No source uses an AI API; everything is plain HTTP plus parsing.

Events listed on more than one site are merged into one entry. Well-known companies are
detected from titles, organizers and descriptions, so you can filter for, say, every
Anthropic or OpenAI event.

## How it works

```
sources/*.py  →  normalize to Hackathon  →  drop past events  →  tag sponsors  →  merge duplicates  →  web/data/hackathons.json
```

- Each source module has a pure `parse()` (tested against saved responses in
  `tests/fixtures/`) and a `fetch()` that does the network calls.
- If a source fails or returns nothing, the previous run's listings for it are kept and
  it is marked stale in the feed's `sources` health block.
- `first_seen` is carried between runs to power the "New" badge.
- The site in `web/` is static HTML/CSS/JS that filters the JSON in the browser. Filters are
  kept in the URL, so filtered views can be shared or bookmarked.

## Other commands

```sh
uv run hackathon-tracker fetch                     # all sources → web/data/hackathons.json
uv run hackathon-tracker fetch --only devpost,mlh  # refresh some, keep the rest
uv run hackathon-tracker sources                   # list source names
uv run hackathon-tracker -v fetch                  # show tracebacks for failing sources
uv run pytest
```

## Deploy

`.github/workflows/update.yml` runs every 6 hours: tests, fetch, commit the refreshed JSON,
and publish `web/` to GitHub Pages. Enable Pages with source "GitHub Actions" in the repo
settings.

## Adding a source

1. Save a trimmed real response to `tests/fixtures/`.
2. Write `src/hackathon_tracker/sources/<name>.py` with `NAME`, `parse()` and `fetch()`.
3. Register it in `sources/__init__.py` and give it a place in `dedupe.SOURCE_PRIORITY`.
4. Add a test in `tests/test_sources.py`.
