# """
# Services package — central exports (v3.2 FIXED)
# ─────────────────────────────────────────────────
# Re-exports both:
#   - v1 functions that pre-existing routes (country, data, amenities,
#     predict, etc.) rely on
#   - v3 functions added during the upgrade

# Behaviour change from v3.0: when a service module fails to import,
# this file now logs the actual failure via the warning channel instead
# of silently swallowing it. The defensive try/except is still here
# (so a missing optional service doesn't crash the app), but at least
# you can grep the logs for "service-import-failed" to see what's wrong.
# """
# import logging

# _log = logging.getLogger("services.__init__")


# def _try_import(module_path: str, names: list[str]):
#     """
#     Attempt to import `names` from `module_path` into this namespace.
#     On ImportError, log a warning naming the module and missing name(s),
#     and define no-op fallbacks so dependent code doesn't crash at runtime.
#     """
#     try:
#         mod = __import__(module_path, fromlist=names)
#         for n in names:
#             if hasattr(mod, n):
#                 globals()[n] = getattr(mod, n)
#             else:
#                 _log.warning("service-import-failed: %s has no attribute '%s'",
#                              module_path, n)
#                 globals()[n] = _make_fallback(n)
#     except ImportError as e:
#         _log.warning("service-import-failed: cannot import %s (%s)", module_path, e)
#         for n in names:
#             globals()[n] = _make_fallback(n)


# def _make_fallback(name: str):
#     """Return a no-op callable that warns when invoked."""
#     def _fb(*args, **kwargs):
#         _log.warning("Called fallback for missing service '%s' — returning None/[].", name)
#         if "list" in name or name.endswith("s"):
#             return []
#         return None
#     _fb.__name__ = name
#     return _fb


# # ────────────────────────────────────────────────────────────────────
# # v1: session store
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.session_store", [
#     "new_session", "get_key", "set_key", "get_session",
#     "session_exists", "purge_expired",
# ])

# # Backwards-compat alias for v3 code that uses create_session/delete_session
# if "new_session" in globals() and "create_session" not in globals():
#     create_session = globals()["new_session"]

# def delete_session(sid):
#     """No-op: existing session_store doesn't have delete; sessions auto-purge."""
#     pass


# # ────────────────────────────────────────────────────────────────────
# # v1: demographics
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.demographics_service", [
#     "load_demographics", "get_countries_list",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v1: amenities
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.amenities_service", [
#     "get_amenities", "count_amenities_near_points", "get_cache_status",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v1: scoring / pipeline
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.scoring_service", [
#     "run_pipeline", "parse_uploaded_df", "standardise_df",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v1: clustering / business units
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.clustering_service", [
#     "load_business_units",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v1: real estate
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.real_estate_service", [
#     # Whatever functions exist; we re-export defensively.
# ])


# # ────────────────────────────────────────────────────────────────────
# # v2: hex aggregation
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.hex_aggregation_service", [
#     "compute_hex_heatmap", "suggest_resolution",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v3: data validation
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.data_validation_service", [
#     "validate_stores",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v3: peer-context
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.peer_context_service", [
#     "cluster_stores_by_catchment",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v3 + v3.1: competitor
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.competitor_service", [
#     "load_templates", "get_suggested_competitors", "get_available_categories",
#     "initialize_tenant_competitors",
#     # v3.1 new names:
#     "get_competitor_locations_for_tenant", "aggregate_locations_to_hexes",
#     "get_competitor_density_for_tenant",
#     # v3.0 legacy names still referenced by site_discovery_service:
#     "aggregate_competitors_to_hexes",
#     "CompetitorBrand",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v3: untapped demand
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.untapped_demand_service", [
#     "compute_untapped_demand", "generate_candidate_grid",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v3: site discovery
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.site_discovery_service", [
#     "list_available_territories", "get_territory_bbox", "analyse_territory",
# ])


# # ────────────────────────────────────────────────────────────────────
# # v3: region geocoding
# # ────────────────────────────────────────────────────────────────────
# _try_import("app.services.region_geocoding_service", [
#     "reverse_geocode", "reverse_geocode_many", "enrich_stores_with_regions",
# ])


