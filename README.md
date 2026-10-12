# Car Deal Finder

A local Python tool that scrapes Lithuanian car listing sites, scores every listing as a deal, and produces a self-contained HTML results page you can open in any browser — no server, no account, no internet required after generation.

---

## What it does

1. **Scrapes** autoplius.lt and autogidas.lt for used cars matching your filters
2. **Scores** each listing 0–100 based on price, mileage, freshness, and seller type
3. **Applies bonuses/penalties** for known-reliable models (+5–10 pts) and damaged cars (−30 pts)
4. **Selects** a diverse set of results so every configured brand is represented
5. **Renders** a polished, filterable, sortable HTML file with all results

---

## Project structure

```
car-deal-finder/
├── main.py              # Entry point — orchestrates scraping, scoring, and output
├── config.py            # All user settings live here (target models, price, city, TA)
├── models.py            # CarListing dataclass
├── scorer.py            # Deal-scoring logic and reliable-model bonuses
├── renderer.py          # Jinja2 HTML template + render function
├── scrapers/
│   ├── base.py          # BaseScraper — HTTP session, caching, filter application
│   ├── autoplius.py     # Scraper for autoplius.lt
│   └── autogidas.py     # Scraper for autogidas.lt
├── market.py            # Market price: median of comparable listings
├── storage.py           # JSON persistence and price-history merging
├── output/
│   └── results.html     # Generated output (created on first run)
├── cache/               # Raw HTML cache (auto-created, speeds up re-runs)
└── requirements.txt
```

---

## Requirements

- Python 3.10 or newer
- pip

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/TempestFlow/Car-deal-finder.git
cd Car-deal-finder

# 2. Create a virtual environment (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Open `config.py` and set your preferences — no command-line arguments needed.

```python
TARGETS = [                 # Only these make/model pairs are searched
    ("Toyota", "Corolla"), ("Honda", "Civic"),
    ("Skoda", "Octavia"), ("Toyota", "Prius"),
]

FILTERS = {
    "price_min": 1500,      # EUR
    "price_max": 4500,      # EUR
    "city": "Vilnius",      # Listing location
    "ta_min": "2028-01",    # Techninė apžiūra must be valid at least until YYYY-MM
    "year_min": None,
    "year_max": None,
    "fuel_types": [],       # e.g. ["Diesel", "Petrol"] — empty means all fuel types
}

SCRAPER_SETTINGS = {
    "max_pages": 5,          # Pages per model per site; stops early when a page has nothing new
    "request_delay": 1.5,    # Seconds to wait between requests (be polite to the servers)
    "timeout": 10,           # HTTP timeout in seconds
    "enrich_details": True,  # Required — the TA date is only on the listing detail page
}

OUTPUT_FILE = "output/results.html"
TOP_N_RESULTS = 150          # Max listings shown in the output file
```

All filters are put into the site search URL, so only matching listings are downloaded:

| Filter | autogidas.lt | autoplius.lt |
|---|---|---|
| Make / model | URL path `/toyota/corolla/` | `make_id`, `model_id` |
| Price | `f_215` / `f_216` | `sell_price_from` / `sell_price_to` |
| City | `f_13=Vilnius` | `fk_place_countries_id=1&fk_place_cities_id=1` |
| Year | `f_41` / `f_42` | `make_date_from` / `make_date_to` |
| TA | — (checked on detail page) | `technical_passport=1` + exact date checked on detail page |

Listings whose TA is missing, unknown or earlier than `ta_min` are dropped.

### autoplius.lt and Cloudflare

autoplius.lt answers plain HTTP requests with a Cloudflare check (HTTP 403), so it is fetched with a
**visible** Microsoft Edge window driven by Playwright (headless mode does not pass the check). The
browser profile is kept in `cache/browser_profile/`, so the check normally runs only once. On Windows
the installed Edge is used; elsewhere run `playwright install chromium` once.

---

## Running

```bash
python main.py
```

Then open the output file:

```bash
# Windows
start output\results.html

# macOS
open output/results.html

# Linux
xdg-open output/results.html
```

### Re-scraping fresh data

By default the tool reuses a local HTML cache so re-runs are instant during development. To force a full re-scrape:

```bash
python main.py --fresh
```

The cache lives in `cache/` and can be deleted manually at any time.

---

## How it works

### Pipeline

```
config.py
    ↓
AutopliusScraper  ──┐
AutogidasScraper  ──┴──▶  score_listings()  ──▶  _select_diverse()  ──▶  render_html()
                                                                               ↓
                                                                       output/results.html
```

### Scrapers (`scrapers/autoplius.py`, `scrapers/autogidas.py`)

Each scraper:
- Builds search URLs from `TARGETS` + `FILTERS` (model, price range, city, TA)
- Fetches listing pages with a browser-like `User-Agent` and `Accept-Language: lt` header
- Caches raw HTML to `cache/<source>/` (MD5-keyed per URL)
- Parses each listing card for: URL, title, make, model, year, price, mileage, fuel type, and thumbnail image
- Detects damage from Lithuanian keywords in the card text (`avarinis`, `daužtas`, `avarija`, `pažeidas`, etc.)
- When `enrich_details: True`, visits each listing's detail page to refine seller type (`private` vs `dealer`), listed date, and damage information

