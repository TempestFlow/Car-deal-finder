import dataclasses
import json
import os
from datetime import date, datetime

from models import CarListing

DATA_FILE = "data/listings.json"
MAX_AGE_HOURS = 24


def save_listings(listings: list, path: str = DATA_FILE):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    records = []
    for l in listings:
        d = dataclasses.asdict(l)
        d["listed_date"] = l.listed_date.isoformat()
        records.append(d)
    payload = {"saved_at": datetime.now().isoformat(), "listings": records}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(listings)} listings to {path}")


def load_listings(path: str = DATA_FILE) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    listings = []
    for d in payload.get("listings", []):
        d["listed_date"] = date.fromisoformat(d["listed_date"])
        listings.append(CarListing(**d))
    return listings


def merge_price_history(old_listings: list, new_listings: list) -> list:
    """Carry forward price history from previous runs so drops are detectable."""
    old_by_id = {l.id: l for l in old_listings}
    for listing in new_listings:
        old = old_by_id.get(listing.id)
        if old and old.price_history:
            # Keep original history; append new price only if it changed
            history = list(old.price_history)
            if listing.price > 0 and listing.price != history[-1]:
                history.append(listing.price)
            listing.price_history = history
    return new_listings


def is_cache_fresh(path: str = DATA_FILE, max_age_hours: int = MAX_AGE_HOURS) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    saved_at = payload.get("saved_at", "")
    if not saved_at:
        return False
    age = datetime.now() - datetime.fromisoformat(saved_at)
    return age.total_seconds() < max_age_hours * 3600
