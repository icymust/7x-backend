import pandas as pd

from app.importers.validators import validate_dataframe


def create_valid_dataframe():
    return pd.DataFrame(
        [
            {
                "store_id": "DXB-001",
                "time_bucket": "2026-08-01 09:00",
                "forecast_shipments": 120,
                "available_permanent": 8,
                "available_outsourced": 4,
                "productivity_per_courier": 10,
            },
            {
                "store_id": "DXB-002",
                "time_bucket": "2026-08-01 10:00",
                "forecast_shipments": 80,
                "available_permanent": 6,
                "available_outsourced": 3,
                "productivity_per_courier": 9,
            },
        ]
    )


def test_valid_dataframe_has_no_issues():
    dataframe = create_valid_dataframe()

    assert validate_dataframe(dataframe) == []


def test_detects_invalid_values():
    dataframe = create_valid_dataframe()

    dataframe.loc[0, "store_id"] = ""
    dataframe.loc[0, "forecast_shipments"] = -10
    dataframe.loc[1, "time_bucket"] = "wrong-date"
    dataframe.loc[1, "productivity_per_courier"] = 0

    issues = validate_dataframe(dataframe)
    codes = {issue["code"] for issue in issues}

    assert codes == {
        "missing_store_id",
        "negative_value",
        "invalid_date",
        "invalid_productivity",
    }


def test_detects_duplicate_store_time():
    dataframe = create_valid_dataframe()
    dataframe.loc[1, "store_id"] = dataframe.loc[0, "store_id"]
    dataframe.loc[1, "time_bucket"] = dataframe.loc[0, "time_bucket"]

    issues = validate_dataframe(dataframe)

    assert {
        "code": "duplicate_store_time",
        "rows": [2, 3],
    } in issues
