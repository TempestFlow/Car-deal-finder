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
