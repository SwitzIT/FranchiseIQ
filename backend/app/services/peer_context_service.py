"""
Peer-Context Benchmarking Service
─────────────────────────────────
Cluster stores by their CATCHMENT PROFILE (population, income, competitor
density, amenity richness in the surrounding area) and compare each store
to OTHER STORES IN THE SAME CLUSTER — not to the network average.

Why this matters
────────────────
A Park Street store doing ₹1.5 Cr looks "above network avg" (₹1.43 Cr) using
naive aggregation. But Park Street stores typically do ₹2.5 Cr. So it's
actually UNDERPERFORMING its peer group.

Conversely, a Bongaon (rural town) store doing ₹1.5 Cr looks merely "above
avg" naively, but rural peers do ₹1.0 Cr. So it's a TRUE OUTPERFORMER — the
kind of store you'd want to replicate.

Output:
- A cluster label per store
- Cluster averages
- pct_of_peer_avg per store (analogous to pct_of_network_avg)
- Classification (above/on_target/below) vs peer benchmark
"""
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from app.utils import get_logger, safe_float

log = get_logger("services.peer_context")

# ── Tunables ────────────────────────────────────────────────────────────────
DEFAULT_K = 4                # number of peer clusters
MIN_STORES_PER_CLUSTER = 3   # below this we collapse the cluster
ABOVE_PEER_THRESHOLD = 1.10  # ≥110% of peer avg → "above peers"
BELOW_PEER_THRESHOLD = 0.90  # ≤ 90% of peer avg → "below peers"

# Human-readable labels we assign post-hoc based on feature centroids.
# Order: (population_pct, income_pct, competitor_pct) — high/low
CLUSTER_NAMES_FALLBACK = [
    "urban premium", "suburban family", "high-street commercial", "rural town",
    "transit hub", "industrial corridor", "secondary urban",
]


# ─────────────────────────────────────────────────────────────────────────────
# Feature extraction
# ─────────────────────────────────────────────────────────────────────────────

def _features_for_store(store: Dict[str, Any]) -> List[float]:
    """
    Build the catchment-profile feature vector for a single store.

    Expected enrichment keys (added by demographics_service and amenities_service):
      catchment_population        (people within X km)
      catchment_income_index      (relative wealth, 0-1 or 0-100)
      catchment_competitor_count  (count of competitor stores within X km)
      catchment_amenity_count     (POI count within X km)

    All are gracefully filled with 0.0 if missing — k-means will treat
    those stores as their own cluster, which is the right failure mode.
    """
    return [
        safe_float(store.get("catchment_population", 0)),
        safe_float(store.get("catchment_income_index", 0)),
        safe_float(store.get("catchment_competitor_count", 0)),
        safe_float(store.get("catchment_amenity_count", 0)),
    ]


def _label_cluster(centroid: np.ndarray, percentiles: List[np.ndarray]) -> str:
    """
    Generate a human-readable label for a cluster based on where its centroid
    sits in the distribution of all centroids.

    centroid: shape (n_features,)
    percentiles: list of arrays, one per feature, giving the 33/67 percentile cuts
    """
    pop, income, compet, amenity = centroid
    pop_pct, income_pct, compet_pct, _ = percentiles

    def level(value, thresholds):
        if value >= thresholds[1]:
            return "high"
        elif value >= thresholds[0]:
            return "mid"
        else:
            return "low"

    pop_l = level(pop, pop_pct)
    inc_l = level(income, income_pct)
    com_l = level(compet, compet_pct)

    # Canonical labels for common patterns
    if pop_l == "high" and inc_l == "high":
        return "urban premium"
    if pop_l == "high" and com_l == "high":
        return "high-street commercial"
    if pop_l == "high" and inc_l == "mid":
        return "secondary urban"
    if pop_l == "mid" and inc_l == "mid":
        return "suburban family"
    if pop_l == "low" and com_l == "low":
        return "rural town"
    if pop_l == "low" and inc_l == "high":
        return "premium outpost"
    return f"{pop_l}-pop {inc_l}-income"


# ─────────────────────────────────────────────────────────────────────────────
# Main API
# ─────────────────────────────────────────────────────────────────────────────

