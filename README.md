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
├── config.py            # All user settings live here (makes, price cap, pages, etc.)
├── models.py            # CarListing dataclass
├── scorer.py            # Deal-scoring logic and reliable-model bonuses
├── renderer.py          # Jinja2 HTML template + render function
├── scrapers/
│   ├── base.py          # BaseScraper — HTTP session, caching, filter application
│   ├── autoplius.py     # Scraper for autoplius.lt
│   └── autogidas.py     # Scraper for autogidas.lt
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
FILTERS = {
    # Car brands to search. Empty list = all makes on the site.
    "makes": ["Toyota", "Volkswagen", "BMW", "Audi", "Mercedes-Benz",
              "Skoda", "Opel", "Ford", "Renault", "Honda",
              "Hyundai", "Kia", "Mazda", "Volvo"],

    "models": [],           # Not yet used by scrapers; reserved for future filtering
    "year_min": 2010,       # Minimum registration year
    "year_max": 2022,       # Maximum registration year
    "price_max": 15000,     # Maximum price in EUR
    "fuel_types": [],       # e.g. ["Diesel", "Petrol"] — empty means all fuel types
}

SCRAPER_SETTINGS = {
    "max_pages": 10,         # Pages to fetch per make per site (more = slower but more results)
    "request_delay": 1.5,    # Seconds to wait between requests (be polite to the servers)
    "timeout": 10,           # HTTP timeout in seconds
    "enrich_details":False,  # Set True to visit each listing page for seller type, date,
                             # and damage info — much slower but more accurate scoring
}

OUTPUT_FILE = "output/results.html"
TOP_N_RESULTS = 150          # Max listings shown in the output file
```

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
- Builds search URLs from your `FILTERS` (make, year range, max price)
- Fetches listing pages with a browser-like `User-Agent` and `Accept-Language: lt` header
- Caches raw HTML to `cache/<source>/` (MD5-keyed per URL)
- Parses each listing card for: URL, title, make, model, year, price, mileage, fuel type, and thumbnail image
- Detects damage from Lithuanian keywords in the card text (`avarinis`, `daužtas`, `avarija`, `pažeidas`, etc.)
- When `enrich_details: True`, visits each listing's detail page to refine seller type (`private` vs `dealer`), listed date, and damage information

### Scoring (`scorer.py`)

Each listing gets a `deal_score` from 0 to 100:

| Factor | Weight | How it's calculated |
|---|---|---|
| **Price** | 40% | Compared to the median price of identical/similar make·model·year listings scraped in the same run. 50% below median = 100 pts. At or above median = 0 pts. |
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
| Sort | Score (default) · Price · Mileage · Year buttons |
| View listing | "View Listing →" button opens original URL in a new tab |

---

## Tips

- **Start fast:** keep `enrich_details: False` and `max_pages: 3` for a quick first run, then increase once the pipeline is confirmed working.
- **Cache is your friend:** the tool never re-downloads a page it has already cached. Delete `cache/` only when you want fully fresh data.
- **Price drops:** run the tool twice over consecutive days. On the second run, listings whose price fell since the first run get a +15 freshness bonus, surfacing motivated sellers.
- **Adjust `max_pages`:** autoplius.lt typically returns 30–40 listings per page, so `max_pages: 10` can yield up to ~400 listings per make before deduplication and filtering.
- **Narrow your search:** if results are too noisy, add specific models to `FILTERS["makes"]` or tighten `year_min`/`price_max`.

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP fetching |
| `beautifulsoup4` + `lxml` | HTML parsing |
| `python-dateutil` | Parsing Lithuanian date strings |
| `Jinja2` | HTML templating |
| `playwright` | Optional — only needed if a site requires JavaScript rendering |

---

## Legal / ethical notes

- The tool inserts a configurable delay between requests (`request_delay: 1.5 s` by default) to avoid overloading servers.
- Raw HTML is cached locally so the same page is never fetched twice in the same session.
- This tool is for personal use only. Check autoplius.lt and autogidas.lt terms of service before heavy use.
