import logging
import re
from datetime import date
from urllib.parse import urlencode, urljoin

from dateutil import parser as dateparser

from models import CarListing
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://autoplius.lt"
SEARCH_PATH = "/skelbimai/naudoti-automobiliai"

# Numeric IDs from autoplius.lt make dropdown (select[name='make_id_list'])
AUTOPLIUS_MAKE_IDS: dict[str, int] = {
    "Alfa Romeo": 103, "Audi": 99, "BMW": 97, "Chevrolet": 94,
    "Citroen": 92, "Dacia": 110, "Fiat": 86, "Ford": 85,
    "Honda": 84, "Hyundai": 82, "Kia": 77, "Lexus": 72,
    "Mazda": 68, "Mercedes-Benz": 67, "Mini": 64, "Mitsubishi": 63,
    "Nissan": 62, "Opel": 60, "Peugeot": 59, "Renault": 54,
    "Seat": 49, "Skoda": 48, "Subaru": 46, "Suzuki": 45,
    "Toyota": 44, "Volkswagen": 43, "Volvo": 42,
}

# Lithuanian fuel names → normalized
FUEL_KEYWORDS = {
    "dyzelinas": "Diesel",
    "benzinas": "Petrol",
    "elektra": "Electric",
    "hibridas": "Hybrid",
    "dujos": "Gas",
}

# Lithuanian damage/accident keywords (case-insensitive scan of card/detail HTML)
DAMAGE_KEYWORDS = ["avarinis", "daužtas", "sudaužtas", "kėbulo žala", "avarija", "pažeistas", "žala"]
UNDAMAGED_KEYWORDS = ["nepažeistas", "nesudaužtas"]

# Known Lithuanian cities/towns — nominative AND genitive forms (lowercase).
# Genitive is used by autoplius in district labels: "Vilniaus r.", "Kauno m." etc.
LITHUANIAN_CITIES: set[str] = {
    # Nominative
    "vilnius", "kaunas", "klaipėda", "klaipeda", "šiauliai", "siauliai",
    "panevėžys", "panevezys", "alytus", "marijampolė", "marijampole",
    "mažeikiai", "mazeikiai", "jonava", "utena", "kėdainiai", "kedainiai",
    "telšiai", "telsiai", "tauragė", "taurage", "ukmergė", "ukmerge",
    "visaginas", "plungė", "plunge", "kretinga", "radviliškis", "radviliskis",
    "palanga", "druskininkai", "elektrėnai", "elektroenai", "gargždai", "gargzdai",
    "jurbarkas", "rokiškis", "rokiskis", "biržai", "birzai", "kuršėnai",
    "varėna", "varena", "zarasai", "skuodas", "šakiai", "sakiai",
    "vilkaviškis", "vilkaviskis", "prienai", "lazdijai", "šilutė", "silute",
    "šilalė", "silale", "raseiniai", "kelmė", "kelme", "joniškis", "joniskis",
    "pakruojis", "trakai", "molėtai", "moletai", "ignalina", "neringa",
    "švenčionys", "svenciones", "akmenė", "akmene", "rietavas",
    # Genitive forms (used in "Vilniaus r.", "Kauno m." district labels)
    "vilniaus", "kauno", "klaipėdos", "klaipedos", "šiaulių", "siauliu",
    "panevėžio", "panevezio", "alytaus", "marijampolės", "marijampoles",
    "mažeikių", "mazeikiu", "utenos", "kėdainių", "kedainiu",
    "telšių", "telsiu", "tauragės", "taurages", "ukmergės", "ukmerges",
    "plungės", "plunges", "kretingos", "radviliškio", "radviliskio",
    "palangos", "druskininkų", "elektrėnų", "elektrenu", "gargždų", "gargzdu",
    "jurbarko", "rokiškio", "rokiskio", "biržų", "birzų", "kuršėnų",
    "varėnos", "varenos", "zarasų", "skuodo", "šakių", "sakiu",
    "vilkaviškio", "vilkaviskio", "prienų", "lazdijų", "šilutės", "silutes",
    "šilalės", "silales", "raseinių", "kelmės", "kelmes", "joniškio", "joniskio",
    "pakruojo", "trakų", "traku", "molėtų", "moletu", "ignalinos", "neringos",
    "švenčionių", "svencioniu", "akmenės", "akmenes",
}


