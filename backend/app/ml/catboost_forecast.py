import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from catboost import CatBoostError, CatBoostRegressor, Pool

from app.ml.demand_features import (
    MODEL_FEATURE_COLUMNS,
    MODEL_TARGET_COLUMN,
    DemandTrainingDataError,
    build_demand_training_data,
    split_training_data_by_time,
)
from app.ml.forecast_metrics import calculate_forecast_metrics


MODEL_VERSION = "catboost-daily-residual-v1"
PREDICTION_COLUMN = "predicted_shipments"
CATEGORICAL_FEATURE_COLUMNS = ["store_id", "emirate", "zone"]
DEFAULT_MODEL_PATH = Path(
    os.getenv(
        "CATBOOST_MODEL_PATH",
        Path(__file__).resolve().parents[2]
        / "model_artifacts"
        / "demand_forecast.cbm",
    )
)
BASELINE_MODEL_VERSION = "official-daily-forecast-baseline-v1"

CATBOOST_PARAMETERS = {
    "iterations": 50,
    "depth": 4,
    "learning_rate": 0.05,
    "loss_function": "MAE",
    "l2_leaf_reg": 5,
    "random_seed": 42,
    "verbose": False,
    "allow_writing_files": False,
    "thread_count": 1,
}


@dataclass
class CatBoostBacktestResult:
    model: CatBoostRegressor
    predictions: pd.DataFrame
    baseline_metrics: dict[str, int | float | None]
    model_metrics: dict[str, int | float | None]
    train_date_to: str
    test_date_from: str


@dataclass
class DailyDemandPredictionResult:
    dataframe: pd.DataFrame
    prediction_source: str
    model_version: str
    fallback_reason: str | None


def prepare_model_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    features = dataframe[MODEL_FEATURE_COLUMNS].copy()

    for column in CATEGORICAL_FEATURE_COLUMNS:
        features[column] = features[column].fillna("unknown").astype(str)

    features["is_weekend"] = features["is_weekend"].astype(int)

    return features


def train_catboost_model(dataframe: pd.DataFrame) -> CatBoostRegressor:
    residual_target = (
        dataframe[MODEL_TARGET_COLUMN] - dataframe["forecast_shipments"]
    )
    training_pool = Pool(
        prepare_model_features(dataframe),
        label=residual_target,
        cat_features=CATEGORICAL_FEATURE_COLUMNS,
    )
    model = CatBoostRegressor(**CATBOOST_PARAMETERS)
    model.fit(training_pool)

    return model


def load_catboost_model(
    model_path: Path = DEFAULT_MODEL_PATH,
) -> CatBoostRegressor:
    model = CatBoostRegressor()
    model.load_model(str(model_path))
    return model


def predict_daily_demand(
    model: CatBoostRegressor,
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    result = dataframe.copy()
    predicted_correction = model.predict(prepare_model_features(dataframe))
    result["prediction_correction"] = predicted_correction
    result[PREDICTION_COLUMN] = (
        result["forecast_shipments"] + result["prediction_correction"]
    ).clip(lower=0)
    result["prediction_source"] = "catboost"
    result["model_version"] = MODEL_VERSION

    return result


def backtest_catboost_model(
    dataframe: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
) -> CatBoostBacktestResult:
    split = split_training_data_by_time(
        dataframe,
        test_fraction=test_fraction,
    )
    model = train_catboost_model(split.train)
    predictions = predict_daily_demand(model, split.test)

    return CatBoostBacktestResult(
        model=model,
        predictions=predictions,
        baseline_metrics=calculate_forecast_metrics(split.test),
        model_metrics=calculate_forecast_metrics(
            predictions,
            prediction_column=PREDICTION_COLUMN,
        ),
        train_date_to=split.train_date_to,
        test_date_from=split.test_date_from,
    )


def apply_catboost_to_daily_capacity(
    workbook,
    daily_capacity_rows: pd.DataFrame,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
) -> DailyDemandPredictionResult:
    dataframe = daily_capacity_rows.copy()
    dataframe["baseline_forecast_shipments"] = dataframe[
        "forecast_shipments"
    ].astype(float)

    try:
        model = load_catboost_model(model_path)
        features = build_demand_training_data(workbook)
        predictions = predict_daily_demand(model, features)
        prediction_columns = [
            "store_id",
            "date",
            PREDICTION_COLUMN,
            "prediction_correction",
        ]
        dataframe = dataframe.merge(
            predictions[prediction_columns],
            on=["store_id", "date"],
            how="left",
            validate="one_to_one",
        )

        if dataframe[PREDICTION_COLUMN].isna().any():
            raise ValueError("CatBoost predictions do not cover all store-days")

        dataframe["prediction_source"] = "catboost"
        dataframe["model_version"] = MODEL_VERSION

        if "actual_shipments" in dataframe.columns:
            dataframe["prediction_error"] = (
                dataframe["actual_shipments"]
                - dataframe[PREDICTION_COLUMN]
            )

        return DailyDemandPredictionResult(
            dataframe=dataframe,
            prediction_source="catboost",
            model_version=MODEL_VERSION,
            fallback_reason=None,
        )
    except (
        CatBoostError,
        DemandTrainingDataError,
        FileNotFoundError,
        KeyError,
        OSError,
        ValueError,
    ):
        dataframe[PREDICTION_COLUMN] = dataframe[
            "baseline_forecast_shipments"
        ]
        dataframe["prediction_correction"] = 0.0
        dataframe["prediction_source"] = "excel_baseline"
        dataframe["model_version"] = BASELINE_MODEL_VERSION

        return DailyDemandPredictionResult(
            dataframe=dataframe,
            prediction_source="excel_baseline",
            model_version=BASELINE_MODEL_VERSION,
            fallback_reason="catboost_unavailable_or_incompatible",
        )
