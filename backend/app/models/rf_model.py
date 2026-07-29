"""
Random Forest Prediction Model — v3.6
=====================================
Trains on existing franchise stores, predicts revenue for candidate locations.

Improvements over v3.5:
  - Log-transformed target (revenue is log-normal): more stable predictions
  - Held-out validation (80/20 split) for honest R² and MAE; retrains on full
    data for production predictions afterwards
  - Absolute scoring: Score 50 = matches MEDIAN existing store, 100 = 2x median.
    Comparable across runs (not normalised to batch max).
  - Feature importance retained on the model so the API can surface drivers
  - Out-of-distribution detection: flags candidates whose feature values lie
    above the 95th percentile of training data (extrapolation risk)
  - Predicted revenue is hard-capped at 2x the maximum existing store —
    prevents wild extrapolation on weird grid candidates
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
import warnings
warnings.filterwarnings("ignore")

from app.utils import get_logger

log = get_logger("rf_model")

FEATURE_COLS = [
    "cnt_food", "cnt_retail", "cnt_education", "cnt_health",
    "cnt_leisure", "cnt_transport", "cnt_finance",
    "Population", "Income",
    "Nearest_Store_km", "stores_2km", "stores_5km",
    "Cannibalization_Score",
    # v3.7 — geographic features (added from OSM via osm_geographic_service)
    "dist_to_nearest_road_m",
    "is_commercial", "is_residential",
    "is_industrial", "is_agricultural", "is_natural",
]
RE_FEATURE_COLS = [
    "property_cost_index", "property_growth_score",
    "avg_property_price_3km", "avg_rent_3km", "commercial_count_3km",
    "commercial_density_3km", "property_growth_3km", "vacancy_rate_3km",
    "income_property_ratio", "amenity_growth_score",
    "population_commercial_score", "franchise_density_score",
    "market_saturation_score",
]
BU_FEATURE_COLS = ["BU_Dist_km", "BU_Weight"]


class FranchiseModel:
    """RF on existing stores → revenue prediction for candidates."""

    def __init__(self):
        self.model = None
        self.scaler = MinMaxScaler()
        self.feature_cols: list[str] = []
        self.median_existing_revenue: float = 1.0
        self.max_existing_revenue: float = 1.0
        self.training_feature_stats: dict[str, dict] = {}
        self.feature_importances: dict[str, float] = {}
        self.metrics: dict = {}
        self._is_trained = False

    # ────────────────────────────────────────────────────────────
    # TRAINING
    # ────────────────────────────────────────────────────────────
    def train(self, stores_df: pd.DataFrame, has_bu: bool = False,
              holdout_pct: float = 0.20) -> dict:
        """
        Train with held-out validation, then retrain on full data.

        Target = Adjusted_Sales (preferred) or Sales, then log1p-transformed.

        Returns honest metrics dict (R² on test split, NOT training fit).
        """
        df = stores_df.copy().fillna(0)

        # Drop stores with zero/missing sales — they are not informative
        target_col = "Adjusted_Sales" if "Adjusted_Sales" in df.columns else "Sales"
        if target_col not in df.columns:
            log.error("[Model] No target column found; cannot train")
            return {"error": "no target column"}

        df = df[pd.to_numeric(df[target_col], errors="coerce").fillna(0) > 0].copy()
        if len(df) == 0:
            log.error("[Model] No stores with positive sales")
            return {"error": "no positive-sales stores"}

        self.feature_cols = self._select_features(df, has_bu)
        y_raw = pd.to_numeric(df[target_col], errors="coerce").fillna(0).values.astype(float)

        # Persist revenue benchmarks for absolute scoring & cap
        self.median_existing_revenue = float(np.median(y_raw))
        self.max_existing_revenue = float(np.max(y_raw))

        # LOG-TRANSFORM TARGET (revenue is log-normal)
        y_log = np.log1p(y_raw)

        # Build feature matrix
        X = df.reindex(columns=self.feature_cols, fill_value=0).values.astype(float)

        # Store per-feature distribution stats — used later for OOD flagging
        for i, col in enumerate(self.feature_cols):
            col_vals = X[:, i]
            self.training_feature_stats[col] = {
                "min":  float(col_vals.min()),
                "p5":   float(np.percentile(col_vals, 5)),
                "mean": float(col_vals.mean()),
                "p95": float(np.percentile(col_vals, 95)),
                "max":  float(col_vals.max()),
            }

        X_scaled = self.scaler.fit_transform(X)

        # HELD-OUT VALIDATION
        # Need at least 10 samples to make an 80/20 split meaningful
        if len(X_scaled) >= 10:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y_log, test_size=holdout_pct, random_state=42,
            )

            self.model = RandomForestRegressor(
                n_estimators=300,
                max_depth=None,
                min_samples_split=2,
                min_samples_leaf=3,        # increased vs old (was 1) — reduces overfit
                random_state=42,
                n_jobs=-1,
            )
            self.model.fit(X_train, y_train)

            # Compute honest test-set metrics in REVENUE space (not log space)
            y_pred_log = self.model.predict(X_test)
            y_pred_raw = np.expm1(y_pred_log)
            y_test_raw = np.expm1(y_test)

            self.metrics = {
                "r2_test":        float(r2_score(y_test_raw, y_pred_raw)),
                "mae_test":       float(mean_absolute_error(y_test_raw, y_pred_raw)),
                "n_train":        int(len(X_train)),
                "n_test":         int(len(X_test)),
                "median_revenue": self.median_existing_revenue,
                "max_revenue":    self.max_existing_revenue,
                "validation":     "holdout_80_20",
            }

            # Retrain on FULL data for production predictions
            self.model.fit(X_scaled, y_log)

        elif len(X_scaled) >= 3:
            # Small dataset — train on everything, skip held-out
            self.model = RandomForestRegressor(
                n_estimators=200, min_samples_leaf=2,
                random_state=42, n_jobs=-1,
            )
            self.model.fit(X_scaled, y_log)
            self.metrics = {
                "r2_test": None, "mae_test": None,
                "n_train": int(len(X_scaled)), "n_test": 0,
                "median_revenue": self.median_existing_revenue,
                "max_revenue": self.max_existing_revenue,
                "validation": "no_holdout_small_dataset",
            }

        else:
            # Tiny dataset — Ridge fallback
            log.warning("[Model] < 3 training samples — Ridge fallback")
            self.model = Ridge(alpha=1.0)
            self.model.fit(X_scaled, y_log)
            self.metrics = {
                "r2_test": None, "mae_test": None,
                "n_train": int(len(X_scaled)), "n_test": 0,
                "median_revenue": self.median_existing_revenue,
                "max_revenue": self.max_existing_revenue,
                "validation": "ridge_fallback",
            }

        # Feature importance (RF only)
        if isinstance(self.model, RandomForestRegressor):
            self.feature_importances = {
                col: float(imp)
                for col, imp in zip(self.feature_cols, self.model.feature_importances_)
            }

        self._is_trained = True

        log.info(
            "[Model] trained on %d stores | val=%s | R²_test=%s | median_rev=%.0f",
            len(X_scaled),
            self.metrics.get("validation"),
            f"{self.metrics['r2_test']:.3f}" if self.metrics.get("r2_test") is not None else "N/A",
            self.median_existing_revenue,
        )

        return self.metrics

    # ────────────────────────────────────────────────────────────
    # PREDICTION
    # ────────────────────────────────────────────────────────────
    def predict(self, candidates_df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict revenue + absolute score for each candidate.

        Adds columns:
            Predicted_Revenue
            Rev_Lower / Rev_Upper (90% confidence interval)
            Final_Score (0-100, absolute: 50 = matches median existing store)
            OOD_Feature_Count (number of features above training p95)
            OOD_Features (comma-separated names)
        """
        if not self._is_trained:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        df = candidates_df.copy().fillna(0)
        X = df.reindex(columns=self.feature_cols, fill_value=0).values.astype(float)
        X_scaled = self.scaler.transform(X)

        # Predict in log space, then back-transform
        y_pred_log = self.model.predict(X_scaled)
        y_pred_revenue = np.expm1(y_pred_log)
        y_pred_revenue = np.clip(y_pred_revenue, 0, None)

        # HARD CAP at 2x the maximum existing store — prevents wild extrapolation
        cap = self.max_existing_revenue * 2.0
        y_pred_revenue = np.minimum(y_pred_revenue, cap)

        # Confidence interval — std across individual tree predictions
        if isinstance(self.model, RandomForestRegressor):
            tree_preds_log = np.array([t.predict(X_scaled) for t in self.model.estimators_])
            tree_preds_raw = np.expm1(tree_preds_log)
            std = tree_preds_raw.std(axis=0)
        else:
            std = y_pred_revenue * 0.15

        df["Predicted_Revenue"] = y_pred_revenue
        df["Rev_Lower"] = np.clip(y_pred_revenue - 1.65 * std, 0, None)
        df["Rev_Upper"] = y_pred_revenue + 1.65 * std

        # ABSOLUTE SCORING:
        #   Score = 50 × (predicted_revenue / median_existing_revenue), capped at 100
        #   So 50 = matches median existing store, 100 = predicted to do 2x median.
        med = max(self.median_existing_revenue, 1.0)
        df["Final_Score"] = np.clip(50.0 * (y_pred_revenue / med), 0, 100)

        # OOD detection: count features that exceed 1.5× the training p95 ceiling
        ood_counts = np.zeros(len(df), dtype=int)
        ood_lists: list[list[str]] = [[] for _ in range(len(df))]
        for i, col in enumerate(self.feature_cols):
            stats = self.training_feature_stats.get(col)
            if not stats:
                continue
            threshold = stats["p95"] * 1.5
            if threshold <= 0:
                continue
            mask = X[:, i] > threshold
            ood_counts += mask.astype(int)
            for idx_row in np.where(mask)[0]:
                ood_lists[idx_row].append(col)

        df["OOD_Feature_Count"] = ood_counts
        df["OOD_Features"] = [",".join(items) for items in ood_lists]

        return df

    # ────────────────────────────────────────────────────────────
    # Public API for surfacing model state
    # ────────────────────────────────────────────────────────────
    def get_diagnostics(self, top_n_features: int = 10) -> dict:
        """
        Returns a dict for the API to expose under `model_diagnostics`.
        """
        sorted_imps = sorted(
            self.feature_importances.items(), key=lambda kv: -kv[1]
        )[:top_n_features]
        diag = dict(self.metrics)
        # Aliases for downstream code that expects 'r2'/'mae' (without _test suffix)
        if "r2_test" in diag and "r2" not in diag:
            diag["r2"] = diag["r2_test"]
        if "mae_test" in diag and "mae" not in diag:
            diag["mae"] = diag["mae_test"]
        diag["top_features"] = [
            {"feature": col, "importance": round(imp, 4)}
            for col, imp in sorted_imps
        ]
        diag["training_feature_stats"] = self.training_feature_stats
        return diag

    # ────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────
    def _select_features(self, df: pd.DataFrame, has_bu: bool) -> list[str]:
        cols = [c for c in FEATURE_COLS if c in df.columns]
        cols += [c for c in RE_FEATURE_COLS if c in df.columns]
        if has_bu:
            cols += [c for c in BU_FEATURE_COLS if c in df.columns]
        return cols
