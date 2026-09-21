"""
Agent 3 — Amenities Manager Service (v5.0 — LOCAL DATA, no OSM)
================================================================
Loads a pre-collected amenities file (CSV or XLSX) per country/state from
disk, categorises each row into a bucket (food/retail/education/health/
leisure/transport/finance/hospitality/civic), and caches the parsed result
— first in-process memory, then as a lightweight GeoJSON on disk so a
restart doesn't need to re-parse the raw file. There is NO network call
anywhere in this module.

Expected raw file: any CSV/XLSX with Latitude/Longitude columns plus one of
Category / Type / Amenity / Query describing what the place is. Built and
verified against `AmenitiesWB.csv` (columns: Name, Address, Query, Place
URL, Latitude, Longitude — where Query looks like "restaurant in Kolkata,
West Bengal").
"""
import re
from pathlib import Path

import pandas as pd
import geopandas as gpd

from app.config import (
    get_amenities_source_path, get_amenities_cache_path,
    LOCAL_AMENITY_CATEGORY_BUCKETS, AMENITY_BUCKET_NAMES, BUFFER_RADIUS_M,
    AMENITY_BUCKETS,
)
from app.utils import get_logger

log = get_logger("amenities_service")

# In-process cache — avoids re-reading disk on every call within one run.
_MEMORY_CACHE: dict[str, gpd.GeoDataFrame] = {}


# ─────────────────────────────────────────────────────────────
# PUBLIC API — same signatures as the old OSM-based version, so
# routes/amenities.py and scoring_service.py need zero changes.
# ─────────────────────────────────────────────────────────────
def get_amenities(country: str, state: str) -> tuple[gpd.GeoDataFrame, bool]:
    """
    Returns (amenities_gdf, was_cached).
    Loads from the local amenities source file for this country/state.
    `was_cached` is True whenever we didn't have to re-parse the raw file
    (in-memory or on-disk GeoJSON cache hit) — the frontend's "cached"
    indicator still means something, it just no longer refers to OSM.
    """
    key = f"{country}|{state}"
    if key in _MEMORY_CACHE:
        log.info(f"[Amenities] In-memory cache hit for {key}")
        return _MEMORY_CACHE[key], True

    cache_path = get_amenities_cache_path(country, state)
    if cache_path.exists():
        try:
            log.info(f"[Amenities] GeoJSON cache hit → {cache_path}")
            gdf = gpd.read_file(cache_path)
            gdf = _ensure_crs(gdf)
            if "bucket" not in gdf.columns or gdf.empty:
                raise ValueError("cached file has no usable 'bucket' data")
            src = get_amenities_source_path(country, state)
            if "type" not in gdf.columns and src and src.exists():
                raise ValueError("cached file predates amenity 'type' labels")
            if "place_id" not in gdf.columns and src and src.exists() \
                    and src.suffix.lower() in (".csv", ".xlsx", ".xls"):
                raise ValueError("cached file predates Google place IDs")
            _MEMORY_CACHE[key] = gdf
            return gdf, True
        except Exception as e:
            log.warning(
                f"[Amenities] Cached file at {cache_path} is unreadable/stale "
                f"({e}) — re-parsing from the local source file instead."
            )

    src_path = get_amenities_source_path(country, state)
    if not src_path or not src_path.exists():
        raise FileNotFoundError(
            f"No local amenities file configured/found for {country}/{state}. "
            f"Expected a CSV/XLSX at the path returned by "
            f"get_amenities_source_path() — check app/config.py's "
            f"AMENITIES_SOURCE_DIR and the state's 'amenities_file' entry."
        )

    log.info(f"[Amenities] Parsing local source → {src_path}")
    gdf = _load_local_file(src_path)
    _save_cache(gdf, cache_path)
    _MEMORY_CACHE[key] = gdf
    return gdf, False


