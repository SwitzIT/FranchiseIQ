"""
Local Competitor Density Service (v5.0)
========================================
Loads a static, pre-collected competitor spreadsheet (e.g. Mio_competitor.xlsx)
per country/state and computes competitor density features for stores and
candidates — no live Places API calls, no network of any kind.

Adds two features used by the scoring model:
    Competitor_2km — count of rival shops within 2km
    Competitor_5km — count of rival shops within 5km
Both are "lower is better" — more direct competitors nearby generally means
a more saturated, harder market for a new franchise location.
"""
import numpy as np
import pandas as pd

from app.config import get_competitor_path
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
    "city":           "City",
}


def load_competitors(country: str, state: str) -> pd.DataFrame:
    """Loads (and caches) the local competitor file for a country/state.
    Returns an empty DataFrame (not an error) if none is configured — the
    pipeline just skips competitor features in that case."""
    key = f"{country}|{state}"
    if key in _MEMORY_CACHE:
        return _MEMORY_CACHE[key]

    path = get_competitor_path(country, state)
    if not path or not path.exists():
        log.info(f"[Competitors] No local competitor file for {country}/{state} — "
                 f"Competitor_2km/5km will be 0 for all rows.")
        df = pd.DataFrame(columns=["Latitude", "Longitude", "Name", "Category", "City"])
        _MEMORY_CACHE[key] = df
        return df

    suffix = path.suffix.lower()
    df = pd.read_csv(path) if suffix == ".csv" else pd.read_excel(path)
    df.columns = df.columns.astype(str).str.strip()
    rename = {c: _RENAME[c.lower()] for c in df.columns if c.lower() in _RENAME}
    df = df.rename(columns=rename)

    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        log.warning(f"[Competitors] '{path.name}' has no Latitude/Longitude columns "
                     f"after rename — found {list(df.columns)}. Skipping.")
        df = pd.DataFrame(columns=["Latitude", "Longitude", "Name", "Category", "City"])
        _MEMORY_CACHE[key] = df
        return df

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df = df.dropna(subset=["Latitude", "Longitude"])
    df = df[(df["Latitude"] != 0) | (df["Longitude"] != 0)]

    log.info(f"[Competitors] Loaded {len(df)} competitor locations from {path.name}")
    _MEMORY_CACHE[key] = df
    return df


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
