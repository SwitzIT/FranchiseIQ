"""Country + State selection endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import COUNTRIES, get_state_config
from app.services import get_countries_list, new_session, set_key
from app.utils import get_logger

log = get_logger("routes.country")
router = APIRouter(tags=["Country"])


@router.get("/countries")
def list_countries():
    """Return all supported countries with their states and data status."""
    return {"success": True, "countries": get_countries_list()}


class SelectCountryRequest(BaseModel):
    country: str


@router.post("/select_country")
def select_country(body: SelectCountryRequest):
    """
    Creates a new session, stores selected country.
    Returns states available for that country.
    """
    country = body.country
    if country not in COUNTRIES:
        raise HTTPException(400, f"Unsupported country: '{country}'")

    sid = new_session()
    set_key(sid, "country", country)

    states_meta = []
    for state_name, scfg in COUNTRIES[country]["states"].items():
        from app.config import get_demographics_path
        p = get_demographics_path(country, state_name)
        states_meta.append({
            "name":       state_name,
            "has_data":   p.exists(),
            "center":     scfg["center"],
            "zoom":       scfg["zoom"],
        })

    log.info(f"[Country] session={sid} country={country}")
    return {
        "success":    True,
        "session_id": sid,
        "country":    country,
        "currency_symbol": COUNTRIES[country].get("currency_symbol", "$"),
        "currency_code":   COUNTRIES[country].get("currency_code", "USD"),
        "states":     states_meta,
    }


class SelectStateRequest(BaseModel):
    session_id: str
    state: str


@router.post("/select_state")
def select_state(body: SelectStateRequest):
    """Store selected state in session, return config metadata."""
    from app.services import session_exists
    if not session_exists(body.session_id):
        raise HTTPException(404, "Session not found. Call /api/select_country first.")
    from app.services import get_key
    country = get_key(body.session_id, "country")
    if not country:
        raise HTTPException(400, "Country not set in session.")
    try:
        cfg = get_state_config(country, body.state)
    except ValueError as e:
        raise HTTPException(400, str(e))

    set_key(body.session_id, "state", body.state)
    log.info(f"[State] session={body.session_id} state={body.state}")
    return {
        "success":       True,
        "state":         body.state,
        "center":        cfg["center"],
        "zoom":          cfg["zoom"],
        "has_kitchen":   cfg["default_kitchen"] is not None,
        "default_kitchen": cfg["default_kitchen"],
    }