def _normalize_fuel(text: str) -> str:
    low = text.lower()
    for lt, en in FUEL_KEYWORDS.items():
        if lt in low:
            return en
    return text.capitalize()


class AutopliusScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "autoplius"

    def scrape(self) -> list:
        listings = []
        seen_urls: set = set()
        makes = self.filters.get("makes") or []
        # Build list of make_ids to iterate; empty list means no make filter (scrape all)
        make_jobs: list[tuple[str, int | None]] = []
        if makes:
            for m in makes:
                mid = AUTOPLIUS_MAKE_IDS.get(m)
                if mid:
                    make_jobs.append((m, mid))
                else:
                    logger.warning("No autoplius make_id for %r — skipping", m)
        else:
            make_jobs = [("all", None)]

        # --fresh sets use_html_cache=False; apply only to search pages, not detail pages
        search_cache = self.settings.get("use_html_cache", True)

        for make_name, make_id in make_jobs:
            base_params = self._build_params(make_id)
            logger.info("autoplius: scraping make=%s (id=%s)", make_name, make_id)
            for page in range(1, self.settings["max_pages"] + 1):
                params = dict(base_params)
                params["page"] = page
                url = f"{BASE_URL}{SEARCH_PATH}?{urlencode(params)}"
                logger.info("autoplius page %d: %s", page, url)

                soup = self._get_page(url, use_cache=search_cache)
                if soup is None:
                    break

                items = soup.select("a.announcement-item")
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

                logger.info("autoplius page %d: %d listings so far", page, len(listings))

        if self.settings.get("enrich_details", True):
            for listing in listings:
                try:
                    self._enrich_detail(listing)
                except Exception as e:
                    logger.debug("Detail enrich failed for %s: %s", listing.url, e)

        logger.info("autoplius total: %d listings", len(listings))
        return listings

    def _build_params(self, make_id: int | None = None) -> dict:
        p: dict = {}
        if make_id:
            p["make_id"] = make_id
        if self.filters.get("year_min"):
            p["year_from"] = self.filters["year_min"]
        if self.filters.get("year_max"):
            p["year_to"] = self.filters["year_max"]
        if self.filters.get("price_max"):
            p["price_to"] = self.filters["price_max"]
        return p

    def _parse_item(self, item) -> CarListing | None:
        url = item.get("href", "")
        if not url:
            return None
        if not url.startswith("http"):
            url = urljoin(BASE_URL, url)

        # ID from trailing number in slug
        m = re.search(r"-(\d{5,})\.html", url)
        listing_id = f"autoplius_{m.group(1)}" if m else f"autoplius_{hash(url)}"

        title_el = item.select_one("div.announcement-title")
        title = title_el.get_text(strip=True) if title_el else ""

        price_el = item.select_one("div.announcement-pricing-info strong")
        price = _parse_price(price_el.get_text() if price_el else "")

        img_el = item.select_one("img.lazy-img")
        images = []
        if img_el:
            src = img_el.get("data-src") or img_el.get("src") or ""
            if src and not src.startswith("data:"):
                images.append(src)

        # Parameter spans: [year, body_type, fuel, transmission, engine, mileage_km, city, ...]
        params = [s.get_text(strip=True) for s in item.select("div.announcement-parameters span")]

        year = _parse_year(params[0]) if params else 0
        fuel_type = ""
        mileage = 0
        city = ""
        for p in params[1:]:
            low = p.lower().strip()
            if not fuel_type and any(k in low for k in FUEL_KEYWORDS):
                fuel_type = _normalize_fuel(p)
            if not mileage and low.endswith("km"):
                mileage = _parse_int(p)
            if not city:
                matched = _match_city(p)
                if matched:
                    city = matched

        make, model = _split_make_model(title, year)

        # Detect damage from card HTML (no extra request needed)
        card_text = item.get_text().lower()
        damage, damage_info = _detect_damage(card_text)

        return CarListing(
            id=listing_id,
            source="autoplius",
            url=url,
            title=title,
            make=make,
            model=model,
            year=year,
            price=price,
            mileage=mileage,
            fuel_type=fuel_type,
            seller_type="dealer",  # refined in _enrich_detail
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

        # Seller type
        if "privatus asmuo" in full_text or "fizinis asmuo" in full_text:
            listing.seller_type = "private"
        elif "autosalonas" in full_text or "juridinis asmuo" in full_text:
            listing.seller_type = "dealer"

        # Listed date
        for sel in ["[class*='date']", "time[datetime]", "[class*='posted']"]:
            el = soup.select_one(sel)
            if el:
                dt_str = el.get("datetime") or el.get_text(strip=True)
                try:
                    listing.listed_date = dateparser.parse(dt_str, dayfirst=True).date()
                    break
                except Exception:
                    pass

        # Damage — re-check with full detail page text (more reliable than card)
        if not listing.damage:
            damage, damage_info = _detect_damage(full_text)
            if damage:
                listing.damage = damage
                listing.damage_info = damage_info

        # Techninė apžiūra (Technical Inspection / MOT)
        if not listing.technical_inspection:
            listing.technical_inspection = _extract_ta(soup)

        # City — from detail page if not found on card
        if not listing.city:
            listing.city = _extract_city(soup)


def _extract_ta(soup) -> str:
    """Extract Tech. apžiūra iki date from a detail page soup.
    autoplius structure: div.parameter-row > div.parameter-label + div.parameter-value
    """
    for row in soup.select("div.parameter-row"):
        label = row.select_one("div.parameter-label")
        value = row.select_one("div.parameter-value")
        if label and value:
            ltext = label.get_text(strip=True).lower()
            if "apžiūra" in ltext or "apziura" in ltext or ("tech" in ltext and "iki" in ltext):
                val = value.get_text(strip=True)
                if val:
                    return val

    # Fallback: regex on full page text
    m = re.search(
        r"tech\.?\s*apž[iū]ra\s*iki\s*(20\d{2}[-\.]\d{1,2}|n[eė]ra)",
        soup.get_text(), re.I,
    )
    if m:
        raw = m.group(1).strip()
        return "Nėra" if re.match(r"n[eė]ra", raw, re.I) else raw

    return ""


def _extract_city(soup) -> str:
    """Extract city from autoplius detail page location elements.
    Format is always 'City, Lietuva' — take the part before the comma.
    """
    for sel in [
        "span.seller-contact-location",
        "div.owner-location",
        "div.sticky-announcement-location",
    ]:
        el = soup.select_one(sel)
        if el:
            city = el.get_text(strip=True).split(",")[0].strip()
            if city:
                return city
    return ""


def _match_city(text: str) -> str:
    """Return the Lithuanian city name found at the start of text, or ''."""
    low = text.lower().strip()
    # Try exact match first, then prefix match for "Vilnius, Vilniaus r." style
    if low in LITHUANIAN_CITIES:
        return text.strip()
    for city in sorted(LITHUANIAN_CITIES, key=len, reverse=True):
        if low.startswith(city):
            # Return just the city portion (before comma or district suffix)
            return text.split(",")[0].strip()
    return ""


def _detect_damage(text_lower: str) -> tuple[bool, str]:
    """Return (is_damaged, damage_keyword_found) by scanning lowercased text."""
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
    # "7 500 €" → 7500.0
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
    # Remove year from parts if present
    parts = [p for p in parts if p != str(year)]
    make = parts[0] if parts else ""
    model = " ".join(parts[1:]) if len(parts) > 1 else ""
    return make, model
