"""
Site Discovery routes
─────────────────────
For tenants entering a new market (no existing stores in the territory).

Workflow:
1. UI calls GET /territories to populate the country/state dropdown
2. User picks a territory; UI calls POST /analyse with country + territory
3. Service runs the four-layer analysis (untapped demand + competitor density)
4. UI renders the result on the map
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import get_key, session_exists
from app.services.site_discovery_service import (
    list_available_territories,
    get_territory_bbox,
    analyse_territory,
)
from app.services.competitor_service import CompetitorBrand
from app.utils import get_logger

log = get_logger("routes.site_discovery")
router = APIRouter(prefix="/site-discovery", tags=["Site Discovery"])


class AnalyseRequest(BaseModel):
    session_id: str
    country: str
    territory: str
    resolution: int = 6


@router.get("/territories")
def get_territories(country: Optional[str] = None):
    """Country/state dropdown — list all configured territories."""
    return list_available_territories(country)


@router.get("/territory")
def get_territory(country: str, territory: str):
    """Detail for a single territory (bbox)."""
    bbox = get_territory_bbox(country, territory)
    if not bbox:
        raise HTTPException(404, f"Territory '{territory}' not found for {country}")
    return {
        "country": country,
        "name": territory,
        "bbox": bbox,
    }


@router.post("/analyse")
def analyse(req: AnalyseRequest):
    """
    Run the full Site Discovery analysis for a (country, territory).
    Returns untapped demand hexes + competitor density (if configured).
    """
    if not session_exists(req.session_id):
        raise HTTPException(404, "Session not found.")

    # Pull configured competitors from session
    brands_data = get_key(req.session_id, "competitors") or []
    competitors = [
        CompetitorBrand(
            name=b["name"],
            selected=b["selected"],
            locations=b.get("locations", []),
            last_fetched_at=b.get("last_fetched_at"),
        )
        for b in brands_data
    ] or None

    # demographics_fetcher: in v3 we leave this as None; the platform's existing
    # demographics_service can be wired in here later. With None, the service
    # returns valid-shape output with zeros — useful for testing the pipeline.
    result = analyse_territory(
        country=req.country,
        territory=req.territory,
        competitors=competitors,
        demographics_fetcher=None,
        resolution=req.resolution,
    )

    if "error" in result:
        raise HTTPException(404, result["error"])

    return result
