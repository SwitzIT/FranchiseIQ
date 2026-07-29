"""
Region Geocoding Service
────────────────────────
Reverse-geocode lat/lng coordinates to admin regions using OpenStreetMap's
Nominatim API. Auto-derives region/state/district/city/locality so tenants
don't need to provide region data themselves.

CRITICAL: Nominatim has a 1 req/sec rate limit and requires a custom
User-Agent. Results are cached aggressively (LRU + disk) since admin
boundaries don't change.

Falls back gracefully on network errors — returns None rather than blocking
the analytics pipeline.
"""
from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

import requests

from app.utils import get_logger, safe_float

log = get_logger("services.region_geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "FranchiseIQ/1.0 (data-platform; contact@franchiseiq.example.com)"
RATE_LIMIT_SECONDS = 1.05   # Nominatim policy: max 1 req/sec; we add buffer
COORD_PRECISION = 4         # 4 decimal places ≈ 11m; cache key granularity
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "geocode_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "nominatim_cache.json")

# Module-level state for rate limiting + disk cache
_last_request_time = 0.0
_disk_cache: Optional[Dict[str, Dict[str, Any]]] = None


def _load_disk_cache() -> Dict[str, Dict[str, Any]]:
    global _disk_cache
    if _disk_cache is not None:
        return _disk_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _disk_cache = json.load(f)
                log.info("Loaded %d cached geocoding results from disk", len(_disk_cache))
                return _disk_cache
        except Exception as e:
            log.warning("Could not load geocode cache: %s", e)
    _disk_cache = {}
    return _disk_cache


def _save_disk_cache() -> None:
    if _disk_cache is None:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_disk_cache, f, ensure_ascii=False)
    except Exception as e:
        log.warning("Could not save geocode cache: %s", e)


def _cache_key(lat: float, lng: float) -> str:
    return f"{round(lat, COORD_PRECISION)},{round(lng, COORD_PRECISION)}"


def _throttle() -> None:
    """Enforce Nominatim's 1 req/sec rate limit."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _last_request_time = time.time()


def reverse_geocode(lat: float, lng: float) -> Optional[Dict[str, Any]]:
    """
    Reverse-geocode a single coordinate. Cached on disk between runs.

    Returns
    -------
    {
        "country":   "India",
        "state":     "West Bengal",
        "district":  "Kolkata",
        "city":      "Kolkata",
        "suburb":    "Park Street",
        "postcode":  "700016",
        "display":   "Park Street, Kolkata, West Bengal, India",
    }
    or None on failure.
    """
    lat = safe_float(lat)
    lng = safe_float(lng)
    if lat == 0.0 and lng == 0.0:
        return None

    cache = _load_disk_cache()
    key = _cache_key(lat, lng)
    if key in cache:
        return cache[key]

    _throttle()
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "lat": lat, "lon": lng,
                "format": "json",
                "addressdetails": 1, "zoom": 14,
                "accept-language": "en",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("Nominatim lookup failed for (%.4f, %.4f): %s", lat, lng, e)
        return None

    addr = data.get("address", {})
    result = {
        "country":  addr.get("country"),
        "state":    addr.get("state") or addr.get("region"),
        "district": addr.get("state_district") or addr.get("county") or addr.get("district"),
        "city":     addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality"),
        "suburb":   addr.get("suburb") or addr.get("neighbourhood") or addr.get("locality"),
        "postcode": addr.get("postcode"),
        "display":  data.get("display_name"),
    }

    cache[key] = result
    # Save every 25 new entries to amortise disk writes
    if len(cache) % 25 == 0:
        _save_disk_cache()
    return result


def reverse_geocode_many(coords: list[Tuple[float, float]]) -> list[Optional[Dict[str, Any]]]:
    """
    Reverse-geocode a batch of coordinates. Respects rate limit, uses cache.

    For large batches (hundreds of stores), expect this to take minutes
    on a fresh cache. Subsequent runs return instantly from cache.
    """
    results = []
    for lat, lng in coords:
        results.append(reverse_geocode(lat, lng))
    _save_disk_cache()
    return results


def enrich_stores_with_regions(stores: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Mutate-in-place: add 'region', 'district', 'city', 'suburb' fields to
    each store dict that doesn't already have them.

    Existing values are preserved — we only fill blanks.
    """
    coords = [(safe_float(s.get("lat")), safe_float(s.get("lng"))) for s in stores]
    geocoded = reverse_geocode_many(coords)

    enriched_count = 0
    for store, geo in zip(stores, geocoded):
        if geo is None:
            continue
        # Map Nominatim fields to store fields, only filling blanks
        mapping = {
            "region":   geo.get("state"),    # use state as "region" by default
            "state":    geo.get("state"),
            "district": geo.get("district"),
            "city":     geo.get("city"),
            "suburb":   geo.get("suburb"),
        }
        for k, v in mapping.items():
            if v and not store.get(k):
                store[k] = v
                enriched_count += 1

    log.info("Enriched %d store fields via reverse geocoding", enriched_count)
    return stores
