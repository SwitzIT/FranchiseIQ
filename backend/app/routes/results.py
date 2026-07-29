"""Results retrieval and Excel export route."""
import io
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.services import get_key, session_exists
from app.utils import get_logger
from app.auth import get_current_user

log = get_logger("routes.results")
router = APIRouter(tags=["Results"])


@router.get("/get_results")
def get_results(session_id: str, current_user: str = Depends(get_current_user)):
    """Return cached prediction results for the session."""
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")
    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet. Call /predict first.")
    return {"success": True, **results}


@router.get("/download_results")
def download_results(session_id: str, current_user: str = Depends(get_current_user)):
    """Download full results as an Excel file."""
    if not session_exists(session_id):
        raise HTTPException(404, "Session not found.")
    results = get_key(session_id, "results")
    if results is None:
        raise HTTPException(400, "No results. Run /predict first.")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        top_df  = pd.DataFrame(results.get("top_picks", []))
        all_df  = pd.DataFrame(results.get("all_candidates", []))
        kpi_df  = pd.DataFrame([results.get("kpis", {})])
        if not top_df.empty:
            top_df.to_excel(writer, sheet_name="Top Picks", index=False)
        if not all_df.empty:
            all_df.to_excel(writer, sheet_name="All Candidates", index=False)
        if not kpi_df.empty:
            kpi_df.to_excel(writer, sheet_name="KPIs", index=False)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=franchise_results.xlsx"},
    )