# # ────────────────────────────────────────────────────────────────────
# # __all__ for IDE autocomplete + namespace hygiene
# # ────────────────────────────────────────────────────────────────────
# __all__ = [
#     # session
#     "new_session", "create_session", "delete_session",
#     "get_key", "set_key", "get_session", "session_exists", "purge_expired",
#     # demographics
#     "load_demographics", "get_countries_list",
#     # amenities
#     "get_amenities", "count_amenities_near_points", "get_cache_status",
#     # scoring
#     "run_pipeline", "parse_uploaded_df", "standardise_df",
#     # clustering
#     "load_business_units",
#     # hex
#     "compute_hex_heatmap", "suggest_resolution",
#     # v3
#     "validate_stores",
#     "cluster_stores_by_catchment",
#     "load_templates", "get_suggested_competitors", "get_available_categories",
#     "initialize_tenant_competitors",
#     "get_competitor_locations_for_tenant", "aggregate_locations_to_hexes",
#     "get_competitor_density_for_tenant",
#     "aggregate_competitors_to_hexes",
#     "CompetitorBrand",
#     "compute_untapped_demand", "generate_candidate_grid",
#     "list_available_territories", "get_territory_bbox", "analyse_territory",
#     "reverse_geocode", "reverse_geocode_many", "enrich_stores_with_regions",
# ]
"""
Services package — Lazy Import Version

Benefits:
- No eager imports during startup
- Heavy dependencies (pandas, geopandas, h3, ML models, etc.)
  load only when actually needed
- Failed imports are logged
- Imported objects are cached after first access
"""

from __future__ import annotations

import importlib
import logging

_log = logging.getLogger("services")

# ------------------------------------------------------------------
# Lazy export registry
# ------------------------------------------------------------------

_EXPORTS = {
    # --------------------------------------------------------------
    # session_store
    # --------------------------------------------------------------
    "new_session": (
        "app.services.session_store",
        "new_session",
    ),
    "get_key": (
        "app.services.session_store",
        "get_key",
    ),
    "set_key": (
        "app.services.session_store",
        "set_key",
    ),
    "get_session": (
        "app.services.session_store",
        "get_session",
    ),
    "session_exists": (
        "app.services.session_store",
        "session_exists",
    ),
    "purge_expired": (
        "app.services.session_store",
        "purge_expired",
    ),

    # --------------------------------------------------------------
    # demographics
    # --------------------------------------------------------------
    "load_demographics": (
        "app.services.demographics_service",
        "load_demographics",
    ),
    "get_countries_list": (
        "app.services.demographics_service",
        "get_countries_list",
    ),

    # --------------------------------------------------------------
    # amenities
    # --------------------------------------------------------------
    "get_amenities": (
        "app.services.amenities_service",
        "get_amenities",
    ),
    "count_amenities_near_points": (
        "app.services.amenities_service",
        "count_amenities_near_points",
    ),
    "get_cache_status": (
        "app.services.amenities_service",
        "get_cache_status",
    ),

    # --------------------------------------------------------------
    # scoring
    # --------------------------------------------------------------
    "run_pipeline": (
        "app.services.scoring_service",
        "run_pipeline",
    ),
    "parse_uploaded_df": (
        "app.services.scoring_service",
        "parse_uploaded_df",
    ),
    "standardise_df": (
        "app.services.scoring_service",
        "standardise_df",
    ),

    # --------------------------------------------------------------
    # clustering
    # --------------------------------------------------------------
    "load_business_units": (
        "app.services.clustering_service",
        "load_business_units",
    ),

    # --------------------------------------------------------------
    # hex aggregation
    # --------------------------------------------------------------
    "compute_hex_heatmap": (
        "app.services.hex_aggregation_service",
        "compute_hex_heatmap",
    ),
    "suggest_resolution": (
        "app.services.hex_aggregation_service",
        "suggest_resolution",
    ),

    # --------------------------------------------------------------
    # data validation
    # --------------------------------------------------------------
    "validate_stores": (
        "app.services.data_validation_service",
        "validate_stores",
    ),

    # --------------------------------------------------------------
    # peer context
    # --------------------------------------------------------------
    "cluster_stores_by_catchment": (
        "app.services.peer_context_service",
        "cluster_stores_by_catchment",
    ),

    # --------------------------------------------------------------
    # competitor
    # --------------------------------------------------------------
    "load_templates": (
        "app.services.competitor_service",
        "load_templates",
    ),
    "get_suggested_competitors": (
        "app.services.competitor_service",
        "get_suggested_competitors",
    ),
    "get_available_categories": (
        "app.services.competitor_service",
        "get_available_categories",
    ),
    "initialize_tenant_competitors": (
        "app.services.competitor_service",
        "initialize_tenant_competitors",
    ),
    "get_competitor_locations_for_tenant": (
        "app.services.competitor_service",
        "get_competitor_locations_for_tenant",
    ),
    "aggregate_locations_to_hexes": (
        "app.services.competitor_service",
        "aggregate_locations_to_hexes",
    ),
    "get_competitor_density_for_tenant": (
        "app.services.competitor_service",
        "get_competitor_density_for_tenant",
    ),
    "aggregate_competitors_to_hexes": (
        "app.services.competitor_service",
        "aggregate_competitors_to_hexes",
    ),
    "CompetitorBrand": (
        "app.services.competitor_service",
        "CompetitorBrand",
    ),

    # --------------------------------------------------------------
    # untapped demand
    # --------------------------------------------------------------
    "compute_untapped_demand": (
        "app.services.untapped_demand_service",
        "compute_untapped_demand",
    ),
    "generate_candidate_grid": (
        "app.services.untapped_demand_service",
        "generate_candidate_grid",
    ),

    # --------------------------------------------------------------
    # site discovery
    # --------------------------------------------------------------
    "list_available_territories": (
        "app.services.site_discovery_service",
        "list_available_territories",
    ),
    "get_territory_bbox": (
        "app.services.site_discovery_service",
        "get_territory_bbox",
    ),
    "analyse_territory": (
        "app.services.site_discovery_service",
        "analyse_territory",
    ),

    # --------------------------------------------------------------
    # region geocoding
    # --------------------------------------------------------------
    "reverse_geocode": (
        "app.services.region_geocoding_service",
        "reverse_geocode",
    ),
    "reverse_geocode_many": (
        "app.services.region_geocoding_service",
        "reverse_geocode_many",
    ),
    "enrich_stores_with_regions": (
        "app.services.region_geocoding_service",
        "enrich_stores_with_regions",
    ),
}


