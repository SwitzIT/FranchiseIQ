"""Business units upload route."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.services.clustering_service import load_business_units
from app.services import get_key, set_key, session_exists
from app.utils import get_logger

log = get_logger("routes.business_units")
router = APIRouter(tags=["Business Units"])


@router.post("/upload_business_units")
async def upload_business_units(
    session_id: str        = Form(...),
    bu_file:    UploadFile = File(...),
):
    """
    Upload a CSV/Excel file with business unit (kitchen/hub) locations.
    Required columns: Name, Latitude, Longitude
    """
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    file_bytes = await bu_file.read()
    try:
        bu_df = load_business_units(file_bytes, bu_file.filename)
        set_key(session_id, "bu_df", bu_df)
    except ValueError as e:
        raise HTTPException(422, str(e))

    preview = bu_df.head(5).to_dict(orient="records")
    log.info(f"[BU] session={session_id} n={len(bu_df)}")
    return {
        "success":     True,
        "n_units":     len(bu_df),
        "preview":     preview,
        "columns":     list(bu_df.columns),
    }


@router.delete("/business_units")
def clear_business_units(session_id: str):
    """Remove business units from session (user chose 'No')."""
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")
    set_key(session_id, "bu_df", None)
    return {"success": True, "message": "Business units cleared."}
