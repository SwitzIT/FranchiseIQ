"""
District Aggregation Service (v3.5)
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Group stores by administrative district (admin2 level via offline reverse
geocoding) and produce a performance rollup.

v3.5: each store now carries TWO percentages â€”
  - pct_of_network_avg  â†’ store vs whole-network baseline (â‚¹1.43 Cr for Mio)
  - pct_of_district_avg â†’ store vs its district's average (peer-level signal)

This lets the UI show both lenses side-by-side: "this store is at 48% of
network AND 37% of its district peers â€” it's the clear laggard in Birbhum."
"""
from typing import Any, Dict, List

import reverse_geocoder as _rg

from app.utils import get_logger, safe_float

log = get_logger("services.district_aggregation")

DISTRICT_RENAME: Dict[str, str] = {
    "Haora":              "Howrah",
    "Hugli":              "Hooghly",
    "Barddhaman":         "Bardhaman",
    "Purba Medinipur":    "East Midnapore",
    "Paschim Medinipur":  "West Midnapore",
    "South 24 Paraganas": "South 24 Parganas",
    "Koch Bihar":         "Cooch Behar",
}

DEFAULT_ABOVE_THRESHOLD = 1.10
DEFAULT_BELOW_THRESHOLD = 0.90


def _normalise_district(raw: str) -> str:
    return DISTRICT_RENAME.get(raw, raw) if raw else "Unassigned"


def _reverse_geocode_missing(stores: List[Dict[str, Any]]) -> int:
    coords: List[tuple] = []
    indices: List[int] = []
    for i, s in enumerate(stores):
        if s.get("district"):
            continue
        lat = safe_float(s.get("lat"))
        lng = safe_float(s.get("lng"))
        if lat == 0.0 and lng == 0.0:
            continue
        coords.append((lat, lng))
        indices.append(i)

    if not coords:
        return 0

    results = _rg.search(coords, mode=1, verbose=False)
    for idx, r in zip(indices, results):
        stores[idx]["district"] = _normalise_district(r.get("admin2", ""))
        if not stores[idx].get("state"):
            stores[idx]["state"] = r.get("admin1", "")
        if not stores[idx].get("city"):
            stores[idx]["city"] = r.get("name", "")

    log.info("reverse-geocoded %d stores â†’ district", len(coords))
    return len(coords)


def aggregate_stores_by_district(
    stores: List[Dict[str, Any]],
    above_threshold: float = DEFAULT_ABOVE_THRESHOLD,
    below_threshold: float = DEFAULT_BELOW_THRESHOLD,
) -> Dict[str, Any]:
    if not stores:
        return {
            "districts": [], "network_avg": 0.0,
            "total_stores": 0, "total_districts": 0,
            "thresholds": {"above_pct": round(above_threshold * 100, 1),
                           "below_pct": round(below_threshold * 100, 1)},
        }

    _reverse_geocode_missing(stores)

    revenues = [safe_float(s.get("revenue", 0)) for s in stores]
    network_avg = sum(revenues) / len(revenues) if revenues else 0.0

    # Bucket stores by district, accumulating raw store info (we'll
    # compute district avg first, THEN derive pct_of_district_avg per store)
    district_map: Dict[str, Dict[str, Any]] = {}
    for s in stores:
        district = s.get("district") or "Unassigned"
        state    = s.get("state") or ""
        rev      = safe_float(s.get("revenue", 0))

        bucket = district_map.setdefault(district, {
            "district":      district,
            "state":         state,
            "total_revenue": 0.0,
            "raw_stores":    [],   # accumulate first, transform later
        })
        bucket["total_revenue"] += rev
        bucket["raw_stores"].append({
            "name":    s.get("name", "") or s.get("id", ""),
            "revenue": rev,
            "lat":     safe_float(s.get("lat")),
            "lng":     safe_float(s.get("lng")),
        })

    # Now build the final output with both percentages computed
    districts_out: List[Dict[str, Any]] = []
    for district, data in district_map.items():
        n = len(data["raw_stores"])
        if n == 0:
            continue
        district_avg = data["total_revenue"] / n
        pct = district_avg / network_avg if network_avg > 0 else 1.0

        if pct >= above_threshold:
            classification = "above"
        elif pct <= below_threshold:
            classification = "below"
        else:
            classification = "on_target"

        # Build per-store list with BOTH percentages
        store_list = []
        for s in data["raw_stores"]:
            store_list.append({
                "name":                 s["name"],
                "revenue":              round(s["revenue"], 2),
                "lat":                  s["lat"],
                "lng":                  s["lng"],
                "pct_of_network_avg":   round(s["revenue"] / network_avg  * 100, 1) if network_avg  > 0 else 0,
                "pct_of_district_avg":  round(s["revenue"] / district_avg * 100, 1) if district_avg > 0 else 0,
            })
        store_list.sort(key=lambda x: -x["revenue"])
        revenues_in_district = [s["revenue"] for s in store_list]

        districts_out.append({
            "district":           district,
            "state":              data["state"],
            "store_count":        n,
            "total_revenue":      round(data["total_revenue"], 2),
            "avg_revenue":        round(district_avg, 2),
            "min_revenue":        round(min(revenues_in_district), 2),
            "max_revenue":        round(max(revenues_in_district), 2),
            "pct_of_network_avg": round(pct * 100, 1),
            "classification":     classification,
            "stores":             store_list,
        })

    districts_out.sort(key=lambda d: -d["store_count"])

    log.info("district rollup: %d districts, %d stores, net avg %.2f",
             len(districts_out), len(stores), network_avg)

    return {
        "districts":       districts_out,
        "network_avg":     round(network_avg, 2),
        "total_stores":    len(stores),
        "total_districts": len(districts_out),
        "thresholds":      {"above_pct": round(above_threshold * 100, 1),
                            "below_pct": round(below_threshold * 100, 1)},
    }
