"""Analytics routes — Region KPIs, Hex heatmap, Peer-context, Untapped demand."""
import math
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.services import get_key, session_exists, compute_hex_heatmap
from app.services.hex_aggregation_service import suggest_resolution as _suggest_hex_resolution
from app.services.peer_context_service import cluster_stores_by_catchment
from app.services.untapped_demand_service import compute_untapped_demand, generate_candidate_grid
from app.utils import get_logger, safe_float

log = get_logger("routes.analytics")
router = APIRouter(tags=["Analytics"])


# ─────────────────────────────────────────────────────────────────────────────
# Region KPIs (unchanged from v2 — included here so the file is self-contained)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/region-kpis")
def region_kpis(session_id: str):
    """Per-region KPIs from the current session's store + prediction data."""
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet. Run /predict first.")

    stores_records = results.get("stores", [])
    all_candidates = results.get("all_candidates", [])

    if not stores_records:
        return {"regions": [], "best_region": None, "worst_region": None, "region_count": 0}

    region_map: dict[str, dict] = {}
    for s in stores_records:
        region = s.get("region") or "Unassigned"
        if region not in region_map:
            region_map[region] = {
                "name": region, "store_count": 0, "total_revenue": 0.0,
                "revenues": [], "scores": [], "candidates": [],
            }
        rm = region_map[region]
        rm["store_count"] += 1
        rev = safe_float(s.get("revenue", 0))
        rm["revenues"].append(rev)
        rm["total_revenue"] += rev

    for c in all_candidates:
        region = c.get("region") or "Unassigned"
        if region in region_map:
            region_map[region]["scores"].append(safe_float(c.get("score", 0)))
            region_map[region]["candidates"].append(c)

    regions_out = []
    for region, data in region_map.items():
        revs = data["revenues"]
        avg_rev = sum(revs) / len(revs) if revs else 0.0
        scores = data["scores"]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        top_cand = None
        if data["candidates"]:
            best = max(data["candidates"], key=lambda x: x.get("score", 0))
            top_cand = {
                "name": best.get("name", ""), "lat": best.get("lat"),
                "lng": best.get("lng"), "score": safe_float(best.get("score", 0)),
            }
        regions_out.append({
            "name": region, "store_count": data["store_count"],
            "avg_revenue": round(avg_rev, 2),
            "total_revenue": round(data["total_revenue"], 2),
            "avg_final_score": round(avg_score, 2),
            "top_candidate": top_cand,
            "revenue_rank": 0, "performance_label": "mid",
        })

    regions_out.sort(key=lambda x: x["avg_revenue"], reverse=True)
    n = len(regions_out)
    third = max(1, math.ceil(n / 3))
    for i, r in enumerate(regions_out):
        r["revenue_rank"] = i + 1
        if i < third:
            r["performance_label"] = "top"
        elif i >= n - third:
            r["performance_label"] = "low"
        else:
            r["performance_label"] = "mid"

    return {
        "regions": regions_out,
        "best_region": regions_out[0]["name"] if regions_out else None,
        "worst_region": regions_out[-1]["name"] if regions_out else None,
        "region_count": len(regions_out),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Hex heatmap (auto-resolution; same as v2)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/hex-heatmap")
def hex_heatmap(
    session_id: str,
    resolution: Optional[int] = Query(None, ge=4, le=9,
        description="H3 resolution. Omit for auto-select based on dataset size and spread."),
    above_threshold: float = Query(1.10, ge=1.0, le=2.0),
    below_threshold: float = Query(0.90, ge=0.0, le=1.0),
):
    """Hex-aggregated performance heatmap. Multi-scale safe."""
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet. Run /predict first.")

    return compute_hex_heatmap(
        stores=results.get("stores", []),
        resolution=resolution,
        above_threshold=above_threshold,
        below_threshold=below_threshold,
    )


@router.get("/hex-heatmap/suggest-resolution")
def suggest_hex_resolution_endpoint(session_id: str):
    """Lightweight: just the suggested resolution, no full computation."""
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")
    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet.")
    stores = results.get("stores", [])
    return {"suggested_resolution": _suggest_hex_resolution(stores), "store_count": len(stores)}


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Peer-context benchmarking
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/peer-context")
def peer_context(
    session_id: str,
    k: Optional[int] = Query(None, ge=2, le=8,
        description="Number of peer clusters. Default ~4, auto-capped by dataset size."),
):
    """
    Cluster stores by catchment profile and benchmark each store against
    its cluster peers (instead of the network average).

    Stores in the response carry both `revenue` and `pct_of_peer_avg`,
    with a classification ('above'/'on_target'/'below') vs peer benchmark.
    """
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")
    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet. Run /predict first.")

    return cluster_stores_by_catchment(stores=results.get("stores", []), k=k)


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Untapped-demand layer
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/untapped-demand")
def untapped_demand(
    session_id: str,
    resolution: int = Query(6, ge=4, le=9),
    supply_radius_km: float = Query(3.0, ge=0.5, le=20.0,
        description="A store within this distance counts as 'covered'."),
    min_demand_percentile: int = Query(50, ge=0, le=95,
        description="Filter to hexes above this percentile of demand."),
):
    """
    Identify hex cells with high demand but no nearby existing store.

    Returns cells ranked by `untapped_score` (demand × (1 − supply)).
    Designed to be rendered as a separate map layer alongside the
    performance heatmap.

    NOTE: In v3 the candidate hex enrichment (population, income, amenities)
    relies on the platform's demographics service being wired in via the
    `compute_untapped_demand()` candidate input. Until that's wired, this
    endpoint returns the supply layer only, with demand placeholder values
    of zero. UI will show "demand enrichment pending" until then.
    """
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")
    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet. Run /predict first.")

    stores = results.get("stores", [])
    if not stores:
        return {"hexes": [], "resolution": resolution, "total_cells": 0,
                "supply_radius_km": supply_radius_km}

    # Build a bbox from existing stores (1 deg padding to look around)
    lats = [safe_float(s.get("lat")) for s in stores if safe_float(s.get("lat")) != 0]
    lngs = [safe_float(s.get("lng")) for s in stores if safe_float(s.get("lng")) != 0]
    if not lats or not lngs:
        return {"hexes": [], "resolution": resolution, "total_cells": 0,
                "supply_radius_km": supply_radius_km}

    pad = 0.5
    bbox = (min(lats) - pad, max(lats) + pad, min(lngs) - pad, max(lngs) + pad)

    candidates = generate_candidate_grid(bbox, resolution=resolution)

    # If demographics_service is available on the app, enrich. Otherwise zeros.
    try:
        from app.services.demographics_service import enrich_hex_demographics  # type: ignore
        for c in candidates:
            enrichment = enrich_hex_demographics(c["lat"], c["lng"]) or {}
            c.update(enrichment)
    except Exception:
        for c in candidates:
            c.setdefault("population", 0)
            c.setdefault("income_index", 0)
            c.setdefault("amenity_count", 0)

    return compute_untapped_demand(
        candidate_hexes=candidates,
        existing_stores=stores,
        resolution=resolution,
        supply_radius_km=supply_radius_km,
        min_demand_percentile=min_demand_percentile,
    )
