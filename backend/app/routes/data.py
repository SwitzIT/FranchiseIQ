"""Data loading route — uploads stores + requests files, loads demographics, or loads preloaded backend files."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
import pandas as pd
from pathlib import Path

from app.config import get_preloaded_files
from app.services import (
    load_demographics, parse_uploaded_df, standardise_df,
    get_key, set_key, session_exists,
)
from app.utils import get_logger

log = get_logger("routes.data")
router = APIRouter(tags=["Data"])


class LoadPreloadedRequest(BaseModel):
    session_id: str


def _read_excel_or_csv(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        try:
            return pd.read_excel(path, sheet_name="Franchise Data")
        except Exception:
            return pd.read_excel(path)
    else:
        return pd.read_csv(path)


@router.post("/load_data")
async def load_data(
    session_id:     str        = Form(...),
    stores_file:    UploadFile = File(...),
    requests_file:  UploadFile = File(None),
):
    """
    Accepts:
      - stores_file   (required) — existing franchise stores
      - requests_file (optional) — franchise request locations
    Loads demographics for the country/state in the current session.
    Stores all DataFrames in session for downstream pipeline use.
    """
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    country = get_key(session_id, "country")
    state   = get_key(session_id, "state")
    if not country or not state:
        raise HTTPException(400, "Country/state not selected. Call /select_country and /select_state first.")

    # Load demographics
    try:
        demog_df = load_demographics(country, state)
        set_key(session_id, "demographics_df", demog_df)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(422, str(e))

    # Parse stores
    stores_bytes = await stores_file.read()
    try:
        stores_df = parse_uploaded_df(stores_bytes, stores_file.filename)
        set_key(session_id, "stores_df", stores_df)
    except ValueError as e:
        raise HTTPException(422, f"Stores file error: {e}")

    # Parse requests (optional)
    requests_df = None
    if requests_file and requests_file.filename:
        req_bytes = await requests_file.read()
        try:
            requests_df = parse_uploaded_df(req_bytes, requests_file.filename)
            set_key(session_id, "requests_df", requests_df)
        except ValueError as e:
            raise HTTPException(422, f"Requests file error: {e}")

    log.info(f"[Data] session={session_id} stores={len(stores_df)} requests={len(requests_df) if requests_df is not None else 0}")

    return {
        "success":         True,
        "n_stores":        len(stores_df),
        "n_requests":      len(requests_df) if requests_df is not None else 0,
        "n_demographics":  len(demog_df),
        "store_columns":   list(stores_df.columns),
    }


@router.post("/load_preloaded")
def load_preloaded(body: LoadPreloadedRequest):
    """Loads configured store, requests, and business units files from backend downloads directory."""
    session_id = body.session_id
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    country = get_key(session_id, "country")
    state   = get_key(session_id, "state")
    if not country or not state:
        raise HTTPException(400, "Country/state not selected. Call /select_country and /select_state first.")

    # Load demographics
    try:
        demog_df = load_demographics(country, state)
        set_key(session_id, "demographics_df", demog_df)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(422, str(e))

    preloads = get_preloaded_files(country, state)
    stores_path = preloads.get("stores_file")
    bu_path = preloads.get("bu_file")
    requests_path = preloads.get("requests_file")

    if not stores_path:
        raise HTTPException(422, f"No preloaded stores file found for {state}, {country}.")

    # Load Stores
    try:
        df_stores = _read_excel_or_csv(stores_path)
        stores_df = standardise_df(df_stores)
        set_key(session_id, "stores_df", stores_df)
    except Exception as e:
        raise HTTPException(422, f"Failed to load preloaded stores file: {e}")

    # Load Requests (optional)
    requests_df = None
    if requests_path:
        try:
            df_req = _read_excel_or_csv(requests_path)
            requests_df = standardise_df(df_req)
            set_key(session_id, "requests_df", requests_df)
        except Exception as e:
            log.warning(f"Failed to load optional requests file {requests_path}: {e}")

    # Load Business Units (optional)
    bu_df = None
    if bu_path:
        try:
            df_bu = _read_excel_or_csv(bu_path)
            bu_df = standardise_df(df_bu)
            set_key(session_id, "bu_df", bu_df)
            set_key(session_id, "has_bu", True)
        except Exception as e:
            log.warning(f"Failed to load optional business units file {bu_path}: {e}")
    else:
        set_key(session_id, "has_bu", False)

    log.info(f"[Data Preloaded] session={session_id} stores={len(stores_df)} requests={len(requests_df) if requests_df is not None else 0} bu={len(bu_df) if bu_df is not None else 0}")

    return {
        "success": True,
        "n_stores": len(stores_df),
        "n_requests": len(requests_df) if requests_df is not None else 0,
        "n_bu": len(bu_df) if bu_df is not None else 0,
        "n_demographics": len(demog_df),
        "has_bu": bu_df is not None,
        "store_columns": list(stores_df.columns),
    }
