"""
FranchiseIQ application package initialization.

NOTE:
- Do NOT import FastAPI objects or routers here.
- This file should only expose core app-level constants/classes.
"""

from app.config import APP_TITLE, APP_VERSION
from app.models.affinity_model import FranchiseModel
from app.utils import get_logger, haversine_vectorized, safe_int, safe_float

# IMPORTANT:
# Routers are NOT imported here anymore.
# They are managed exclusively in app.routes and main.py.

__all__ = [
    "APP_TITLE",
    "APP_VERSION",
    "FranchiseModel",
    "get_logger",
    "haversine_vectorized",
    "safe_int",
    "safe_float",
]
