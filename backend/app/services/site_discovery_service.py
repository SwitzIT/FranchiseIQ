"""
Site Discovery Service
──────────────────────
The "I'm entering a new market" use case. Tenant picks a city/state from a
dropdown (no upload required, no sales data required). The service:

1. Resolves the city/state to a bounding box
2. Generates a candidate hex grid covering the territory
3. Enriches each hex with demographics + amenities (platform data layers)
4. Layers in competitor density (if competitors configured)
5. Returns the four-layer view ready for the map:
     - Untapped demand hexes (the recommendations)
     - Competitor density hexes (the threats)
     - Demographic context (the why)

This sits on top of the other services — it's a coordinator, not new logic.
"""
from typing import Any, Dict, List, Optional, Tuple

from app.utils import get_logger
from app.services.untapped_demand_service import (
    compute_untapped_demand, generate_candidate_grid,
)
from app.services.competitor_service import aggregate_competitors_to_hexes

log = get_logger("services.site_discovery")

# ── Hardcoded bounding boxes for India + Sri Lanka territories ──────────────
# For v1 we ship a list of major markets the product supports out of the box.
# At runtime these could come from GADM admin boundary data (see scripts/).
TERRITORY_BBOXES: Dict[str, Dict[str, Tuple[float, float, float, float]]] = {
    "India": {
        # Format: (lat_min, lat_max, lng_min, lng_max)
        "West Bengal":      (21.5, 27.2, 85.8, 89.9),
        "Maharashtra":      (15.6, 22.0, 72.6, 80.9),
        "Uttar Pradesh":    (23.9, 30.4, 77.1, 84.6),
        "Karnataka":        (11.6, 18.5, 74.0, 78.6),
        "Tamil Nadu":       ( 8.1, 13.6, 76.2, 80.4),
        "Delhi":            (28.4, 28.9, 76.8, 77.4),
        "Chhattisgarh":     (17.8, 24.1, 80.2, 84.4),
        "Kolkata City":     (22.4, 22.8, 88.2, 88.6),
        "Mumbai City":      (18.9, 19.3, 72.7, 73.0),
        "Raipur City":      (21.1, 21.4, 81.5, 81.8),
        "Bengaluru City":   (12.8, 13.2, 77.4, 77.8),
        "Lucknow City":     (26.7, 27.0, 80.8, 81.1),
    },
    "Sri Lanka": {
        "Western Province":  ( 6.5,  7.4, 79.7, 80.4),
        "Central Province":  ( 6.8,  7.8, 80.3, 81.2),
        "Southern Province": ( 5.9,  6.9, 80.0, 81.9),
        "Northern Province": ( 8.5,  9.9, 79.7, 81.0),
        "Colombo City":      ( 6.8,  7.0, 79.8, 79.95),
        "Kandy City":        ( 7.2,  7.4, 80.55, 80.75),
        "Galle City":        ( 6.0,  6.1, 80.18, 80.30),
    },
}


def list_available_territories(country: Optional[str] = None) -> Dict[str, List[str]]:
    """
    For the city/state dropdown. Returns a country → [territory names] map.
    Pass country=None to get all available territories across all countries.
    """
    if country:
        territories = TERRITORY_BBOXES.get(country, {})
        return {country: list(territories.keys())}
    return {c: list(t.keys()) for c, t in TERRITORY_BBOXES.items()}


def get_territory_bbox(country: str, territory: str) -> Optional[Tuple[float, float, float, float]]:
    """Look up the bounding box for a (country, territory) pair."""
    return TERRITORY_BBOXES.get(country, {}).get(territory)


def analyse_territory(
    country: str,
    territory: str,
    competitors: Optional[List[Any]] = None,
    demographics_fetcher=None,
    resolution: int = 6,
    supply_radius_km: float = 3.0,
) -> Dict[str, Any]:
    """
    Run the full Site Discovery analysis for a (country, territory).

    Parameters
    ----------
    country, territory : selected from the dropdown
    competitors : list of CompetitorBrand (from competitor_service); optional
    demographics_fetcher : callable(lat, lng) → {population, income_index, amenity_count}
                            — pass in the platform's demographics service. If None,
                            uses zeros (which will produce a low-confidence result).
    resolution : H3 resolution for the candidate grid
    supply_radius_km : not used here (no existing stores in site discovery mode)

    Returns
    -------
    {
        "territory":           {country, name, bbox},
        "untapped_demand":     { hexes: [...], total_cells, ... },
        "competitor_density":  { hexes: [...], ... }    # only if competitors provided
        "candidate_count":     int,
        "resolution":          int,
    }
    """
    bbox = get_territory_bbox(country, territory)
    if not bbox:
        return {
            "error": f"Territory '{territory}' not configured for {country}",
            "available": list_available_territories(country),
        }

    log.info("site_discovery: analysing %s / %s, bbox=%s, res=%d",
             country, territory, bbox, resolution)

    # 1. Generate the candidate hex grid covering the territory
    candidates = generate_candidate_grid(bbox, resolution=resolution)

    # 2. Enrich each candidate with demographics (caller-provided fetcher)
    if demographics_fetcher is not None:
        for c in candidates:
            try:
                enrichment = demographics_fetcher(c["lat"], c["lng"]) or {}
                c["population"]    = enrichment.get("population", 0)
                c["income_index"]  = enrichment.get("income_index", 0)
                c["amenity_count"] = enrichment.get("amenity_count", 0)
            except Exception as e:
                log.warning("Enrichment failed for hex at %s,%s: %s", c["lat"], c["lng"], e)
                c["population"] = 0
                c["income_index"] = 0
                c["amenity_count"] = 0
    else:
        for c in candidates:
            c.setdefault("population", 0)
            c.setdefault("income_index", 0)
            c.setdefault("amenity_count", 0)

    # 3. Untapped demand — here "existing_stores" is empty (entering a new market)
    untapped = compute_untapped_demand(
        candidate_hexes=candidates,
        existing_stores=[],
        resolution=resolution,
        supply_radius_km=supply_radius_km,
    )

    # 4. Competitor density (if competitor list provided)
    competitor_layer = None
    if competitors:
        competitor_layer = aggregate_competitors_to_hexes(competitors, resolution)

    return {
        "territory": {
            "country": country,
            "name": territory,
            "bbox": bbox,
        },
        "untapped_demand":    untapped,
        "competitor_density": competitor_layer,
        "candidate_count":    len(candidates),
        "resolution":         resolution,
        "demographics_used":  demographics_fetcher is not None,
    }
