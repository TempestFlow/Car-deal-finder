from datetime import date

from models import CarListing
from scrapers.autogidas import AutogidasScraper
from scrapers.base import parse_ta

FILTERS = {"price_min": 1500, "price_max": 4500, "city": "Vilnius", "ta_min": "2028-01"}
TARGET = ("Toyota", "Corolla")


def make_scraper() -> AutogidasScraper:
    return AutogidasScraper(FILTERS, {"max_pages": 1}, [TARGET])


def make_listing(**kwargs) -> CarListing:
    defaults = dict(
        id="t1", source="autogidas", url="https://example.com/1", title="Toyota Corolla",
        make="Toyota", model="Corolla", year=2010, price=3000.0, mileage=200000,
        fuel_type="Petrol", seller_type="private", listed_date=date.today(), city="Vilnius",
    )
    defaults.update(kwargs)
    return CarListing(**defaults)


def test_parse_ta():
    assert parse_ta("2028-03") == (2028, 3)
    assert parse_ta("2028-03-15") == (2028, 3)
    assert parse_ta("2028") == (2028, 1)
    assert parse_ta("Nėra") is None
    assert parse_ta("") is None


def test_ta_threshold():
    s = make_scraper()
    assert not s._passes_ta(make_listing(technical_inspection="2027-12"))
    assert s._passes_ta(make_listing(technical_inspection="2028-01"))
    assert s._passes_ta(make_listing(technical_inspection="2029-06"))
    assert not s._passes_ta(make_listing(technical_inspection="Nėra"))
    assert not s._passes_ta(make_listing(technical_inspection=""))


def test_card_filters():
    s = make_scraper()
    assert s._apply_filters(make_listing(), TARGET)
    assert not s._apply_filters(make_listing(price=1400), TARGET)
    assert not s._apply_filters(make_listing(price=4600), TARGET)
    assert not s._apply_filters(make_listing(price=0), TARGET)
    assert not s._apply_filters(make_listing(city="Kaunas"), TARGET)
    assert not s._apply_filters(make_listing(model="Corolla Verso"), TARGET)
    assert not s._apply_filters(make_listing(model="Auris"), TARGET)
    assert s._apply_filters(make_listing(model="Corolla 1.6"), TARGET)
