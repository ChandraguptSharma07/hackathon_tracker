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

`./launch --metro delhi` opens straight on in-person and hybrid events in Delhi NCR (Delhi,
Gurugram, Noida, Greater Noida, Ghaziabad, Faridabad). The same view is the "In person in Delhi
NCR" quick link on the page, and the "Near" filter covers Bengaluru, Mumbai, Hyderabad, Pune,
Chennai, SF Bay Area, New York and London too. Metro aliases live in
`src/hackathon_tracker/places.py`.

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
| lu.ma | Discover search around 22 tech hubs | In-person AI and startup hackathons (incl. lab-run ones) |
| ETHGlobal | Next.js payload | Ethereum hackathons |
| DoraHacks | JSON API behind the site | Web3 and AI hackathons |
| TAIKAI | Next.js Apollo cache | European hackathons and innovation challenges |
| Hack Club | JSON API | High school hackathons |
| Kaggle | Site's own listing endpoint (no API key) | ML competitions, lab-sponsored ones (Google DeepMind…) |
| Zindi | JSON API | African data science competitions |

Kaggle and Zindi entries are tagged as ML competitions and can be filtered by Type.

No source uses an AI API; everything is plain HTTP plus parsing.

## Registration status

Listings whose registration has closed are hidden by default ("Show closed registration"
brings them back). Sites differ: Kaggle, Devpost, DoraHacks, Zindi, HackerEarth and lablab.ai
let you join while an online event is running, while Unstop, MLH, Devfolio, lu.ma, ETHGlobal and
most in-person events close registration before they start. `registration.py` decides the last
moment you can join, in this order:

1. the site's own deadline (Unstop registration end, Kaggle entry deadline, Devfolio and
   ETHGlobal application close, TAIKAI registration step, Zindi entry close);
2. the site's open/closed flag (lu.ma full or waitlist, lablab signups off, Cerebral Valley
   sold out);
3. the site's policy: join until the end on late-join sites, until the start elsewhere;
4. otherwise online events and ML competitions until the end, physical ones until the start.

Estimated dates show with a "~" and say so on hover. Notes such as "Waitlist" or "Approval
required" appear as tags, and running events you can still enter are marked "Running · open to
join". The check runs again in the browser, so a feed a few hours old still hides events that
closed since.

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