def count_amenities_near_points(
    points_df: pd.DataFrame,
    amenities_gdf: gpd.GeoDataFrame,
    buffer_m: int = BUFFER_RADIUS_M,
) -> pd.DataFrame:
    """
    For each row in points_df (must have Latitude, Longitude),
    count amenities of each bucket category within buffer_m metres.
    Adds columns: cnt_food, cnt_retail, cnt_education, cnt_health,
                  cnt_leisure, cnt_transport, cnt_finance,
                  cnt_hospitality, cnt_civic, Total_Amenities
    """
    log.info(f"[Amenities] Counting within {buffer_m}m for {len(points_df)} points")

    if amenities_gdf is None or amenities_gdf.empty:
        for b in AMENITY_BUCKET_NAMES:
            points_df[f"cnt_{b}"] = 0
        points_df["Total_Amenities"] = 0
        return points_df

    gdf_proj = amenities_gdf.to_crs(epsg=3857)
    pts_gdf = gpd.GeoDataFrame(
        points_df.copy(),
        geometry=gpd.points_from_xy(points_df["Longitude"], points_df["Latitude"]),
        crs="EPSG:4326",
    ).to_crs(epsg=3857)

    pts_gdf["_buf"] = pts_gdf.geometry.buffer(buffer_m)
    buf_gdf = pts_gdf.set_geometry("_buf").copy()
    buf_gdf["_idx"] = range(len(buf_gdf))

    joined = gpd.sjoin(gdf_proj, buf_gdf[["_idx", "_buf"]], how="inner",
                       predicate="intersects")

    counts = (
        joined.groupby(["_idx", "bucket"])
        .size()
        .unstack(fill_value=0)
    )

    for b in AMENITY_BUCKET_NAMES:
        if b not in counts.columns:
            counts[b] = 0

    n = len(points_df)
    for b in AMENITY_BUCKET_NAMES:
        col_name = f"cnt_{b}"
        points_df[col_name] = [
            int(counts.loc[i, b]) if i in counts.index else 0
            for i in range(n)
        ]

    points_df["Total_Amenities"] = points_df[[f"cnt_{b}" for b in AMENITY_BUCKET_NAMES]].sum(axis=1)
    return points_df


def get_cache_status(country: str, state: str) -> dict:
    key = f"{country}|{state}"
    if key in _MEMORY_CACHE:
        return {"cached": True, "path": "in-memory", "size_mb": 0.0}
    path = get_amenities_cache_path(country, state)
    exists = path.exists()
    size_mb = round(path.stat().st_size / (1024 * 1024), 2) if exists else 0
    return {
        "cached": exists,
        "path": str(path),
        "size_mb": size_mb,
    }


# ─────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────
def _load_local_file(path: Path) -> gpd.GeoDataFrame:
    suffix = path.suffix.lower()
    if suffix in (".geojson", ".json"):
        # v9.0 — raw OSM-extract input (e.g. Sri Lanka): a totally
        # different shape from the CSV/XLSX case below — multiple
        # possible tag columns (amenity/shop/leisure), not a single
        # Category/Query column, and geometry is already embedded.
        return _load_geojson_file(path)
    if suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    df.columns = df.columns.astype(str).str.strip()

    lat_col = next((c for c in df.columns if c.strip().lower() in ("latitude", "lat")), None)
    lon_col = next((c for c in df.columns if c.strip().lower() in ("longitude", "lon", "long")), None)
    if not lat_col or not lon_col:
        raise ValueError(
            f"Amenities file '{path.name}' needs Latitude/Longitude columns; "
            f"found: {list(df.columns)}"
        )

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])
    df = df[(df[lat_col] != 0) | (df[lon_col] != 0)]

    df["bucket"] = _categorize(df)
    df["type"] = _raw_type(df)
    # Google Maps place ID (e.g. "ChIJ344e...") from a "Place URL" column, so
    # the map can open the exact listing for each amenity.
    url_col = next((c for c in df.columns if c.strip().lower() in ("place url", "place_url", "url", "google maps url")), None)
    df["place_id"] = (df[url_col].astype(str).str.extract(r"!19s(ChIJ[\w-]+)")[0]
                      if url_col else None)
    n_before = len(df)
    df = df[df["bucket"].notna()].copy()
    n_dropped = n_before - len(df)
    if n_dropped:
        log.info(f"[Amenities] {n_dropped} rows had no recognisable category and were dropped")

    name_col = next((c for c in df.columns if c.strip().lower() == "name"), None)

    gdf = gpd.GeoDataFrame(
        {
            "bucket": df["bucket"].values,
            "type": df["type"].values,
            "place_id": df["place_id"].values,
            "name": df[name_col].fillna("").astype(str).values if name_col else "",
        },
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326",
    )
    log.info(
        f"[Amenities] Parsed {len(gdf)} amenity points from {path.name} | "
        f"buckets={gdf['bucket'].value_counts().to_dict()}"
    )
    return gdf


