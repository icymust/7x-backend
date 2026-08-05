from dataclasses import dataclass

import pandas as pd
from catboost import CatBoostRegressor, Pool

from app.ml.demand_features import (
    MODEL_FEATURE_COLUMNS,
    MODEL_TARGET_COLUMN,
    split_training_data_by_time,
)
from app.ml.forecast_metrics import calculate_forecast_metrics


MODEL_VERSION = "catboost-daily-residual-v1"
PREDICTION_COLUMN = "predicted_shipments"
CATEGORICAL_FEATURE_COLUMNS = ["store_id", "emirate", "zone"]

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
