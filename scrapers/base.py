import hashlib
import logging
import os
import re
import time
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup

from models import CarListing

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "lt,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BROWSER_PROFILE_DIR = os.path.join("cache", "browser_profile")
CHALLENGE_MARKERS = ("Tikriname jūsų naršyklę", "Just a moment", "challenge-platform")
CHALLENGE_TIMEOUT = 60  # seconds to wait for a Cloudflare check to clear
MARKET_CACHE_HOURS = 72  # market-sample search pages change slowly; reuse them even with --fresh
MARKET_MIN_PRICE = 300   # below this a card is a placeholder price or parts car, not a market price


def parse_ta(value: str) -> tuple[int, int] | None:
    """'2028-03' / '2028-03-15' / '2028.03' → (2028, 3). 'Nėra', '' or garbage → None."""
    if not value:
        return None
    m = re.search(r"(20\d{2})(?:\s*[-./]\s*(\d{1,2}))?", value)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2) or 1)


def _is_challenge(html: str) -> bool:
    return any(marker in html for marker in CHALLENGE_MARKERS)


class BaseScraper(ABC):
    # Sites behind a Cloudflare JS challenge set this; pages are then fetched with a real browser
    needs_browser = False
    item_selector = ""   # CSS selector of one listing card on a search page
    page_size = 0        # cards per full search page; 0 = unknown (no short-page stop)

    def __init__(self, filters: dict, settings: dict, targets: list[tuple[str, str]]):
        self.filters = filters
        self.settings = settings
        self.targets = targets
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._cache_dir = os.path.join("cache", self.source_name)
        os.makedirs(self._cache_dir, exist_ok=True)
        self._pw = None
        self._browser = None
        self._page = None

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    def scrape(self) -> list:
        """Candidates: site search with all filters in the URL, then detail pages for TA."""
        # --fresh sets use_html_cache=False; apply only to search pages, not detail pages
        search_cache = self.settings.get("use_html_cache", True)
        listings, seen = [], set()

        for target in self.targets:
            params = self._build_params(target)
            if params is None:
                continue
            logger.info("%s: scraping %s %s", self.source_name, *target)
            found = self._search(target, params, lambda l, t=target: self._apply_filters(l, t),
                                 self.settings["max_pages"], use_cache=search_cache)
            for listing in found:
                if listing.url not in seen:
                    seen.add(listing.url)
                    listings.append(listing)

        if self.settings.get("enrich_details", True):
            for listing in listings:
                try:
                    self._enrich_detail(listing)
                except Exception as e:
                    logger.debug("Detail enrich failed for %s: %s", listing.url, e)

        listings = self._final_filter(listings)
        logger.info("%s total: %d listings", self.source_name, len(listings))
        return listings

    @abstractmethod
    def _build_params(self, target: tuple[str, str]) -> dict | None:
        """Search params for candidates; None = this site can't search the target."""

    @abstractmethod
    def _enrich_detail(self, listing: CarListing):
        pass

    def close(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._pw = self._browser = self._page = None

    def scrape_market(self, windows: dict) -> list:
        """Comparable listings for market prices: same model and year window, all of Lithuania,
        no price/city/TA filter. Search cards only (no detail pages), cached for MARKET_CACHE_HOURS."""
        samples = []
        for target, (y0, y1) in windows.items():
            def keep(l, target=target, y0=y0, y1=y1):
                return (self._matches_target(l, target) and l.price >= MARKET_MIN_PRICE
                        and not l.damage and y0 <= l.year <= y1)

            logger.info("%s: market sample %s %s %d–%d", self.source_name, *target, y0, y1)
            params = self._market_params(target, y0, y1)
            if params is None:
                continue
            samples += self._search(target, params, keep, self.settings.get("market_pages", 3),
                                    max_age_hours=MARKET_CACHE_HOURS)
        logger.info("%s: %d market samples", self.source_name, len(samples))
        return samples

    @abstractmethod
    def _market_params(self, target: tuple[str, str], year_from: int, year_to: int) -> dict | None:
        pass

    @abstractmethod
    def _search_url(self, target: tuple[str, str], params: dict, page: int) -> str:
        pass

    @abstractmethod
    def _parse_item(self, item) -> CarListing | None:
        pass

    def _search(self, target, params: dict, keep, max_pages: int,
                use_cache: bool = True, max_age_hours: float | None = None) -> list:
        """Walk search result pages, returning parsed cards for which keep(listing) is True.
        Stops at the first page with no kept cards (end of results / site padding) or a short page."""
        found, seen = [], set()
        for page in range(1, max_pages + 1):
            url = self._search_url(target, params, page)
            logger.info("%s page %d: %s", self.source_name, page, url)
            soup = self._get_page(url, use_cache=use_cache, max_age_hours=max_age_hours)
            if soup is None:
                break

            items = soup.select(self.item_selector)
            kept = 0
            for item in items:
                try:
                    listing = self._parse_item(item)
                except Exception as e:
                    logger.error("Parse error: %s", e)
                    continue
                if not listing or listing.url in seen:
                    continue
                seen.add(listing.url)
                if keep(listing):
                    found.append(listing)
                    kept += 1

            logger.info("%s page %d: %d matching cards", self.source_name, page, kept)
            if not kept or (self.page_size and len(items) < self.page_size):
                break
        return found

    def _get_page(self, url: str, use_cache: bool = True, max_age_hours: float | None = None) -> BeautifulSoup | None:
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(self._cache_dir, f"{cache_key}.html")

        if use_cache and os.path.exists(cache_path) and (
            max_age_hours is None or time.time() - os.path.getmtime(cache_path) < max_age_hours * 3600
        ):
            logger.debug("Cache hit: %s", url)
            with open(cache_path, "r", encoding="utf-8") as f:
                return BeautifulSoup(f.read(), "lxml")

        time.sleep(self.settings.get("request_delay", 1.5))
        html = self._fetch_browser(url) if self.needs_browser else self._fetch_requests(url)
        if html is None:
            return None

        if use_cache:
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(html)

        return BeautifulSoup(html, "lxml")

    def _fetch_requests(self, url: str) -> str | None:
        try:
            resp = self.session.get(url, timeout=self.settings.get("timeout", 10))
        except requests.RequestException as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return None
        if resp.status_code == 403 and _is_challenge(resp.text):
            logger.info("Cloudflare challenge on %s — switching %s to browser mode", url, self.source_name)
            self.needs_browser = True
            return self._fetch_browser(url)
        if not resp.ok:
            logger.error("Failed to fetch %s: HTTP %s", url, resp.status_code)
            return None
        return resp.text

    def _fetch_browser(self, url: str) -> str | None:
        """Fetch with a visible Edge/Chromium window (Cloudflare blocks headless and plain requests).
        A persistent profile keeps the clearance cookie, so the check is usually passed only once."""
        try:
            if self._page is None:
                self._start_browser()
            self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
            deadline = time.time() + CHALLENGE_TIMEOUT
            html = self._page.content()
            while _is_challenge(html) and time.time() < deadline:
                time.sleep(1)
                html = self._page.content()
            if _is_challenge(html):
                logger.error("Cloudflare challenge not cleared for %s", url)
                return None
            return html
        except Exception as e:
            logger.error("Browser fetch failed for %s: %s", url, e)
            return None

    def _start_browser(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        opts = dict(
            headless=False,
            locale="lt-LT",
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            # Installed Edge — no `playwright install` needed on Windows
            self._browser = self._pw.chromium.launch_persistent_context(BROWSER_PROFILE_DIR, channel="msedge", **opts)
        except Exception:
            self._browser = self._pw.chromium.launch_persistent_context(BROWSER_PROFILE_DIR, **opts)
        self._page = self._browser.pages[0] if self._browser.pages else self._browser.new_page()

    def _matches_target(self, listing: CarListing, target: tuple[str, str]) -> bool:
        make, model = target
        words = listing.model.lower().split()
        if listing.make.lower() != make.lower() or not words or words[0] != model.lower():
            return False
        # Corolla Verso is a different car (minivan) that some sites file under Corolla
        return "verso" not in words

    def _apply_filters(self, listing: CarListing, target: tuple[str, str]) -> bool:
        """Card-level check (before any detail request). The site search already applies these;
        this guards against promoted/irrelevant cards slipping into the results."""
        year_min = self.filters.get("year_min")
        year_max = self.filters.get("year_max")
        price_min = self.filters.get("price_min")
        price_max = self.filters.get("price_max")
        city = self.filters.get("city")
        fuel_types = self.filters.get("fuel_types") or []

        if not self._matches_target(listing, target):
            return False
        if year_min and listing.year and listing.year < year_min:
            return False
        if year_max and listing.year and listing.year > year_max:
            return False
        if not listing.price:
            return False
        if price_min and listing.price < price_min:
            return False
        if price_max and listing.price > price_max:
            return False
        if city and listing.city and listing.city.lower() != city.lower():
            return False
        if fuel_types and listing.fuel_type:
            if not any(listing.fuel_type.lower() == ft.lower() for ft in fuel_types):
                return False
        return True

    def _passes_ta(self, listing: CarListing) -> bool:
        """TA must be valid at least until filters['ta_min']. Unknown or missing TA fails."""
        ta_min = parse_ta(self.filters.get("ta_min") or "")
        if ta_min is None:
            return True
        ta = parse_ta(listing.technical_inspection)
        return ta is not None and ta >= ta_min

    def _final_filter(self, listings: list) -> list:
        """Post-detail filter: TA date and city (detail page city is authoritative)."""
        city = (self.filters.get("city") or "").lower()
        kept = []
        for l in listings:
            if not self._passes_ta(l):
                logger.info("%s: drop (TA %r) %s", self.source_name, l.technical_inspection or "unknown", l.url)
            elif city and l.city and l.city.lower() != city:
                logger.info("%s: drop (city %r) %s", self.source_name, l.city, l.url)
            else:
                kept.append(l)
        logger.info("%s: %d/%d listings pass TA ≥ %s", self.source_name, len(kept), len(listings),
                    self.filters.get("ta_min"))
        return kept