def cluster_stores_by_catchment(
    stores: List[Dict[str, Any]],
    k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Cluster stores by their catchment profile and benchmark each store
    against its cluster peers.

    Parameters
    ----------
    stores : list of store dicts (must have revenue + catchment_* features)
    k : number of clusters (default DEFAULT_K, capped by sqrt(n)/2)

    Returns
    -------
    {
        "clusters": [
            {
                "label":          "urban premium",
                "cluster_id":     0,
                "store_count":    27,
                "avg_revenue":    25_000_000,
                "median_revenue": 23_000_000,
                "centroid_features": {pop, income, competitor, amenity}
            }, ...
        ],
        "stores": [
            {
                "name":              "Park Street",
                "cluster_id":        0,
                "cluster_label":     "urban premium",
                "revenue":           18_000_000,
                "peer_avg":          25_000_000,
                "pct_of_peer_avg":   72.0,
                "classification":    "below",      # vs peers
            }, ...
        ],
        "k_used":           int,
        "feature_coverage": float,   # 0-1, fraction of stores with non-zero features
    }
    """
    n = len(stores)
    if n < 4:
        log.info("peer_context: only %d stores — clustering not meaningful, returning singleton group", n)
        return _singleton_cluster_response(stores)

    # Build feature matrix
    X = np.array([_features_for_store(s) for s in stores])

    # Coverage: how many stores have at least one non-zero feature?
    non_zero_mask = (X.sum(axis=1) > 0)
    coverage = float(non_zero_mask.sum()) / n

    if coverage < 0.5:
        log.warning("peer_context: only %.0f%% of stores have catchment features — "
                    "clustering will be noisy. Returning singleton group.", coverage * 100)
        return _singleton_cluster_response(stores)

    # Standardise features so they're comparable in k-means
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Pick k: caller's value, or DEFAULT_K, capped by sqrt(n)/2 to keep clusters meaningful
    max_k = max(2, int(np.sqrt(n) / 2))
    k_used = min(k or DEFAULT_K, max_k)

    km = KMeans(n_clusters=k_used, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)

    # Compute percentiles per feature (un-scaled) for labelling
    feature_percentiles = [
        (np.percentile(X[:, i], 33), np.percentile(X[:, i], 67))
        for i in range(X.shape[1])
    ]

    # Map cluster_id → label using un-scaled centroids
    centroids_unscaled = scaler.inverse_transform(km.cluster_centers_)
    cluster_labels: Dict[int, str] = {}
    used_labels: set = set()
    for cid in range(k_used):
        base = _label_cluster(centroids_unscaled[cid], feature_percentiles)
        label = base
        # Disambiguate if two clusters get the same name
        suffix = 2
        while label in used_labels:
            label = f"{base} {suffix}"
            suffix += 1
        used_labels.add(label)
        cluster_labels[cid] = label

    # Compute per-cluster stats
    revenues = np.array([safe_float(s.get("revenue", 0)) for s in stores])
    clusters_out: List[Dict[str, Any]] = []
    cluster_avgs: Dict[int, float] = {}

    for cid in range(k_used):
        mask = (labels == cid)
        store_count = int(mask.sum())
        if store_count == 0:
            continue
        cluster_rev = revenues[mask]
        avg = float(cluster_rev.mean()) if store_count else 0.0
        median = float(np.median(cluster_rev)) if store_count else 0.0
        cluster_avgs[cid] = avg

        centroid = centroids_unscaled[cid]
        clusters_out.append({
            "cluster_id":    cid,
            "label":         cluster_labels[cid],
            "store_count":   store_count,
            "avg_revenue":   round(avg, 2),
            "median_revenue": round(median, 2),
            "centroid_features": {
                "population":         round(float(centroid[0]), 2),
                "income_index":       round(float(centroid[1]), 4),
                "competitor_count":   round(float(centroid[2]), 2),
                "amenity_count":      round(float(centroid[3]), 2),
            },
        })

    # Annotate each store with its cluster + peer comparison
    stores_out: List[Dict[str, Any]] = []
    for i, s in enumerate(stores):
        cid = int(labels[i])
        rev = safe_float(s.get("revenue", 0))
        peer_avg = cluster_avgs.get(cid, 0.0)
        pct = (rev / peer_avg) if peer_avg > 0 else 1.0

        if pct >= ABOVE_PEER_THRESHOLD:
            classification = "above"
        elif pct <= BELOW_PEER_THRESHOLD:
            classification = "below"
        else:
            classification = "on_target"

        stores_out.append({
            "name":               s.get("name"),
            "lat":                safe_float(s.get("lat")),
            "lng":                safe_float(s.get("lng")),
            "revenue":            rev,
            "cluster_id":         cid,
            "cluster_label":      cluster_labels[cid],
            "peer_avg":           round(peer_avg, 2),
            "pct_of_peer_avg":    round(pct * 100, 1),
            "classification":     classification,
        })

    log.info(
        "peer_context: %d stores into %d clusters | %s",
        n, k_used,
        ", ".join(f"{c['label']}={c['store_count']}" for c in clusters_out),
    )

    return {
        "clusters":         clusters_out,
        "stores":           stores_out,
        "k_used":           k_used,
        "feature_coverage": round(coverage, 3),
    }


def _singleton_cluster_response(stores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback when clustering isn't meaningful (too few stores or no features)."""
    revenues = [safe_float(s.get("revenue", 0)) for s in stores]
    avg = sum(revenues) / len(revenues) if revenues else 0.0
    return {
        "clusters": [{
            "cluster_id": 0,
            "label": "all stores",
            "store_count": len(stores),
            "avg_revenue": round(avg, 2),
            "median_revenue": round(float(np.median(revenues)) if revenues else 0.0, 2),
            "centroid_features": {},
        }],
        "stores": [{
            "name": s.get("name"),
            "lat": safe_float(s.get("lat")),
            "lng": safe_float(s.get("lng")),
            "revenue": safe_float(s.get("revenue", 0)),
            "cluster_id": 0,
            "cluster_label": "all stores",
            "peer_avg": round(avg, 2),
            "pct_of_peer_avg": round((safe_float(s.get("revenue", 0)) / avg * 100) if avg > 0 else 100.0, 1),
            "classification": "on_target",
        } for s in stores],
        "k_used": 1,
        "feature_coverage": 0.0,
    }