# ------------------------------------------------------------------
# Compatibility alias
# ------------------------------------------------------------------

def create_session(*args, **kwargs):
    return __getattr__("new_session")(*args, **kwargs)


def delete_session(_sid):
    """
    Existing session_store has no delete function.
    Sessions are cleaned via purge_expired().
    """
    return None


# ------------------------------------------------------------------
# Lazy loader
# ------------------------------------------------------------------

def __getattr__(name):
    """
    Load exported service functions/classes on first access.
    """

    if name not in _EXPORTS:
        raise AttributeError(
            f"module '{__name__}' has no attribute '{name}'"
        )

    module_name, attr_name = _EXPORTS[name]

    try:
        module = importlib.import_module(module_name)
        value = getattr(module, attr_name)

        # Cache for future access
        globals()[name] = value

        return value

    except Exception:
        _log.exception(
            "lazy-service-import-failed: %s.%s",
            module_name,
            attr_name,
        )
        raise


# ------------------------------------------------------------------
# IDE support
# ------------------------------------------------------------------

__all__ = [
    "new_session",
    "create_session",
    "delete_session",
    "get_key",
    "set_key",
    "get_session",
    "session_exists",
    "purge_expired",

    "load_demographics",
    "get_countries_list",

    "get_amenities",
    "count_amenities_near_points",
    "get_cache_status",

    "run_pipeline",
    "parse_uploaded_df",
    "standardise_df",

    "load_business_units",

    "compute_hex_heatmap",
    "suggest_resolution",

    "validate_stores",

    "cluster_stores_by_catchment",

    "load_templates",
    "get_suggested_competitors",
    "get_available_categories",
    "initialize_tenant_competitors",
    "get_competitor_locations_for_tenant",
    "aggregate_locations_to_hexes",
    "get_competitor_density_for_tenant",
    "aggregate_competitors_to_hexes",
    "CompetitorBrand",

    "compute_untapped_demand",
    "generate_candidate_grid",

    "list_available_territories",
    "get_territory_bbox",
    "analyse_territory",

    "reverse_geocode",
    "reverse_geocode_many",
    "enrich_stores_with_regions",
]