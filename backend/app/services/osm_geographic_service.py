"""
OSM Geographic Service - v3.7.2 (fail-fast)
============================================
60s timeout, 1 attempt, graceful fallback. Pipeline runs fine without
geographic features. Run Prewarm-OSM-Cache.py separately to populate cache.
"""
from __future__ import annotations
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from app.config import AMENITIES_DIR
from app.utils import get_logger

log = get_logger("osm_geographic_service")

GEO_OSM_RETRY_LIMIT = 1
GEO_REQUESTS_TIMEOUT = 60

RETAIL_VIABLE_HIGHWAYS = {
    "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "living_street", "pedestrian",
}

LANDUSE_TO_BINARY = {
    "commercial": "is_commercial", "retail": "is_commercial",
    "residential": "is_residential",
    "industrial": "is_industrial", "quarry": "is_industrial",
    "depot": "is_industrial", "landfill": "is_industrial", "port": "is_industrial",
    "farmland": "is_agricultural", "farmyard": "is_agricultural",
    "orchard": "is_agricultural", "vineyard": "is_agricultural",
    "meadow": "is_agricultural", "allotments": "is_agricultural",
    "forest": "is_natural", "forestry": "is_natural",
}

NATURAL_TAGS = {
    "wood", "tree_row", "scrub", "heath", "grassland",
    "water", "wetland", "bay", "coastline", "beach", "reef",
    "bare_rock", "scree", "cliff",
}

BINARY_COLS = [
    "is_commercial", "is_residential",
    "is_industrial", "is_agricultural", "is_natural",
]

LANDUSE_BUFFER_M = 500
ROAD_SEARCH_RADIUS_M = 5000


def get_roads_and_landuse(country, state):
    roads_path = _roads_cache_path(country, state)
    landuse_path = _landuse_cache_path(country, state)

    if roads_path.exists():
        log.info(f"[Geo] Roads cache hit -> {roads_path.name}")
        try:
            roads_gdf = _ensure_crs(gpd.read_file(roads_path))
        except Exception as e:
            log.warning(f"[Geo] Roads cache read failed ({e}); using empty")
            roads_gdf = _empty_lines_gdf()
    else:
        log.warning("[Geo] No roads cache - brief fetch attempt (60s max)")
        roads_gdf = _fetch_roads(country, state)
        if roads_gdf is not None and not roads_gdf.empty:
            _save(roads_gdf, roads_path)

    if landuse_path.exists():
        log.info(f"[Geo] Landuse cache hit -> {landuse_path.name}")
        try:
            landuse_gdf = _ensure_crs(gpd.read_file(landuse_path))
        except Exception as e:
            log.warning(f"[Geo] Landuse cache read failed ({e}); using empty")
            landuse_gdf = _empty_polys_gdf()
    else:
        log.warning("[Geo] No landuse cache - brief fetch attempt (60s max)")
        landuse_gdf = _fetch_landuse(country, state)
        if landuse_gdf is not None and not landuse_gdf.empty:
            _save(landuse_gdf, landuse_path)

    return roads_gdf, landuse_gdf


def enrich_with_geography(points_df, roads_gdf, landuse_gdf):
    df = points_df.copy()
    n = len(df)
    if n == 0:
        for c in ["dist_to_nearest_road_m"] + BINARY_COLS:
            df[c] = 0
        return df

    df["dist_to_nearest_road_m"] = 99999.0
    for c in BINARY_COLS:
        df[c] = 0

    pts = gpd.GeoDataFrame(
        df[["Latitude", "Longitude"]].copy(),
        geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
        crs="EPSG:4326",
    ).to_crs(epsg=3857)

    if roads_gdf is not None and not roads_gdf.empty:
        try:
            roads_proj = roads_gdf.to_crs(epsg=3857).reset_index(drop=True)
            joined = gpd.sjoin_nearest(
                pts[["geometry"]].reset_index(),
                roads_proj[["geometry"]],
                how="left", distance_col="dist_m",
                max_distance=ROAD_SEARCH_RADIUS_M,
            )
            joined = joined.drop_duplicates(subset=["index"], keep="first").sort_values("index")
            dist = joined["dist_m"].fillna(ROAD_SEARCH_RADIUS_M).values
            df["dist_to_nearest_road_m"] = dist
            log.info(f"[Geo] road-distance: median={np.median(dist):.0f}m, p95={np.percentile(dist, 95):.0f}m")
        except Exception as e:
            log.warning(f"[Geo] road distance failed: {type(e).__name__}: {e}")
    else:
        log.warning("[Geo] No roads data - default 99999m (run prewarm to enable)")

    if landuse_gdf is not None and not landuse_gdf.empty:
        try:
            landuse_proj = landuse_gdf.to_crs(epsg=3857).reset_index(drop=True)
            landuse_proj["_binary"] = landuse_proj.apply(_classify_landuse_row, axis=1)
            landuse_proj = landuse_proj[landuse_proj["_binary"].notna()].copy()
            if not landuse_proj.empty:
                pts_buf = pts.copy()
                pts_buf["geometry"] = pts_buf.geometry.buffer(LANDUSE_BUFFER_M)
                pts_buf = pts_buf.reset_index().rename(columns={"index": "_pt_idx"})
                joined = gpd.sjoin(
                    landuse_proj[["geometry", "_binary"]],
                    pts_buf[["_pt_idx", "geometry"]],
                    how="inner", predicate="intersects",
                )
                for binary_col in BINARY_COLS:
                    hits = joined[joined["_binary"] == binary_col]["_pt_idx"].unique()
                    df.loc[df.index[hits], binary_col] = 1
                log.info(f"[Geo] landuse hits: {dict((c, int(df[c].sum())) for c in BINARY_COLS)}")
        except Exception as e:
            log.warning(f"[Geo] landuse classification failed: {type(e).__name__}: {e}")
    else:
        log.warning("[Geo] No landuse data - binaries default to 0 (run prewarm to enable)")

    return df


