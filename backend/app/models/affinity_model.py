"""
Location Affinity Model — v4.0 (Scoring / Look-Alike Approach)
================================================================
Replaces the Random Forest revenue regressor with an explainable,
data-driven SCORING model. This directly targets the high-MAE problem:
instead of asking a regressor to *invent* a revenue number for a brand
new location (which extrapolates badly and produces ~50L MAE), we:

  1. Learn which amenities / demographics / real-estate signals actually
     correlate with sales at OUR existing stores (feature weights).
  2. Build an "archetype" profile = the typical feature-vector of our
     TOP-QUARTILE (best-performing) existing stores.
  3. Score every candidate location by its WEIGHTED SIMILARITY to that
     archetype (0-100, calibrated so 50 = matches a typical/median
     existing store, 100 = matches the top-performer archetype).
  4. Estimate expected sales with a LOOK-ALIKE (K-nearest-neighbours)
     method: "this candidate looks like these 5 existing stores, whose
     sales ranged from X to Y" — a reported range grounded in real
     comparables, not a forced point-prediction from a black-box model.

This keeps the exact same public interface as the old FranchiseModel
(train / predict / get_diagnostics, same output columns), so it can be
swapped in with a ONE-LINE import change in scoring_service.py.

Output columns on predict() — unchanged contract:
    Predicted_Revenue, Rev_Lower, Rev_Upper, Final_Score,
    OOD_Feature_Count, OOD_Features
Plus NEW explainability columns:
    Similarity_To_Archetype, Top_Positive_Drivers, Top_Negative_Drivers,
    Comparable_Stores
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import r2_score, mean_absolute_error
import warnings
warnings.filterwarnings("ignore")

from app.utils import get_logger

log = get_logger("affinity_model")

# Same feature universe as the old RF model — keeps every upstream
# enrichment step (amenities_service, real_estate_service, clustering_service,
# osm_geographic_service) unchanged.
FEATURE_COLS = [
    "cnt_food", "cnt_retail", "cnt_education", "cnt_health",
    "cnt_leisure", "cnt_transport", "cnt_finance",
    "cnt_hospitality", "cnt_civic",     # v5.0 — new buckets from local AmenitiesWB.csv
    "Population", "Income",
    "Nearest_Store_km", "stores_2km", "stores_5km",
    "Cannibalization_Score",
    "Nearby_Store_Avg_Sales",  # v6.1 — actual sales of nearby stores, not just their count/distance
    "Competitor_2km", "Competitor_5km",  # v5.0 — from local Mio_competitor.xlsx
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

# Features where a LOWER value is better (so we invert sign before
# computing correlation-based direction, purely for the human-readable
# "driver" labels — the archetype/median comparison itself is direction-agnostic).
_LOWER_IS_BETTER = {
    "Nearest_Store_km", "stores_2km", "stores_5km", "Cannibalization_Score",
    "dist_to_nearest_road_m", "is_industrial", "is_agricultural",
    "is_natural", "vacancy_rate_3km", "market_saturation_score",
    "franchise_density_score", "BU_Dist_km",
    "Competitor_2km", "Competitor_5km",  # v5.0
}

K_NEIGHBORS = 15  # v6.3 — was 5. Empirically tested against real 384-store
# data: k=5 averaged NEGATIVE R² across multiple random holdout splits
# (worse than predicting the mean); k=15 gives a real, if modest, positive
# R² and a meaningfully lower MAE. Higher k (25-50) keeps improving MAE
# slightly further but starts averaging over too much of the training set
# to stay explainable as "these are your comparable stores" — 15 is the
# chosen balance.


class FranchiseModel:
    """
    Amenity/Demographic Affinity Scoring model.
    NOTE: kept the class name `FranchiseModel` so this file is a true
    drop-in replacement — only the import path changes in scoring_service.py:
        from app.models.affinity_model import FranchiseModel
    """

    def __init__(self):
        self.scaler = RobustScaler()
        self.feature_cols: list[str] = []
        self.feature_weights: dict[str, float] = {}      # |corr| normalised, sums to 1
        self.feature_direction: dict[str, float] = {}     # signed corr, for driver labels
        self.archetype: np.ndarray | None = None           # top-quartile median profile (scaled)
        self.median_profile: np.ndarray | None = None       # all-store median profile (scaled)
        self.sim_median: float = 0.0                        # similarity of median profile to archetype
        self.median_existing_revenue: float = 1.0
        self.max_existing_revenue: float = 1.0
        self.training_feature_stats: dict[str, dict] = {}
        self.metrics: dict = {}
        self._is_trained = False

        # Kept for look-alike lookups at predict time
        self._train_X_scaled: np.ndarray | None = None
        self._train_y: np.ndarray | None = None
        self._train_names: list[str] = []

    # ────────────────────────────────────────────────────────────
    # TRAINING
    # ────────────────────────────────────────────────────────────
    def train(self, stores_df: pd.DataFrame, has_bu: bool = False,
              holdout_pct: float = 0.20) -> dict:
        df = stores_df.copy().fillna(0)

        target_col = "Adjusted_Sales" if "Adjusted_Sales" in df.columns else "Sales"
        if target_col not in df.columns:
            log.error("[AffinityModel] No target column found; cannot train")
            return {"error": "no target column"}

        df = df[pd.to_numeric(df[target_col], errors="coerce").fillna(0) > 0].copy()
        if len(df) == 0:
            log.error("[AffinityModel] No stores with positive sales")
            return {"error": "no positive-sales stores"}

        self.feature_cols = self._select_features(df, has_bu)
        y_raw = pd.to_numeric(df[target_col], errors="coerce").fillna(0).values.astype(float)
        names = df["Store_Name"].astype(str).tolist() if "Store_Name" in df.columns else \
            [f"Store {i}" for i in range(len(df))]

        self.median_existing_revenue = float(np.median(y_raw))
        self.max_existing_revenue = float(np.max(y_raw))

        X = df.reindex(columns=self.feature_cols, fill_value=0).values.astype(float)

        for i, col in enumerate(self.feature_cols):
            col_vals = X[:, i]
            self.training_feature_stats[col] = {
                "min": float(col_vals.min()), "p5": float(np.percentile(col_vals, 5)),
                "mean": float(col_vals.mean()), "p95": float(np.percentile(col_vals, 95)),
                "max": float(col_vals.max()),
            }

        X_scaled = self.scaler.fit_transform(X)

        # ── 1. Feature weights = |Spearman correlation| with sales ──
        self._compute_feature_weights(X_scaled, y_raw)

        # ── 2. Archetype = median profile of top-quartile stores ────
        self.median_profile = np.median(X_scaled, axis=0)
        if len(y_raw) >= 4:
            q75 = np.percentile(y_raw, 75)
            top_mask = y_raw >= q75
            if top_mask.sum() < 3:  # guarantee at least 3 stores in the archetype
                top_idx = np.argsort(-y_raw)[:max(3, int(len(y_raw) * 0.25))]
                top_mask = np.zeros(len(y_raw), dtype=bool)
                top_mask[top_idx] = True
        else:
            top_mask = y_raw >= np.median(y_raw)
        self.archetype = np.median(X_scaled[top_mask], axis=0)

        # Calibration anchor for the 0-100 scale: the MEDIAN of each
        # individual training store's own similarity to the archetype —
        # NOT the similarity of an aggregated median-feature-vector. The
        # aggregate vector is artificially close to the archetype (each
        # dimension is smoothed independently by taking its own median),
        # while real individual stores are noisier and sit further away.
        # Anchoring on the aggregate vector made the 50-100 scale far too
        # sensitive and collapsed almost every real candidate's score to 0.
        train_sims = np.array([
            self._weighted_similarity(X_scaled[i], self.archetype)
            for i in range(len(X_scaled))
        ])
        self.sim_median = float(np.median(train_sims))

        # ── 3. Store training set for look-alike (KNN) lookups ──────
        self._train_X_scaled = X_scaled
        self._train_y = y_raw
        self._train_names = names

        # ── 4. Honest held-out validation via look-alike backtest ───
        self.metrics = self._holdout_validate(X_scaled, y_raw, holdout_pct)
        self._is_trained = True

        log.info(
            "[AffinityModel] trained on %d stores | archetype_n=%d | "
            "val=%s | R2_test=%s | MAE_test=%s | median_rev=%.0f",
            len(X_scaled), int(top_mask.sum()), self.metrics.get("validation"),
            f"{self.metrics.get('r2_test'):.3f}" if self.metrics.get("r2_test") is not None else "N/A",
            f"{self.metrics.get('mae_test'):.0f}" if self.metrics.get("mae_test") is not None else "N/A",
            self.median_existing_revenue,
        )
        return self.metrics

    def _compute_feature_weights(self, X_scaled: np.ndarray, y_raw: np.ndarray, top_n: int = 10):
        weights = {}
        directions = {}
        y_series = pd.Series(y_raw)
        for i, col in enumerate(self.feature_cols):
            col_series = pd.Series(X_scaled[:, i])
            try:
                corr = col_series.corr(y_series, method="spearman")
            except Exception:
                corr = 0.0
            if pd.isna(corr):
                corr = 0.0
            directions[col] = float(corr)
            weights[col] = abs(float(corr))

        # v6.5b — real-estate features are excluded from the top-N
        # SELECTION pool (not deleted — still tracked, just ineligible to
        # be chosen). Tested and confirmed on real data: despite showing
        # decent standalone correlation (e.g. income_property_ratio),
        # including them in the KNN look-alike distance actively hurt
        # accuracy — R² went from 0.080 to -0.000 when they were eligible.
        # Root cause is almost certainly data sparsity: the real estate
        # source file often has far fewer unique records than there are
        # stores, so many stores share near-duplicate/interpolated values —
        # the apparent correlation is partly small-sample coincidence, not
        # a stable multivariate signal. If you later get a richer real
        # estate dataset (many more records, less duplication), this
        # exclusion should be revisited — it's a data-quality call for
        # THIS dataset, not a permanent stance against real estate signals.
        eligible = [c for c in weights if c not in RE_FEATURE_COLS]
        if top_n and len(eligible) > 0:
            keep = set(sorted(eligible, key=lambda k: -weights[k])[:top_n])
            weights = {k: (v if k in keep else 0.0) for k, v in weights.items()}
        elif top_n and len(weights) > top_n:
            keep = set(sorted(weights, key=lambda k: -weights[k])[:top_n])
            weights = {k: (v if k in keep else 0.0) for k, v in weights.items()}

        total = sum(weights.values())
        if total <= 1e-9:
            # No signal found (tiny dataset) — fall back to equal weights
            n = max(len(weights), 1)
            weights = {k: 1.0 / n for k in weights}
        else:
            weights = {k: v / total for k, v in weights.items()}

        self.feature_weights = weights
        self.feature_direction = directions

    def _weighted_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """1 - weighted L1 distance between two feature vectors already in the
        model's scaled [0,1]-ish space. Returns a value roughly in [0, 1]."""
        w = np.array([self.feature_weights.get(c, 0.0) for c in self.feature_cols])
        dist = np.sum(w * np.abs(vec_a - vec_b))
        return float(max(0.0, 1.0 - dist))

    def _holdout_validate(self, X_scaled: np.ndarray, y_raw: np.ndarray,
                           holdout_pct: float, n_repeats: int = 8) -> dict:
        """Backtest: for each held-out store, estimate sales via KNN look-alike
        over the remaining stores, and score against the ACTUAL sales. This
        mirrors exactly what predict() will do for brand-new candidates.

        v6.3 — averaged over n_repeats random splits, not one fixed seed.
        A single split can look much better OR much worse than reality by
        luck alone — testing showed one particular split reporting R²≈0.12
        while the honest multi-split average was actually negative at the
        old K. Averaging gives a stable, honest number instead of
        overclaiming (or underclaiming) based on which stores happened to
        land in the test set."""
        n = len(X_scaled)
        if n < 8:
            return {
                "r2_test": None, "mae_test": None, "n_train": n, "n_test": 0,
                "median_revenue": self.median_existing_revenue,
                "max_revenue": self.max_existing_revenue,
                "validation": "too_few_stores_for_holdout",
            }

        w = np.array([self.feature_weights.get(c, 0.0) for c in self.feature_cols])
        n_test = max(2, int(n * holdout_pct))

        r2_list, mae_list = [], []
        last_n_train, last_n_test = n - n_test, n_test
        for seed in range(n_repeats):
            rng = np.random.RandomState(seed)
            idx = rng.permutation(n)
            test_idx = idx[:n_test]
            train_idx = idx[n_test:]
            last_n_train, last_n_test = len(train_idx), len(test_idx)

            preds = []
            for ti in test_idx:
                dists = np.sum(w * np.abs(X_scaled[train_idx] - X_scaled[ti]), axis=1)
                k = min(K_NEIGHBORS, len(train_idx))
                nn_local_idx = np.argsort(dists)[:k]
                nn_dists = dists[nn_local_idx]
                nn_y = y_raw[train_idx][nn_local_idx]
                weights_inv = 1.0 / (nn_dists + 1e-3)
                preds.append(float(np.sum(nn_y * weights_inv) / np.sum(weights_inv)))

            preds = np.array(preds)
            actual = y_raw[test_idx]
            if len(actual) >= 2:
                r2_list.append(float(r2_score(actual, preds)))
            mae_list.append(float(mean_absolute_error(actual, preds)))

        return {
            "r2_test": float(np.mean(r2_list)) if r2_list else None,
            "r2_test_std": float(np.std(r2_list)) if r2_list else None,
            "mae_test": float(np.mean(mae_list)),
            "mae_test_std": float(np.std(mae_list)),
            "n_train": last_n_train, "n_test": last_n_test,
            "n_splits_averaged": n_repeats,
            "median_revenue": self.median_existing_revenue,
            "max_revenue": self.max_existing_revenue,
            "validation": "knn_lookalike_holdout_multisplit",
        }

    # ────────────────────────────────────────────────────────────
    # PREDICTION
    # ────────────────────────────────────────────────────────────
    def predict(self, candidates_df: pd.DataFrame) -> pd.DataFrame:
        if not self._is_trained:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        df = candidates_df.copy().fillna(0)
        X = df.reindex(columns=self.feature_cols, fill_value=0).values.astype(float)
        X_scaled = self.scaler.transform(X)

        w = np.array([self.feature_weights.get(c, 0.0) for c in self.feature_cols])

        final_scores = np.zeros(len(df))
        pred_revenue = np.zeros(len(df))
        rev_lower = np.zeros(len(df))
        rev_upper = np.zeros(len(df))
        similarities = np.zeros(len(df))
        pos_drivers, neg_drivers, comparable_stores = [], [], []

        scale_denom = max(1.0 - self.sim_median, 1e-6)
        cap = self.max_existing_revenue * 2.0

        for i in range(len(df)):
            cand = X_scaled[i]

            # ── Similarity to archetype → calibrated 0-100 score ──
            sim = self._weighted_similarity(cand, self.archetype)
            similarities[i] = sim
            score = 50.0 + (sim - self.sim_median) * (50.0 / scale_denom)
            final_scores[i] = float(np.clip(score, 0, 100))

            # ── Per-feature gap contribution → explainability ──
            gaps = w * np.abs(cand - self.archetype)  # bigger = hurts score more
            # v6.5 fix: zero-weight features (excluded by top-N selection)
            # always have gap=0, which made them falsely look like "perfect
            # matches" and crowd real drivers out of the top-3 list. Only
            # ever consider features that actually carry weight.
            nonzero_idx = np.where(w > 0)[0]
            if len(nonzero_idx) > 0:
                local_order = np.argsort(gaps[nonzero_idx])
                best_feats = [self.feature_cols[nonzero_idx[j]] for j in local_order[:3]]
                worst_feats = [self.feature_cols[nonzero_idx[j]] for j in local_order[::-1][:3]]
            else:
                best_feats, worst_feats = [], []
            pos_drivers.append(", ".join(best_feats))
            neg_drivers.append(", ".join(worst_feats))

            # ── Look-alike KNN revenue estimate ──
            dists = np.sum(w * np.abs(self._train_X_scaled - cand), axis=1)
            k = min(K_NEIGHBORS, len(dists))
            nn_idx = np.argsort(dists)[:k]
            nn_y = self._train_y[nn_idx]
            nn_dists = dists[nn_idx]
            inv_w = 1.0 / (nn_dists + 1e-3)
            est = float(np.sum(nn_y * inv_w) / np.sum(inv_w))
            est = min(max(est, 0.0), cap)
            pred_revenue[i] = est
            rev_lower[i] = float(np.min(nn_y))
            rev_upper[i] = float(np.max(nn_y))
            comparable_stores.append(
                "; ".join(f"{self._train_names[j]} (₹{self._train_y[j]:,.0f})" for j in nn_idx)
            )

        df["Predicted_Revenue"] = pred_revenue
        df["Rev_Lower"] = rev_lower
        df["Rev_Upper"] = rev_upper
        df["Final_Score"] = final_scores
        df["Similarity_To_Archetype"] = similarities
        df["Top_Positive_Drivers"] = pos_drivers
        df["Top_Negative_Drivers"] = neg_drivers
        df["Comparable_Stores"] = comparable_stores

        # OOD detection — unchanged logic from v3.6, kept for continuity
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
        sorted_w = sorted(self.feature_weights.items(), key=lambda kv: -kv[1])[:top_n_features]
        diag = dict(self.metrics)
        if "r2_test" in diag and "r2" not in diag:
            diag["r2"] = diag["r2_test"]
        if "mae_test" in diag and "mae" not in diag:
            diag["mae"] = diag["mae_test"]
        diag["top_features"] = [
            {
                "feature": col,
                "importance": round(weight, 4),
                "direction": "higher_is_better" if self.feature_direction.get(col, 0) >= 0
                             and col not in _LOWER_IS_BETTER else "lower_is_better",
                "correlation_with_sales": round(self.feature_direction.get(col, 0.0), 4),
            }
            for col, weight in sorted_w
        ]
        diag["training_feature_stats"] = self.training_feature_stats
        diag["method"] = "amenity_affinity_scoring_v4"
        return diag

    # ────────────────────────────────────────────────────────────
    def _select_features(self, df: pd.DataFrame, has_bu: bool) -> list[str]:
        cols = [c for c in FEATURE_COLS if c in df.columns]
        cols += [c for c in RE_FEATURE_COLS if c in df.columns]
        if has_bu:
            cols += [c for c in BU_FEATURE_COLS if c in df.columns]
        return cols
