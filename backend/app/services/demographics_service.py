"""
Agent 2 — Demographics Loader Service
Loads pre-existing demographic data for a country/state.
Supports CSV, XLSX, and Parquet. Validates required columns.
"""
import pandas as pd
from pathlib import Path

from app.config import get_demographics_path, COUNTRIES
from app.utils import get_logger

log = get_logger("demographics_service")

REQUIRED_COLS = {"Latitude", "Longitude"}
OPTIONAL_RENAME = {
    "latitude": "Latitude", "lat": "Latitude",
    "longitude": "Longitude", "lon": "Longitude", "long": "Longitude",
    "population": "Population", "pop": "Population",
    "income": "Income", "avg_income": "Income",
    # v4.0 — your real West Bengal file uses these exact headers; the old
    # exact-match rename above never matched any of them, so Income
    # silently defaulted to 0 for every row. Your file has BOTH monthly
    # and annual columns at once, so each gets its own unique target
    # column (mapping two source columns to "Income" would create a
    # duplicate-named column and break downstream numeric coercion).
    # "Income" (used by the model's FEATURE_COLS) = monthly, INR.
    "monthly income (inr)": "Income",
    "annual income (inr)": "Annual_Income_INR",
    "monthly income (usd)": "Income_USD",
    "annual income (usd)": "Annual_Income_USD",
    "economic index": "Economic_Index",
}


def load_demographics(country: str, state: str) -> pd.DataFrame:
    """
    Load and validate demographic data for the given country/state.
    Returns a clean DataFrame with at minimum Latitude, Longitude columns.
    Raises FileNotFoundError if the file is missing.
    """
    path = get_demographics_path(country, state)
    log.info(f"[Demographics] Loading: {path}")

    if not path.exists():
        raise FileNotFoundError(
            f"Demographics file not found for {country}/{state}.\n"
            f"Expected: {path}\n"
            f"Please place your file at that location and restart."
        )

    df = _read_file(path)
    df = _normalise_columns(df)
    _validate(df, path)
    df = _coerce_numerics(df)
    df = df.dropna(subset=["Latitude", "Longitude"])
    df = df[(df["Latitude"] != 0) | (df["Longitude"] != 0)]
    log.info(f"[Demographics] Loaded {len(df)} rows from {path.name}")
    return df.reset_index(drop=True)


def get_countries_list() -> list[dict]:
    """Return countries + states metadata for the /api/countries endpoint."""
    from app.config import get_preloaded_files
    result = []
    for country_name, meta in COUNTRIES.items():
        states = []
        for state_name, scfg in meta["states"].items():
            p = get_demographics_path(country_name, state_name)
            preloads = get_preloaded_files(country_name, state_name)
            has_preloads = preloads.get("stores_file") is not None
            states.append({"name": state_name, "has_data": p.exists() and has_preloads})
        result.append({
            "name": country_name,
            "code": meta["code"],
            "states": states,
        })
    return result


# ─────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────
def _read_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    try:
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(path)
        elif suffix == ".csv":
            return pd.read_csv(path)
        elif suffix == ".parquet":
            return pd.read_parquet(path)
        else:
            # Try Excel default
            return pd.read_excel(path)
    except Exception as e:
        raise ValueError(f"Could not read demographics file {path}: {e}") from e


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.strip()
    rename = {
        col: OPTIONAL_RENAME[col.lower()]
        for col in df.columns
        if col.lower() in OPTIONAL_RENAME
    }
    return df.rename(columns=rename)


def _validate(df: pd.DataFrame, path: Path) -> None:
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"Demographics file '{path.name}' is missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )


def _coerce_numerics(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["Latitude", "Longitude", "Population", "Income"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ""), errors="coerce"
            )
    return df
