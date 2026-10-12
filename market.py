"""Market value: median asking price of comparable listings (same model, similar year)."""
import logging
from statistics import median

from models import CarListing

logger = logging.getLogger(__name__)

MIN_SAMPLES = 5        # fewer comparables than this → market price unknown
YEAR_STEPS = (1, 2)    # try ±1 year first, widen to ±2 if too few comparables


def base_model(listing: CarListing) -> str:
    """'Civic VII' / 'Civic i-VTEC' → 'civic'."""
    words = listing.model.lower().split()
    return words[0] if words else ""


def _key(listing: CarListing) -> tuple[str, str]:
    return listing.make.lower(), base_model(listing)


def year_windows(listings: list, targets: list) -> dict:
    """{target: (year_from, year_to)}: the candidates' years ± the widest comparable step.
    Targets without candidates get no window (nothing to price)."""
    reach = max(YEAR_STEPS)
    windows = {}
    for target in targets:
        key = (target[0].lower(), target[1].lower())
        years = [l.year for l in listings if l.year and _key(l) == key]
        if years:
            windows[target] = (min(years) - reach, max(years) + reach)
    return windows


def estimate(listing: CarListing, samples: list) -> tuple[float, int]:
    """(median price, n) of comparables, or (0, n) when there are fewer than MIN_SAMPLES.
    Prefers same-fuel comparables when there are enough of them."""
    if not listing.year:
        return 0.0, 0
    key = _key(listing)
    same_model = [s for s in samples if _key(s) == key and s.url != listing.url and s.year and s.price > 0]

    comparables = []
    for step in YEAR_STEPS:
        comparables = [s for s in same_model if abs(s.year - listing.year) <= step]
        if len(comparables) >= MIN_SAMPLES:
            break
    if len(comparables) < MIN_SAMPLES:
        return 0.0, len(comparables)

    if listing.fuel_type:
        same_fuel = [s for s in comparables if s.fuel_type == listing.fuel_type]
        if len(same_fuel) >= MIN_SAMPLES:
            comparables = same_fuel

    return float(median(s.price for s in comparables)), len(comparables)


def apply_market(listings: list, samples: list) -> None:
    # The same car is often listed on both sites — count each URL once
    unique = list({s.url: s for s in samples}.values())
    known = 0
    for listing in listings:
        price, n = estimate(listing, unique)
        listing.market_price = round(price)
        listing.market_samples = n
        listing.market_diff_pct = round((listing.price - price) / price * 100, 1) if price and listing.price else 0.0
        known += bool(price)
    logger.info("Market price known for %d/%d listings (%d samples)", known, len(listings), len(unique))
