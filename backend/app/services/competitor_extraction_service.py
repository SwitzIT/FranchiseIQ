"""
Competitor Extraction Service (ETL: Places API → DB)
─────────────────────────────────────────────────────
Single responsibility: fetch competitor brand locations from the Google
Places API and persist them to the competitor DB cache.

This module is the ONLY place in the codebase that calls the Places API.
Runtime queries (the four-layer map view, competitor density, untapped
demand) never call Places — they query the DB via competitor_db_service.

Called from:
- Tenant onboarding (one-off extraction for newly configured brands)
- Monthly cron (refresh all brands)
- Manual admin extraction via scripts/extract_competitor_locations.py

If GOOGLE_PLACES_API_KEY isn't set, calls log a warning and return zero —
no exceptions, no crashes. Useful for dev environments.
"""
import os
from typing import Any, Dict, List, Optional

import requests

from app.utils import get_logger
from app.services.competitor_db_service import upsert_brand_locations

log = get_logger("services.competitor_extraction")

PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
PLACES_URL = "https://places.googleapis.com/v1/places:searchText"


# ─────────────────────────────────────────────────────────────────────────────
# Internal: one Places API call
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_from_places(
    brand: str, country: str, region_hint: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    One Places text-search call. Returns the locations as plain dicts in
    the shape competitor_db_service expects.
    """
    if not PLACES_API_KEY:
        log.warning("GOOGLE_PLACES_API_KEY not set — returning [] for '%s' in %s",
                    brand, country)
        return []

    query = brand
    if region_hint:
        query += f" {region_hint}"
    query += f", {country}"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,places.location,places.formattedAddress,"
            "places.id,places.rating"
        ),
    }
    payload = {"textQuery": query, "maxResultCount": 20}

    locations: List[Dict[str, Any]] = []
    try:
        resp = requests.post(PLACES_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for p in data.get("places", []):
            loc = p.get("location") or {}
            locations.append({
                "name":        (p.get("displayName") or {}).get("text", brand),
                "lat":         loc.get("latitude"),
                "lng":         loc.get("longitude"),
                "address":     p.get("formattedAddress"),
                "place_id":    p.get("id"),
                "rating":      p.get("rating"),
                "region_hint": region_hint,
            })
    except Exception as e:
        log.warning("Places API failed for '%s' in %s: %s", brand, country, e)

    log.info("fetched %d locations for '%s' in %s", len(locations), brand, country)
    return locations


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def extract_brand_to_db(
    brand: str, country: str, region_hint: Optional[str] = None
) -> int:
    """
    Fetch one brand's locations from Places and upsert to DB.

    Returns the number of locations stored. Returns 0 if the API key is
    missing or the fetch returns nothing — no exception, no DB write.
    """
    locations = _fetch_from_places(brand, country, region_hint)
    if not locations:
        return 0
    return upsert_brand_locations(brand, country, locations)


def extract_brands_batch(
    brands: List[str], country: str, region_hint: Optional[str] = None
) -> Dict[str, int]:
    """
    Bulk extract for many brands in the same country.
    Returns {brand_name: rows_stored}.

    Used at:
    - Tenant onboarding (after they save their competitor list)
    - Monthly cron (refresh every active brand)
    """
    results: Dict[str, int] = {}
    for brand in brands:
        try:
            results[brand] = extract_brand_to_db(brand, country, region_hint)
        except Exception as e:
            log.error("Extract failed for '%s' in %s: %s", brand, country, e)
            results[brand] = 0
    return results
