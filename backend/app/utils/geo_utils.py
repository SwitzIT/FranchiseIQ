"""Geospatial utility functions for FranchiseIQ."""
import numpy as np
import pandas as pd


def haversine_vectorized(lat1: np.ndarray, lon1: np.ndarray,
                          lat2: float, lon2: float) -> np.ndarray:
    """Vectorised Haversine distance (km) from one point to an array of points."""
    R = 6371.0
    lat1r, lon1r, lat2r, lon2r = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def haversine_scalar(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Scalar Haversine distance (km)."""
    return float(haversine_vectorized(
        np.array([lat1]), np.array([lon1]), lat2, lon2
    )[0])


def distance_weight(dist_km: float, scale: float = 0.1) -> float:
    """
    Converts distance to a weight [0, 1].
    Closer → higher weight. scale controls decay steepness.
    weight = 1 / (1 + scale * dist_km)
    """
    return 1.0 / (1.0 + scale * max(dist_km, 0.0))


def nearest_neighbor_index(target_lats: np.ndarray,
                            target_lons: np.ndarray,
                            query_lat: float,
                            query_lon: float) -> tuple[int, float]:
    """
    Returns (index, distance_km) of the nearest point in (target_lats, target_lons)
    to the given query point.
    """
    dists = haversine_vectorized(target_lats, target_lons, query_lat, query_lon)
    idx = int(np.argmin(dists))
    return idx, float(dists[idx])


def safe_int(v, default: int = 0) -> int:
    """Convert a value to int, returning default on NaN / errors."""
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def safe_float(v, default: float = 0.0) -> float:
    """Convert a value to float, returning default on NaN / errors."""
    try:
        if v is None:
            return default
        f = float(v)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default
