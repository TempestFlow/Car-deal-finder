import logging
import os
import sys

from config import FILTERS, OUTPUT_FILE, SCRAPER_SETTINGS, TOP_N_RESULTS
from models import CarListing
from scrapers.autoplius import AutopliusScraper
from scrapers.autogidas import AutogidasScraper
from scorer import score_listings
from renderer import render_html
from storage import DATA_FILE, is_cache_fresh, load_listings, merge_price_history, save_listings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _select_diverse(listings: list, top_n: int, per_make: int = 5) -> list:
    """Return up to top_n listings ensuring every make gets at least per_make slots."""
    by_make: dict[str, list] = {}
    for l in listings:
        by_make.setdefault(l.make.lower(), []).append(l)

    selected_ids: set = set()
    result = []

    # Reserve per_make slots for each make (listings are already sorted by score desc)
    for make_listings in by_make.values():
        for l in make_listings[:per_make]:
            if l.id not in selected_ids:
                selected_ids.add(l.id)
                result.append(l)

    # Fill remaining slots from global top by score
    for l in listings:
        if len(result) >= top_n:
            break
        if l.id not in selected_ids:
            selected_ids.add(l.id)
            result.append(l)

    result.sort(key=lambda l: l.deal_score, reverse=True)
    return result


def main():
    use_cache = "--fresh" not in sys.argv and is_cache_fresh(DATA_FILE)

    if use_cache:
        logger.info("Loading cached listings from %s (use --fresh to re-scrape)", DATA_FILE)
        all_listings = load_listings(DATA_FILE)
        logger.info("Loaded %d listings from cache", len(all_listings))
    else:
        os.makedirs("output", exist_ok=True)
        scraper_settings = dict(SCRAPER_SETTINGS)
        if "--fresh" in sys.argv:
            scraper_settings["use_html_cache"] = False
            logger.info("--fresh: HTML page cache bypassed, fetching live pages")
        scrapers = [
            AutopliusScraper(FILTERS, scraper_settings),
            AutogidasScraper(FILTERS, scraper_settings),
        ]

        all_listings: list[CarListing] = []
        seen_urls: set = set()

        for scraper in scrapers:
            logger.info("Starting scraper: %s", scraper.source_name)
            try:
                results = scraper.scrape()
                for listing in results:
                    if listing.url not in seen_urls:
                        seen_urls.add(listing.url)
                        all_listings.append(listing)
            except Exception as e:
                logger.error("Scraper %s failed: %s", scraper.source_name, e)

        logger.info("Total unique listings collected: %d", len(all_listings))

        if all_listings:
            # Carry forward price history from previous run to detect drops
            old = load_listings(DATA_FILE)
            if old:
                all_listings = merge_price_history(old, all_listings)
            save_listings(all_listings, DATA_FILE)

    if not all_listings:
        logger.warning("No listings found. Check your filters and network connection.")
        return

    scored = score_listings(all_listings)
    scored.sort(key=lambda l: l.deal_score, reverse=True)
    top = _select_diverse(scored, TOP_N_RESULTS)

    score_range = f"{top[-1].deal_score:.1f} – {top[0].deal_score:.1f}" if top else "n/a"
    logger.info("Top %d deals (score range: %s)", len(top), score_range)

    render_html(top, OUTPUT_FILE)
    print(f"\nDone! Open {OUTPUT_FILE} in your browser.")
    print(f"Listings saved to {DATA_FILE} (run with --fresh to re-scrape)")


if __name__ == "__main__":
    main()
