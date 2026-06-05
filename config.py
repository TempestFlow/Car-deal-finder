FILTERS = {
    "makes": [                                   # Empty list = all makes
        "Toyota", "Volkswagen", "BMW", "Audi", "Mercedes-Benz",
        "Skoda", "Opel", "Ford", "Renault", "Honda",
        "Hyundai", "Kia", "Mazda", "Volvo",
    ],
    "models": [],                                # Empty list = all models
    "year_min": 2010,
    "year_max": 2022,
    "price_max": 15000,                          # EUR
    "fuel_types": [],                            # Empty = all fuels. e.g. ["Diesel", "Petrol"]
}

SCRAPER_SETTINGS = {
    "max_pages": 5,
    "request_delay": 1.5,
    "timeout": 10,
    "enrich_details": True,   # Fetches detail pages for seller type, city fallback & Techninė apžiūra
}

OUTPUT_FILE = "output/results.html"
INSIGHTS_FILE = "output/insights.html"
TOP_N_RESULTS = 150
