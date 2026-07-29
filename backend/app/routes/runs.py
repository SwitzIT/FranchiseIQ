"""Saved prediction run history — lets a user come back and see past results."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import PredictionRun
from app.auth import get_current_user
from app.services import get_key, session_exists

router = APIRouter(prefix="/runs", tags=["Prediction Runs"])


class SaveRunRequest(BaseModel):
    session_id: str
    label: str | None = None


@router.post("/save")
def save_run(body: SaveRunRequest, db: Session = Depends(get_db),
             current_user: str = Depends(get_current_user)):
    if not session_exists(body.session_id):
        raise HTTPException(404, "Session not found.")
    results = get_key(body.session_id, "results")
    if results is None:
        raise HTTPException(400, "No results yet for this session. Call /predict first.")

    run = PredictionRun(
        user_email=current_user,
        country=get_key(body.session_id, "country") or "",
        state=get_key(body.session_id, "state") or "",
        label=body.label,
        top_picks=results.get("top_picks", []),
        kpis=results.get("kpis", {}),
        model_metrics=results.get("model_metrics", {}),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"success": True, "run_id": run.id}


@router.get("")
def list_runs(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    runs = (
        db.query(PredictionRun)
        .filter(PredictionRun.user_email == current_user)
        .order_by(PredictionRun.created_at.desc())
        .all()
    )
    return {
        "success": True,
        "runs": [
            {
                "id": r.id, "country": r.country, "state": r.state, "label": r.label,
                "kpis": r.kpis, "model_metrics": r.model_metrics,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ],
    }


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db),
            current_user: str = Depends(get_current_user)):
    run = db.query(PredictionRun).filter(
        PredictionRun.id == run_id, PredictionRun.user_email == current_user
    ).first()
    if not run:
        raise HTTPException(404, "Run not found.")
    return {
        "success": True,
        "id": run.id, "country": run.country, "state": run.state, "label": run.label,
        "top_picks": run.top_picks, "kpis": run.kpis, "model_metrics": run.model_metrics,
        "created_at": run.created_at.isoformat(),
    }


@router.delete("/{run_id}")
def delete_run(run_id: str, db: Session = Depends(get_db),
                current_user: str = Depends(get_current_user)):
    run = db.query(PredictionRun).filter(
        PredictionRun.id == run_id, PredictionRun.user_email == current_user
    ).first()
    if not run:
        raise HTTPException(404, "Run not found.")
    db.delete(run)
    db.commit()
    return {"success": True}
