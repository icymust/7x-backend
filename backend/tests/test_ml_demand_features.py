import pandas as pd

from app.importers.workforce_loader import WorkforceWorkbook
from app.ml.demand_features import (
    MODEL_FEATURE_COLUMNS,
    MODEL_TARGET_COLUMN,
    DemandTrainingDataError,
    build_demand_training_data,
    split_training_data_by_time,
)


def create_workbook() -> WorkforceWorkbook:
    demand_rows = []

    for day, forecast, actual in [
        ("2026-04-28", 3, 2),
        ("2026-04-29", 3, 4),
        ("2026-04-30", 5, 6),
    ]:
        demand_rows.append(
            {
                "store_id": "QED_DXB_01",
                "date": day,
                "time_slot": "08:00",
                "forecast_shipments": forecast,
                "actual_shipments": actual,
                "forecast_error": actual - forecast,
            }
        )

    demand_rows.append(
        {
            "store_id": "QED_DXB_01",
            "date": "2026-04-28",
            "time_slot": "08:30",
            "forecast_shipments": 2,
            "actual_shipments": 3,
            "forecast_error": 1,
        }
    )

    return WorkforceWorkbook(
        store_metadata=pd.DataFrame(
            [
                {
                    "store_id": "QED_DXB_01",
                    "emirate": "Dubai",
                    "zone": "Al Quoz",
                    "latitude": 25.1348,
                    "longitude": 55.2308,
                    "base_productivity_per_hour": 2.0,
                }
            ]
        ),
        demand_forecast=pd.DataFrame(demand_rows),
        courier_roster=pd.DataFrame(
            [
                {
                    "courier_id": "C3001",
                    "store_id": "QED_DXB_01",
                    "employment_type": "FTE",
                    "shift_start": "08:00",
                    "shift_end": "17:00",
                    "working_hours": 8,
                    "weekly_off_day": "Saturday",
                    "courier_productivity_per_hour": 2,
                    "status": "Active",
                }
            ]
        ),
        source_sheets={
            "Store_Metadata": "store_metadata",
            "Demand_Forecast": "demand_forecast",
            "Courier_Roster": "courier_roster",
        },
    )


def test_builds_leakage_safe_demand_features():
    dataframe = build_demand_training_data(create_workbook())

    assert MODEL_TARGET_COLUMN == "actual_shipments"
    assert MODEL_TARGET_COLUMN not in MODEL_FEATURE_COLUMNS
    assert len(dataframe) == 3
    assert dataframe.iloc[0]["forecast_shipments"] == 5
    assert dataframe.iloc[0]["actual_shipments"] == 5
    assert dataframe.iloc[0]["planning_grain"] == "store_day"
    assert pd.isna(dataframe.iloc[0]["actual_lag_1d"])
    assert dataframe.iloc[1]["actual_lag_1d"] == 5
    assert dataframe.iloc[2]["actual_rolling_mean_7d"] == 4.5


def test_splits_training_data_by_future_dates():
    dataframe = build_demand_training_data(create_workbook())
    split = split_training_data_by_time(dataframe, test_fraction=0.2)

    assert split.train_date_to == "2026-04-29"
    assert split.test_date_from == "2026-04-30"
    assert len(split.train) == 2
    assert len(split.test) == 1


def test_requires_historical_actual_target():
    workbook = create_workbook()
    workbook.demand_forecast = workbook.demand_forecast.drop(
        columns=["actual_shipments", "forecast_error"]
    )

    try:
        build_demand_training_data(workbook)
    except DemandTrainingDataError as error:
        assert error.issues == [
            {
                "code": "missing_training_target",
                "sheet": "demand_forecast",
                "column": "actual_shipments",
            }
        ]
    else:
        raise AssertionError("Expected missing training target error")
