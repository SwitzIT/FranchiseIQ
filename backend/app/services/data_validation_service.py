"""
Data Validation Service
───────────────────────
Two-stage validation for tenant-uploaded store data:
  - Stage A: HARD rules (block ingestion if any row fails)
  - Stage B: SOFT warnings (proceed with notice)

Required (hard): store identifier, latitude, longitude, revenue
Everything else is optional — the platform enriches missing fields
(regions via reverse-geocoding, etc.).

Output is a structured report the UI can render as a "Data Health" panel.
"""
from typing import Any, Dict, List, Optional, Tuple
import math
import statistics

from app.utils import safe_float, get_logger

log = get_logger("services.data_validation")

# ── Country bounds for lat/lng sanity checks ────────────────────────────────
# Bounding boxes are generous — they catch "wrong country" mistakes without
# tripping on legitimate edge-of-country stores.
COUNTRY_BOUNDS: Dict[str, Tuple[float, float, float, float]] = {
    # (lat_min, lat_max, lng_min, lng_max)
    "India":      (6.0,  37.5,  68.0,  97.5),
    "Sri Lanka":  (5.5,  10.0,  79.5,  82.0),
    "Bangladesh": (20.5, 26.7,  88.0,  92.7),
    "Nepal":      (26.3, 30.5,  80.0,  88.3),
    "UAE":        (22.5, 26.5,  51.5,  56.5),
}

# Tunable thresholds
OUTLIER_HIGH_MULTIPLIER = 5.0    # >5x median revenue → flag
OUTLIER_LOW_MULTIPLIER = 0.1     # <10% median revenue → flag
CANNIBAL_DISTANCE_M = 200.0      # stores closer than this → potential cannibalisation
DUPLICATE_COORD_TOLERANCE = 1e-5 # ~1m precision


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in metres between two lat/lng points."""
    R = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _row_id(row: Dict[str, Any], idx: int) -> str:
    """Stable identifier for a row for reporting purposes."""
    for k in ("store_id", "id", "name", "store_name"):
        v = row.get(k)
        if v:
            return str(v)
    return f"row {idx}"


# ─────────────────────────────────────────────────────────────────────────────
# Stage A: Hard rules — block ingestion if any row fails
# ─────────────────────────────────────────────────────────────────────────────

def _check_hard_rules(
    rows: List[Dict[str, Any]],
    country: Optional[str] = None,
    require_revenue: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return a list of hard-rule violations. Empty list = ingestion can proceed.

    `require_revenue=False` is for Site Discovery mode where the tenant has
    no historical sales yet — only locations.
    """
    errors: List[Dict[str, Any]] = []
    seen_ids = set()

    bounds = COUNTRY_BOUNDS.get(country) if country else None

    for idx, row in enumerate(rows):
        rid = _row_id(row, idx)

        # Identifier
        ident = row.get("store_id") or row.get("id") or row.get("name") or row.get("store_name")
        if not ident:
            errors.append({"row": idx, "id": rid, "field": "store_id/name",
                           "issue": "Missing store identifier"})
        elif str(ident) in seen_ids:
            errors.append({"row": idx, "id": rid, "field": "store_id",
                           "issue": f"Duplicate identifier '{ident}'"})
        else:
            seen_ids.add(str(ident))

        # Latitude
        lat = safe_float(row.get("lat") or row.get("latitude"))
        if lat == 0.0:
            errors.append({"row": idx, "id": rid, "field": "lat",
                           "issue": "Latitude is missing or zero"})
        elif not (-90 <= lat <= 90):
            errors.append({"row": idx, "id": rid, "field": "lat",
                           "issue": f"Latitude {lat} is outside [-90, 90]"})
        elif bounds and not (bounds[0] <= lat <= bounds[1]):
            errors.append({"row": idx, "id": rid, "field": "lat",
                           "issue": f"Latitude {lat} is outside {country} bounds"})

        # Longitude
        lng = safe_float(row.get("lng") or row.get("longitude"))
        if lng == 0.0:
            errors.append({"row": idx, "id": rid, "field": "lng",
                           "issue": "Longitude is missing or zero"})
        elif not (-180 <= lng <= 180):
            errors.append({"row": idx, "id": rid, "field": "lng",
                           "issue": f"Longitude {lng} is outside [-180, 180]"})
        elif bounds and not (bounds[2] <= lng <= bounds[3]):
            errors.append({"row": idx, "id": rid, "field": "lng",
                           "issue": f"Longitude {lng} is outside {country} bounds"})

        # Revenue (only when required)
        if require_revenue:
            rev = safe_float(row.get("revenue") or row.get("sales"))
            if rev <= 0:
                errors.append({"row": idx, "id": rid, "field": "revenue",
                               "issue": "Revenue/sales is missing, zero or negative"})

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Stage B: Soft warnings — proceed with notice
# ─────────────────────────────────────────────────────────────────────────────

