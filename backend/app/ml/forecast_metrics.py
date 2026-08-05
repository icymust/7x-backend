import pandas as pd


def calculate_forecast_metrics(
    dataframe: pd.DataFrame,
    *,
    actual_column: str = "actual_shipments",
    prediction_column: str = "forecast_shipments",
) -> dict[str, int | float | None]:
    actual = pd.to_numeric(dataframe[actual_column], errors="coerce")
    prediction = pd.to_numeric(dataframe[prediction_column], errors="coerce")
    valid = actual.notna() & prediction.notna()

    if not valid.any():
        raise ValueError("No valid actual and prediction pairs")

    actual = actual[valid]
    prediction = prediction[valid]
    error = actual - prediction
    absolute_error = error.abs()
    actual_total = float(actual.abs().sum())

    return {
        "row_count": int(valid.sum()),
        "mae": round(float(absolute_error.mean()), 4),
        "bias": round(float(error.mean()), 4),
        "wape_percent": (
            round(float(absolute_error.sum()) / actual_total * 100, 4)
            if actual_total
            else None
        ),
    }
