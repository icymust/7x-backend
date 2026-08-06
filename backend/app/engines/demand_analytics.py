import pandas as pd


def _monthly_orders(
    dataframe: pd.DataFrame,
    *,
    value_column: str,
    source: str,
) -> list[dict]:
    if dataframe.empty:
        return []

    monthly = dataframe[["date", value_column]].copy()
    monthly["date"] = pd.to_datetime(monthly["date"]).dt.normalize()
    monthly[value_column] = pd.to_numeric(monthly[value_column]).astype(float)
    monthly["month"] = monthly["date"].dt.strftime("%Y-%m")

    grouped = monthly.groupby("month", as_index=False).agg(
        orders=(value_column, "sum"),
        covered_days=("date", "nunique"),
        date_from=("date", "min"),
        date_to=("date", "max"),
    )

    return [
        {
            "month": row.month,
            "source": source,
            "orders": round(float(row.orders), 2),
            "average_orders_per_day": round(
                float(row.orders) / int(row.covered_days),
                2,
            ),
            "covered_days": int(row.covered_days),
            "date_from": pd.Timestamp(row.date_from).date().isoformat(),
            "date_to": pd.Timestamp(row.date_to).date().isoformat(),
        }
        for row in grouped.itertuples(index=False)
    ]


def build_demand_analytics(
    historical: pd.DataFrame,
    forecast: pd.DataFrame,
    *,
    model_version: str,
) -> dict:
    historical_monthly = _monthly_orders(
        historical,
        value_column="actual_shipments",
        source="actual",
    )
    forecast_monthly = _monthly_orders(
        forecast,
        value_column="predicted_shipments",
        source="ml_forecast",
    )

    return {
        "model_version": model_version,
        "historical_total_orders": round(
            sum(row["orders"] for row in historical_monthly),
            2,
        ),
        "forecast_total_orders": round(
            sum(row["orders"] for row in forecast_monthly),
            2,
        ),
        "historical_monthly": historical_monthly,
        "forecast_monthly": forecast_monthly,
    }
