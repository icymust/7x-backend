import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
from catboost import CatBoostError, CatBoostRegressor, Pool

from app.ml.catboost_forecast import CATBOOST_PARAMETERS
from app.ml.demand_features import MODEL_TARGET_COLUMN, split_training_data_by_time
from app.ml.forecast_metrics import calculate_forecast_metrics


FUTURE_MODEL_VERSION = "catboost-daily-future-v1"
FUTURE_PREDICTION_SOURCE = "catboost_future"
FUTURE_FALLBACK_VERSION = "seasonal-naive-7d-v1"
FUTURE_FALLBACK_SOURCE = "seasonal_naive"
DEFAULT_FUTURE_HORIZON_DAYS = 90
FUTURE_CORRECTION_WEIGHT = 0.25
DEFAULT_FUTURE_MODEL_PATH = Path(
    os.getenv(
        "CATBOOST_FUTURE_MODEL_PATH",
        Path(__file__).resolve().parents[2]
        / "model_artifacts"
        / "demand_future.cbm",
    )
)

FUTURE_FEATURE_COLUMNS = [
    "store_id",
    "emirate",
    "zone",
    "weekday",
    "month",
    "day_of_year",
    "is_weekend",
    "seasonal_baseline_orders",
    "demand_lag_1d",
    "demand_rolling_mean_7d",
    "demand_rolling_mean_28d",
]
FUTURE_CATEGORICAL_FEATURE_COLUMNS = ["store_id", "emirate", "zone"]


@dataclass
class FutureDemandPredictionResult:
    dataframe: pd.DataFrame
    prediction_source: str
    model_version: str
    fallback_reason: str | None
    historical_date_to: str
    horizon_start: str
    horizon_end: str


@dataclass
class FutureForecastBacktestResult:
    model: CatBoostRegressor
    predictions: pd.DataFrame
    baseline_metrics: dict[str, int | float | None]
    model_metrics: dict[str, int | float | None]
    train_date_to: str
    test_date_from: str


def build_future_training_data(history: pd.DataFrame) -> pd.DataFrame:
    dataframe = history.copy()
    dataframe["date"] = pd.to_datetime(dataframe["date"]).dt.normalize()
    dataframe = dataframe.sort_values(
        ["store_id", "date"],
        ignore_index=True,
    )

    grouped = dataframe.groupby("store_id", sort=False)[MODEL_TARGET_COLUMN]
    dataframe["seasonal_baseline_orders"] = dataframe[
        "forecast_shipments"
    ].astype(float)
    dataframe["demand_lag_1d"] = grouped.shift(1)
    dataframe["demand_rolling_mean_7d"] = grouped.transform(
        lambda values: values.shift(1).rolling(7, min_periods=1).mean()
    )
    dataframe["demand_rolling_mean_28d"] = grouped.transform(
        lambda values: values.shift(1).rolling(28, min_periods=1).mean()
    )
    return dataframe.dropna(
        subset=[
            "seasonal_baseline_orders",
            "demand_lag_1d",
            "demand_rolling_mean_7d",
            "demand_rolling_mean_28d",
        ]
    ).reset_index(drop=True)


def prepare_future_model_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    features = dataframe[FUTURE_FEATURE_COLUMNS].copy()

    for column in FUTURE_CATEGORICAL_FEATURE_COLUMNS:
        features[column] = features[column].fillna("unknown").astype(str)

    features["is_weekend"] = features["is_weekend"].astype(int)
    return features


def train_future_catboost_model(
    dataframe: pd.DataFrame,
) -> CatBoostRegressor:
    residual_target = (
        dataframe[MODEL_TARGET_COLUMN]
        - dataframe["seasonal_baseline_orders"]
    )
    training_pool = Pool(
        prepare_future_model_features(dataframe),
        label=residual_target,
        cat_features=FUTURE_CATEGORICAL_FEATURE_COLUMNS,
    )
    model = CatBoostRegressor(**CATBOOST_PARAMETERS)
    model.fit(training_pool)
    return model


def load_future_catboost_model(
    model_path: Path = DEFAULT_FUTURE_MODEL_PATH,
) -> CatBoostRegressor:
    model = CatBoostRegressor()
    model.load_model(str(model_path))
    return model


def _future_feature_row(
    *,
    store_id: str,
    emirate: str,
    zone: str,
    forecast_date: pd.Timestamp,
    demand_history: list[float],
    baseline_history: list[float],
) -> dict:
    recent_7 = demand_history[-7:]
    recent_28 = demand_history[-28:]
    seasonal_baseline = (
        baseline_history[-7]
        if len(baseline_history) >= 7
        else sum(recent_7) / len(recent_7)
    )

    return {
        "store_id": store_id,
        "emirate": emirate,
        "zone": zone,
        "weekday": forecast_date.weekday(),
        "month": forecast_date.month,
        "day_of_year": forecast_date.dayofyear,
        "is_weekend": forecast_date.day_name() in {"Friday", "Saturday"},
        "seasonal_baseline_orders": float(seasonal_baseline),
        "demand_lag_1d": float(demand_history[-1]),
        "demand_rolling_mean_7d": float(sum(recent_7) / len(recent_7)),
        "demand_rolling_mean_28d": float(sum(recent_28) / len(recent_28)),
    }