def _check_soft_warnings(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect data-quality concerns that don't block ingestion."""
    warnings: List[Dict[str, Any]] = []
    n = len(rows)
    if n == 0:
        return warnings

    revenues: List[float] = []
    coords: List[Tuple[int, str, float, float]] = []  # (idx, rid, lat, lng)

    for idx, row in enumerate(rows):
        rid = _row_id(row, idx)
        rev = safe_float(row.get("revenue") or row.get("sales"))
        if rev > 0:
            revenues.append(rev)
        lat = safe_float(row.get("lat") or row.get("latitude"))
        lng = safe_float(row.get("lng") or row.get("longitude"))
        if lat != 0.0 and lng != 0.0:
            coords.append((idx, rid, lat, lng))

    # Revenue outliers (vs median to be robust)
    if len(revenues) >= 5:
        median = statistics.median(revenues)
        high_thresh = median * OUTLIER_HIGH_MULTIPLIER
        low_thresh = median * OUTLIER_LOW_MULTIPLIER

        for idx, row in enumerate(rows):
            rid = _row_id(row, idx)
            rev = safe_float(row.get("revenue") or row.get("sales"))
            if rev > 0:
                if rev > high_thresh:
                    warnings.append({"row": idx, "id": rid, "field": "revenue",
                                     "issue": f"Revenue {rev:,.0f} is {rev/median:.1f}× the network median — verify this isn't a data entry error",
                                     "severity": "medium"})
                elif rev < low_thresh:
                    warnings.append({"row": idx, "id": rid, "field": "revenue",
                                     "issue": f"Revenue {rev:,.0f} is only {rev/median:.0%} of network median — verify this is a real operating store",
                                     "severity": "medium"})

    # Duplicate coordinates
    coord_map: Dict[Tuple[float, float], List[Tuple[int, str]]] = {}
    for idx, rid, lat, lng in coords:
        key = (round(lat / DUPLICATE_COORD_TOLERANCE), round(lng / DUPLICATE_COORD_TOLERANCE))
        coord_map.setdefault(key, []).append((idx, rid))
    for key, group in coord_map.items():
        if len(group) > 1:
            ids = [rid for _, rid in group]
            warnings.append({"row": group[0][0], "id": ids[0], "field": "lat/lng",
                             "issue": f"{len(group)} stores at the same coordinates: {', '.join(ids)}",
                             "severity": "high"})

    # Close-by stores (cannibalisation risk) — O(n²), fine for ≤ a few thousand stores
    if len(coords) <= 5000:
        flagged_pairs: set = set()
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                _, rid_i, lat_i, lng_i = coords[i]
                _, rid_j, lat_j, lng_j = coords[j]
                # Quick reject by approximate degree distance before haversine
                if abs(lat_i - lat_j) > 0.003 or abs(lng_i - lng_j) > 0.003:
                    continue
                d = _haversine_m(lat_i, lng_i, lat_j, lng_j)
                if 0 < d < CANNIBAL_DISTANCE_M:
                    pair_key = tuple(sorted([rid_i, rid_j]))
                    if pair_key not in flagged_pairs:
                        flagged_pairs.add(pair_key)
                        warnings.append({
                            "row": coords[i][0], "id": rid_i, "field": "lat/lng",
                            "issue": f"Within {d:.0f}m of '{rid_j}' — potential cannibalisation",
                            "severity": "low",
                        })

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def validate_stores(
    rows: List[Dict[str, Any]],
    country: Optional[str] = None,
    require_revenue: bool = True,
) -> Dict[str, Any]:
    """
    Run two-stage validation on a list of store records.

    Returns
    -------
    {
        "passed":           bool,   # True if hard rules all passed
        "row_count":        int,
        "valid_count":      int,    # rows without hard errors
        "errors":           [ {row, id, field, issue}, ... ],
        "warnings":         [ {row, id, field, issue, severity}, ... ],
        "health_score":     float,  # 0-100 composite score
        "summary":          str,    # human-readable single line
        "field_coverage":   { field_name: pct_filled, ... },
    }
    """
    if not rows:
        return {
            "passed": False, "row_count": 0, "valid_count": 0,
            "errors": [{"row": -1, "id": "-", "field": "file",
                        "issue": "No rows to validate"}],
            "warnings": [], "health_score": 0.0,
            "summary": "Empty dataset", "field_coverage": {},
        }

    errors = _check_hard_rules(rows, country=country, require_revenue=require_revenue)
    warnings = _check_soft_warnings(rows)

    # Field coverage (% of rows where each common field is filled)
    interesting_fields = ["region", "postal_code", "address", "name", "revenue"]
    coverage = {}
    for f in interesting_fields:
        filled = sum(1 for r in rows if r.get(f) not in (None, "", "NIL", "nil"))
        coverage[f] = round(filled * 100.0 / len(rows), 1)

    n = len(rows)
    bad_rows = {e["row"] for e in errors}
    valid_count = n - len(bad_rows)

    # Health score — simple composite
    passed = len(errors) == 0
    score = 100.0
    score -= len(errors) * 100.0 / n   # each hard error costs proportionally
    severity_weight = {"high": 5.0, "medium": 2.0, "low": 0.5}
    for w in warnings:
        score -= severity_weight.get(w.get("severity", "low"), 0.5)
    score = max(0.0, min(100.0, score))

    summary_parts = []
    if passed:
        summary_parts.append(f"{n} stores validated")
    else:
        summary_parts.append(f"{len(errors)} hard error(s)")
    if warnings:
        summary_parts.append(f"{len(warnings)} warning(s)")
    summary = " · ".join(summary_parts)

    log.info("validate_stores: country=%s rows=%d errors=%d warnings=%d score=%.1f",
             country, n, len(errors), len(warnings), score)

    return {
        "passed": passed,
        "row_count": n,
        "valid_count": valid_count,
        "errors": errors,
        "warnings": warnings,
        "health_score": round(score, 1),
        "summary": summary,
        "field_coverage": coverage,
    }
