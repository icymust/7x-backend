import pandas as pd

NON_NEGATIVE_COLUMNS = [
    "forecast_shipments",
    "available_permanent",
    "available_outsourced",
]


def _excel_rows(mask: pd.Series) -> list[int]:
    return [
        position + 2 for position, is_invalid in enumerate(mask.tolist()) if is_invalid
    ]


def validate_dataframe(dataframe: pd.DataFrame) -> list[dict]:
    issues = []

    empty_store = dataframe["store_id"].fillna("").astype(str).str.strip().eq("")

    if empty_store.any():
        issues.append(
            {
                "code": "missing_store_id",
                "column": "store_id",
                "rows": _excel_rows(empty_store),
            }
        )

    invalid_dates = pd.to_datetime(
        dataframe["time_bucket"],
        errors="coerce",
    ).isna()

    if invalid_dates.any():
        issues.append(
            {
                "code": "invalid_date",
                "column": "time_bucket",
                "rows": _excel_rows(invalid_dates),
            }
        )

    for column in NON_NEGATIVE_COLUMNS:
        values = pd.to_numeric(dataframe[column], errors="coerce")

        invalid_numbers = values.isna()
        if invalid_numbers.any():
            issues.append(
                {
                    "code": "invalid_number",
                    "column": column,
                    "rows": _excel_rows(invalid_numbers),
                }
            )

        negative_values = values < 0
        if negative_values.any():
            issues.append(
                {
                    "code": "negative_value",
                    "column": column,
                    "rows": _excel_rows(negative_values),
                }
            )

    productivity = pd.to_numeric(dataframe["productivity_per_courier"], errors="coerce")

    invalid_productivity = productivity.isna() | (productivity <= 0)

    if invalid_productivity.any():
        issues.append(
            {
                "code": "invalid_productivity",
                "column": "productivity_per_courier",
                "rows": _excel_rows(invalid_productivity),
            }
        )

    duplicates = dataframe.duplicated(
        subset=["store_id", "time_bucket"],
        keep=False,
    )

    if duplicates.any():
        issues.append(
            {
                "code": "duplicate_store_time",
                "rows": _excel_rows(duplicates),
            }
        )

    return issues
