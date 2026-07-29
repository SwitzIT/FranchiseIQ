"""
FranchiseIQ — Central Configuration
Defines all country/state metadata, paths, and app settings.
No hardcoded file paths outside this file.

v5.0 — OSM removed as a dependency for amenities. All spatial context now
comes from local files you already have: AmenitiesWB.csv and
Mio_competitor.xlsx. Live OSM road/landuse enrichment is still supported
but OFF by default (ENABLE_OSM_GEO_FEATURES=false) since you don't want any
network fetching.
"""
import os
from pathlib import Path

# PROJECT_ROOT = FranchiseIQ/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ─────────────────────────────────────────────────────────────
# DIRECTORY PATHS  (resolved at runtime, Docker-friendly)
# ─────────────────────────────────────────────────────────────
DATA_DIR             = Path(os.getenv("DATA_DIR",             str(PROJECT_ROOT / "data")))
AMENITIES_DIR        = Path(os.getenv("AMENITIES_DIR",        str(PROJECT_ROOT / "amenities_cache")))
AMENITIES_SOURCE_DIR = Path(os.getenv("AMENITIES_SOURCE_DIR", str(PROJECT_ROOT / "amenities")))
COMPETITOR_DIR       = Path(os.getenv("COMPETITOR_DIR",       str(PROJECT_ROOT / "competitor")))
UPLOADS_DIR          = Path(os.getenv("UPLOADS_DIR",          str(PROJECT_ROOT / "uploads")))
OUTPUTS_DIR          = Path(os.getenv("OUTPUTS_DIR",          str(PROJECT_ROOT / "outputs")))
LOGS_DIR             = Path(os.getenv("LOGS_DIR",             str(PROJECT_ROOT / "logs")))
DOWNLOADS_DIR        = Path(os.getenv("DOWNLOADS_DIR",        str(PROJECT_ROOT / "downloads")))
REAL_ESTATE_DIR      = Path(os.getenv("REAL_ESTATE_DIR",      str(PROJECT_ROOT / "real_estate_data")))

