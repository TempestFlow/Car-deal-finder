from datetime import date

from market import apply_market, estimate, year_windows
from models import CarListing
from scorer import _price_score, score_listings

_n = 0


def car(year=2009, price=3000.0, model="Prius", make="Toyota", fuel="Hybrid", url=None) -> CarListing:
    global _n
    _n += 1
    return CarListing(
        id=f"t{_n}", source="autoplius", url=url or f"https://example.com/{_n}", title=f"{make} {model}",
        make=make, model=model, year=year, price=price, mileage=200000, fuel_type=fuel,
        seller_type="private", listed_date=date.today(),
    )


def test_median_of_comparables():
    samples = [car(2009, p) for p in (3000, 3500, 4000, 4500, 5000)]
    assert estimate(car(2009, 2500), samples) == (4000.0, 5)


def test_year_window_widens_to_two():
    # Only 3 within ±1, 5 within ±2 → widened
    samples = [car(2009, 3000), car(2010, 3200), car(2008, 2800), car(2011, 3600), car(2007, 2400)]
    price, n = estimate(car(2009), samples)
    assert n == 5 and price == 3000.0


def test_too_few_comparables_unknown():
    samples = [car(2009, 3000), car(2009, 3200), car(2015, 9000)]
    assert estimate(car(2009), samples) == (0.0, 2)


def test_same_fuel_preferred_when_enough():
    petrol = [car(2009, 2000, model="Octavia", make="Skoda", fuel="Petrol") for _ in range(5)]
    diesel = [car(2009, 4000, model="Octavia", make="Skoda", fuel="Diesel") for _ in range(5)]
    price, n = estimate(car(2009, model="Octavia", make="Skoda", fuel="Diesel"), petrol + diesel)
    assert (price, n) == (4000.0, 5)


def test_base_model_and_self_excluded():
    me = car(2009, 1000, model="Civic", make="Honda", fuel="Petrol", url="https://example.com/me")
    samples = [car(2009, 3000, model=m, make="Honda", fuel="Petrol")
               for m in ("Civic VII", "Civic i-VTEC", "Civic", "Civic", "Civic")]
    samples.append(me)  # the candidate itself shows up in the market sample
    assert estimate(me, samples) == (3000.0, 5)


def test_other_models_ignored():
    samples = [car(2009, 9000, model="Auris") for _ in range(10)]
    assert estimate(car(2009), samples) == (0.0, 0)


def test_apply_market_and_price_score():
    listing = car(2009, 3000)
    samples = [car(2009, 4000) for _ in range(5)]
    apply_market([listing], samples)
    assert listing.market_price == 4000 and listing.market_samples == 5
    assert listing.market_diff_pct == -25.0
    assert _price_score(listing, [listing]) == 50.0  # 25% below market → 50 pts

    pricey = car(2009, 5000)
    apply_market([pricey], samples)
    assert pricey.market_diff_pct == 25.0
    assert _price_score(pricey, [pricey]) == 0.0


def test_unknown_market_gets_typical_score():
    known = [car(2009, p) for p in (4000, 3000, 2000)]  # 0%, 25%, 50% below market
    for l in known:
        l.market_price = 4000
    unknown = car(1995, 3500, model="Civic", make="Honda")  # no market price, no comparables
    score_listings(known + [unknown])
    assert unknown.price_sub_score == 50.0  # median of 0 / 50 / 100, not a bargain bonus


def test_year_windows():
    listings = [car(2006), car(2010), car(2012, model="Civic", make="Honda")]
    w = year_windows(listings, [("Toyota", "Prius"), ("Honda", "Civic"), ("Skoda", "Octavia")])
    assert w == {("Toyota", "Prius"): (2004, 2012), ("Honda", "Civic"): (2010, 2014)}


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            print(f"FAIL: {t.__name__} {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
