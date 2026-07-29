"""
Session store — in-memory with TTL.
Stores per-session DataFrames and pipeline state so API calls
can be stateless (just pass session_id).
"""
import time
import threading
import uuid
from typing import Any

from app.config import SESSION_TTL_SEC
from app.utils import get_logger

log = get_logger("session_store")

_store: dict[str, dict] = {}
_lock = threading.Lock()


def new_session() -> str:
    sid = str(uuid.uuid4())
    with _lock:
        _store[sid] = {"_ts": time.time()}
    return sid


def set_key(sid: str, key: str, value: Any):
    with _lock:
        if sid not in _store:
            _store[sid] = {}
        _store[sid][key] = value
        _store[sid]["_ts"] = time.time()


def get_key(sid: str, key: str, default=None):
    with _lock:
        return _store.get(sid, {}).get(key, default)


def get_session(sid: str) -> dict:
    with _lock:
        return _store.get(sid, {}).copy()


def session_exists(sid: str) -> bool:
    with _lock:
        return sid in _store


def purge_expired():
    """Remove sessions older than SESSION_TTL_SEC. Call periodically."""
    now = time.time()
    with _lock:
        expired = [k for k, v in _store.items() if now - v.get("_ts", 0) > SESSION_TTL_SEC]
        for k in expired:
            del _store[k]
    if expired:
        log.info(f"[Session] Purged {len(expired)} expired sessions")
