"""Data validation routes — POST endpoint for validating store uploads."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List

from app.services.data_validation_service import validate_stores
from app.services import get_key, session_exists
from app.utils import get_logger

log = get_logger("routes.validation")
router = APIRouter(tags=["Validation"])


class ValidateStoresRequest(BaseModel):
    rows: List[Dict[str, Any]] = Field(..., description="List of store rows as dicts")
    country: Optional[str] = Field(None, description="Country for bounds checking (e.g. 'India')")
    require_revenue: bool = Field(True, description="False for Site Discovery mode")


@router.post("/validate-stores")
def validate_stores_endpoint(payload: ValidateStoresRequest):
    """
    Run two-stage validation on a list of store rows.

    Stage A (hard rules): blocks ingestion if any row has missing/invalid
    identifier, coordinates, or revenue.

    Stage B (soft warnings): proceeds with notice — flags duplicates,
    revenue outliers, possible cannibalisation.

    Returns a structured report including a 0-100 health score.
    """
    if not payload.rows:
        raise HTTPException(400, "No rows provided for validation")

    return validate_stores(
        rows=payload.rows,
        country=payload.country,
        require_revenue=payload.require_revenue,
    )


@router.get("/validate-session")
def validate_session(session_id: str):
    """
    Validate the stores already loaded into a session. Useful for showing the
    Data Health panel after upload without requiring the data to be re-sent.
    """
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet. Run /predict first or upload data.")

    stores = results.get("stores", [])
    country = get_key(session_id, "country")

    # Map session store dicts to validation input schema
    rows = []
    for s in stores:
        rows.append({
            "store_id":  s.get("id") or s.get("store_id"),
            "name":      s.get("name"),
            "lat":       s.get("lat"),
            "lng":       s.get("lng"),
            "revenue":   s.get("revenue"),
            "region":    s.get("region"),
            "postal_code": s.get("postal_code"),
            "address":   s.get("address"),
        })

    return validate_stores(rows=rows, country=country, require_revenue=True)
