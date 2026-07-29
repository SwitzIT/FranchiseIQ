"""
Agent 4 — Scoring / Feature Engineering Service
Orchestrates the full pipeline:
  1. Standardise uploaded store / request DataFrames
  2. Amenity counting (via amenities_service)
  3. Demographic mapping (nearest neighbour)
  4. Competition & cannibalization analysis
  5. Business-unit clustering (if provided)
  6. RF model training → candidate prediction
  7. Grid candidate generation (when no requests uploaded)
Returns top_picks list + full results DataFrame.
"""
import io
import uuid
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from scipy.optimize import minimize

from app.config import (
    get_state_config, get_real_estate_path, BUFFER_RADIUS_M, GRID_STEP_DEG, TOP_N_LOCATIONS,
    ENABLE_OSM_GEO_FEATURES,
)
from app.models.affinity_model import FranchiseModel  # v4.0: amenity-affinity scoring, replaces RF regression
from app.services.amenities_service import count_amenities_near_points
from app.services.clustering_service import assign_business_units
from app.services.real_estate_service import load_and_preprocess_real_estate, enrich_with_real_estate
from app.services.osm_geographic_service import get_roads_and_landuse, enrich_with_geography
from app.services.local_competitor_service import load_competitors, count_competitors_near_points
from app.utils import (
    get_logger, haversine_vectorized, nearest_neighbor_index, safe_int, safe_float,
)

log = get_logger("scoring_service")

# ─────────────────────────────────────────────────────────────
# COLUMN NORMALISATION
# ─────────────────────────────────────────────────────────────
_RENAME_MAP = {
    "store id":       "Store_ID",
    "store name":     "Store_Name",
    "name":           "Store_Name",
    "customer name":  "Store_Name",
    "address line 1": "Address",
    "locality":       "Locality",
    "latitude":       "Latitude",  "lat": "Latitude",
    "longitude":      "Longitude", "lon": "Longitude", "long": "Longitude",
    "sales":          "Sales",     "sales 2025": "Sales",
    "returns":        "Returns",   "returns 2025": "Returns",
    "district":       "District",
    "region":         "Region",
    "zone":           "Region",
    "area":           "Region",
    "territory":      "Region",
}


# ─────────────────────────────────────────────────────────────
# SCORING + GUARDRAILS (v6.2 — factored out so it can be re-run
# identically after the snap step moves coordinates)
# ─────────────────────────────────────────────────────────────
def distance_penalty(d):
    d = float(d) if pd.notnull(d) else 100.0
    if d < 1.0: return 0.2
    elif d < 2.0: return 0.5
    elif d < 3.0: return 0.75
    else: return 1.0


def _score_and_flag(df: pd.DataFrame, model, has_bu: bool) -> pd.DataFrame:
    """Runs the trained model + every guardrail/flag/verdict on df, in the
    correct order. Used for the initial grid AND again after snapping —
    the snap step moves coordinates, so everything scored against the
    pre-snap point must be recomputed against the real, final point."""
    df = model.predict(df)

    if has_bu and "BU_Weight" in df.columns:
        df["Final_Score"] = np.clip(df["Final_Score"] * df["BU_Weight"] * 1.05, 0, 100)

    if "Nearest_Store_km" in df.columns:
        df["Distance_Penalty"] = df["Nearest_Store_km"].apply(distance_penalty)
        df["Is_Too_Close"] = df["Nearest_Store_km"] < 1.0
        df["Adjusted_Final_Score"] = df["Final_Score"] * df["Distance_Penalty"]
        df["Final_Score"] = df["Adjusted_Final_Score"]

    # Nearby-underperformance guardrail (v6.2): direct evidence beats
    # inferred similarity — see _apply_nearby_underperformance_guardrail.
    df = _apply_nearby_underperformance_guardrail(df, model.median_existing_revenue)

    # Profitability signal (v6.2) — data-honest cost-vs-revenue percentile
    # proxy, not a fabricated ₹ profit number. See _apply_profitability_flag.
    df = _apply_profitability_flag(df)

    df = df.sort_values("Final_Score", ascending=False).reset_index(drop=True)

    # Plain-language verdict (v6.2)
    df = _apply_verdict(df)
    return df


