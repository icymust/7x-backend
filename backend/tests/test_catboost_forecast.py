import pandas as pd

from app.ml.catboost_forecast import (
    MODEL_VERSION,
    PREDICTION_COLUMN,
    backtest_catboost_model,
    predict_daily_demand,
    train_catboost_model,
)


def create_daily_training_data() -> pd.DataFrame:
    rows = []

    for day_index, day in enumerate(pd.date_range("2026-01-01", periods=10)):
        for store_index, store_id in enumerate(["DXB-01", "AUH-01"]):
            forecast = 100 + day_index * 2 + store_index * 10
            rows.append(
                {
                    "store_id": store_id,
                    "emirate": "Dubai" if store_index == 0 else "Abu Dhabi",
                    "zone": "Central",
                    "date": day,
                    "time_bucket": day,
                    "planning_grain": "store_day",
                    "weekday": day.weekday(),
                    "month": day.month,
                    "day_of_year": day.dayofyear,
                    "is_weekend": day.day_name() in {"Friday", "Saturday"},
                    "forecast_shipments": float(forecast),
                    "actual_shipments": float(forecast + store_index + 1),
                    "actual_lag_1d": float(forecast - 1),
                    "actual_rolling_mean_7d": float(forecast - 2),
                    "actual_rolling_mean_28d": float(forecast - 3),
                }
            )

    return pd.DataFrame(rows)


def test_trains_and_predicts_non_negative_daily_demand():
    dataframe = create_daily_training_data()
    model = train_catboost_model(dataframe)
    predictions = predict_daily_demand(model, dataframe.tail(2))

    assert (predictions[PREDICTION_COLUMN] >= 0).all()
    assert set(predictions["prediction_source"]) == {"catboost"}
    assert set(predictions["model_version"]) == {MODEL_VERSION}


def test_backtests_on_future_dates_only():
    result = backtest_catboost_model(
        create_daily_training_data(),
        test_fraction=0.2,
    )

    assert result.train_date_to == "2026-01-08"
    assert result.test_date_from == "2026-01-09"
    assert len(result.predictions) == 4
    assert result.baseline_metrics["row_count"] == 4
    assert result.model_metrics["row_count"] == 4
