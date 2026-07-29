"""
Competitor DB Cache
───────────────────
Persistent storage for competitor brand locations. Backs the
extract-once-then-query pattern used across all enrichment data in
FranchiseIQ.

Storage backend: SQLite by default (zero-config, file-based, fine up
to ~hundreds of thousands of rows). To swap in Postgres/MySQL to match
your production DB, only the four public functions below need to be
re-implemented against the new driver — callers don't change.

The DB file path is configurable via the COMPETITOR_DB_PATH env var,
defaulting to `backend/data/competitor_cache.db`.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.utils import get_logger

log = get_logger("services.competitor_db")

DB_PATH = os.environ.get(
    "COMPETITOR_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "competitor_cache.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS competitor_locations (
    brand_name   TEXT NOT NULL,
    country      TEXT NOT NULL,
    place_id     TEXT NOT NULL,
    name         TEXT,
    lat          REAL NOT NULL,
    lng          REAL NOT NULL,
    address      TEXT,
    rating       REAL,
    region_hint  TEXT,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (brand_name, country, place_id)
);

CREATE INDEX IF NOT EXISTS idx_brand_country
    ON competitor_locations(brand_name, country);
CREATE INDEX IF NOT EXISTS idx_country
    ON competitor_locations(country);
"""


@contextmanager
def _connect():
    """Open a SQLite connection, ensuring schema exists. Commits on success."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Public API — these four functions are what callers use
# ─────────────────────────────────────────────────────────────────────────────

def upsert_brand_locations(
    brand: str, country: str, locations: List[Dict[str, Any]]
) -> int:
    """
    Replace all stored locations for (brand, country) with the new list.

    Atomic: deletes existing rows for the brand, then inserts new ones in
    the same transaction. Returns the number of rows inserted.
    """
    now = datetime.utcnow().isoformat() + "Z"
    rows = [
        (brand, country, loc.get("place_id"), loc.get("name"),
         loc.get("lat"), loc.get("lng"), loc.get("address"),
         loc.get("rating"), loc.get("region_hint"), now)
        for loc in locations
        if loc.get("place_id") and loc.get("lat") is not None and loc.get("lng") is not None
    ]

    with _connect() as conn:
        conn.execute(
            "DELETE FROM competitor_locations WHERE brand_name=? AND country=?",
            (brand, country),
        )
        if rows:
            conn.executemany(
                "INSERT INTO competitor_locations "
                "(brand_name, country, place_id, name, lat, lng, address, rating, "
                " region_hint, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    log.info("upsert %d locations for '%s' in %s", len(rows), brand, country)
    return len(rows)


def get_brand_locations(brand: str, country: str) -> List[Dict[str, Any]]:
    """Read all cached locations for a single (brand, country) pair."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM competitor_locations WHERE brand_name=? AND country=?",
            (brand, country),
        ).fetchall()
    return [dict(r) for r in rows]


def get_locations_for_brands(
    brands: List[str], country: str
) -> List[Dict[str, Any]]:
    """
    Bulk query across multiple brands in a country. Used at runtime to
    assemble the competitor density layer.
    """
    if not brands:
        return []
    placeholders = ",".join("?" * len(brands))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM competitor_locations "
            f"WHERE country=? AND brand_name IN ({placeholders})",
            (country, *brands),
        ).fetchall()
    return [dict(r) for r in rows]


def get_brand_freshness(brand: str, country: str) -> Optional[str]:
    """
    Last-refreshed timestamp for a brand+country (ISO string), or None
    if never fetched. Used by the monthly cron to decide what to refresh.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(fetched_at) AS last FROM competitor_locations "
            "WHERE brand_name=? AND country=?",
            (brand, country),
        ).fetchone()
    return row["last"] if row and row["last"] else None


def delete_brand(brand: str, country: str) -> int:
    """Remove all rows for a brand+country (used when a tenant deselects a brand)."""
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM competitor_locations WHERE brand_name=? AND country=?",
            (brand, country),
        )
        return cur.rowcount


def list_brands_for_country(country: str) -> List[Dict[str, Any]]:
    """
    For admin / debugging: list every brand in the cache for a country
    with row count and last-refresh timestamp.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT brand_name, COUNT(*) AS count, MAX(fetched_at) AS last_refresh "
            "FROM competitor_locations WHERE country=? GROUP BY brand_name "
            "ORDER BY brand_name",
            (country,),
        ).fetchall()
    return [dict(r) for r in rows]