def standardise_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    rename = {c: _RENAME_MAP[c.lower()] for c in df.columns if c.lower() in _RENAME_MAP}
    df.rename(columns=rename, inplace=True)
    for col in ("Latitude", "Longitude"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
    if "Latitude" in df.columns and "Longitude" in df.columns:
        df = df.dropna(subset=["Latitude", "Longitude"])
        df = df[(df["Latitude"] != 0) | (df["Longitude"] != 0)]
    # Default Region to "Unassigned" if not present
    if "Region" not in df.columns:
        df["Region"] = "Unassigned"
    else:
        df["Region"] = df["Region"].fillna("Unassigned").astype(str).str.strip()
        df["Region"] = df["Region"].replace("", "Unassigned")
    return df.reset_index(drop=True)


def parse_uploaded_df(file_bytes: bytes, filename: str) -> pd.DataFrame:
    suffix = filename.rsplit(".", 1)[-1].lower()
    buf = io.BytesIO(file_bytes)
    try:
        if suffix in ("xlsx", "xls"):
            try:
                df = pd.read_excel(buf, sheet_name="Franchise Data")
            except Exception:
                buf.seek(0)
                df = pd.read_excel(buf)
        else:
            df = pd.read_csv(buf)
    except Exception as e:
        raise ValueError(f"Could not parse '{filename}': {e}") from e
    return standardise_df(df)


# ─────────────────────────────────────────────────────────────
# FULL PIPELINE
# ─────────────────────────────────────────────────────────────
def run_pipeline(
    country: str,
    state: str,
    stores_df: pd.DataFrame,
    demographics_df: pd.DataFrame,
    amenities_gdf: gpd.GeoDataFrame,
    requests_df: pd.DataFrame | None = None,
    bu_df: pd.DataFrame | None = None,
    top_n: int = TOP_N_LOCATIONS,
) -> dict:
    """
    Full scoring pipeline. Returns a results dict ready for the API response.
    """
    cfg = get_state_config(country, state)
    has_bu = bu_df is not None and not bu_df.empty
    log.info(f"[Pipeline] {country}/{state} | stores={len(stores_df)} "
             f"| requests={len(requests_df) if requests_df is not None else 0} "
             f"| BU={has_bu}")

    # Load Real Estate Data
    re_path = get_real_estate_path(country, state)
    re_gdf = gpd.GeoDataFrame()
    if re_path:
        re_gdf = load_and_preprocess_real_estate(re_path)

    # v5.0 — local competitor density (Mio_competitor.xlsx), no live Places API
    competitors_df = load_competitors(country, state)

    # v3.7 — OSM roads & landuse. OFF by default (v5.0): set
    # ENABLE_OSM_GEO_FEATURES=true only if you want this extra signal and are
    # fine with a live Overpass/osmnx fetch on first run per state.
    roads_gdf, landuse_gdf = None, None
    if ENABLE_OSM_GEO_FEATURES:
        try:
            roads_gdf, landuse_gdf = get_roads_and_landuse(country, state)
        except Exception as e:
            log.warning(f"[Pipeline] OSM geographic fetch failed ({e}) - continuing without road/landuse features")
    else:
        log.info("[Pipeline] ENABLE_OSM_GEO_FEATURES=false — skipping road/landuse enrichment, no network calls made")

    # ── 1. Prepare stores ─────────────────────────────────────
    stores_df = _add_adjusted_sales(stores_df)
    stores_df = _enrich(stores_df, demographics_df, amenities_gdf, re_gdf, stores_df, cfg, is_store=True,
                        roads_gdf=roads_gdf, landuse_gdf=landuse_gdf, competitors_df=competitors_df)
    if has_bu:
        stores_df = assign_business_units(stores_df, bu_df)

    # ── 2. Prepare candidates ─────────────────────────────────
    if requests_df is not None and not requests_df.empty:
        cands_df = _enrich(requests_df.copy(), demographics_df, amenities_gdf,
                           re_gdf, stores_df, cfg, is_store=False,
                           roads_gdf=roads_gdf, landuse_gdf=landuse_gdf, competitors_df=competitors_df)
        if has_bu:
            cands_df = assign_business_units(cands_df, bu_df)
    else:
        cands_df = _generate_grid(cfg, demographics_df)
        cands_df = _enrich(cands_df, demographics_df, amenities_gdf,
                           re_gdf, stores_df, cfg, is_store=False,
                           roads_gdf=roads_gdf, landuse_gdf=landuse_gdf, competitors_df=competitors_df)
        if has_bu:
            cands_df = assign_business_units(cands_df, bu_df)

    # ── 3. Fit amenity-affinity weights + score candidates ────
    model = FranchiseModel()
    train_metrics = model.train(stores_df, has_bu=has_bu)
    log.info(f"[Pipeline] Model R²={train_metrics.get('r2_test', 'N/A')} "
             f"MAE={train_metrics.get('mae_test', 'N/A')} method={train_metrics.get('validation')}")
    
    # Cap extreme demand values before scoring layer
    if "Population" in cands_df.columns:
        cands_df["Population"] = cands_df["Population"].clip(upper=500000)

    cands_df = _score_and_flag(cands_df, model, has_bu)

    # v3.8.3 - branch based on grid mode (no requests uploaded) vs uploaded mode
    if requests_df is None or requests_df.empty:
        # GRID MODE: opinionated filtering / diversity / look-alike snap
        mio_density = _v382_compute_store_density_profile(stores_df, amenities_gdf, cluster_radius_m=500)
        log.info(f"[Calibration] Mio store density (500m cluster) - n={mio_density['n_stores']}, median={mio_density['median']:.0f}, p10={mio_density['p10']:.0f}, p25={mio_density['p25']:.0f}, mean={mio_density['mean']:.1f}")
        min_cluster_threshold = max(5, int(mio_density.get('p10', 10)))
        log.info(f"[Calibration] using min_cluster_threshold={min_cluster_threshold} (max of 5 floor and Mio p10)")

        viable_df = _filter_viable_candidates(cands_df, min_amenities=5, min_population=1000)
        diverse_df = _select_diverse_top_picks(viable_df, n=top_n * 3, min_distance_km=15.0)
        snapped_df = _snap_or_drop_to_dense_cluster(diverse_df, amenities_gdf,
                                                     min_cluster_size=min_cluster_threshold,
                                                     cluster_radius_m=500, hex_half_km=3.0)

        # ── v6.2 — RE-ENRICH + RE-SCORE at the SNAPPED coordinates ──────
        # Snapping moves each pick's lat/lon to a real nearby amenity
        # anchor point — verified up to ~3km from the original grid point
        # it was scored at. Every number shown for that pin (amenities,
        # nearby-store performance, revenue, drivers, guardrails) must
        # reflect the FINAL displayed coordinate, not the pre-snap one, or
        # the explanation doesn't match the map. Re-running the same
        # enrichment + scoring here guarantees that.
        if snapped_df is not None and len(snapped_df) > 0:
            snapped_df = _enrich(snapped_df, demographics_df, amenities_gdf, re_gdf, stores_df, cfg,
                                 is_store=False, roads_gdf=roads_gdf, landuse_gdf=landuse_gdf,
                                 competitors_df=competitors_df)
            if has_bu:
                snapped_df = assign_business_units(snapped_df, bu_df)
            if "Population" in snapped_df.columns:
                snapped_df["Population"] = snapped_df["Population"].clip(upper=500000)
            snapped_df = _score_and_flag(snapped_df, model, has_bu)

        top_df = snapped_df.head(top_n).reset_index(drop=True)
    else:
        # UPLOADED MODE: honest scoring of user-supplied locations - no filtering, no snap
        log.info(f"[Pipeline] Uploaded mode - scoring {len(cands_df)} user-supplied locations as-is (no viability filter, no diversity, no snap)")
        top_df = cands_df.head(top_n).reset_index(drop=True)
    
    if len(top_df) < top_n:
        log.warning(f"[Pipeline] Only found {len(top_df)} candidates. Requested top {top_n}.")

    def _amenities_to_records(gdf):
        if gdf is None or gdf.empty: return []
        records = []
        for idx, row in gdf.iterrows():
            if not row.geometry or row.geometry.is_empty: continue
            
            # Handle non-point geometries (Polygons) by using their centroid
            g = row.geometry
            pt = g if g.geom_type == 'Point' else g.centroid
            
            cat = row.get("amenity") or row.get("shop") or row.get("leisure")
            records.append({
                "lat": safe_float(pt.y),
                "lng": safe_float(pt.x),
                "type": str(cat),
                "name": str(row.get("name", "")),
            })
        return records

    def _real_estate_to_records(gdf):
        if gdf is None or gdf.empty: return []
        records = []
        for idx, row in gdf.iterrows():
            if not row.geometry or row.geometry.is_empty: continue
            pt = row.geometry if row.geometry.geom_type == 'Point' else row.geometry.centroid
            records.append({
                "lat": safe_float(pt.y),
                "lng": safe_float(pt.x),
                "price": safe_float(row.get("price")),
                "rent": safe_float(row.get("rent")),
                "property_cost_index": safe_float(row.get("property_cost_index")),
                "property_growth_score": safe_float(row.get("property_growth_score")),
            })
        return records

    region_stats = _compute_region_stats(stores_df, cands_df, demographics_df)

    return {
        "top_picks":      _to_records(top_df, "prediction"),
        "all_candidates": _to_records(cands_df, "prediction"),
        "stores":         _to_records(stores_df, "store"),
        "requests":       _to_records(requests_df, "request") if requests_df is not None else [],
        "business_units": _to_records(bu_df, "bu") if has_bu else [],
        "amenities":      _amenities_to_records(amenities_gdf),
        "real_estate":    _real_estate_to_records(re_gdf) if not re_gdf.empty else [],
        "kpis":           _compute_kpis(stores_df, top_df),
        "model_metrics":  train_metrics,
        "region_stats":   region_stats,
    }


def _compute_region_stats(stores_df: pd.DataFrame, cands_df: pd.DataFrame, demographics_df: pd.DataFrame) -> list[dict]:
    # Group existing stores by district
    store_stats = {}
    if "District" in stores_df.columns and "Sales" in stores_df.columns:
        grouped = stores_df.groupby("District")
        for district, group in grouped:
            sales = pd.to_numeric(group["Sales"], errors="coerce").fillna(0)
            store_stats[district] = {
                "store_count": len(group),
                "total_sales": float(sales.sum()),
                "avg_sales": float(sales.mean()),
            }

    # Group candidates by district
    cand_stats = {}
    if "District" in cands_df.columns and "Final_Score" in cands_df.columns:
        grouped = cands_df.groupby("District")
        for district, group in grouped:
            score = pd.to_numeric(group["Final_Score"], errors="coerce").fillna(0)
            cand_stats[district] = {
                "candidate_count": len(group),
                "avg_score": float(score.mean()),
            }

    # Group demographics by district
    demog_stats = {}
    if "District" in demographics_df.columns:
        pop_col = "Population" if "Population" in demographics_df else demographics_df.columns[2]
        inc_cols = [c for c in demographics_df.columns if "income" in c.lower()]
        inc_col = inc_cols[0] if inc_cols else None
        
        grouped = demographics_df.groupby("District")
        for district, group in grouped:
            pop = pd.to_numeric(group[pop_col], errors="coerce").fillna(0)
            inc = pd.to_numeric(group[inc_col], errors="coerce").fillna(0) if inc_col else pd.Series([0]*len(group))
            demog_stats[district] = {
                "avg_population": float(pop.mean()),
                "avg_income": float(inc.mean()),
            }

    # Combine all stats
    all_districts = set(store_stats.keys()) | set(cand_stats.keys()) | set(demog_stats.keys())
    result = []
    
    mean_sales = stores_df["Sales"].mean() if "Sales" in stores_df.columns and len(stores_df) > 0 else 0
    
    for dist in all_districts:
        if not dist or pd.isna(dist) or str(dist).lower() in ("nan", "unknown", "n/a", ""):
            continue
        
        s = store_stats.get(dist, {"store_count": 0, "total_sales": 0.0, "avg_sales": 0.0})
        c = cand_stats.get(dist, {"candidate_count": 0, "avg_score": 0.0})
        d = demog_stats.get(dist, {"avg_population": 0.0, "avg_income": 0.0})
        
        avg_sales = s["avg_sales"]
        avg_score = c["avg_score"]
        
        # Performance label
        if s["store_count"] > 0:
            if mean_sales > 0:
                performance = "High Performing" if avg_sales >= 1.1 * mean_sales else \
                              "Low Performing" if avg_sales <= 0.9 * mean_sales else \
                              "Average Performing"
            else:
                performance = "Average Performing"
        else:
            performance = "High Potential" if avg_score >= 60 else "Moderate Potential"
            
        result.append({
            "district": str(dist),
            "store_count": int(s["store_count"]),
            "total_sales": float(s["total_sales"]),
            "avg_sales": float(s["avg_sales"]),
            "candidate_count": int(c["candidate_count"]),
            "avg_score": float(avg_score),
            "avg_population": float(d["avg_population"]),
            "avg_income": float(d["avg_income"]),
            "performance": performance,
        })
        
    # Sort by store_count desc, avg_sales desc, avg_score desc
    result.sort(key=lambda x: (x["store_count"] > 0, x["avg_sales"], x["avg_score"]), reverse=True)
    return result


# ─────────────────────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────
def _enrich(df, demographics_df, amenities_gdf, re_gdf, stores_df, cfg, is_store,
            roads_gdf=None, landuse_gdf=None, competitors_df=None):
    df = count_amenities_near_points(df, amenities_gdf, buffer_m=BUFFER_RADIUS_M)
    df = _map_demographics(df, demographics_df)
    df = _competition_analysis(df, stores_df, is_store=is_store)
    df = enrich_with_real_estate(df, re_gdf)
    df = _cannibalization(df)
    # v6.1 — actual nearby-store PERFORMANCE, not just distance/count.
    # This is what Cannibalization_Score/stores_5km were missing: whether
    # existing stores near this point are actually selling well.
    df = _nearby_store_performance(df, stores_df, is_store=is_store)
    # v5.0 — local competitor density (Mio_competitor.xlsx), no network call
    df = count_competitors_near_points(df, competitors_df)
    # v3.7 — geographic features (roads + landuse), only if explicitly enabled
    if roads_gdf is not None or landuse_gdf is not None:
        df = enrich_with_geography(df, roads_gdf, landuse_gdf)
    if cfg.get("default_kitchen"):
        ck_lat, ck_lon = cfg["default_kitchen"]
        df["Kitchen_Dist_km"] = haversine_vectorized(
            df["Latitude"].values, df["Longitude"].values, ck_lat, ck_lon
        )
    else:
        df["Kitchen_Dist_km"] = 0.0
    return df


def _map_demographics(df, demographics_df):
    d_lats = demographics_df["Latitude"].values
    d_lons = demographics_df["Longitude"].values
    pop_col = "Population" if "Population" in demographics_df else demographics_df.columns[2]
    d_pop = demographics_df[pop_col].values
    inc_cols = [c for c in demographics_df.columns if "income" in c.lower()]
    d_inc = demographics_df[inc_cols[0]].values if inc_cols else np.zeros(len(demographics_df))
    
    pops, incs, districts = [], [], []
    for lat, lon in zip(df["Latitude"], df["Longitude"]):
        idx, _ = nearest_neighbor_index(d_lats, d_lons, lat, lon)
        pops.append(d_pop[idx])
        incs.append(d_inc[idx])
        districts.append(demographics_df["District"].values[idx] if "District" in demographics_df.columns else "Unknown")
        
    df["Population"] = pd.to_numeric(pd.Series(pops), errors="coerce").fillna(0).values
    df["Income"]     = pd.to_numeric(pd.Series(incs), errors="coerce").fillna(0).values
    
    if "District" not in df.columns:
        df["District"] = districts
    else:
        df["District"] = df["District"].fillna(pd.Series(districts))
    return df


def _competition_analysis(df, stores_df, is_store):
    s_lats  = stores_df["Latitude"].values
    s_lons  = stores_df["Longitude"].values
    s_names = stores_df["Store_Name"].values if "Store_Name" in stores_df.columns else np.array([""] * len(s_lats))
    nd, nn, s2, s5 = [], [], [], []
    for enum_i, (_, row) in enumerate(df.iterrows()):
        dists = haversine_vectorized(s_lats, s_lons, row["Latitude"], row["Longitude"])
        if is_store:
            dists[enum_i] = np.inf
        idx = int(np.argmin(dists)) if len(dists) else 0
        nd.append(safe_float(dists[idx]) if len(dists) else 100.0)
        nn.append(str(s_names[idx]) if len(s_names) else "")
        s2.append(int(np.sum(dists <= 2.0)))
        s5.append(int(np.sum(dists <= 5.0)))
    df["Nearest_Store_km"]   = nd
    df["Nearest_Store_Name"] = nn
    df["stores_2km"]         = s2
    df["stores_5km"]         = s5
    return df


def _cannibalization(df):
    def _score(d):
        if d < 1.0:   return 0.0
        elif d < 3.0: return 0.3
        elif d < 6.0: return 1.0
        elif d < 10.: return 0.7
        return 0.4
    df["Cannibalization_Score"] = df["Nearest_Store_km"].apply(_score)
    return df


def _nearby_store_performance(df, stores_df, is_store, radius_km: float = 5.0):
    """v6.1 — the direct signal the model was missing: are the existing
    stores actually near this point selling WELL, not just how many are
    nearby. Cannibalization_Score/stores_2km/stores_5km only ever counted
    density/distance; none of them looked at the sales those nearby stores
    actually achieved. A cluster of underperforming stores right next to a
    candidate is strong first-hand evidence about that micro-market —
    stronger than inferring quality from amenity/demographic similarity
    alone.

    When no store is within radius_km, falls back to the network-wide mean
    (a NEUTRAL value) rather than 0 or NaN — a truly unstudied area
    shouldn't be penalized as if it were a proven underperformer.
    """
    s_lats = stores_df["Latitude"].values
    s_lons = stores_df["Longitude"].values
    s_sales = pd.to_numeric(
        stores_df.get("Adjusted_Sales", stores_df.get("Sales", 0)), errors="coerce"
    ).fillna(0).values
    network_mean = float(np.mean(s_sales)) if len(s_sales) else 0.0

    avgs, counts = [], []
    for enum_i, (_, row) in enumerate(df.iterrows()):
        dists = haversine_vectorized(s_lats, s_lons, row["Latitude"], row["Longitude"])
        if is_store:
            dists[enum_i] = np.inf
        mask = dists <= radius_km
        n_nearby = int(np.sum(mask))
        if n_nearby > 0:
            avgs.append(float(np.mean(s_sales[mask])))
        else:
            avgs.append(network_mean)
        counts.append(n_nearby)

    df["Nearby_Store_Avg_Sales"] = avgs
    df["Nearby_Store_Count_Perf"] = counts  # how many stores that average is based on; 0 = neutral fallback used
    return df


def _apply_nearby_underperformance_guardrail(df, median_existing_revenue,
                                              min_nearby: int = 3, threshold_ratio: float = 0.75,
                                              penalty_multiplier: float = 0.55):
    """v6.2 — hard business rule: if >= min_nearby real existing stores
    within 5km are averaging under threshold_ratio × the network median,
    directly penalize Final_Score, don't just leave it to the model's
    correlation-based weight for Nearby_Store_Avg_Sales (which testing
    showed only carries modest statistical weight on its own)."""
    if "Nearby_Store_Count_Perf" not in df.columns or "Nearby_Store_Avg_Sales" not in df.columns:
        df["Nearby_Underperformance_Flag"] = False
        return df
    threshold = threshold_ratio * median_existing_revenue
    flag = (df["Nearby_Store_Count_Perf"] >= min_nearby) & (df["Nearby_Store_Avg_Sales"] < threshold)
    df["Nearby_Underperformance_Flag"] = flag
    if "Final_Score" in df.columns:
        df.loc[flag, "Final_Score"] = df.loc[flag, "Final_Score"] * penalty_multiplier
    try:
        log.info(f"[Guardrail] {int(flag.sum())}/{len(df)} candidates flagged for nearby-store "
                 f"underperformance (>= {min_nearby} stores within 5km averaging < "
                 f"₹{threshold:,.0f}), Final_Score penalized ×{penalty_multiplier}")
    except Exception:
        pass
    return df


def _apply_profitability_flag(df, cost_col_candidates=("avg_property_price_3km", "property_cost_index"),
                               gap_threshold: float = 20.0):
    """v6.2 — data-honest profitability proxy. The real estate source has
    NO rent or operating-cost figures, only purchase price per sqft, so we
    do not fabricate a ₹ profit estimate. Instead: rank this candidate's
    property cost against every other candidate in this batch, rank its
    predicted revenue the same way, and flag a meaningful gap between the
    two as "Cost-Heavy" (cost ranks much higher than revenue) or
    "Cost-Efficient" (the reverse) — an honest relative signal, not a
    precise financial forecast."""
    cost_col = next((c for c in cost_col_candidates if c in df.columns and df[c].fillna(0).sum() > 0), None)
    if cost_col is None or "Predicted_Revenue" not in df.columns or len(df) < 3:
        df["Cost_Percentile"] = np.nan
        df["Revenue_Percentile"] = np.nan
        df["Profitability_Flag"] = "Insufficient Data"
        return df

    df["Cost_Percentile"] = df[cost_col].rank(pct=True) * 100.0
    df["Revenue_Percentile"] = df["Predicted_Revenue"].rank(pct=True) * 100.0
    gap = df["Cost_Percentile"] - df["Revenue_Percentile"]
    df["Profitability_Flag"] = np.where(
        gap > gap_threshold, "Cost-Heavy",
        np.where(gap < -gap_threshold, "Cost-Efficient", "Balanced")
    )
    return df


def _apply_verdict(df):
    """v6.2 — plain-language recommendation combining the statistical score
    with the explicit guardrail/profitability/OOD flags, so the tool gives
    a clear answer rather than just a bare 0-100 number. Computed on the
    full candidate pool (before viability filtering) so percentiles are
    consistent regardless of downstream diversity/snap selection."""
    if "Final_Score" not in df.columns or len(df) < 3:
        df["Verdict"] = "Insufficient Data"
        df["Caution_Reasons"] = ""
        return df

    score_pct = df["Final_Score"].rank(pct=True) * 100.0
    verdicts, reasons_list = [], []
    for i in range(len(df)):
        cautions = []
        if bool(df["Nearby_Underperformance_Flag"].iloc[i]) if "Nearby_Underperformance_Flag" in df.columns else False:
            cautions.append("Nearby stores underperforming")
        if df.get("Profitability_Flag", pd.Series(["Balanced"] * len(df))).iloc[i] == "Cost-Heavy":
            cautions.append("High property cost vs. predicted revenue")
        if int(df.get("OOD_Feature_Count", pd.Series([0] * len(df))).iloc[i]) > 2:
            cautions.append("Unusual profile vs. existing stores")

        sp = score_pct.iloc[i]
        if sp >= 70 and not cautions:
            v = "Strong Candidate"
        elif sp >= 40 and len(cautions) <= 1:
            v = "Viable — Review Cautions" if cautions else "Promising Candidate"
        else:
            v = "Not Recommended"
        verdicts.append(v)
        reasons_list.append("; ".join(cautions))

    df["Verdict"] = verdicts
    df["Caution_Reasons"] = reasons_list
    return df


def _add_adjusted_sales(df):
    if "Sales" not in df.columns:
        df["Sales"] = 100_000.0
    if "Returns" not in df.columns:
        df["Returns"] = 0.0
    df["Sales"]   = pd.to_numeric(df["Sales"],   errors="coerce").fillna(0)
    df["Returns"] = pd.to_numeric(df["Returns"], errors="coerce").fillna(0)
    df["Adjusted_Sales"] = df["Sales"] * (1 - df["Returns"] / df["Sales"].replace(0, 1))
    return df


def _generate_grid(cfg, demographics_df):
    gb = cfg["grid_bounds"]  # [lat_min, lat_max, lon_min, lon_max]
    lats = np.arange(gb[0], gb[1], GRID_STEP_DEG)
    lons = np.arange(gb[2], gb[3], GRID_STEP_DEG)
    import geopandas as gpd
    from shapely.geometry import Point
    demog_gdf = gpd.GeoDataFrame(
        demographics_df,
        geometry=gpd.points_from_xy(demographics_df.Longitude, demographics_df.Latitude),
        crs="EPSG:4326",
    )
    land_buf = demog_gdf.geometry.buffer(0.1).unary_union
    pts = [Point(lon, lat) for lat in lats for lon in lons if land_buf.contains(Point(lon, lat))]
    rows = [{"Store_Name": f"Grid Candidate {i+1}", "Latitude": p.y, "Longitude": p.x}
            for i, p in enumerate(pts)]
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────
def _to_records(df, kind: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    records = []
    for _, row in df.iterrows():
        r = {
            "type":      kind,
            "lat":       safe_float(row.get("Latitude")),
            "lng":       safe_float(row.get("Longitude")),
            "name":      str(row.get("Store_Name", row.get("Name", "Unknown"))),
            "address":   str(row.get("Address", row.get("Locality", ""))),
            "score":     safe_float(row.get("Final_Score", 0)),
            "revenue":   safe_float(row.get("Predicted_Revenue", row.get("Sales", 0))),
            "rev_lower": safe_float(row.get("Rev_Lower", 0)),
            "rev_upper": safe_float(row.get("Rev_Upper", 0)),
            "population":  safe_int(row.get("Population", 0)),
            "income":      safe_float(row.get("Income", 0)),
            "total_amenities": safe_int(row.get("Total_Amenities", 0)),
            "cnt_food":     safe_int(row.get("cnt_food", 0)),
            "cnt_retail":   safe_int(row.get("cnt_retail", 0)),
            "cnt_education":safe_int(row.get("cnt_education", 0)),
            "cnt_health":   safe_int(row.get("cnt_health", 0)),
            "cnt_hospitality": safe_int(row.get("cnt_hospitality", 0)),
            "cnt_civic":       safe_int(row.get("cnt_civic", 0)),
            "competitor_2km":  safe_int(row.get("Competitor_2km", 0)),
            "competitor_5km":  safe_int(row.get("Competitor_5km", 0)),
            "nearby_store_avg_sales": safe_float(row.get("Nearby_Store_Avg_Sales", 0)),
            "nearby_store_count":     safe_int(row.get("Nearby_Store_Count_Perf", 0)),
            "nearby_underperformance_flag": bool(row.get("Nearby_Underperformance_Flag", False)),
            "cost_percentile":     safe_float(row.get("Cost_Percentile", None)) if row.get("Cost_Percentile") is not None else None,
            "revenue_percentile":  safe_float(row.get("Revenue_Percentile", None)) if row.get("Revenue_Percentile") is not None else None,
            "profitability_flag":  str(row.get("Profitability_Flag", "")),
            "verdict":             str(row.get("Verdict", "")),
            "caution_reasons":     str(row.get("Caution_Reasons", "")),
            "nearest_store":     str(row.get("Nearest_Store_Name", "")),
            "nearest_store_km":  safe_float(row.get("Nearest_Store_km", 0)),
            "bu_name":    str(row.get("BU_Name", "")),
            "bu_dist_km": safe_float(row.get("BU_Dist_km", 0)),
            # Explainability additions
            "distance_penalty": safe_float(row.get("Distance_Penalty", 1.0)),
            "is_too_close": bool(row.get("Is_Too_Close", False)),
            "adjusted_final_score": safe_float(row.get("Adjusted_Final_Score", row.get("Final_Score", 0))),
            "district":  str(row.get("District", "")),
            "region":    str(row.get("Region", "Unassigned")),
            "property_cost_index": safe_float(row.get("property_cost_index", 50.0)),
            "market_saturation_score": safe_float(row.get("market_saturation_score", 0.0)),
            "expansion_score": safe_float(row.get("expansion_score", 0.0)),
            "property_growth_score": safe_float(row.get("property_growth_score", 0.0)),
            "avg_property_price_3km": safe_float(row.get("avg_property_price_3km", 0.0)),
            "avg_property_price_5km": safe_float(row.get("avg_property_price_5km", 0.0)),
            # v3.7 — geographic features
            "dist_to_nearest_road_m": safe_float(row.get("dist_to_nearest_road_m", 99999)),
            "is_commercial":   safe_int(row.get("is_commercial", 0)),
            "is_residential":  safe_int(row.get("is_residential", 0)),
            "is_industrial":   safe_int(row.get("is_industrial", 0)),
            "is_agricultural": safe_int(row.get("is_agricultural", 0)),
            "is_natural":      safe_int(row.get("is_natural", 0)),
            # v4.0 — amenity-affinity explainability
            "similarity_to_archetype": safe_float(row.get("Similarity_To_Archetype", 0.0)),
            "top_positive_drivers":    str(row.get("Top_Positive_Drivers", "")),
            "top_negative_drivers":    str(row.get("Top_Negative_Drivers", "")),
            "comparable_stores":       str(row.get("Comparable_Stores", "")),
        }
        records.append(r)
    return records


def _compute_kpis(stores_df, top_df):
    sales = pd.to_numeric(stores_df.get("Sales", pd.Series([])), errors="coerce").fillna(0)
    
    # We use top_df for location-specific KPIs to show the "quality" of predictions
    has_top = top_df is not None and not top_df.empty
    
    kpis = {
        "total_stores":   len(stores_df),
        "total_sales":    safe_float(sales.sum()),
        "avg_sales":      safe_float(sales.mean()),
        "max_sales":      safe_float(sales.max()),
        "min_sales":      safe_float(sales.min()),
        "top_candidates": len(top_df),
        "avg_score":      safe_float(top_df["Final_Score"].mean()) if has_top else 0,
        "max_score":      safe_float(top_df["Final_Score"].max()) if has_top else 0,
        "avg_predicted_revenue": safe_float(top_df["Predicted_Revenue"].mean()) if has_top else 0,
        
        # New Strategic KPIs
        "avg_population":   safe_float(top_df["Population"].mean()) if has_top else 0,
        "avg_income":       safe_float(top_df["Income"].mean()) if has_top else 0,
        "logistics_coverage": safe_float((top_df["BU_Dist_km"] < 20.0).mean() * 100) if has_top and "BU_Dist_km" in top_df.columns else 0,
        "cannibalization_risk": safe_float((top_df["Nearest_Store_km"] < 3.0).mean() * 100) if has_top and "Nearest_Store_km" in top_df.columns else 0,
    }
    
    # Top sales-producing amenity: correlate amenity counts with store sales
    amenity_buckets = {
        "food": "🍽️ Food",
        "retail": "🛒 Retail",
        "education": "🏫 Education",
        "health": "🏥 Health",
        "leisure": "🎡 Leisure",
        "transport": "🚌 Transport",
        "finance": "🏦 Finance",
    }
    best_corr, best_amenity = -1, "food"
    for bucket_key, bucket_label in amenity_buckets.items():
        col = f"cnt_{bucket_key}"
        if col in stores_df.columns and "Sales" in stores_df.columns:
            try:
                corr = stores_df[col].astype(float).corr(stores_df["Sales"].astype(float))
                if pd.notna(corr) and corr > best_corr:
                    best_corr = corr
                    best_amenity = bucket_key
            except Exception:
                pass
    kpis["top_amenity"] = best_amenity
    kpis["top_amenity_label"] = amenity_buckets.get(best_amenity, "🍽️ Food")
    kpis["top_amenity_corr"] = safe_float(best_corr) if best_corr > -1 else 0
    
    return kpis


# =====================================================================
# v3.8 - Candidate Viability Filter + Spatial Diversity Selection
# =====================================================================
import math as _v38_math

_V38_AMENITY_COLS = [
    "cnt_food", "cnt_retail", "cnt_education", "cnt_health",
    "cnt_leisure", "cnt_transport", "cnt_finance",
    "cnt_hospitality", "cnt_civic",  # v5.0 — new buckets from local amenities data
]


def _filter_viable_candidates(df, min_amenities: int = 5, min_population: int = 1000):
    """Drop unviable candidates (jungles/rivers/empty land) before scoring."""
    if df is None or len(df) == 0:
        return df
    import pandas as _pd
    present = [c for c in _V38_AMENITY_COLS if c in df.columns]
    amen_sum = df[present].fillna(0).sum(axis=1) if present else _pd.Series(0, index=df.index)
    pop = _pd.to_numeric(df.get("Population", 0), errors="coerce").fillna(0)
    keep = (amen_sum >= min_amenities) & (pop >= min_population)
    out = df.loc[keep].copy()
    try:
        log.info(
            f"[Viability] {len(df)} candidates -> {len(out)} viable "
            f"(min_amenities={min_amenities}, min_population={min_population})"
        )
    except Exception:
        pass
    return out


def _v38_haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = _v38_math.radians(lat2 - lat1)
    dlon = _v38_math.radians(lon2 - lon1)
    a = (_v38_math.sin(dlat / 2) ** 2
         + _v38_math.cos(_v38_math.radians(lat1)) * _v38_math.cos(_v38_math.radians(lat2))
         * _v38_math.sin(dlon / 2) ** 2)
    return 2 * R * _v38_math.asin(_v38_math.sqrt(a))


def _select_diverse_top_picks(scored_df, n: int, min_distance_km: float = 15.0):
    """Greedy spatial diversity: skip picks within min_distance_km of an existing pick."""
    if scored_df is None or len(scored_df) == 0 or n <= 0:
        import pandas as _pd
        return scored_df.iloc[0:0] if scored_df is not None else _pd.DataFrame()
    sorted_df = scored_df.sort_values("Final_Score", ascending=False).reset_index(drop=True)
    if min_distance_km <= 0:
        return sorted_df.head(n).reset_index(drop=True)
    picks = []
    for idx, row in sorted_df.iterrows():
        if len(picks) >= n:
            break
        lat1 = float(row["Latitude"])
        lon1 = float(row["Longitude"])
        too_close = False
        for (_, lat2, lon2) in picks:
            if _v38_haversine_km(lat1, lon1, lat2, lon2) < min_distance_km:
                too_close = True
                break
        if not too_close:
            picks.append((idx, lat1, lon1))
    pick_indices = [p[0] for p in picks]
    out = sorted_df.loc[pick_indices].reset_index(drop=True)
    try:
        log.info(
            f"[Diversity] requested n={n}, min_distance_km={min_distance_km}, "
            f"picked={len(out)} from {len(sorted_df)} ranked candidates"
        )
    except Exception:
        pass
    return out

# =====================================================================

# =====================================================================
# v3.8.2 - Look-alike matching: snap-or-DROP to dense amenity cluster
# Threshold is derived from existing stores (p10 of densest 500m cluster)
# =====================================================================

def _v382_compute_store_density_profile(stores_df, amenities_gdf, cluster_radius_m: int = 500):
    """For each existing store, count amenities within cluster_radius_m.
    Returns dict of percentile stats so we can use Mio's worst stores as the floor."""
    if stores_df is None or len(stores_df) == 0 or amenities_gdf is None or amenities_gdf.empty:
        return {"n_stores": 0, "median": 0, "p5": 0, "p10": 0, "p25": 0, "mean": 0}
    try:
        import numpy as _np
        deg = cluster_radius_m / 111000.0
        amen_lats = amenities_gdf.geometry.y.values
        amen_lons = amenities_gdf.geometry.x.values
        densities = []
        for _, store in stores_df.iterrows():
            try:
                slat = float(store["Latitude"])
                slon = float(store["Longitude"])
            except (TypeError, ValueError, KeyError):
                continue
            mask = ((amen_lats >= slat - deg) & (amen_lats <= slat + deg)
                    & (amen_lons >= slon - deg) & (amen_lons <= slon + deg))
            count = 0
            for la, lo in zip(amen_lats[mask], amen_lons[mask]):
                if _v38_haversine_km(slat, slon, la, lo) * 1000.0 <= cluster_radius_m:
                    count += 1
            densities.append(count)
        if not densities:
            return {"n_stores": 0, "median": 0, "p5": 0, "p10": 0, "p25": 0, "mean": 0}
        arr = _np.array(densities)
        return {
            "n_stores": int(len(arr)),
            "mean":   float(arr.mean()),
            "median": float(_np.median(arr)),
            "p5":     float(_np.percentile(arr, 5)),
            "p10":    float(_np.percentile(arr, 10)),
            "p25":    float(_np.percentile(arr, 25)),
        }
    except Exception as e:
        try:
            log.warning(f"[Calibration] store density profile failed: {type(e).__name__}: {e}")
        except Exception:
            pass
        return {"n_stores": 0, "median": 0, "p5": 0, "p10": 0, "p25": 0, "mean": 0}


def _snap_or_drop_to_dense_cluster(picks_df, amenities_gdf, min_cluster_size: int = 10,
                                    cluster_radius_m: int = 500, hex_half_km: float = 3.0):
    """For each pick:
       1. Find amenities inside the hex (hex_half_km radius)
       2. Find the amenity that has the most neighbors within cluster_radius_m
       3. If best_count < min_cluster_size -> DROP the pick
       4. Else -> SNAP the pick's lat/lng to that anchor amenity
    """
    if picks_df is None or len(picks_df) == 0:
        return picks_df
    if amenities_gdf is None or amenities_gdf.empty:
        try:
            log.warning("[Snap] no amenities_gdf - returning picks unchanged")
        except Exception:
            pass
        return picks_df
    import pandas as _pd
    deg = hex_half_km / 111.0
    amen_lats = amenities_gdf.geometry.y.values
    amen_lons = amenities_gdf.geometry.x.values
    kept_rows = []
    n_dropped = 0
    n_snapped = 0
    for _, row in picks_df.iterrows():
        try:
            plat = float(row["Latitude"]); plon = float(row["Longitude"])
        except (TypeError, ValueError, KeyError):
            continue
        mask = ((amen_lats >= plat - deg) & (amen_lats <= plat + deg)
                & (amen_lons >= plon - deg) & (amen_lons <= plon + deg))
        ax = amen_lats[mask]; ay = amen_lons[mask]
        if len(ax) == 0:
            n_dropped += 1
            try:
                log.info(f"[Snap] DROP ({plat:.4f},{plon:.4f}) - no amenities in hex")
            except Exception:
                pass
            continue
        # Find amenity with most neighbors within cluster_radius_m
        best_count = 0
        best_lat = plat
        best_lon = plon
        for i in range(len(ax)):
            count = 0
            for j in range(len(ax)):
                if i == j:
                    continue
                if _v38_haversine_km(ax[i], ay[i], ax[j], ay[j]) * 1000.0 <= cluster_radius_m:
                    count += 1
            if count > best_count:
                best_count = count
                best_lat = float(ax[i])
                best_lon = float(ay[i])
        if best_count < min_cluster_size:
            n_dropped += 1
            try:
                log.info(f"[Snap] DROP ({plat:.4f},{plon:.4f}) - densest cluster only {best_count} amenities (need {min_cluster_size})")
            except Exception:
                pass
            continue
        new_row = row.copy()
        new_row["Latitude"] = best_lat
        new_row["Longitude"] = best_lon
        kept_rows.append(new_row)
        n_snapped += 1
        try:
            log.info(f"[Snap] SNAP ({plat:.4f},{plon:.4f}) -> ({best_lat:.4f},{best_lon:.4f}) {best_count} amenities in {cluster_radius_m}m")
        except Exception:
            pass
    try:
        log.info(f"[Snap] {n_snapped} snapped, {n_dropped} dropped (threshold={min_cluster_size})")
    except Exception:
        pass
    if not kept_rows:
        return picks_df.iloc[0:0]
    return _pd.DataFrame(kept_rows).reset_index(drop=True)
