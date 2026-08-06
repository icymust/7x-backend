import pandas as pd

from app.engines.demand_analytics import build_demand_analytics


def test_builds_monthly_actual_and_ml_forecast_totals():
    historical = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-01", "2026-05-01"],
            "actual_shipments": [10, 15, 30],
        }
    )
    forecast = pd.DataFrame(
        {
            "date": ["2026-08-06", "2026-08-06", "2026-09-01"],
            "predicted_shipments": [20.5, 24.5, 40],
        }
    )

    result = build_demand_analytics(
        historical,
        forecast,
        model_version="catboost-daily-future-v1",
    )

    assert result["historical_total_orders"] == 55
    assert result["forecast_total_orders"] == 85
    assert result["historical_monthly"][0] == {
        "month": "2026-04",
        "source": "actual",
        "orders": 25.0,
        "average_orders_per_day": 25.0,
        "covered_days": 1,
        "date_from": "2026-04-01",
        "date_to": "2026-04-01",
    }
    assert result["forecast_monthly"][0]["source"] == "ml_forecast"
