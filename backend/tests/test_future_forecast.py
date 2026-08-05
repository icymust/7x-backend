from pathlib import Path

import pandas as pd

from app.ml.future_forecast import (
    FUTURE_FALLBACK_SOURCE,
    FUTURE_FALLBACK_VERSION,
    build_future_training_data,
    forecast_future_demand,
    generate_future_demand,
)


def create_history(*, stores: int = 1, days: int = 14) -> pd.DataFrame:
    rows = []

    for store_index in range(stores):
        for day_index, current_date in enumerate(
            pd.date_range("2026-01-01", periods=days)
        ):
            baseline = 100 + store_index * 10 + current_date.weekday()
            rows.append(
                {
                    "store_id": f"STORE-{store_index + 1}",
                    "emirate": "Dubai",
                    "zone": "Central",
                    "date": current_date,
                    "weekday": current_date.weekday(),
                    "month": current_date.month,
                    "day_of_year": current_date.dayofyear,
                    "is_weekend": current_date.day_name()
                    in {"Friday", "Saturday"},
                    "forecast_shipments": float(baseline),
                    "actual_shipments": float(baseline + day_index % 3),
                }
            )

    return pd.DataFrame(rows)


def test_builds_leakage_safe_future_training_features():
    training = build_future_training_data(create_history())

    assert len(training) == 13
    assert training.iloc[0]["demand_lag_1d"] == 103
    assert training.iloc[0]["seasonal_baseline_orders"] == 104


def test_generates_new_future_dates_from_weekly_baseline():
    history = create_history()
    predictions = generate_future_demand(
        history,
        horizon_start=pd.Timestamp("2026-01-15").date(),
        horizon_days=3,
        model=None,
    )

    assert predictions["date"].dt.date.astype(str).tolist() == [
        "2026-01-15",
        "2026-01-16",
        "2026-01-17",
    ]
    assert predictions["forecast_shipments"].tolist() == [103.0, 104.0, 105.0]
    assert predictions["predicted_shipments"].tolist() == [103.0, 104.0, 105.0]
    assert "actual_shipments" not in predictions


def test_uses_seasonal_fallback_when_future_model_is_missing():
    result = forecast_future_demand(
        create_history(stores=2),
        horizon_start=pd.Timestamp("2026-01-15").date(),
        horizon_days=5,
        model_path=Path("missing-future-model.cbm"),
    )

    assert len(result.dataframe) == 10
    assert result.prediction_source == FUTURE_FALLBACK_SOURCE
    assert result.model_version == FUTURE_FALLBACK_VERSION
    assert result.fallback_reason == (
        "future_catboost_unavailable_or_incompatible"
    )
    assert result.horizon_start == "2026-01-15"
    assert result.horizon_end == "2026-01-19"
