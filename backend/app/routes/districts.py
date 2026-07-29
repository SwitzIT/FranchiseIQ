"""Districts route — performance rollup grouped by admin district."""
from fastapi import APIRouter, HTTPException

from app.services import get_key, session_exists
from app.services.district_aggregation_service import aggregate_stores_by_district
from app.utils import get_logger

log = get_logger("routes.districts")
router = APIRouter(tags=["Districts"])


@router.get("/district-performance")
def district_performance(session_id: str):
    """
    Returns the 'District View' rollup — stores grouped by admin district
    with per-district performance vs network avg.

    Reverse-geocodes any stores that don't already have a `district` field,
    using offline data (no external API calls). Fast even for thousands
    of stores.

    Response shape: see `district_aggregation_service.aggregate_stores_by_district`.
    """
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet. Run /predict first.")

    stores = results.get("stores", [])
    return aggregate_stores_by_district(stores)
