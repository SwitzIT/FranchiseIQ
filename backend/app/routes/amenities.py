"""Amenities fetch/cache route."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import get_amenities, get_cache_status, get_key, set_key, session_exists
from app.utils import get_logger

log = get_logger("routes.amenities")
router = APIRouter(tags=["Amenities"])


class AmenitiesRequest(BaseModel):
    session_id: str


@router.post("/fetch_amenities")
def fetch_amenities(body: AmenitiesRequest):
    """
    Check if amenity cache exists for the session's country/state.
    If not → fetch via OSMnx and cache.
    Stores the loaded GDF in the session for use in /predict.
    NOTE: This can take several minutes for a full state.
    """
    if not session_exists(body.session_id):
        raise HTTPException(404, "Session not found.")

    country = get_key(body.session_id, "country")
    state   = get_key(body.session_id, "state")
    if not country or not state:
        raise HTTPException(400, "Country/state not selected.")

    try:
        gdf, was_cached = get_amenities(country, state)
        set_key(body.session_id, "amenities_gdf", gdf)
    except RuntimeError as e:
        raise HTTPException(503, f"OSMnx fetch failed: {e}")

    status = get_cache_status(country, state)
    log.info(f"[Amenities] session={body.session_id} cached={was_cached} n={len(gdf)}")

    return {
        "success":         True,
        "was_cached":      was_cached,
        "amenities_count": len(gdf),
        "cache_size_mb":   status["size_mb"],
    }


@router.get("/amenities_status")
def amenities_status(session_id: str, country: str, state: str):
    """Check cache status without fetching."""
    return {"success": True, **get_cache_status(country, state)}
