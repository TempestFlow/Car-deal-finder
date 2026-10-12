TARGETS = [                                      # (make, model) — only these are searched
    ("Toyota", "Corolla"),
    ("Honda", "Civic"),
    ("Skoda", "Octavia"),
    ("Toyota", "Prius"),
]

FILTERS = {
    "price_min": 1500,                           # EUR
    "price_max": 4500,                           # EUR
    "city": "Vilnius",                           # Listing location (applied in the site search URL)
    "ta_min": "2028-01",                         # Techninė apžiūra must be valid at least until YYYY-MM
    "year_min": None,
    "year_max": None,
    "fuel_types": [],                            # Empty = all fuels. e.g. ["Diesel", "Petrol"]
}

SCRAPER_SETTINGS = {
    "max_pages": 5,           # Per model; stops earlier when a page has no new listings
    "market_pages": 3,        # Per model per site for the market-price sample (search cards only, cached 72 h)
    "request_delay": 1.5,
    "timeout": 10,
    "enrich_details": True,   # Required: detail pages hold the TA date, seller type & city
}

OUTPUT_FILE = "output/results.html"
INSIGHTS_FILE = "output/insights.html"
TOP_N_RESULTS = 150
