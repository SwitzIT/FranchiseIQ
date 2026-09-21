"""Prediction orchestration route."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.services import run_pipeline, get_key, set_key, session_exists
from app.utils import get_logger
from app.auth import get_current_user

log = get_logger("routes.predict")
router = APIRouter(tags=["Prediction"])


class PredictRequest(BaseModel):
    session_id: str
    top_n: int = 10


@router.post("/predict")
def predict(body: PredictRequest, current_user: str = Depends(get_current_user)):
    """
    Runs the full scoring pipeline:
      1. Feature engineering (amenities + demographics + competition)
      2. Business unit clustering (if uploaded)
      3. Amenity-Affinity scoring (look-alike to top-performing stores)
    Returns top picks + all candidates + KPIs.
    Requires authentication (see users.json for who's allowed to log in).
    """
    sid = body.session_id
    if not session_exists(sid):
        raise HTTPException(404, "Session not found.")

    country      = get_key(sid, "country")
    state        = get_key(sid, "state")
    stores_df    = get_key(sid, "stores_df")
    demog_df     = get_key(sid, "demographics_df")
    amenities_gdf = get_key(sid, "amenities_gdf")
    requests_df  = get_key(sid, "requests_df")   # may be None
    bu_df        = get_key(sid, "bu_df")          # may be None

    if not country or not state:
        raise HTTPException(400, "Country/state not selected.")
    if stores_df is None:
        raise HTTPException(400, "Stores data not loaded. Call /load_data first.")
    if demog_df is None:
        raise HTTPException(400, "Demographics not loaded. Call /load_data first.")
    if amenities_gdf is None:
        raise HTTPException(400, "Amenities not loaded. Call /fetch_amenities first.")

    try:
        results = run_pipeline(
            country=country,
            state=state,
            stores_df=stores_df,
            demographics_df=demog_df,
            amenities_gdf=amenities_gdf,
            requests_df=requests_df,
            bu_df=bu_df,
            top_n=body.top_n,
        )
    except Exception as e:
        log.exception(f"[Predict] Pipeline error: {e}")
        raise HTTPException(500, f"Prediction pipeline failed: {str(e)}")

    set_key(sid, "results", results)
    log.info(f"[Predict] user={current_user} session={sid} top_picks={len(results['top_picks'])}")

    # Return the JSON directly: the result holds ~45k amenity points, and
    # FastAPI's default encoder makes several full copies of it first
    # (~100 MB extra), enough to exceed a 512 MB instance.
    return JSONResponse(content={"success": True, **results})
