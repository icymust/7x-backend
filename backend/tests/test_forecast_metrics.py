import pandas as pd

from app.ml.forecast_metrics import calculate_forecast_metrics


def test_calculates_forecast_quality_metrics():
    dataframe = pd.DataFrame(
        {
            "actual_shipments": [4, 2],
            "forecast_shipments": [3, 3],
        }
    )

    assert calculate_forecast_metrics(dataframe) == {
        "row_count": 2,
        "mae": 1.0,
        "bias": 0.0,
        "wape_percent": 33.3333,
    }


def test_returns_no_wape_when_actual_total_is_zero():
    dataframe = pd.DataFrame(
        {
            "actual_shipments": [0, 0],
            "forecast_shipments": [0, 1],
        }
    )

    result = calculate_forecast_metrics(dataframe)

    assert result["mae"] == 0.5
    assert result["bias"] == -0.5
    assert result["wape_percent"] is None