### Market price (`market.py`)

The budget filter (1500–4500 €) only decides which cars are candidates. Whether a candidate is a good deal is
judged against the wider market: after the candidate search, each scraper also reads up to `market_pages`
search pages per model with **no price, city or TA filter** (all of Lithuania, the candidates' years ± 2).
Only search cards are used — no detail pages — and these pages are cached for 72 h, even with `--fresh`.

For each candidate the market price is the median asking price of comparable listings: same make and base
model (`Civic VII` counts as `Civic`), year ±1 (widened to ±2 if needed), same fuel when there are enough,
excluding damaged cards and prices under 300 €. With fewer than 5 comparables the market price is unknown and
the score falls back to comparing within the scraped candidates. Cards show `market ~€3,200 · −18%`, and
the **vs Market** sort puts the biggest discounts first.

### Scoring (`scorer.py`)

Each listing gets a `deal_score` from 0 to 100:

| Factor | Weight | How it's calculated |
|---|---|---|
| **Price** | 40% | Compared to the **market price** (see below). 50% below market = 100 pts. At or above market = 0 pts. |
| **Mileage** | 30% | Expected mileage = `(current_year − listing_year) × 15,000 km`. At expected = 50 pts. Zero mileage = 100 pts. Double expected = 0 pts. Suspiciously low mileage on old cars is capped at 90 (odometer fraud guard). |
| **Freshness** | 15% | Starts at 100, loses 1 pt per day the listing has been live. Hits 0 after 100 days. A detected price drop adds +15 bonus points. |
| **Seller type** | 15% | Private seller = 100 pts (no dealer markup). Dealer = 40 pts. |

**Post-scoring adjustments:**

- **Reliability bonus (+5 to +10 pts):** Applied to well-known reliable models. Tier 1 (+10): Toyota Corolla/Camry/RAV4/Yaris/Prius/Land Cruiser, Honda Civic/Accord/CR-V/Jazz, all Lexus models. Tier 2 (+7–9): Mazda 3/6/CX-5, Hyundai i30/Tucson/Ioniq, Kia Ceed/Sportage, Suzuki Swift/Vitara, Subaru Forester/Impreza. Tier 3 (+4–6): Skoda Octavia/Superb, VW Golf/Passat/Polo.
- **Damage penalty (−30 pts):** Applied when a listing mentions damage or accident history in Lithuanian.

### Brand-diverse selection (`main.py`)

Instead of simply taking the top 150 listings by score (which would exclude budget brands), the tool guarantees **at least 5 listings per configured make**, then fills remaining slots from the global top by score.

### Output (`renderer.py`)

A single self-contained `results.html` with no external dependencies:

- **Score ring** — overlaid on the car photo, colour-coded green (≥70) / amber (40–69) / red (<40)
- **Reliable / Damaged badges** — overlaid top-left on the photo
- **Spec chips** — year, fuel, mileage, seller type, source
- **Metric bars** — gradient bars showing each sub-score
- **Sticky filter bar** — filter by make, seller, fuel, source, max price; sort by score/price/mileage/year
- **Live result counter** — updates as you filter

---

## Output HTML features

| Feature | How to use |
|---|---|
| Filter by make | "Make" dropdown — shows only brands found in results |
| Filter by seller | "Seller" dropdown — Private / Dealer |
| Filter by fuel | "Fuel" dropdown — Diesel / Petrol / Electric / etc. |
| Filter by source | "Source" dropdown — autoplius / autogidas |
| Max price cap | Type a number in the "Max €" field |
| Sort | Score (default) · Price · vs Market · Mileage · Year buttons |
| View listing | "View Listing →" button opens original URL in a new tab |

---

## Tips

- **Start fast:** keep `enrich_details: False` and `max_pages: 3` for a quick first run, then increase once the pipeline is confirmed working.
- **Cache is your friend:** the tool never re-downloads a page it has already cached. Delete `cache/` only when you want fully fresh data.
- **Price drops:** run the tool twice over consecutive days. On the second run, listings whose price fell since the first run get a +15 freshness bonus, surfacing motivated sellers.
- **Adjust `max_pages`:** autoplius.lt typically returns 30–40 listings per page, so `max_pages: 10` can yield up to ~400 listings per make before deduplication and filtering.
- **Change the search:** edit `TARGETS` (autoplius also needs the model's id in `AUTOPLIUS_MODEL_IDS`) or the ranges in `FILTERS`.

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP fetching |
| `beautifulsoup4` + `lxml` | HTML parsing |
| `python-dateutil` | Parsing Lithuanian date strings |
| `Jinja2` | HTML templating |
| `playwright` | Drives a real browser for autoplius.lt (Cloudflare check) |

---

## Legal / ethical notes

- The tool inserts a configurable delay between requests (`request_delay: 1.5 s` by default) to avoid overloading servers.
- Raw HTML is cached locally so the same page is never fetched twice in the same session.
- This tool is for personal use only. Check autoplius.lt and autogidas.lt terms of service before heavy use.