def _load_geojson_file(path: Path) -> gpd.GeoDataFrame:
    """v9.0 — raw OSM-extract GeoJSON input (e.g. Sri Lanka's
    sri_lanka_sri_lanka.geojson): a FeatureCollection where each feature
    has ONE of amenity/shop/leisure as a raw OSM tag key (e.g.
    {"amenity": "school"}), not a Category/Type/Query text column like
    the CSV-based loader expects. Maps tag VALUES directly against
    AMENITY_BUCKETS (exact match — OSM tag values are clean canonical
    strings like "school"/"supermarket", not free text needing the
    substring extraction _categorize() below does for Query-style CSVs)."""
    gdf_raw = gpd.read_file(path)
    if gdf_raw.empty:
        raise ValueError(f"'{path.name}' parsed as GeoJSON but contained no features.")

    tag_cols = [c for c in ("amenity", "shop", "leisure") if c in gdf_raw.columns]
    if not tag_cols:
        raise ValueError(
            f"'{path.name}' has no amenity/shop/leisure tag columns to categorize by — "
            f"found: {list(gdf_raw.columns)}"
        )

    bucket = pd.Series([None] * len(gdf_raw), index=gdf_raw.index)
    raw_type = pd.Series([None] * len(gdf_raw), index=gdf_raw.index)
    for col in tag_cols:
        vals = gdf_raw[col].astype(str).str.strip().str.lower()
        mapped = vals.map(AMENITY_BUCKETS)
        # Keep the specific OSM tag (e.g. "school", "pharmacy") alongside the
        # bucket so the map can label amenities that have no name.
        raw_type = raw_type.fillna(vals.where(mapped.notna()))
        bucket = bucket.fillna(mapped)

    n_before = len(gdf_raw)
    keep = bucket.notna()
    n_dropped = n_before - int(keep.sum())
    if n_dropped:
        log.info(f"[Amenities] {n_dropped} rows had no recognisable category and were dropped "
                 f"(tag value not in AMENITY_BUCKETS)")

    name_col = next((c for c in gdf_raw.columns if c.strip().lower() == "name"), None)

    # v9.0 — this Sri Lanka extract has a real mix of geometry types, not
    # just points: 39% of features are Polygon/MultiPolygon (e.g. a school
    # or park mapped as a building/area outline in OSM rather than a
    # single point). Convert any non-Point geometry to its centroid — the
    # same approach already used elsewhere in this codebase (see
    # _real_estate_to_records) — since every downstream distance
    # calculation (Competitor_2km, the snap-to-density step, etc.)
    # requires pure Point geometries.
    geoms = gdf_raw.geometry[keep.values].values
    geoms = [g if g.geom_type == "Point" else g.centroid for g in geoms]

    out = gpd.GeoDataFrame(
        {
            "bucket": bucket[keep].values,
            "type": raw_type[keep].values,
            "name": gdf_raw[name_col][keep].fillna("").astype(str).values if name_col else "",
        },
        geometry=geoms,
        crs=gdf_raw.crs or "EPSG:4326",
    )
    log.info(
        f"[Amenities] Parsed {len(out)} amenity points from {path.name} | "
        f"buckets={out['bucket'].value_counts().to_dict()}"
    )
    return out


def _categorize(df: pd.DataFrame) -> pd.Series:
    """
    Looks for a Category/Type/Amenity/Query column and maps each value to a
    bucket via LOCAL_AMENITY_CATEGORY_BUCKETS (substring match on the text
    before " in " for Query-style values like "restaurant in Kolkata, West
    Bengal", and on the full text otherwise).
    """
    cat_col = next(
        (c for c in df.columns if c.strip().lower() in
         ("category", "type", "type of shop", "amenity", "query")),
        None,
    )
    if cat_col is None:
        log.warning(
            "[Amenities] No Category/Type/Amenity/Query column found — "
            "every row will be dropped. Available columns: %s", list(df.columns)
        )
        return pd.Series([None] * len(df), index=df.index)

    def _match(raw):
        if not isinstance(raw, str) or not raw.strip():
            return None
        text = raw.lower()
        head = re.split(r"\s+in\s+", text, maxsplit=1)[0].strip()
        # Match on the category part ("hotel" in "hotel in Bankura, West
        # Bengal") before looking at the whole text. Checking the full text
        # first matched place names — "Bankura" contains "bank", so hotels,
        # police stations and post offices there were counted as banks.
        if head in LOCAL_AMENITY_CATEGORY_BUCKETS:
            return LOCAL_AMENITY_CATEGORY_BUCKETS[head]
        for keyword, bucket in LOCAL_AMENITY_CATEGORY_BUCKETS.items():
            if keyword in head:
                return bucket
        for keyword, bucket in LOCAL_AMENITY_CATEGORY_BUCKETS.items():
            if re.search(rf"\b{re.escape(keyword)}\b", text):
                return bucket
        return None

    return df[cat_col].apply(_match)


def _raw_type(df: pd.DataFrame) -> pd.Series:
    """The specific place type searched for, e.g. "hospital" from
    "hospital in Kolkata, West Bengal" — kept alongside the bucket so the
    map can label points and counts can be checked per type."""
    cat_col = next(
        (c for c in df.columns if c.strip().lower() in
         ("category", "type", "type of shop", "amenity", "query")),
        None,
    )
    if cat_col is None:
        return pd.Series([None] * len(df), index=df.index)
    head = (df[cat_col].astype(str).str.lower()
            .str.split(r"\s+in\s+", n=1, regex=True).str[0].str.strip())
    return head.where(head.isin(list(LOCAL_AMENITY_CATEGORY_BUCKETS)), None)


def _save_cache(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(str(path), driver="GeoJSON")
    log.info(f"[Amenities] Cached parsed amenities → {path}")


def _ensure_crs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    return gdf
