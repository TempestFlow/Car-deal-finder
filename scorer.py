from datetime import date
from statistics import median

from models import CarListing

NEUTRAL_SCORE = 50.0
EXPECTED_KM_PER_YEAR = 15000

# Known-reliable models with score bonuses. Keys are lowercase substrings matched
# against listing.model.lower() — so "corolla" matches "Corolla Verso", "Golf VII", etc.
# Tier 1 (+10): Japanese workhorses and Lexus — exceptional long-term reliability records.
# Tier 2 (+5): Strong reliability, slightly more complex or newer track record.
RELIABLE_MODELS: dict[str, dict[str, float]] = {
    "toyota": {
        "corolla": 10, "camry": 10, "rav4": 10, "yaris": 10, "prius": 10,
        "auris": 9, "avensis": 9, "hilux": 10, "land cruiser": 10,
        "verso": 8, "chr": 8, "c-hr": 8,
    },
    "honda": {
        "civic": 10, "accord": 10, "cr-v": 10, "crv": 10,
        "jazz": 10, "fit": 10, "hr-v": 9, "hrv": 9, "fr-v": 8,
    },
    "lexus": {
        "is": 10, "es": 10, "rx": 10, "gs": 10, "ls": 10, "ct": 9, "ux": 9, "nx": 9,
    },
    "mazda": {
        "3": 7, "6": 7, "cx-5": 7, "cx5": 7, "cx-3": 6, "cx3": 6,
        "2": 6, "mx-5": 7, "mx5": 7,
    },
    "hyundai": {
        "i30": 7, "tucson": 7, "ioniq": 8, "elantra": 6, "i20": 6,
        "kona": 6, "santa fe": 6,
    },
    "kia": {
        "ceed": 7, "sportage": 7, "rio": 6, "stonic": 6, "niro": 7,
        "proceed": 7, "xceed": 6,
    },
    "suzuki": {
        "swift": 8, "vitara": 7, "sx4": 6, "ignis": 6, "baleno": 6,
    },
    "subaru": {
        "forester": 7, "impreza": 7, "outback": 7, "legacy": 6, "xv": 6,
    },
    "skoda": {
        "octavia": 6, "superb": 6, "fabia": 5, "kodiaq": 5, "karoq": 5,
    },
    "volkswagen": {
        "golf": 5, "passat": 5, "polo": 5, "tiguan": 4,
    },
}


def _reliability_bonus(listing: CarListing) -> float:
    make = listing.make.lower()
    model = listing.model.lower()
    models = RELIABLE_MODELS.get(make, {})
    best = 0.0
    for known_model, bonus in models.items():
        if known_model in model:
            best = max(best, bonus)
    return best


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _price_score(listing: CarListing, all_listings: list) -> float:
    make = listing.make.lower()
    model = listing.model.lower()
    year = listing.year

    # Tiered grouping: try exact year → any year → make only
    def group_prices(key_fn):
        return [l.price for l in all_listings if l.price > 0 and l.id != listing.id and key_fn(l)]

    for key_fn in [
        lambda l: l.make.lower() == make and l.model.lower() == model and l.year == year,
        lambda l: l.make.lower() == make and l.model.lower() == model and abs(l.year - year) <= 2,
        lambda l: l.make.lower() == make,
    ]:
        prices = group_prices(key_fn)
        if len(prices) >= 1:
            med = median(prices)
            if med > 0:
                return _clamp((med - listing.price) / med * 200, 0, 100)

    return NEUTRAL_SCORE


def _mileage_score(listing: CarListing) -> float:
    if listing.year <= 0 or listing.mileage <= 0:
        return NEUTRAL_SCORE
    current_year = date.today().year
    age = max(current_year - listing.year, 1)
    expected = age * EXPECTED_KM_PER_YEAR
    ratio = listing.mileage / expected
    score = _clamp((2 - ratio) * 50, 0, 100)
    # Cap suspiciously low mileage on older cars (possible odometer fraud)
    if age > 3 and listing.mileage < 10000:
        score = min(score, 90.0)
    return score


def _freshness_score(listing: CarListing) -> float:
    age_days = (date.today() - listing.listed_date).days
    # 1 pt/day decay — hits 0 at 100 days
    base = _clamp(100 - age_days * 1.0, 0, 100)
    # +15 bonus if a real price drop was detected across scrape runs
    if len(listing.price_history) >= 2 and listing.price_history[-1] < listing.price_history[0]:
        base = min(base + 15, 100)
    return base


def _seller_score(listing: CarListing) -> float:
    return 100.0 if listing.seller_type == "private" else 40.0


def score_listings(listings: list) -> list:
    for listing in listings:
        ps = _price_score(listing, listings)
        ms = _mileage_score(listing)
        fs = _freshness_score(listing)
        ss = _seller_score(listing)

        listing.price_sub_score = round(ps, 1)
        listing.mileage_sub_score = round(ms, 1)
        listing.freshness_sub_score = round(fs, 1)
        listing.seller_sub_score = round(ss, 1)
        rb = _reliability_bonus(listing)
        listing.reliability_bonus = rb

        score = round(ps * 0.40 + ms * 0.30 + fs * 0.15 + ss * 0.15, 2)
        if listing.damage:
            score = max(0.0, score - 30.0)
        listing.deal_score = min(100.0, score + rb)

    return listings
