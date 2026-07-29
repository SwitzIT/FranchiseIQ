"""
Competitor Service (v3.1)
──────────────────────────
Tenant-facing competitor management. Two responsibilities:

  1. Templates: load suggested brand lists per (country, category) from
     the YAML config and present them in onboarding.
  2. Density layer: read pre-extracted locations from the DB cache and
     aggregate to H3 hexes for map rendering.

NO live Places API calls happen here. Extraction is handled by
competitor_extraction_service.py (called from onboarding + cron only).
This split is what makes runtime queries fast and predictable.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from app.utils import get_logger
from app.services.competitor_db_service import (
    get_locations_for_brands, list_brands_for_country,
)

log = get_logger("services.competitor")

TEMPLATE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "competitor_templates.yaml"
)
_templates_cache: Optional[Dict[str, Dict[str, List[str]]]] = None


@dataclass
class CompetitorBrand:
    name: str
    selected: bool = True
    locations: List[Dict[str, Any]] = field(default_factory=list)
    last_fetched_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Templates (YAML config — editable without code changes)
# ─────────────────────────────────────────────────────────────────────────────

def load_templates() -> Dict[str, Dict[str, List[str]]]:
    """Load competitor templates from YAML. Cached for process lifetime."""
    global _templates_cache
    if _templates_cache is not None:
        return _templates_cache
    try:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            _templates_cache = yaml.safe_load(f) or {}
        log.info("loaded competitor templates: %d countries", len(_templates_cache))
    except FileNotFoundError:
        log.warning("template file not found at %s", TEMPLATE_FILE)
        _templates_cache = {}
    except Exception as e:
        log.error("template parse failed: %s", e)
        _templates_cache = {}
    return _templates_cache


def get_suggested_competitors(country: str, category: str) -> List[str]:
    """Seed brand list for (country, category)."""
    return load_templates().get(country, {}).get(category, [])


def get_available_categories(country: str) -> List[str]:
    return list(load_templates().get(country, {}).keys())


def initialize_tenant_competitors(
    country: str, category: str, custom_additions: Optional[List[str]] = None
) -> List[CompetitorBrand]:
    """Combine suggested + custom into the tenant's initial brand list."""
    suggested = get_suggested_competitors(country, category)
    customs = custom_additions or []

    seen = set()
    out: List[CompetitorBrand] = []
    for name in suggested + customs:
        norm = name.strip()
        if not norm or norm.lower() in seen:
            continue
        seen.add(norm.lower())
        out.append(CompetitorBrand(name=norm, selected=True))
    log.info("initialised tenant competitors %s/%s: %d brands",
             country, category, len(out))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Runtime query — reads from DB cache, no external API calls
# ─────────────────────────────────────────────────────────────────────────────

def get_competitor_locations_for_tenant(
    brands_data: List[Dict[str, Any]], country: str
) -> List[Dict[str, Any]]:
    """
    Read all currently-selected competitor locations for a tenant from
    the DB cache. Returns plain location dicts.

    `brands_data` is the tenant's saved competitor config from the
    session store: a list of {name, selected, ...} dicts.
    """
    selected_brand_names = [b["name"] for b in brands_data if b.get("selected")]
    if not selected_brand_names:
        return []

    rows = get_locations_for_brands(selected_brand_names, country)
    # Add brand back into the dict shape callers expect
    out = []
    for r in rows:
        out.append({
            "brand":   r["brand_name"],
            "name":    r["name"],
            "lat":     r["lat"],
            "lng":     r["lng"],
            "address": r["address"],
            "place_id": r["place_id"],
            "rating":  r["rating"],
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation: locations → H3 hexes for the competitor density map layer
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_locations_to_hexes(
    locations: List[Dict[str, Any]], resolution: int = 6
) -> Dict[str, Any]:
    """
    Group competitor locations into H3 cells and produce hex polygons
    suitable for the map renderer. Same output shape as the performance
    heatmap so the UI can stack them.
    """
    import h3

    hex_counts: Dict[str, Dict[str, Any]] = {}
    total = 0
    for loc in locations:
        lat, lng = loc.get("lat"), loc.get("lng")
        if lat is None or lng is None:
            continue
        try:
            cell = h3.latlng_to_cell(float(lat), float(lng), resolution)
        except Exception:
            continue
        total += 1
        bucket = hex_counts.setdefault(cell, {
            "cell": cell, "competitor_count": 0, "brands": {},
        })
        bucket["competitor_count"] += 1
        brand = loc.get("brand", "unknown")
        bucket["brands"][brand] = bucket["brands"].get(brand, 0) + 1

    out: List[Dict[str, Any]] = []
    for cell, data in hex_counts.items():
        try:
            boundary = [[float(la), float(ln)] for la, ln in h3.cell_to_boundary(cell)]
            clat, clng = h3.cell_to_latlng(cell)
        except Exception:
            continue
        out.append({
            "cell":             cell,
            "boundary":         boundary,
            "center":           [float(clat), float(clng)],
            "competitor_count": data["competitor_count"],
            "brands":           data["brands"],
        })

    out.sort(key=lambda h: -h["competitor_count"])
    return {
        "hexes":           out,
        "resolution":      resolution,
        "total_cells":     len(out),
        "total_locations": total,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrappers used by routes
# ─────────────────────────────────────────────────────────────────────────────

def get_competitor_density_for_tenant(
    brands_data: List[Dict[str, Any]], country: str, resolution: int = 6
) -> Dict[str, Any]:
    """One-stop: read DB, aggregate to hexes. The runtime entry point."""
    locations = get_competitor_locations_for_tenant(brands_data, country)
    return aggregate_locations_to_hexes(locations, resolution)


def list_brands_in_db(country: str) -> List[Dict[str, Any]]:
    """Admin/debug: see what's currently in the cache for a country."""
    return list_brands_for_country(country)


# ─────────────────────────────────────────────────────────────────────────────
# Legacy alias for backward compatibility (v3.2 fix)
# ─────────────────────────────────────────────────────────────────────────────
# site_discovery_service.py was written against the v3.0 API where this
# function accepted a list of CompetitorBrand objects. The v3.1 rewrite
# changed it to accept plain location dicts via aggregate_locations_to_hexes.
# This alias preserves the old call signature so the older callers keep
# working without modification.

def aggregate_competitors_to_hexes(competitors, resolution: int = 6):
    """
    Legacy API: take a list of CompetitorBrand dataclasses (each with a
    .locations attribute), flatten to plain locations, and pass through
    to the v3.1 aggregator.
    """
    flat = []
    for brand in competitors or []:
        # CompetitorBrand dataclass or dict — handle both
        if hasattr(brand, "name"):
            name = brand.name
            locs = getattr(brand, "locations", []) or []
        else:
            name = brand.get("name") if isinstance(brand, dict) else None
            locs = brand.get("locations", []) if isinstance(brand, dict) else []
        for loc in locs:
            entry = dict(loc) if isinstance(loc, dict) else {}
            if "brand" not in entry and name:
                entry["brand"] = name
            flat.append(entry)
    return aggregate_locations_to_hexes(flat, resolution)
