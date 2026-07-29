"""
Hex aggregation service — performance heatmap.
v3.3 enhancement: per-hex output now includes `stores_detail` (each store's
revenue + % of network avg) and `dominant_locality` (auto-derived from
store regions), so the UI can render an explainable drill-down panel.
"""
from collections import Counter
from typing import Any, Dict, List, Optional

import h3

from app.utils import get_logger, safe_float

log = get_logger("services.hex_aggregation")

# ── Resolution selection (v2, unchanged) ────────────────────────────
MIN_RESOLUTION = 4
MAX_RESOLUTION = 9
TARGET_AVG_PER_CELL = 5.0
IDEAL_CELL_COUNT_LO = 20
IDEAL_CELL_COUNT_HI = 120

# ── Classification thresholds ───────────────────────────────────────
DEFAULT_ABOVE_THRESHOLD = 1.10   # ≥ 110% of network avg → "above"
DEFAULT_BELOW_THRESHOLD = 0.90   # ≤  90% of network avg → "below"


def suggest_resolution(stores: List[Dict[str, Any]]) -> int:
    """
    Pick an H3 resolution that produces a sensible aggregation given
    dataset size and spread. Same heuristic as v2 — no change.
    """
    valid_pts = [
        (safe_float(s.get("lat")), safe_float(s.get("lng")))
        for s in stores
        if safe_float(s.get("lat")) != 0.0 and safe_float(s.get("lng")) != 0.0
    ]
    if len(valid_pts) < 5:
        return 6

    best_res, best_score = 6, -float("inf")
    for res in range(MIN_RESOLUTION, MAX_RESOLUTION + 1):
        cell_counts: Dict[str, int] = {}
        for lat, lng in valid_pts:
            try:
                c = h3.latlng_to_cell(lat, lng, res)
                cell_counts[c] = cell_counts.get(c, 0) + 1
            except Exception:
                continue
        if not cell_counts:
            continue

        n_cells = len(cell_counts)
        avg_per_cell = len(valid_pts) / n_cells
        singleton_ratio = sum(1 for v in cell_counts.values() if v == 1) / n_cells

        avg_score = 10.0 if 3 <= avg_per_cell <= 8 else -abs(avg_per_cell - TARGET_AVG_PER_CELL) * 2
        if IDEAL_CELL_COUNT_LO <= n_cells <= IDEAL_CELL_COUNT_HI:
            count_score = 5.0
        elif n_cells < IDEAL_CELL_COUNT_LO:
            count_score = -(IDEAL_CELL_COUNT_LO - n_cells)
        else:
            count_score = -(n_cells - IDEAL_CELL_COUNT_HI) * 0.05
        singleton_penalty = -singleton_ratio * 10.0
        total = avg_score + count_score + singleton_penalty

        if total > best_score:
            best_score, best_res = total, res

    log.info("suggest_resolution: %d stores → res %d (score %.2f)",
             len(valid_pts), best_res, best_score)
    return best_res


# ─────────────────────────────────────────────────────────────────────────────
# Locality derivation
# ─────────────────────────────────────────────────────────────────────────────

def _dominant_locality(store_regions: List[Dict[str, str]]) -> str:
    """
    Given a list of {city, suburb, district, state} dicts (one per store),
    return the most common non-empty value, prioritising specificity:
    suburb > city > district > state.

    Returns an empty string if nothing is available.
    """
    for field in ("suburb", "city", "district", "state"):
        values = [r.get(field) for r in store_regions if r.get(field)]
        if values:
            counter = Counter(values)
            return counter.most_common(1)[0][0]
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Main aggregation (v3.3: enhanced output)
# ─────────────────────────────────────────────────────────────────────────────

