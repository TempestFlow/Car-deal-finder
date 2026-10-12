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
    # When filtered results run out, autogidas pads pages with unfiltered "similar" listings;
    # BaseScraper._search stops at the first page where no card passes the filter
    item_selector = "div.article-item"

    @property
    def source_name(self) -> str:
        return "autogidas"

    def _search_url(self, target: tuple[str, str], params: dict, page: int) -> str:
        # autogidas filters make/model via URL path: /skelbimai/automobiliai/toyota/corolla/
        make, model = target
        params = dict(params, page=page) if page > 1 else params
        return f"{BASE_URL}{SEARCH_PATH}{_slug(make)}/{_slug(model)}/?{urlencode(params)}"

    def _market_params(self, target: tuple[str, str], year_from: int, year_to: int) -> dict:
        return {"f_41": year_from, "f_42": year_to}

    def _build_params(self, target: tuple[str, str]) -> dict:
        # autogidas search form field names (select[name=f_*] on the search page)
        p: dict = {}
        if self.filters.get("price_min"):
            p["f_215"] = self.filters["price_min"]
        if self.filters.get("price_max"):
            p["f_216"] = self.filters["price_max"]
        if self.filters.get("year_min"):
            p["f_41"] = self.filters["year_min"]
        if self.filters.get("year_max"):
            p["f_42"] = self.filters["year_max"]
        if self.filters.get("city"):
            p["f_13"] = self.filters["city"]
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

        # Parameters: span.parameter-value → [year "2010 m.", fuel, mileage "237 000 km", ..., "Vilnius, Lietuva"]
        param_spans = [s.get_text(strip=True) for s in item.select("span.parameter-value")]

        year = 0
        fuel_type = ""
        mileage = 0
        city = ""
        for p in param_spans:
            low = p.lower()
            if not city and low.endswith("lietuva"):
                city = p.split(",")[0].strip()
            elif not year and re.match(r"\d{4}", p):
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
            city=city,
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

        if not listing.technical_inspection:
            listing.technical_inspection = _extract_ta(soup)


def _extract_ta(soup) -> str:
    """autogidas detail page: div.list-striped-item-title "TA iki" + div.list-striped-item-value "2027-05"."""
    for title in soup.select("div.list-striped-item-title"):
        if title.get_text(strip=True).lower().startswith("ta iki"):
            value = title.find_next_sibling("div", class_="list-striped-item-value")
            if value:
                return value.get_text(strip=True)
    return ""


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


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