for _d in [DATA_DIR, AMENITIES_DIR, AMENITIES_SOURCE_DIR, COMPETITOR_DIR, UPLOADS_DIR,
           OUTPUTS_DIR, LOGS_DIR, DOWNLOADS_DIR, REAL_ESTATE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# APP SETTINGS
# ─────────────────────────────────────────────────────────────
APP_TITLE         = "FranchiseIQ"
APP_VERSION       = "5.0.0"
BUFFER_RADIUS_M   = int(os.getenv("BUFFER_RADIUS_M",   "10000"))   # 10 km in metres
GRID_STEP_DEG     = float(os.getenv("GRID_STEP_DEG",   "0.05"))
TOP_N_LOCATIONS   = int(os.getenv("TOP_N_LOCATIONS",   "10"))
SESSION_TTL_SEC   = int(os.getenv("SESSION_TTL_SEC",   "3600"))    # 1 hour

# v5.0 — OSM road/landuse enrichment is OFF by default: no network calls at
# all during prediction. Flip to "true" only if you later want that extra
# signal AND are fine with a live Overpass/osmnx fetch on first run per state.
ENABLE_OSM_GEO_FEATURES = os.getenv("ENABLE_OSM_GEO_FEATURES", "false").lower() == "true"
OSM_RETRY_LIMIT   = int(os.getenv("OSM_RETRY_LIMIT",   "2"))   # only used if the flag above is enabled

# ─────────────────────────────────────────────────────────────
# COUNTRY / STATE REGISTRY
# ─────────────────────────────────────────────────────────────
COUNTRIES: dict = {
    "India": {
        "code": "IN",
        "currency_symbol": "₹",
        "currency_code": "INR",
        "states": {
            "West Bengal": {
                "demographics_file": "india/west_bengal/demographics.xlsx",
                "stores_file":       "Mio_franchise_stores.xlsx",
                "bu_file":           "Mio_business_unit.xlsx",
                "requests_file":     None,
                "real_estate_file":  "WestBengal_RealEstate.xlsx",
                "amenities_file":    "AmenitiesWB.csv",       # v5.0 — your local Google-Places-style export
                "competitor_file":   "Mio_competitor.xlsx",    # v5.0 — your local competitor spreadsheet
                "center":       [22.9868, 87.8550],
                "zoom":         8,
                "grid_bounds":  [21.0, 27.5, 85.8, 89.9],   # [lat_min, lat_max, lon_min, lon_max]
                "osm_query":    "West Bengal, India",  # only used if ENABLE_OSM_GEO_FEATURES=true
                "default_kitchen": None,
            },
            "Odisha": {
                "demographics_file": "india/odisha/demographics.xlsx",
                "stores_file":       None,
                "bu_file":           None,
                "requests_file":     None,
                "real_estate_file":  None,
                "amenities_file":    None,
                "competitor_file":   None,
                "center":       [20.9517, 85.0985],
                "zoom":         7,
                "grid_bounds":  [17.8, 22.6, 81.4, 87.5],
                "osm_query":    "Odisha, India",
                "default_kitchen": None,
            },
        },
    },
    "Sri Lanka": {
        "code": "LK",
        "currency_symbol": "රු",
        "currency_code": "LKR",
        "states": {
            "Sri Lanka": {
                "demographics_file": "srilanka/demographics.xlsx",
                "stores_file":       "srilanka_franchise_stores.xlsx",
                "bu_file":           "Srilanka_central_kitchen.xlsx",
                "requests_file":     "srilanka_franchise_requests.xlsx",
                "real_estate_file":  "Srilanka_real_estate.xlsx",
                "amenities_file":    None,
                "competitor_file":   None,
                "center":       [7.8731,  80.7718],
                "zoom":         8,
                "grid_bounds":  [5.8, 9.9, 79.5, 82.0],
                "osm_query":    "Sri Lanka",
                "default_kitchen": [6.9271, 79.8612],         # Colombo
            },
        },
    },
}

# ─────────────────────────────────────────────────────────────
# AMENITY BUCKETS
# v5.0 — kept OSM_TAGS/AMENITY_BUCKETS for anyone who later flips
# ENABLE_OSM_GEO_FEATURES / re-enables live OSM amenity fetching (not used
# by the default local-file pipeline), and added LOCAL_AMENITY_CATEGORY_
# BUCKETS which is what the local CSV/XLSX loader actually uses — matched
# against your AmenitiesWB.csv's "Query" column values (e.g. "restaurant
# in Kolkata, West Bengal").
# ─────────────────────────────────────────────────────────────
OSM_TAGS: dict = {
    "amenity": [
        "restaurant", "cafe", "fast_food",
        "school", "college", "university",
        "hospital", "clinic", "pharmacy",
        "bank", "atm",
        "place_of_worship",
        "bus_station",
    ],
    "shop": ["supermarket", "mall", "department_store"],
    "leisure": ["park"],
}

AMENITY_BUCKETS = {
    "restaurant":        "food",
    "cafe":              "food",
    "fast_food":         "food",
    "supermarket":       "retail",
    "mall":              "retail",
    "department_store":  "retail",
    "school":            "education",
    "college":           "education",
    "university":        "education",
    "hospital":          "health",
    "clinic":            "health",
    "pharmacy":          "health",
    "park":              "leisure",
    "bus_station":       "transport",
    "bank":              "finance",
    "atm":               "finance",
}

# Category keyword (lowercase) → bucket, for the LOCAL file loader.
# Order doesn't matter — first substring match wins.
LOCAL_AMENITY_CATEGORY_BUCKETS = {
    "restaurant":        "food",
    "cafe":              "food",
    "fast food":         "food",
    "supermarket":       "retail",
    "grocery":           "retail",
    "market":            "retail",
    "mall":              "retail",
    "department store":  "retail",
    "school":            "education",
    "college":           "education",
    "university":        "education",
    "hospital":          "health",
    "clinic":            "health",
    "pharmacy":          "health",
    "park":              "leisure",
    "bus station":       "transport",
    "bus stop":          "transport",
    "railway station":   "transport",
    "metro station":     "transport",
    "bank":              "finance",
    "atm":               "finance",
    "hotel":             "hospitality",
    "lodge":             "hospitality",
    "resort":            "hospitality",
    "post office":       "civic",
    "police station":    "civic",
}

# Full bucket list the scoring pipeline counts — includes the two new
# buckets (hospitality, civic) that showed up in your real data and weren't
# in the original OSM-tag-driven bucket set.
AMENITY_BUCKET_NAMES = [
    "food", "retail", "education", "health",
    "leisure", "transport", "finance", "hospitality", "civic",
]

# ─────────────────────────────────────────────────────────────
# FEATURE SCORING WEIGHTS  (tuned via scipy in scoring_service)
# ─────────────────────────────────────────────────────────────
DEFAULT_FEATURE_WEIGHTS = {
    "food_score":      0.20,
    "retail_score":    0.15,
    "education_score": 0.15,
    "health_score":    0.10,
    "Population":      0.25,
    "Income":          0.15,
}

# ─────────────────────────────────────────────────────────────
# CORS ORIGINS
# ─────────────────────────────────────────────────────────────
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
).split(",")


