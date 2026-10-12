import re
from datetime import date
from statistics import median

from market import base_model
from models import CarListing

NEUTRAL_SCORE = 50.0
MIN_FALLBACK_SAMPLES = 3
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


def _price_score(listing: CarListing, all_listings: list) -> float | None:
    """50% below the reference price = 100 pts, at or above it = 0. None = no reference price."""
    if not listing.price:
        return None

    # Preferred: market price from the wider comparable sample (market.py)
    if listing.market_price:
        return _clamp((listing.market_price - listing.price) / listing.market_price * 200, 0, 100)

    # Fallback: compare within the scraped listings (same base model, ±2 years)
    make, model = listing.make.lower(), base_model(listing)
    prices = [
        l.price for l in all_listings
        if l.price > 0 and l.id != listing.id and l.make.lower() == make
        and base_model(l) == model and abs(l.year - listing.year) <= 2
    ]
    if len(prices) < MIN_FALLBACK_SAMPLES:
        return None
    med = median(prices)
    return _clamp((med - listing.price) / med * 200, 0, 100)


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


def _parse_ta_months_left(ta_str: str) -> int:
    """Parse TA string → months remaining.
    Returns -1 (unknown), 0 (no TA / Nėra), negative (expired), or positive months left.
    """
    if not ta_str:
        return -1
    if re.match(r"n[eė]ra", ta_str, re.I) or ta_str.strip() in ("-", "–"):
        return 0

    m = re.search(r"(20\d{2})[-\./ ](\d{1,2})", ta_str)
    if not m:
        return -1

    ta_year, ta_month = int(m.group(1)), int(m.group(2))
    today = date.today()
    months_left = (ta_year - today.year) * 12 + (ta_month - today.month)
    # Expired = negative; still valid = positive
    return months_left if months_left >= 0 else months_left  # keep negative for expired


def _ta_bonus(listing: CarListing) -> float:
    """Small bonus/penalty based on Techninė apžiūra validity."""
    ml = listing.ta_months_left
    if ml == -1:
        return 0.0   # unknown — neutral
    if ml <= 0:
        return -10.0 if ml == 0 else -7.0  # no TA or expired
    if ml <= 3:
        return 0.0   # expiring very soon — neutral
    if ml <= 6:
        return 3.0   # a few months left — mild plus
    if ml <= 12:
        return 5.0   # comfortable
    return 8.0       # more than a year left — great


def score_listings(listings: list) -> list:
    price_scores = {l.id: _price_score(l, listings) for l in listings}
    # No reference price → treat as a typical listing (median of known scores), not as a bargain.
    # A fixed 50 would equal "25% below market", far better than most listings score.
    known = [s for s in price_scores.values() if s is not None]
    typical = median(known) if known else NEUTRAL_SCORE

    for listing in listings:
        ps = price_scores[listing.id]
        if ps is None:
            ps = typical
        ms = _mileage_score(listing)
        fs = _freshness_score(listing)
        ss = _seller_score(listing)

        listing.price_sub_score = round(ps, 1)
        listing.mileage_sub_score = round(ms, 1)
        listing.freshness_sub_score = round(fs, 1)
        listing.seller_sub_score = round(ss, 1)

        rb = _reliability_bonus(listing)
        listing.reliability_bonus = rb

        # TA: compute months left then bonus
        listing.ta_months_left = _parse_ta_months_left(listing.technical_inspection)
        tb = _ta_bonus(listing)
        listing.ta_bonus = round(tb, 1)

        score = round(ps * 0.40 + ms * 0.30 + fs * 0.15 + ss * 0.15, 2)
        if listing.damage:
            score = max(0.0, score - 30.0)
        listing.deal_score = min(100.0, score + rb + tb)

    return listings