def generate_future_demand(
    history: pd.DataFrame,
    *,
    horizon_start: date,
    horizon_days: int = DEFAULT_FUTURE_HORIZON_DAYS,
    model: CatBoostRegressor | None,
) -> pd.DataFrame:
    if horizon_days <= 0:
        raise ValueError("horizon_days must be greater than zero")

    dataframe = history.copy()
    dataframe["date"] = pd.to_datetime(dataframe["date"]).dt.normalize()
    dataframe = dataframe.sort_values(["store_id", "date"])
    historical_date_to = pd.Timestamp(dataframe["date"].max())
    requested_start = pd.Timestamp(horizon_start).normalize()

    if requested_start <= historical_date_to:
        raise ValueError("horizon_start must be after historical data")

    horizon_end = requested_start + pd.Timedelta(days=horizon_days - 1)
    forecast_start = historical_date_to + pd.Timedelta(days=1)
    prediction_rows = []

    for store_id, store_history in dataframe.groupby("store_id", sort=True):
        store_history = store_history.sort_values("date")
        values = store_history[MODEL_TARGET_COLUMN].astype(float).tolist()
        baseline_values = store_history["forecast_shipments"].astype(float).tolist()

        if not values:
            raise ValueError(f"No historical demand for store {store_id}")

        emirate = str(store_history["emirate"].iloc[-1])
        zone = str(store_history["zone"].iloc[-1])

        for forecast_date in pd.date_range(forecast_start, horizon_end):
            feature_row = _future_feature_row(
                store_id=str(store_id),
                emirate=emirate,
                zone=zone,
                forecast_date=forecast_date,
                demand_history=values,
                baseline_history=baseline_values,
            )
            baseline = feature_row["seasonal_baseline_orders"]
            predicted = baseline

            if model is not None:
                predicted_correction = float(
                    model.predict(
                        prepare_future_model_features(
                            pd.DataFrame([feature_row])
                        )
                    )[0]
                )
                predicted = (
                    baseline
                    + FUTURE_CORRECTION_WEIGHT * predicted_correction
                )

            predicted = max(predicted, 0.0)
            values.append(predicted)
            baseline_values.append(float(baseline))

            if forecast_date < requested_start:
                continue

            prediction_rows.append(
                {
                    **feature_row,
                    "date": forecast_date,
                    "time_bucket": forecast_date,
                    "forecast_shipments": round(float(baseline), 2),
                    "baseline_forecast_shipments": round(
                        float(baseline),
                        2,
                    ),
                    "predicted_shipments": round(predicted, 2),
                    "prediction_correction": round(
                        predicted - float(baseline),
                        2,
                    ),
                }
            )

    return pd.DataFrame(prediction_rows).sort_values(
        ["date", "store_id"],
        ignore_index=True,
    )


def backtest_future_catboost_model(
    history: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
) -> FutureForecastBacktestResult:
    split = split_training_data_by_time(
        history,
        test_fraction=test_fraction,
    )
    training_data = build_future_training_data(split.train)
    model = train_future_catboost_model(training_data)
    test_dates = pd.to_datetime(split.test["date"]).dt.normalize().unique()
    predictions = generate_future_demand(
        split.train,
        horizon_start=pd.Timestamp(test_dates.min()).date(),
        horizon_days=len(test_dates),
        model=model,
    )
    baseline_predictions = generate_future_demand(
        split.train,
        horizon_start=pd.Timestamp(test_dates.min()).date(),
        horizon_days=len(test_dates),
        model=None,
    )
    actuals = split.test[["store_id", "date", MODEL_TARGET_COLUMN]].copy()
    predictions = predictions.merge(
        actuals,
        on=["store_id", "date"],
        how="left",
        validate="one_to_one",
    )
    baseline_predictions = baseline_predictions.merge(
        actuals,
        on=["store_id", "date"],
        how="left",
        validate="one_to_one",
    )

    return FutureForecastBacktestResult(
        model=model,
        predictions=predictions,
        baseline_metrics=calculate_forecast_metrics(baseline_predictions),
        model_metrics=calculate_forecast_metrics(
            predictions,
            prediction_column="predicted_shipments",
        ),
        train_date_to=split.train_date_to,
        test_date_from=split.test_date_from,
    )


def forecast_future_demand(
    history: pd.DataFrame,
    *,
    horizon_start: date,
    horizon_days: int = DEFAULT_FUTURE_HORIZON_DAYS,
    model_path: Path = DEFAULT_FUTURE_MODEL_PATH,
) -> FutureDemandPredictionResult:
    model = None
    fallback_reason = None
    prediction_source = FUTURE_PREDICTION_SOURCE
    model_version = FUTURE_MODEL_VERSION

    try:
        model = load_future_catboost_model(model_path)
    except (CatBoostError, FileNotFoundError, OSError, ValueError):
        fallback_reason = "future_catboost_unavailable_or_incompatible"
        prediction_source = FUTURE_FALLBACK_SOURCE
        model_version = FUTURE_FALLBACK_VERSION

    predictions = generate_future_demand(
        history,
        horizon_start=horizon_start,
        horizon_days=horizon_days,
        model=model,
    )
    predictions["prediction_source"] = prediction_source
    predictions["model_version"] = model_version

    historical_date_to = pd.Timestamp(history["date"].max()).date()
    horizon_end = horizon_start + pd.Timedelta(days=horizon_days - 1)

    return FutureDemandPredictionResult(
        dataframe=predictions,
        prediction_source=prediction_source,
        model_version=model_version,
        fallback_reason=fallback_reason,
        historical_date_to=historical_date_to.isoformat(),
        horizon_start=horizon_start.isoformat(),
        horizon_end=horizon_end.isoformat(),
    )
