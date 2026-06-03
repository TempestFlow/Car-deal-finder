# Lithuanian Car Deal Finder — Project Prompt for Claude Code

## Project Overview

Build a Python-based local tool that scrapes Lithuanian car listing websites, scores each listing as a "deal", and outputs a self-contained HTML results page with clickable links back to original listings.

---

## Target Websites

- **autoplius.lt** — Lithuania's main car marketplace
- **autogidas.lt** — Secondary Lithuanian car listing site

Both sites are Lithuanian, so expect Lithuanian-language HTML. Use `requests` + `BeautifulSoup4` for scraping. If a site heavily relies on JavaScript rendering, fall back to `playwright` (headless Chromium).

---

## Project Structure

```
car-deal-finder/
├── CLAUDE.md               # This file
├── main.py                 # Entry point — runs scraper, scorer, outputs HTML
├── config.py               # User-configurable filters (see below)
├── scrapers/
│   ├── __init__.py
│   ├── base.py             # Abstract base scraper class
│   ├── autoplius.py        # Scraper for autoplius.lt
│   └── autogidas.py        # Scraper for autogidas.lt
├── scorer.py               # Deal scoring logic
├── renderer.py             # HTML output generator
├── requirements.txt        # Python dependencies
└── output/
    └── results.html        # Generated output (auto-created)
```

---

## User Configuration (`config.py`)

All filters are set here — no CLI args needed. Example:

```python
FILTERS = {
    "makes": ["Toyota", "Volkswagen", "BMW"],   # Empty list = all makes
    "models": [],                                # Empty list = all models
    "year_min": 2010,
    "year_max": 2022,
    "price_max": 15000,                          # EUR
    "fuel_types": ["Diesel", "Petrol"],          # or "Electric", "Hybrid"
}

SCRAPER_SETTINGS = {
    "max_pages": 5,           # Pages to scrape per site per search
    "request_delay": 1.5,     # Seconds between requests (be polite)
    "timeout": 10,
}

OUTPUT_FILE = "output/results.html"
TOP_N_RESULTS = 50            # Show top N deals in output
```

---

## Data Model

Each scraped listing should be normalized into this structure:

```python
@dataclass
class CarListing:
    id: str                  # Unique ID (source + listing ID)
    source: str              # "autoplius" or "autogidas"
    url: str                 # Direct link to the listing
    title: str               # e.g. "Volkswagen Golf 2016"
    make: str
    model: str
    year: int
    price: float             # EUR
    mileage: int             # km
    fuel_type: str
    seller_type: str         # "private" or "dealer"
    listed_date: date        # When it was first listed
    price_history: list[float]  # If available (for price drop detection)
    images: list[str]        # URLs of listing photos
    deal_score: float        # Filled in by scorer.py (0–100)
```

---

## Scraper Implementation Notes

### autoplius.lt
- Search URL pattern: `https://autoplius.lt/skelbimai/naudoti-automobiliai?make={make}&year_from={year_min}&year_to={year_max}&price_to={price_max}`
- Listings are in `<article>` or `<div class="announcement-item">` elements
- Pagination via `?page=N` query parameter
- Seller type visible on listing detail page
- Use `Accept-Language: lt` header

### autogidas.lt
- Search URL pattern: `https://autogidas.lt/automobiliai/?make={make}&price_to={price_max}`
- Similar BeautifulSoup approach
- Inspect the site to find actual CSS selectors — they may change

### General Rules
- Add `User-Agent` header mimicking a real browser
- Respect `robots.txt` — check before scraping
- Catch and log errors per-listing, never crash the whole run
- Cache raw HTML locally (in `cache/`) to avoid re-scraping during development

---

## Scoring Logic (`scorer.py`)

Each listing gets a `deal_score` from 0 to 100. Higher = better deal. Compute it as a weighted sum of these sub-scores:

### 1. Price vs. Market Average (weight: 40%)
- Group all scraped listings by `(make, model, year ± 1)`
- Compute median price for the group
- Sub-score = `clamp((median - listing.price) / median * 100 * 2, 0, 100)`
- A listing 20% below median scores ~40 points on this factor alone

### 2. Mileage Score (weight: 30%)
- Expected mileage = `(current_year - listing.year) * 15000` km (15k/year average)
- Ratio = `listing.mileage / expected_mileage`
- Sub-score = `clamp((2 - ratio) * 50, 0, 100)` — 0 means 2× expected mileage or worse

### 3. Listing Freshness / Price Drop (weight: 15%)
- If price history shows a drop: +20 bonus points (capped at 100 total)
- Listing age in days: sub-score = `clamp(100 - listing_age_days * 2, 0, 100)`
- Fresh listings score higher (less likely to have hidden problems)

### 4. Seller Type (weight: 15%)
- Private seller = 100 points (no dealer markup)
- Dealer = 40 points

### Final Score
```python
deal_score = (
    price_score * 0.40 +
    mileage_score * 0.30 +
    freshness_score * 0.15 +
    seller_score * 0.15
)
```

---

## HTML Output (`renderer.py`)

Generate a **single self-contained `results.html`** file. Requirements:

- No external dependencies (inline all CSS/JS)
- Responsive, clean design — think a simple card grid or sortable table
- Each card/row shows:
  - Thumbnail image (first photo from listing)
  - Title, Year, Price (€), Mileage (km), Fuel type, Seller type
  - Source badge ("autoplius" or "autogidas")
  - **Deal Score** — shown as a colored badge (green ≥70, yellow 40–69, red <40)
  - **"View Listing" button** — opens original URL in new tab
- Top of page: summary stats (total listings found, average price, best deal)
- Sortable columns (JS): by score, price, mileage, year
- Filter bar (JS): filter by source, seller type, fuel type client-side

---

## Running the Tool

```bash
# Install dependencies
pip install -r requirements.txt

# Edit your filters
nano config.py

# Run
python main.py

# Open results
open output/results.html   # macOS
xdg-open output/results.html  # Linux
start output/results.html  # Windows
```

---

## Requirements.txt (starting point)

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
playwright>=1.40.0   # Only if JS rendering needed
python-dateutil>=2.8.0
Jinja2>=3.1.0        # For HTML templating in renderer.py
```

---

## Development Tips for Claude Code

1. **Start with autoplius.lt only** — get the full pipeline working end-to-end before adding autogidas.lt
2. **Inspect the real HTML first** — run a quick `requests.get(url)` and `print(soup.prettify())` to find actual CSS selectors before writing the full scraper
3. **Use sample data early** — hardcode 5–10 fake `CarListing` objects to build and test the scorer and renderer before scraping works
4. **Test the scorer independently** — write a small `test_scorer.py` with edge cases (no comparable listings, very new car, dealer vs private)
5. **The HTML file should open and look good with zero internet connection** — all assets inline

---

## Out of Scope (for now)

- Scheduled/automatic re-runs (no cron, no daemon)
- Database persistence
- User accounts or hosting
- Email/push notifications
- Mobile.de or other non-Lithuanian sites
