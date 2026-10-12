from dataclasses import dataclass, field
from datetime import date


@dataclass
class CarListing:
    id: str
    source: str
    url: str
    title: str
    make: str
    model: str
    year: int
    price: float
    mileage: int
    fuel_type: str
    seller_type: str         # "private" or "dealer"
    listed_date: date
    price_history: list = field(default_factory=list)
    images: list = field(default_factory=list)
    deal_score: float = 0.0
    price_sub_score: float = 0.0
    mileage_sub_score: float = 0.0
    freshness_sub_score: float = 0.0
    seller_sub_score: float = 0.0
    damage: bool = False
    damage_info: str = ""
    reliability_bonus: float = 0.0
    city: str = ""
    technical_inspection: str = ""  # raw scraped value e.g. "2025-12", "Nėra"
    ta_months_left: int = -1        # -1=unknown, 0=no TA, negative=expired, positive=months left
    ta_bonus: float = 0.0
    market_price: float = 0.0       # median asking price of comparable cars (0 = unknown)
    market_samples: int = 0         # how many comparables the median is based on
    market_diff_pct: float = 0.0    # (price - market) / market * 100; negative = below market
