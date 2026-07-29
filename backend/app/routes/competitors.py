"""
Competitor routes (v3.1)
─────────────────────────
Endpoints for the option-c competitor onboarding flow.

Runtime queries (density-hexes) read from the DB cache only — no live
Places API calls. Extraction happens at onboarding (POST /initialize
optionally triggers it) and via the monthly cron.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.services import get_key, session_exists, set_key
from app.services.competitor_service import (
    load_templates, get_suggested_competitors, get_available_categories,
    initialize_tenant_competitors,
    get_competitor_density_for_tenant,
    list_brands_in_db,
    CompetitorBrand,
)
from app.services.competitor_extraction_service import extract_brands_batch
from app.utils import get_logger

log = get_logger("routes.competitors")
router = APIRouter(prefix="/competitors", tags=["Competitors"])


# ── Schemas ─────────────────────────────────────────────────────────

class CompetitorBrandIn(BaseModel):
    name: str
    selected: bool = True


class InitializeRequest(BaseModel):
    session_id: str
    country: str
    category: str
    custom_additions: Optional[List[str]] = None
    extract_immediately: bool = False   # if True, run Places extraction
                                         # synchronously after save


class UpdateRequest(BaseModel):
    session_id: str
    brands: List[CompetitorBrandIn]


class ExtractRequest(BaseModel):
    session_id: str
    region_hint: Optional[str] = None
    background: bool = True   # default: don't block the API response


# ── Templates ───────────────────────────────────────────────────────

@router.get("/templates")
def list_templates():
    return load_templates()


@router.get("/suggested")
def suggested(country: str, category: str):
    suggestions = get_suggested_competitors(country, category)
    return {"country": country, "category": category,
            "suggestions": suggestions, "count": len(suggestions)}


@router.get("/categories")
def categories(country: str):
    return {"country": country, "categories": get_available_categories(country)}


# ── Tenant brand list (session-persisted) ───────────────────────────

@router.post("/initialize")
def initialize(req: InitializeRequest, background_tasks: BackgroundTasks):
    """
    Onboarding: combine suggested + custom into the tenant's brand list.

    If `extract_immediately=True`, the Places API extraction also runs.
    To avoid blocking the response, the extraction is dispatched as a
    background task — the brand list is saved immediately and the UI
    can poll /list to see when locations appear.
    """
    if not session_exists(req.session_id):
        raise HTTPException(404, "Session not found.")

    brands = initialize_tenant_competitors(
        country=req.country, category=req.category,
        custom_additions=req.custom_additions,
    )
    payload = [
        {"name": b.name, "selected": b.selected, "locations": [],
         "last_fetched_at": None}
        for b in brands
    ]
    set_key(req.session_id, "competitors", payload)

    response = {
        "session_id":  req.session_id,
        "country":     req.country,
        "category":    req.category,
        "brands":      payload,
        "count":       len(payload),
        "extraction_scheduled": False,
    }

    if req.extract_immediately:
        selected_names = [b.name for b in brands if b.selected]
        log.info("scheduling background extraction for %d brands in %s",
                 len(selected_names), req.country)
        background_tasks.add_task(
            extract_brands_batch, selected_names, req.country, None,
        )
        response["extraction_scheduled"] = True

    return response


@router.get("/list")
def list_(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")
    return {"brands": get_key(session_id, "competitors") or []}


@router.put("/update")
def update(req: UpdateRequest):
    if not session_exists(req.session_id):
        raise HTTPException(404, "Session not found.")

    updated = [{"name": b.name, "selected": b.selected,
                "locations": [], "last_fetched_at": None}
               for b in req.brands]
    set_key(req.session_id, "competitors", updated)
    return {"brands": updated, "count": len(updated)}


# ── Extraction (Places API → DB) ────────────────────────────────────

@router.post("/extract")
def extract(req: ExtractRequest, background_tasks: BackgroundTasks):
    """
    Trigger extraction of all selected brands for the tenant's session.
    Defaults to running in the background — the response returns
    immediately with extraction_scheduled=True.

    Pass background=False to run synchronously (useful in scripts).
    """
    if not session_exists(req.session_id):
        raise HTTPException(404, "Session not found.")

    country = get_key(req.session_id, "country") or ""
    brands_data = get_key(req.session_id, "competitors") or []
    selected_names = [b["name"] for b in brands_data if b.get("selected")]

    if not selected_names:
        raise HTTPException(400, "No selected competitors to extract.")

    if req.background:
        background_tasks.add_task(
            extract_brands_batch, selected_names, country, req.region_hint,
        )
        return {"extraction_scheduled": True,
                "brand_count": len(selected_names), "country": country}
    else:
        result = extract_brands_batch(selected_names, country, req.region_hint)
        return {"extraction_scheduled": False, "results": result,
                "total_locations": sum(result.values())}


# ── Runtime: density layer (DB read only, fast) ─────────────────────

@router.get("/density-hexes")
def density_hexes(session_id: str, resolution: int = 6):
    """
    The competitor density layer. Reads from DB cache — no API calls,
    sub-second response. Returns same hex shape as performance heatmap.
    """
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    country = get_key(session_id, "country") or ""
    brands_data = get_key(session_id, "competitors") or []
    return get_competitor_density_for_tenant(brands_data, country, resolution)


# ── Admin: DB inspection ────────────────────────────────────────────

@router.get("/db-status")
def db_status(country: str):
    """List every brand currently in the DB cache for a country."""
    return {"country": country, "brands": list_brands_in_db(country)}
