"""
Random Forest Prediction Model
Trains on existing franchise stores, predicts revenue for candidate locations.
Outputs: Predicted_Revenue, Score (0-100), Confidence_Interval
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings("ignore")

from app.utils import get_logger, safe_float

log = get_logger("rf_model")

FEATURE_COLS = [
    "cnt_food", "cnt_retail", "cnt_education", "cnt_health",
    "cnt_leisure", "cnt_transport", "cnt_finance",
    "Population", "Income",
    "Nearest_Store_km", "stores_2km", "stores_5km",
    "Cannibalization_Score",
]
RE_FEATURE_COLS = [
    "property_cost_index", "property_growth_score",
    "avg_property_price_3km", "avg_rent_3km", "commercial_count_3km",
    "commercial_density_3km", "property_growth_3km", "vacancy_rate_3km",
    "income_property_ratio", "amenity_growth_score",
    "population_commercial_score", "franchise_density_score",
    "market_saturation_score"
]
BU_FEATURE_COLS = ["BU_Dist_km", "BU_Weight"]


class FranchiseModel:
    """
    Trains a Random Forest on historical store data,
    then predicts performance for candidate locations.
    Falls back to Gradient Boosting when RF overfits (< 3 training samples).
    """

    def __init__(self):
        self.model: RandomForestRegressor | None = None
        self.scaler = MinMaxScaler()
        self.feature_cols: list[str] = []
        self.target_max: float = 1.0
        self._is_trained = False

    # ─────────────────────────────────────────────────────────────
    # TRAINING
    # ─────────────────────────────────────────────────────────────
    def train(self, stores_df: pd.DataFrame, has_bu: bool = False) -> dict:
        """
        Train the model on existing store data.
        Target variable: Adjusted_Sales (preferred) or Sales.
        Returns training metrics dict.
        """
        df = stores_df.copy().fillna(0)
        self.feature_cols = self._select_features(df, has_bu)
        X, y = self._prepare_data(df)

        if len(X) < 3:
            log.warning("[Model] < 3 training samples — using simple fallback model")
            self._train_fallback(X, y)
        else:
            estimator = RandomForestRegressor(
                n_estimators=200,
                max_depth=None,
                min_samples_split=2,
                min_samples_leaf=1,
                random_state=42,
                n_jobs=-1,
            )
            estimator.fit(X, y)
            self.model = estimator

        self._is_trained = True
        metrics = self._compute_metrics(X, y)
        log.info(f"[Model] Trained on {len(X)} stores | R²={metrics['r2']:.3f}")
        return metrics

    # ─────────────────────────────────────────────────────────────
    # PREDICTION
    # ─────────────────────────────────────────────────────────────
    def predict(self, candidates_df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict revenue + score for each candidate location.
        Adds columns: Predicted_Revenue, Rev_Lower, Rev_Upper, Final_Score
        """
        if not self._is_trained:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        df = candidates_df.copy().fillna(0)
        X = self._prepare_features(df)
        raw_preds = np.clip(self.model.predict(X) * self.target_max, 0, None)

        # Confidence interval from individual tree predictions (RF only)
        if isinstance(self.model, RandomForestRegressor):
            tree_preds = np.array([
                t.predict(X) * self.target_max
                for t in self.model.estimators_
            ])
            std = tree_preds.std(axis=0)
        else:
            std = raw_preds * 0.15  # fallback: 15% CI

        # Enhance Confidence Intervals with real estate uncertainty
        if "property_growth_3km" in df.columns and "vacancy_rate_3km" in df.columns:
            # Widen interval if high volatility / sparse data
            uncertainty_multiplier = 1.0 + (df["property_growth_3km"] / 100.0) * 0.2 + (df["vacancy_rate_3km"] * 0.5)
            std = std * uncertainty_multiplier.values

        df["Predicted_Revenue"] = raw_preds
        df["Rev_Lower"]         = np.clip(raw_preds - 1.65 * std, 0, None)
        df["Rev_Upper"]         = raw_preds + 1.65 * std

        # Normalize score to 0–100
        max_rev = raw_preds.max() if raw_preds.max() > 0 else 1.0
        df["Final_Score"] = (raw_preds / max_rev) * 100
        return df

    # ─────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────
    def _select_features(self, df: pd.DataFrame, has_bu: bool) -> list[str]:
        cols = [c for c in FEATURE_COLS if c in df.columns]
        cols += [c for c in RE_FEATURE_COLS if c in df.columns]
        if has_bu:
            cols += [c for c in BU_FEATURE_COLS if c in df.columns]
        return cols

    def _prepare_data(self, df: pd.DataFrame):
        target = "Adjusted_Sales" if "Adjusted_Sales" in df.columns else "Sales"
        if target not in df.columns:
            df["Sales"] = 1.0
            target = "Sales"
        y = pd.to_numeric(df[target], errors="coerce").fillna(0).values
        self.target_max = y.max() if y.max() > 0 else 1.0
        y_norm = y / self.target_max
        X = self._prepare_features(df)
        return X, y_norm

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        X = df.reindex(columns=self.feature_cols, fill_value=0).values.astype(float)
        return self.scaler.fit_transform(X) if not self._is_trained else self.scaler.transform(X)

    def _train_fallback(self, X, y):
        from sklearn.linear_model import Ridge
        self.model = Ridge(alpha=1.0)
        self.model.fit(X, y)

    def _compute_metrics(self, X, y) -> dict:
        try:
            scores = cross_val_score(self.model, X, y, cv=min(3, len(X)), scoring="r2")
            r2 = float(np.mean(scores))
        except Exception:
            r2 = float(self.model.score(X, y)) if len(X) > 0 else 0.0
        return {"r2": r2, "n_samples": len(X)}
