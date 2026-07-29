"""
Database engine & session management.

Defaults to a local SQLite file so the app runs with zero setup.
Set DATABASE_URL to point at Postgres in production, e.g.:
    postgresql+psycopg2://user:password@host:5432/franchiseiq
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./franchiseiq.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they don't exist. Call once on startup."""
    from app.db import models  # noqa: F401 (ensures models are registered on Base)
    Base.metadata.create_all(bind=engine)
