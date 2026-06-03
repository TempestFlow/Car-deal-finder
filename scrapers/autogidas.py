import logging
import re
from datetime import date
from urllib.parse import urlencode, urljoin

from dateutil import parser as dateparser

from models import CarListing
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://autogidas.lt"
SEARCH_PATH = "/skelbimai/automobiliai/"

FUEL_KEYWORDS = {
    "dyzelinas": "Diesel",
    "benzinas": "Petrol",
    "elektra": "Electric",
    "hibridas": "Hybrid",
    "dujos": "Gas",
}

DAMAGE_KEYWORDS = ["avarinis", "daužtas", "sudaužtas", "kėbulo žala", "avarija", "pažeistas", "žala"]
UNDAMAGED_KEYWORDS = ["nepažeistas", "nesudaužtas"]


def _normalize_fuel(text: str) -> str:
    low = text.lower()
    for lt, en in FUEL_KEYWORDS.items():
        if lt in low:
            return en
    return text.capitalize()


class AutogidasScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "autogidas"

    def scrape(self) -> list:
        listings = []
        seen_urls: set = set()
        makes = self.filters.get("makes") or [""]  # empty string = no make filter

        for make in makes:
            # autogidas filters by make via URL path: /skelbimai/automobiliai/toyota/
            make_path = f"{SEARCH_PATH}{make.lower()}/" if make else SEARCH_PATH
            base_params = self._build_params()
            logger.info("autogidas: scraping make=%r path=%s", make or "all", make_path)

            for page in range(1, self.settings["max_pages"] + 1):
                params = dict(base_params)
                if page > 1:
                    params["page"] = page
                qs = f"?{urlencode(params)}" if params else ""
                url = f"{BASE_URL}{make_path}{qs}"
                logger.info("autogidas page %d: %s", page, url)

                soup = self._get_page(url)
                if soup is None:
                    break

                items = soup.select("div.article-item")
                if not items:
                    logger.info("No listings on page %d, stopping", page)
                    break

                for item in items:
                    try:
                        listing = self._parse_item(item)
                        if listing and listing.url not in seen_urls and self._apply_filters(listing):
                            seen_urls.add(listing.url)
                            listings.append(listing)
                    except Exception as e:
                        logger.error("Parse error: %s", e)

                logger.info("autogidas page %d: %d listings so far", page, len(listings))

        if self.settings.get("enrich_details", True):
            for listing in listings:
                try:
                    self._enrich_detail(listing)
                except Exception as e:
                    logger.debug("Detail enrich failed for %s: %s", listing.url, e)

        logger.info("autogidas total: %d listings", len(listings))
        return listings

    def _build_params(self) -> dict:
        p: dict = {}
        if self.filters.get("price_max"):
            p["price_to"] = self.filters["price_max"]
        if self.filters.get("year_min"):
            p["year_from"] = self.filters["year_min"]
        if self.filters.get("year_max"):
            p["year_to"] = self.filters["year_max"]
        return p

    def _parse_item(self, item) -> CarListing | None:
        link_el = item.select_one("a.item-link")
        if not link_el:
            return None
        href = link_el.get("href", "")
        if not href:
            return None
        url = urljoin(BASE_URL, href)

        # Skip ad/tracker URLs that aren't real listings
        if not url.startswith(f"{BASE_URL}/skelbimas/"):
            return None

        m = re.search(r"-(\d{7,})\.html", url)
        listing_id = f"autogidas_{m.group(1)}" if m else f"autogidas_{hash(url)}"

        title = link_el.get("title") or link_el.get_text(strip=True)

        price_el = item.select_one("div.item-price")
        price = _parse_price(price_el.get_text() if price_el else "")

        img_el = item.select_one("img.js-image")
        images = []
        if img_el:
            src = img_el.get("src") or img_el.get("data-src") or ""
            if src and not src.startswith("data:") and "svg" not in src:
                images.append(src)

        # Parameters: span.parameter-value → [year "2010 m.", fuel, mileage "237 000 km", ...]
        param_spans = [s.get_text(strip=True) for s in item.select("span.parameter-value")]

        year = 0
        fuel_type = ""
        mileage = 0
        for p in param_spans:
            low = p.lower()
            if not year and re.match(r"\d{4}", p):
                year = _parse_year(p)
            elif not fuel_type and any(k in low for k in FUEL_KEYWORDS):
                fuel_type = _normalize_fuel(p)
            elif not mileage and "km" in low:
                mileage = _parse_int(p)

        make, model = _split_make_model(title, year)

        card_text = item.get_text().lower()
        damage, damage_info = _detect_damage(card_text)

        return CarListing(
            id=listing_id,
            source="autogidas",
            url=url,
            title=title,
            make=make,
            model=model,
            year=year,
            price=price,
            mileage=mileage,
            fuel_type=fuel_type,
            seller_type="dealer",
            listed_date=date.today(),
            price_history=[price] if price else [],
            images=images,
            damage=damage,
            damage_info=damage_info,
        )

    def _enrich_detail(self, listing: CarListing):
        soup = self._get_page(listing.url)
        if soup is None:
            return

        full_text = soup.get_text().lower()
        if "privatus" in full_text or "fizinis asmuo" in full_text:
            listing.seller_type = "private"
        elif "autosalonas" in full_text or "juridinis" in full_text:
            listing.seller_type = "dealer"

        for sel in ["time[datetime]", "[class*='date']"]:
            el = soup.select_one(sel)
            if el:
                dt_str = el.get("datetime") or el.get_text(strip=True)
                try:
                    listing.listed_date = dateparser.parse(dt_str, dayfirst=True).date()
                    break
                except Exception:
                    pass

        if not listing.damage:
            damage, damage_info = _detect_damage(full_text)
            if damage:
                listing.damage = damage
                listing.damage_info = damage_info


def _detect_damage(text_lower: str) -> tuple[bool, str]:
    if any(k in text_lower for k in UNDAMAGED_KEYWORDS):
        return False, ""
    for kw in DAMAGE_KEYWORDS:
        if kw in text_lower:
            return True, kw
    return False, ""


def _parse_year(text: str) -> int:
    m = re.match(r"(\d{4})", text.strip())
    return int(m.group(1)) if m else 0


def _parse_price(text: str) -> float:
    digits = re.sub(r"[^\d]", "", text.replace(",", ""))
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return 0.0


def _parse_int(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0


def _split_make_model(title: str, year: int) -> tuple:
    parts = title.strip().split()
    parts = [p for p in parts if p != str(year)]
    make = parts[0] if parts else ""
    model = " ".join(parts[1:]) if len(parts) > 1 else ""
    return make, model
