from datetime import date, timedelta

from models import CarListing
from scorer import score_listings


def make_listing(**kwargs) -> CarListing:
    defaults = dict(
        id="test_1",
        source="autoplius",
        url="https://example.com/1",
        title="Toyota Corolla 2015",
        make="Toyota",
        model="Corolla",
        year=2015,
        price=8000.0,
        mileage=120000,
        fuel_type="Petrol",
        seller_type="private",
        listed_date=date.today() - timedelta(days=5),
        price_history=[8000.0],
        images=[],
    )
    defaults.update(kwargs)
    return CarListing(**defaults)


def test_private_vs_dealer():
    private = make_listing(id="p1", seller_type="private", price=8000)
    dealer = make_listing(id="d1", seller_type="dealer", price=8000)
    score_listings([private, dealer])
    assert private.deal_score > dealer.deal_score, "Private seller should score higher than dealer"
    print(f"PASS: private={private.deal_score:.1f} > dealer={dealer.deal_score:.1f}")


def test_below_market_price_scores_higher():
    cheap = make_listing(id="c1", price=5000, market_price=8000)
    expensive = make_listing(id="e1", price=12000, market_price=8000)
    score_listings([cheap, expensive])
    assert cheap.deal_score > expensive.deal_score, "Cheaper listing should score higher"
    print(f"PASS: cheap={cheap.deal_score:.1f} > expensive={expensive.deal_score:.1f}")


def test_low_mileage_scores_higher():
    low_km = make_listing(id="lk", mileage=50000, price=8000)
    high_km = make_listing(id="hk", mileage=250000, price=8000)
    score_listings([low_km, high_km])
    assert low_km.deal_score > high_km.deal_score, "Low mileage should score higher"
    print(f"PASS: low_km={low_km.deal_score:.1f} > high_km={high_km.deal_score:.1f}")


def test_fresh_listing_scores_higher():
    fresh = make_listing(id="f1", listed_date=date.today(), price=8000)
    old = make_listing(id="o1", listed_date=date.today() - timedelta(days=60), price=8000)
    score_listings([fresh, old])
    assert fresh.deal_score > old.deal_score, "Fresh listing should score higher"
    print(f"PASS: fresh={fresh.deal_score:.1f} > old={old.deal_score:.1f}")


def test_price_drop_bonus():
    with_drop = make_listing(id="pd1", price_history=[10000.0, 8000.0], price=8000, listed_date=date.today())
    no_drop = make_listing(id="pd2", price_history=[8000.0], price=8000, listed_date=date.today())
    score_listings([with_drop, no_drop])
    assert with_drop.deal_score >= no_drop.deal_score, "Price drop should give bonus"
    print(f"PASS: with_drop={with_drop.deal_score:.1f} >= no_drop={no_drop.deal_score:.1f}")


def test_no_comparable_listings():
    lone = make_listing(id="lone1", make="Rare", model="UniqueModel", year=2015, price=8000)
    score_listings([lone])
    assert 0 <= lone.deal_score <= 100, "Score must be in range even with no comparables"
    print(f"PASS: lone car score={lone.deal_score:.1f} (in 0-100)")


def test_very_new_car():
    new_car = make_listing(id="new1", year=date.today().year, mileage=5000, price=30000)
    score_listings([new_car])
    assert 0 <= new_car.deal_score <= 100
    print(f"PASS: new_car score={new_car.deal_score:.1f}")


def test_score_range():
    listings = [make_listing(id=f"t{i}", price=p) for i, p in enumerate([3000, 6000, 9000, 12000, 15000])]
    score_listings(listings)
    for l in listings:
        assert 0 <= l.deal_score <= 100, f"Score out of range: {l.deal_score}"
    print(f"PASS: all scores in [0,100]: {[round(l.deal_score,1) for l in listings]}")


if __name__ == "__main__":
    tests = [
        test_private_vs_dealer,
        test_below_market_price_scores_higher,
        test_low_mileage_scores_higher,
        test_fresh_listing_scores_higher,
        test_price_drop_bonus,
        test_no_comparable_listings,
        test_very_new_car,
        test_score_range,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {t.__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{passed+failed} tests passed")
