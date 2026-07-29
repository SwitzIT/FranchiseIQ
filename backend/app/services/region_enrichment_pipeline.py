"""
Region Enrichment Pipeline
──────────────────────────
Batch reverse-geocode at UPLOAD time, not query time. After this runs,
each store record carries its region/district/city/suburb directly —
no Nominatim calls during analytics queries.

Designed to be called from the upload flow:

    # in routes/data.py after load_data() finishes:
    from app.services.region_enrichment_pipeline import enrich_session_stores
    enrich_session_stores(session_id)

Performance: Nominatim's 1 req/sec rate limit means 384 stores takes
about 7 minutes on a cold cache. After the first run, subsequent runs
with overlapping coordinates are instant (disk cache hits).

For very large uploads (> 1000 stores), consider running this async
as a background task instead of blocking the upload response.
"""
from typing import Any, Dict

from app.utils import get_logger
from app.services import get_key, set_key, session_exists
from app.services.region_geocoding_service import enrich_stores_with_regions

log = get_logger("services.region_enrichment_pipeline")


def enrich_session_stores(session_id: str) -> Dict[str, Any]:
    """
    Reverse-geocode every store in a session and persist the enriched
    region info back to the session record.

    Returns a summary dict for logging / UI feedback.
    """
    if not session_exists(session_id):
        raise ValueError(f"Session {session_id} not found")

    results = get_key(session_id, "results")
    if not results or not results.get("stores"):
        log.info("no stores to enrich for session %s", session_id)
        return {"enriched_count": 0, "skipped": True,
                "message": "No stores to enrich"}

    stores = results["stores"]
    n = len(stores)
    log.info("enriching %d stores in session %s", n, session_id)

    enrich_stores_with_regions(stores)   # mutates in place

    # Persist back
    results["stores"] = stores
    set_key(session_id, "results", results)

    # Count how many got a region populated
    with_region = sum(1 for s in stores if s.get("region"))
    return {
        "enriched_count":   with_region,
        "total_stores":     n,
        "skipped":          False,
        "message":          f"Region enrichment complete: {with_region}/{n} stores have region info",
    }
