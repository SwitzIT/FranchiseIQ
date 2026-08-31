"""
Local Competitor Density Service (v8.1)
========================================
Loads EVERY spreadsheet in COMPETITOR_DIR — not just one fixed file per
state — and combines them into a single competitor dataset. No live Places
API calls, no network of any kind.

v8.1 — supports two different source schemas, since real-world competitor
files come from different collection methods:
  1. Files with direct Latitude/Longitude columns (e.g. the original
     Mio_competitor.xlsx: Shop Lat / Shop Lon).
  2. Files with ONLY a Google Maps `place_url` column (common output from
     scraping tools) — coordinates are extracted directly from the URL
     text itself, no network request needed. Google Maps embeds
     coordinates in two common formats:
       - "data=" URLs:   ...!3d20.7063454!4d81.5462175!...  (lat, then lon)
       - share/plain URLs: .../@20.7063,81.5462,17z/...
     A URL that matches neither pattern (e.g. a shortened maps.app.goo.gl
     link, which needs a network redirect to resolve) is skipped with a
     logged count — not silently dropped without a trace.

Adds two features used by the scoring model:
    Competitor_2km — count of rival shops within 2km
    Competitor_5km — count of rival shops within 5km
Both are "lower is better" — more direct competitors nearby generally means
a more saturated, harder market for a new franchise location.
"""
import re
import numpy as np
import pandas as pd

from app.config import COMPETITOR_DIR
from app.utils import get_logger, haversine_vectorized

log = get_logger("local_competitor_service")

_MEMORY_CACHE: dict[str, pd.DataFrame] = {}

_RENAME = {
    "shop lat":       "Latitude",
    "shop lon":       "Longitude",
    "latitude":       "Latitude",
    "longitude":      "Longitude",
    "lat":            "Latitude",
    "lon":            "Longitude",
    "shop name":      "Name",
    "name":           "Name",
    "type of shop":   "Category",
    "category":       "Category",
    "matched_brand":  "Category",
    "city":           "City",
    "place_url":      "Place_URL",
    "place url":      "Place_URL",
    "rating":         "Rating",
    "review_count":   "Review_Count",
    "address":        "Address",
}

# "data=" URL format: coordinates appear as !3d{lat}!4d{lon}
_URL_PATTERN_DATA = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
# Share/plain URL format: coordinates appear as @{lat},{lon},{zoom}
_URL_PATTERN_AT = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+),")


def _extract_latlon_from_url(url: str) -> tuple[float, float] | None:
    """Pulls (lat, lon) out of a Google Maps URL's own text — no network
    request. Returns None if the URL doesn't match a known pattern (e.g. a
    shortened maps.app.goo.gl link, which would need a redirect to resolve
    and isn't supported here by design — this app doesn't make live
    network calls for data loading)."""
    if not isinstance(url, str):
        return None
    m = _URL_PATTERN_DATA.search(url)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _URL_PATTERN_AT.search(url)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def _load_one_file(path) -> pd.DataFrame:
    """Loads and normalizes a single competitor file. Returns an empty
    DataFrame (not an error) if it can't be used, so one bad file doesn't
    break loading the rest."""
    try:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            return pd.DataFrame(columns=["Latitude", "Longitude", "Name", "Category", "City"])
    except Exception as e:
        log.warning(f"[Competitors] Could not read '{path.name}': {e}")
        return pd.DataFrame(columns=["Latitude", "Longitude", "Name", "Category", "City"])

    df.columns = df.columns.astype(str).str.strip()
    rename = {c: _RENAME[c.lower()] for c in df.columns if c.lower() in _RENAME}
    df = df.rename(columns=rename)

    if "Latitude" in df.columns and "Longitude" in df.columns:
        # Schema 1: direct coordinate columns
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    elif "Place_URL" in df.columns:
        # Schema 2: extract coordinates from the place_url text
        coords = df["Place_URL"].apply(_extract_latlon_from_url)
        n_total = len(df)
        n_resolved = coords.notna().sum()
        df["Latitude"] = coords.apply(lambda c: c[0] if c else None)
        df["Longitude"] = coords.apply(lambda c: c[1] if c else None)
        n_skipped = n_total - n_resolved
        if n_skipped > 0:
            log.info(f"[Competitors] '{path.name}': extracted coordinates from "
                     f"{n_resolved}/{n_total} place_url values "
                     f"({n_skipped} skipped — unrecognized URL format, likely a "
                     f"shortened link that would need a network request to resolve)")
    else:
        log.warning(f"[Competitors] '{path.name}' has no Latitude/Longitude columns "
                     f"and no place_url column after rename — found {list(df.columns)}. Skipping file.")
        return pd.DataFrame(columns=["Latitude", "Longitude", "Name", "Category", "City"])

    df = df.dropna(subset=["Latitude", "Longitude"])
    df = df[(df["Latitude"] != 0) | (df["Longitude"] != 0)]
    df["_source_file"] = path.name
    log.info(f"[Competitors] Loaded {len(df)} usable competitor locations from {path.name}")
    return df