def get_state_config(country: str, state: str) -> dict:
    """Safe accessor for country/state config. Raises ValueError on bad keys."""
    c = COUNTRIES.get(country)
    if not c:
        raise ValueError(f"Unsupported country: '{country}'. Available: {list(COUNTRIES)}")
    s = c["states"].get(state)
    if not s:
        raise ValueError(
            f"Unsupported state: '{state}' in '{country}'. "
            f"Available: {list(c['states'])}"
        )
    return s


def get_demographics_path(country: str, state: str) -> Path:
    cfg = get_state_config(country, state)
    return DATA_DIR / cfg["demographics_file"]


def get_amenities_cache_path(country: str, state: str) -> Path:
    key = f"{country.lower().replace(' ', '_')}_{state.lower().replace(' ', '_')}"
    return AMENITIES_DIR / f"{key}.geojson"


def get_amenities_source_path(country: str, state: str) -> Path | None:
    """v5.0 — path to your local amenities CSV/XLSX (no network fetch)."""
    cfg = get_state_config(country, state)
    fname = cfg.get("amenities_file")
    if not fname:
        return None
    p = AMENITIES_SOURCE_DIR / fname
    return p if p.exists() else None


def get_competitor_path(country: str, state: str) -> Path | None:
    """v5.0 — path to your local competitor spreadsheet (no live Places API)."""
    cfg = get_state_config(country, state)
    fname = cfg.get("competitor_file")
    if not fname:
        return None
    p = COMPETITOR_DIR / fname
    return p if p.exists() else None


def get_real_estate_path(country: str, state: str) -> Path | None:
    cfg = get_state_config(country, state)
    fname = cfg.get("real_estate_file")
    if fname:
        p = REAL_ESTATE_DIR / fname
        return p if p.exists() else None
    return None


def get_downloads_path(filename: str) -> Path:
    """Return path to a pre-loaded data file in downloads/."""
    return DOWNLOADS_DIR / filename


def get_preloaded_files(country: str, state: str) -> dict:
    """
    Return resolved Path objects for pre-loaded data files of this country/state.
    Values are None when no file is configured or the file does not exist.
    """
    cfg = get_state_config(country, state)
    result = {}
    for key in ("stores_file", "bu_file", "requests_file"):
        fname = cfg.get(key)
        if fname:
            p = DOWNLOADS_DIR / fname
            result[key] = p if p.exists() else None
        else:
            result[key] = None
    return result