def compute_hex_heatmap(
    stores: List[Dict[str, Any]],
    resolution: Optional[int] = None,
    above_threshold: float = DEFAULT_ABOVE_THRESHOLD,
    below_threshold: float = DEFAULT_BELOW_THRESHOLD,
) -> Dict[str, Any]:
    """
    Build the hex-level performance heatmap.

    v3.3 output additions per hex:
      stores_detail: [{name, revenue, pct_of_network_avg, lat, lng}]
      dominant_locality: str (e.g. "Park Street", "Kolkata", "West Bengal")
    """
    auto_selected = resolution is None
    if auto_selected:
        resolution = suggest_resolution(stores)
    else:
        resolution = max(MIN_RESOLUTION, min(MAX_RESOLUTION, int(resolution)))

    thresholds_out = {
        "above_pct": round(above_threshold * 100, 1),
        "below_pct": round(below_threshold * 100, 1),
    }

    if not stores:
        return {
            "hexes": [], "network_avg": 0.0,
            "resolution": resolution, "auto_selected": auto_selected,
            "total_cells": 0, "total_stores": 0,
            "thresholds": thresholds_out,
        }

    revenues = [safe_float(s.get("revenue", 0)) for s in stores]
    network_avg = sum(revenues) / len(revenues) if revenues else 0.0

    hex_map: Dict[str, Dict[str, Any]] = {}
    valid_count = 0

    for s in stores:
        lat = safe_float(s.get("lat"))
        lng = safe_float(s.get("lng"))
        if lat == 0.0 and lng == 0.0:
            continue
        if not (-90.0 < lat < 90.0) or not (-180.0 < lng < 180.0):
            continue

        try:
            cell = h3.latlng_to_cell(lat, lng, resolution)
        except Exception:
            continue

        valid_count += 1
        rev = safe_float(s.get("revenue", 0))
        store_pct = (rev / network_avg * 100) if network_avg > 0 else 0.0

        bucket = hex_map.setdefault(cell, {
            "cell": cell,
            "store_count": 0,
            "total_revenue": 0.0,
            "store_names": [],
            "stores_detail": [],
            "region_breakdown": [],
        })
        bucket["store_count"] += 1
        bucket["total_revenue"] += rev
        store_name = s.get("name", "") or s.get("id", "") or ""
        bucket["store_names"].append(store_name)
        bucket["stores_detail"].append({
            "name":               store_name,
            "revenue":            round(rev, 2),
            "pct_of_network_avg": round(store_pct, 1),
            "lat":                lat,
            "lng":                lng,
        })
        bucket["region_breakdown"].append({
            "state":    s.get("state") or s.get("region") or "",
            "district": s.get("district") or "",
            "city":     s.get("city") or "",
            "suburb":   s.get("suburb") or "",
        })

    # Build output with per-hex enrichment
    hexes_out: List[Dict[str, Any]] = []
    for cell, data in hex_map.items():
        n = data["store_count"]
        avg = data["total_revenue"] / n if n else 0.0
        pct = (avg / network_avg) if network_avg > 0 else 1.0

        if pct >= above_threshold:
            classification = "above"
        elif pct <= below_threshold:
            classification = "below"
        else:
            classification = "on_target"

        try:
            boundary = [[float(la), float(ln)] for la, ln in h3.cell_to_boundary(cell)]
            clat, clng = h3.cell_to_latlng(cell)
        except Exception:
            continue

        # Sort the store detail list inside each hex by revenue desc
        # — makes the drill-down panel naturally rank-ordered
        stores_detail_sorted = sorted(
            data["stores_detail"], key=lambda x: -x["revenue"]
        )

        hexes_out.append({
            "cell":                 cell,
            "boundary":             boundary,
            "center":               [float(clat), float(clng)],
            "store_count":          n,
            "total_revenue":        round(data["total_revenue"], 2),
            "avg_revenue":          round(avg, 2),
            "pct_of_network_avg":   round(pct * 100, 1),
            "classification":       classification,

            # v3.3 additions for the explainable drill-down panel
            "stores_detail":        stores_detail_sorted,
            "dominant_locality":    _dominant_locality(data["region_breakdown"]),

            # legacy field — kept for backward compatibility
            "store_names":          data["store_names"],
        })

    order = {"above": 0, "on_target": 1, "below": 2}
    hexes_out.sort(key=lambda h: (order[h["classification"]], -h["avg_revenue"]))

    return {
        "hexes":         hexes_out,
        "network_avg":   round(network_avg, 2),
        "resolution":    resolution,
        "auto_selected": auto_selected,
        "total_cells":   len(hexes_out),
        "total_stores":  valid_count,
        "thresholds":    thresholds_out,
    }
