"""
Business Unit Clustering Service
Assigns each candidate/store to its nearest business unit (kitchen/hub).
Computes distance-based weights applied as a score multiplier.
"""
import numpy as np
import pandas as pd

from app.utils import get_logger, haversine_vectorized, distance_weight, safe_float

log = get_logger("clustering_service")


def assign_business_units(
    locations_df: pd.DataFrame,
    bu_df: pd.DataFrame,
    scale: float = 0.05,
) -> pd.DataFrame:
    """
    For each row in locations_df (needs Latitude, Longitude):
      - Find the nearest business unit in bu_df (needs Latitude, Longitude, Name)
      - Compute distance
      - Compute weight = 1 / (1 + scale * dist_km)
    Adds columns: BU_Name, BU_Lat, BU_Lon, BU_Dist_km, BU_Weight
    """
    if bu_df is None or bu_df.empty:
        log.warning("[Clustering] No business units provided — skipping assignment")
        locations_df["BU_Name"]    = "N/A"
        locations_df["BU_Dist_km"] = 0.0
        locations_df["BU_Weight"]  = 1.0
        return locations_df

    bu_df = _standardize_bu(bu_df)
    log.info(f"[Clustering] Assigning {len(locations_df)} locations → {len(bu_df)} BUs")

    bu_lats = bu_df["Latitude"].values
    bu_lons = bu_df["Longitude"].values
    bu_names = bu_df["Name"].values

    assigned_names, assigned_dists, assigned_weights = [], [], []

    for _, row in locations_df.iterrows():
        lat, lon = safe_float(row["Latitude"]), safe_float(row["Longitude"])
        dists = haversine_vectorized(bu_lats, bu_lons, lat, lon)
        idx = int(np.argmin(dists))
        dist_km = float(dists[idx])
        w = distance_weight(dist_km, scale=scale)
        assigned_names.append(bu_names[idx])
        assigned_dists.append(round(dist_km, 2))
        assigned_weights.append(round(w, 4))

    locations_df = locations_df.copy()
    locations_df["BU_Name"]    = assigned_names
    locations_df["BU_Dist_km"] = assigned_dists
    locations_df["BU_Weight"]  = assigned_weights
    return locations_df


def load_business_units(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Parse an uploaded business units file (CSV or Excel)."""
    import io
    suffix = filename.rsplit(".", 1)[-1].lower()
    buf = io.BytesIO(file_bytes)
    try:
        df = pd.read_excel(buf) if suffix in ("xlsx", "xls") else pd.read_csv(buf)
    except Exception as e:
        raise ValueError(f"Could not parse business units file: {e}") from e
    return _standardize_bu(df)


def _standardize_bu(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    rename_map = {
        c: target
        for c in df.columns
        for target, aliases in {
            "Name":      ["name", "unit_name", "store_name", "kitchen", "hub"],
            "Latitude":  ["latitude", "lat"],
            "Longitude": ["longitude", "lon", "long"],
        }.items()
        if c.lower() in aliases
    }
    df.rename(columns=rename_map, inplace=True)
    for col in ("Latitude", "Longitude"):
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ""), errors="coerce"
            )
    required = {"Name", "Latitude", "Longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Business units file missing columns: {missing}. "
            f"Found: {list(df.columns)}"
        )
    return df.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
