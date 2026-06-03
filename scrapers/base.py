import hashlib
import logging
import os
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


class BaseScraper(ABC):
    def __init__(self, filters: dict, settings: dict):
        self.filters = filters
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._cache_dir = os.path.join("cache", self.source_name)
        os.makedirs(self._cache_dir, exist_ok=True)

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    def scrape(self) -> list:
        pass

    def _get_page(self, url: str, use_cache: bool = True) -> BeautifulSoup | None:
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(self._cache_dir, f"{cache_key}.html")

        if use_cache and os.path.exists(cache_path):
            logger.debug("Cache hit: %s", url)
            with open(cache_path, "r", encoding="utf-8") as f:
                return BeautifulSoup(f.read(), "lxml")

        time.sleep(self.settings.get("request_delay", 1.5))
        try:
            resp = self.session.get(url, timeout=self.settings.get("timeout", 10))
            resp.raise_for_status()
            html = resp.text
        except requests.RequestException as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return None

        if use_cache:
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(html)

        return BeautifulSoup(html, "lxml")

    def _apply_filters(self, listing: CarListing) -> bool:
        """Return True if the listing passes all config filters."""
        year_min = self.filters.get("year_min")
        year_max = self.filters.get("year_max")
        price_max = self.filters.get("price_max")
        fuel_types = self.filters.get("fuel_types") or []

        if year_min and listing.year and listing.year < year_min:
            return False
        if year_max and listing.year and listing.year > year_max:
            return False
        if price_max and listing.price > 0 and listing.price > price_max:
            return False
        if fuel_types and listing.fuel_type:
            if not any(listing.fuel_type.lower() == ft.lower() for ft in fuel_types):
                return False
        return True