def _fetch_roads(country, state):
    bbox = _state_bbox(country, state)
    log.info(f"[Geo] Fetching roads via bbox={bbox} (FAIL-FAST: 60s timeout)")
    tags = {"highway": list(RETAIL_VIABLE_HIGHWAYS)}
    gdf = _osmnx_fetch(bbox, tags, label="roads")
    if gdf is None or gdf.empty:
        return _empty_lines_gdf()
    gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    keep = [c for c in ["highway", "name", "geometry"] if c in gdf.columns]
    gdf = gdf[keep]
    log.info(f"[Geo] Roads fetched: {len(gdf)} ways")
    return gdf


def _fetch_landuse(country, state):
    bbox = _state_bbox(country, state)
    log.info(f"[Geo] Fetching landuse via bbox={bbox} (FAIL-FAST: 60s timeout)")
    tags = {
        "landuse": list({*LANDUSE_TO_BINARY.keys()}),
        "natural": list(NATURAL_TAGS),
    }
    gdf = _osmnx_fetch(bbox, tags, label="landuse")
    if gdf is None or gdf.empty:
        return _empty_polys_gdf()
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    keep = [c for c in ["landuse", "natural", "geometry"] if c in gdf.columns]
    gdf = gdf[keep]
    log.info(f"[Geo] Landuse fetched: {len(gdf)} polygons")
    return gdf


def _osmnx_fetch(bbox, tags, label):
    import osmnx as ox
    try:
        ox.settings.requests_timeout = GEO_REQUESTS_TIMEOUT
    except Exception:
        pass
    try:
        ox.settings.timeout = GEO_REQUESTS_TIMEOUT
    except Exception:
        pass
    north, south, east, west = bbox
    try:
        log.info(f"[Geo] {label}: OSMnx attempt 1/1 (60s max)")
        try:
            gdf = ox.features_from_bbox(north, south, east, west, tags=tags)
        except TypeError:
            gdf = ox.features_from_bbox(bbox=(north, south, east, west), tags=tags)
        return _ensure_crs(gdf)
    except Exception as e:
        log.warning(f"[Geo] {label}: failed -> {type(e).__name__}: {e}")
        log.warning(f"[Geo] {label}: giving up - use Prewarm-OSM-Cache.py to populate cache")
        return None


def _state_bbox(country, state):
    from app.config import get_state_config
    cfg = get_state_config(country, state)
    gb = cfg["grid_bounds"]
    lat_min, lat_max, lon_min, lon_max = gb
    return (lat_max, lat_min, lon_max, lon_min)


def _classify_landuse_row(row):
    landuse = row.get("landuse")
    if landuse and isinstance(landuse, str) and landuse in LANDUSE_TO_BINARY:
        return LANDUSE_TO_BINARY[landuse]
    natural = row.get("natural")
    if natural and isinstance(natural, str) and natural in NATURAL_TAGS:
        return "is_natural"
    return None


def _roads_cache_path(country, state):
    key = f"{country.lower().replace(' ', '_')}_{state.lower().replace(' ', '_')}"
    return AMENITIES_DIR / f"roads_{key}.geojson"


def _landuse_cache_path(country, state):
    key = f"{country.lower().replace(' ', '_')}_{state.lower().replace(' ', '_')}"
    return AMENITIES_DIR / f"landuse_{key}.geojson"


def _empty_lines_gdf():
    return gpd.GeoDataFrame(columns=["highway", "geometry"], geometry="geometry", crs="EPSG:4326")


def _empty_polys_gdf():
    return gpd.GeoDataFrame(columns=["landuse", "natural", "geometry"], geometry="geometry", crs="EPSG:4326")


def _save(gdf, path):
    if gdf is None or gdf.empty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(str(path), driver="GeoJSON")
    log.info(f"[Geo] Saved {path.name} ({path.stat().st_size // 1024} KB)")


def _ensure_crs(gdf):
    if gdf is None:
        return gdf
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    return gdf
