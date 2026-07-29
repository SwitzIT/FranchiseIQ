import uuid
import datetime as dt
from sqlalchemy import Column, String, DateTime, JSON

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class PredictionRun(Base):
    """A saved snapshot of a /predict pipeline run — lets a user come back
    and see past location recommendations instead of losing everything when
    the session expires.

    v6.0: keyed by `user_email` (a plain string from users.json), not a
    foreign key to a Users table — there's no Users table anymore since
    login credentials live in users.json instead of the database."""
    __tablename__ = "prediction_runs"

    id = Column(String, primary_key=True, default=_uuid)
    user_email = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False)
    state = Column(String, nullable=False)
    label = Column(String, nullable=True)          # optional user-given name
    top_picks = Column(JSON, nullable=False)
    kpis = Column(JSON, nullable=False)
    model_metrics = Column(JSON, nullable=True)
    model_method = Column(String, default="amenity_affinity_scoring_v4")
    created_at = Column(DateTime, default=dt.datetime.utcnow)
