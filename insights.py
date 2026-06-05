from datetime import date
from statistics import median, mean


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def compute_insights(listings: list) -> dict:
    today = date.today()
    priced = [l for l in listings if l.price > 0]

    # ── price_by_make ────────────────────────────────────────────────────────
    make_prices: dict[str, list[float]] = {}
    for l in priced:
        make_prices.setdefault(l.make, []).append(l.price)

    price_by_make = []
    for make, prices in make_prices.items():
        price_by_make.append({
            "make": make,
            "median_price": round(median(prices)),
            "avg_price": round(mean(prices)),
            "count": len(prices),
            "min_price": round(min(prices)),
            "max_price": round(max(prices)),
        })
    price_by_make.sort(key=lambda x: x["median_price"], reverse=True)

    # ── dealer_markup ────────────────────────────────────────────────────────
    dealer_prices: dict[str, list[float]] = {}
    private_prices: dict[str, list[float]] = {}
    for l in priced:
        if l.seller_type == "dealer":
            dealer_prices.setdefault(l.make, []).append(l.price)
        else:
            private_prices.setdefault(l.make, []).append(l.price)

    dealer_markup = []
    for make in dealer_prices:
        d_list = dealer_prices[make]
        p_list = private_prices.get(make, [])
        if len(d_list) < 2 or len(p_list) < 2:
            continue
        d_med = median(d_list)
        p_med = median(p_list)
        if p_med <= 0:
            continue
        markup_pct = round((d_med / p_med - 1) * 100, 1)
        dealer_markup.append({
            "make": make,
            "dealer_median": round(d_med),
            "private_median": round(p_med),
            "markup_pct": markup_pct,
            "dealer_count": len(d_list),
            "private_count": len(p_list),
        })
    dealer_markup.sort(key=lambda x: x["markup_pct"], reverse=True)

    # ── price_drop_freq ──────────────────────────────────────────────────────
    # Only listings with 2+ price_history entries can show a drop
    tracked: dict[tuple, list] = {}
    for l in listings:
        if len(l.price_history) >= 2:
            key = (l.make, l.model)
            tracked.setdefault(key, []).append(l)

    price_drop_freq = []
    for (make, model), group in tracked.items():
        if len(group) < 2:
            continue
        drops = sum(1 for l in group if l.price_history[-1] < l.price_history[0])
        price_drop_freq.append({
            "make": make,
            "model": model,
            "label": f"{make} {model}".strip(),
            "total": len(group),
            "drops": drops,
            "drop_pct": round(drops / len(group) * 100),
        })
    price_drop_freq.sort(key=lambda x: x["drop_pct"], reverse=True)

    # ── market_pressure ──────────────────────────────────────────────────────
    make_groups: dict[str, list] = {}
    for l in listings:
        make_groups.setdefault(l.make, []).append(l)

    market_pressure = []
    for make, group in make_groups.items():
        if len(group) < 3:
            continue
        tracked_group = [l for l in group if len(l.price_history) >= 2]
        drop_rate = (
            sum(1 for l in tracked_group if l.price_history[-1] < l.price_history[0])
            / len(tracked_group)
            if tracked_group else 0.0
        )
        ages = [(today - l.listed_date).days for l in group]
        avg_age = mean(ages)
        stale_rate = sum(1 for a in ages if a > 30) / len(ages)

        pressure = round(
            drop_rate * 0.5
            + _clamp(avg_age / 60, 0, 1) * 0.3
            + stale_rate * 0.2,
            3,
        )
        market_pressure.append({
            "make": make,
            "pressure": pressure,
            "drop_rate": round(drop_rate * 100, 1),
            "avg_age_days": round(avg_age, 1),
            "stale_rate": round(stale_rate * 100, 1),
            "count": len(group),
        })
    market_pressure.sort(key=lambda x: x["pressure"], reverse=True)

    # ── summary ──────────────────────────────────────────────────────────────
    all_prices = [l.price for l in priced]
    summary = {
        "total_listings": len(listings),
        "makes_count": len(make_groups),
        "avg_price": round(mean(all_prices)) if all_prices else 0,
        "freshness_date": today.isoformat(),
        "tracked_listings": sum(len(g) for g in tracked.values()),
    }

    return {
        "price_by_make": price_by_make,
        "dealer_markup": dealer_markup,
        "price_drop_freq": price_drop_freq,
        "market_pressure": market_pressure,
        "summary": summary,
    }