def load_competitors(country: str, state: str) -> pd.DataFrame:
    """Loads (and caches) EVERY competitor file in COMPETITOR_DIR, combined
    into one DataFrame — not scoped per country/state, since competitor
    context is useful regardless of which region is currently selected.
    The country/state args are kept for interface compatibility with the
    rest of the pipeline (and for the in-memory cache key) even though
    every state currently shares the same combined dataset.
    Returns an empty DataFrame (not an error) if the folder has nothing
    usable — the pipeline just skips competitor features in that case."""
    key = "ALL_FILES"  # v8.1 — one combined dataset, not per country/state
    if key in _MEMORY_CACHE:
        return _MEMORY_CACHE[key]

    if not COMPETITOR_DIR.exists():
        log.info(f"[Competitors] No competitor directory at {COMPETITOR_DIR} — "
                 f"Competitor_2km/5km will be 0 for all rows.")
        df = pd.DataFrame(columns=["Latitude", "Longitude", "Name", "Category", "City"])
        _MEMORY_CACHE[key] = df
        return df

    files = sorted(
        [p for p in COMPETITOR_DIR.iterdir() if p.suffix.lower() in (".xlsx", ".xls", ".csv")]
    )
    if not files:
        log.info(f"[Competitors] No files found in {COMPETITOR_DIR} — "
                 f"Competitor_2km/5km will be 0 for all rows.")
        df = pd.DataFrame(columns=["Latitude", "Longitude", "Name", "Category", "City"])
        _MEMORY_CACHE[key] = df
        return df

    frames = [_load_one_file(p) for p in files]
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    combined = combined.dropna(subset=["Latitude", "Longitude"]) if len(combined) else combined

    log.info(f"[Competitors] Combined {len(combined)} total competitor locations "
             f"from {len(files)} file(s): {[p.name for p in files]}")
    _MEMORY_CACHE[key] = combined
    return combined


def count_competitors_near_points(points_df: pd.DataFrame, competitors_df: pd.DataFrame) -> pd.DataFrame:
    """Adds Competitor_2km / Competitor_5km to points_df in place (and returns it)."""
    if competitors_df is None or competitors_df.empty:
        points_df["Competitor_2km"] = 0
        points_df["Competitor_5km"] = 0
        return points_df

    c_lats = competitors_df["Latitude"].values
    c_lons = competitors_df["Longitude"].values
    c2, c5 = [], []
    for _, row in points_df.iterrows():
        dists = haversine_vectorized(c_lats, c_lons, row["Latitude"], row["Longitude"])
        c2.append(int(np.sum(dists <= 2.0)))
        c5.append(int(np.sum(dists <= 5.0)))
    points_df["Competitor_2km"] = c2
    points_df["Competitor_5km"] = c5
    return points_df
